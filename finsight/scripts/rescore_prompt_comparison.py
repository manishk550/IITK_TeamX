"""Re-score the Qwen3-8B prompt comparison with the specification's tolerances.

The strict scorer (run_baseline.classify) needs every must_contain token verbatim,
including the calculator expression, so "6.85%" fails against a gold "6.8%".
The tolerant scorer follows docs/project_specification.md section 5:
percentages within 0.1 percentage points, currency within 0.5%.
It also re-runs the agent with Qwen3-8B rephrasing and records each failure.

Usage: PYTHONPATH=src python3 scripts/rescore_prompt_comparison.py [--skip-phrase]
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from finsight.evaluation import classify_failure, load_eval_set  # noqa: E402
from run_prompt_comparison import CHECKPOINT, CONDITIONS, RESULTS, STRATEGIES  # noqa: E402

NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
REFUSAL = re.compile(r"\b(cannot|can't|unable|not available|refus|do not have|don't have)\b", re.I)


def gold_values(example: dict) -> list[tuple[float, bool]]:
    values = []
    for token in example.get("must_contain") or []:
        if "/" in token or "*" in token or "(" in token:
            continue  # a calculator expression, not a reported value
        for raw in NUM.findall(token):
            values.append((float(raw.replace(",", "")), "%" in token))
    return values


def tolerant_ok(example: dict, answer: str, refused: bool) -> bool:
    if example["expected_behavior"] == "refuse":
        return refused
    if refused:
        return False
    gold = gold_values(example)
    if not gold:
        tokens = example.get("must_contain") or []
        return all(t.lower() in answer.lower() for t in tokens)
    found = [float(n.replace(",", "")) for n in NUM.findall(answer)]
    for value, is_pct in gold:
        limit = 0.1 if is_pct else max(abs(value) * 0.005, 1.0)
        if not any(abs(f - value) <= limit + 1e-9 for f in found):
            return False
    return True


def main() -> None:
    examples = load_eval_set()
    by_id = {e["id"]: e for e in examples}
    done = [json.loads(l) for l in CHECKPOINT.read_text().splitlines() if l.strip()]
    report = json.loads(RESULTS.read_text())
    by_type = {}
    for c in CONDITIONS:
        for s in STRATEGIES:
            key = f"{c}/{s}"
            ok = Counter()
            n = Counter()
            for d in done:
                e = by_id[d["id"]]
                row = d["rows"][key]
                refused = row["failure"] == "refusal_error" if e["expected_behavior"] == "answer" else row["failure"] is None
                good = tolerant_ok(e, row["answer"], refused)
                ok[e["question_type"]] += good
                n[e["question_type"]] += 1
            report["results"][key]["tolerant_accuracy"] = round(sum(ok.values()) / sum(n.values()), 3)
            by_type[key] = {t: f"{ok[t]}/{n[t]}" for t in n}
    report["tolerant_by_type"] = by_type
    if "--skip-phrase" not in sys.argv:
        from finsight.agent import FinancialCopilot, SessionStore
        from finsight.providers import activate, reset
        from finsight.retrieval import HybridRetriever
        from finsight.tools import ToolRegistry
        copilot = FinancialCopilot(ToolRegistry(HybridRetriever()), SessionStore(None), model_name="Qwen/Qwen3-8B")
        strict = tolerant = 0
        failures = []
        for e in examples:
            token = activate("course")
            try:
                time.sleep(1.1)
                r = copilot.answer(e["question"], session_id="rescore-" + e["id"])
            finally:
                reset(token)
            f = classify_failure(e, r)
            strict += f is None
            t = tolerant_ok(e, f"{r.answer}\n{r.calculation or ''}", r.behavior == "refuse")
            tolerant += t
            if f:
                failures.append({"id": e["id"], "type": e["question_type"], "strict": f, "tolerant_ok": t, "answer": r.answer[:240], "must_contain": e["must_contain"]})
        report["agent_phrase"]["strict_accuracy"] = round(strict / len(examples), 3)
        report["agent_phrase"]["tolerant_accuracy"] = round(tolerant / len(examples), 3)
        report["agent_phrase"]["failures"] = failures
    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: (v["accuracy"], v["tolerant_accuracy"]) for k, v in report["results"].items()}, indent=1))
    print(json.dumps(by_type, indent=1))
    if "agent_phrase" in report and "failures" in report["agent_phrase"]:
        ap = report["agent_phrase"]
        print("agent+phrase strict", ap["strict_accuracy"], "tolerant", ap["tolerant_accuracy"])
        for f in ap["failures"]:
            print(f["id"], f["type"], f["strict"], f["tolerant_ok"], "|", f["answer"][:120], "|", f["must_contain"])


if __name__ == "__main__":
    main()
