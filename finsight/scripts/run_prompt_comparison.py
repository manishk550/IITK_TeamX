"""Prompt-strategy comparison on Qwen/Qwen3-8B for the Track B report.

Two conditions over the frozen 82-question set:

* closed_book  - the question only (the Week 1 single-prompt baseline)
* with_evidence - the question plus the top-5 passages from the production
  HybridRetriever (single agent, single prompt, RAG-in-prompt)

Four strategies per condition: zero_shot, structured_few_shot,
self_consistency (3 samples, majority vote), decomposition (plan -> resolve).
A third block, agent_phrase, sends every deterministic agent answer through
the course model's rephrase step and records how often the guard accepts it.

Results are checkpointed per question so the run can resume after a 429.
Usage: PYTHONPATH=src python3 scripts/run_prompt_comparison.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from finsight.evaluation import load_eval_set  # noqa: E402
from finsight.llm import chat, load_config  # noqa: E402
from finsight.prompts import SYSTEM, decomposition_plan, json_dumps, structured_few_shot  # noqa: E402
from finsight.retrieval import HybridRetriever  # noqa: E402
from run_baseline import classify, majority, parse_json  # noqa: E402

CHECKPOINT = ROOT / "reports" / "prompt_comparison_checkpoint.jsonl"
RESULTS = ROOT / "reports" / "prompt_comparison_qwen3_8b.json"
STRATEGIES = ("zero_shot", "structured_few_shot", "self_consistency", "decomposition")
CONDITIONS = ("closed_book", "with_evidence")
MAX_TOKENS = 400
MIN_INTERVAL = 60 / 55  # stay under the 60 requests/minute group limit
_last_call = [0.0]


def _paced_chat(messages: list[dict], temperature: float) -> dict:
    wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()
    return chat(messages, temperature=temperature, max_tokens=MAX_TOKENS, timeout=120)


def _call(messages: list[dict], temperature: float) -> tuple[dict | None, bool, float, dict]:
    started = time.perf_counter()
    try:
        raw = _paced_chat(messages, temperature)
    except RuntimeError as exc:
        if "401" in str(exc):
            raise
        return None, False, (time.perf_counter() - started) * 1000, {"error": str(exc)[:200]}
    parsed, ok = parse_json(raw["content"])
    usage = raw.get("usage") or {}
    return parsed, ok, (time.perf_counter() - started) * 1000, {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }


def _evidence_block(retriever: HybridRetriever, question: str) -> tuple[str, list[str]]:
    hits = retriever.search(question, k=5)
    lines = [f"[{h.document_id} p.{h.page} {h.section}] {h.excerpt[:700]}" for h in hits]
    return "\n".join(lines), [h.document_id for h in hits]


def _user(question: str, evidence: str | None) -> str:
    if evidence is None:
        return question
    return f"{question}\nEvidence:\n{evidence}\nCite document ids from the evidence tags."


def run(strategy: str, question: str, evidence: str | None) -> dict:
    tokens = Counter()
    elapsed = 0.0
    if strategy == "zero_shot":
        parsed, ok, ms, usage = _call([{"role": "system", "content": SYSTEM}, {"role": "user", "content": _user(question, evidence)}], 0.0)
        tokens.update({k: v for k, v in usage.items() if isinstance(v, int)})
        return {"parsed": parsed, "ok": ok, "ms": ms, "tokens": dict(tokens), "agreed": True}
    if strategy == "structured_few_shot":
        parsed, ok, ms, usage = _call(structured_few_shot(_user(question, evidence)), 0.0)
        tokens.update({k: v for k, v in usage.items() if isinstance(v, int)})
        return {"parsed": parsed, "ok": ok, "ms": ms, "tokens": dict(tokens), "agreed": True}
    if strategy == "self_consistency":
        samples, ok_all = [], True
        source = "the evidence" if evidence else "the question text only"
        for n in (1, 2, 3):
            messages = [
                {"role": "system", "content": SYSTEM + f" This is independent sample {n} of 3. Solve from {source}."},
                {"role": "user", "content": _user(question, evidence)},
            ]
            parsed, ok, ms, usage = _call(messages, 0.7)
            samples.append(parsed)
            ok_all = ok_all and ok
            elapsed += ms
            tokens.update({k: v for k, v in usage.items() if isinstance(v, int)})
        answers = {str((s or {}).get("answer", "")).strip().lower() for s in samples if s}
        return {"parsed": majority(samples), "ok": ok_all, "ms": elapsed, "tokens": dict(tokens), "agreed": len(answers) == 1}
    plan, ok1, ms1, u1 = _call(decomposition_plan(_user(question, evidence)), 0.0)
    resolve = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Question: {_user(question, evidence)}\nPlan: {json_dumps(plan or {})}\nResolve the plan and return the final JSON answer."},
    ]
    parsed, ok2, ms2, u2 = _call(resolve, 0.0)
    for usage in (u1, u2):
        tokens.update({k: v for k, v in usage.items() if isinstance(v, int)})
    return {"parsed": parsed, "ok": ok1 and ok2, "ms": ms1 + ms2, "tokens": dict(tokens), "agreed": True}


def _cited_gold(parsed: dict | None, example: dict) -> bool:
    if not parsed:
        return False
    text = json.dumps(parsed.get("citations") or [])
    gold = {e.get("source") for e in example.get("evidence") or [] if e.get("source")}
    return any(g in text for g in gold)


def _summary(rows: list[dict], examples: dict) -> dict:
    n = len(rows)
    lat = sorted(r["ms"] for r in rows)
    fails = Counter(r["failure"] for r in rows if r["failure"])
    answer_rows = [r for r in rows if examples[r["id"]]["expected_behavior"] == "answer"]
    refuse_rows = [r for r in rows if examples[r["id"]]["expected_behavior"] == "refuse"]
    prompt_t = sum(r["tokens"].get("prompt_tokens", 0) for r in rows)
    comp_t = sum(r["tokens"].get("completion_tokens", 0) for r in rows)
    return {
        "examples": n,
        "accuracy": round(sum(not r["failure"] for r in rows) / n, 3) if n else 0,
        "answer_accuracy": round(sum(not r["failure"] for r in answer_rows) / len(answer_rows), 3) if answer_rows else 0,
        "refusal_accuracy": round(sum(not r["failure"] for r in refuse_rows) / len(refuse_rows), 3) if refuse_rows else 0,
        "schema_valid_rate": round(sum(r["ok"] for r in rows) / n, 3) if n else 0,
        "gold_citation_rate": round(sum(r["gold_cited"] for r in answer_rows) / len(answer_rows), 3) if answer_rows else 0,
        "hallucination_rate": round(fails.get("hallucination", 0) / n, 3) if n else 0,
        "agreement_rate": round(sum(r["agreed"] for r in rows) / n, 3) if n else 0,
        "median_latency_ms": round(lat[n // 2], 1) if n else 0,
        "p95_latency_ms": round(lat[min(n - 1, int(0.95 * (n - 1)))], 1) if n else 0,
        "avg_prompt_tokens": round(prompt_t / n, 1) if n else 0,
        "avg_completion_tokens": round(comp_t / n, 1) if n else 0,
        "failure_taxonomy": dict(fails),
    }


def _agent_phrase(examples: list[dict]) -> dict:
    """Send each deterministic agent answer through the course rephrase guard."""
    import os
    os.environ.setdefault("FINSIGHT_STATE_DB", str(ROOT / "reports" / ".phrase_sessions.sqlite"))
    from finsight.agent import FinancialCopilot, SessionStore
    from finsight.evaluation import classify_failure
    from finsight.providers import activate, reset
    from finsight.tools import ToolRegistry
    copilot = FinancialCopilot(ToolRegistry(HybridRetriever()), SessionStore(None), model_name="Qwen/Qwen3-8B")
    notes, correct, lat = Counter(), 0, []
    for example in examples:
        token = activate("course")
        try:
            wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.monotonic()
            response = copilot.answer(example["question"], session_id="phrase-" + example["id"])
        finally:
            reset(token)
        lat.append(response.latency_ms)
        correct += classify_failure(example, response) is None
        note = next((c for c in response.caveats if "course" in c.lower() or "fastapi" in c.lower()), "no rephrase (refusal path)")
        notes[note] += 1
    lat.sort()
    n = len(examples)
    return {
        "examples": n,
        "accuracy": round(correct / n, 3),
        "median_latency_ms": round(lat[n // 2], 1),
        "p95_latency_ms": round(lat[min(n - 1, int(0.95 * (n - 1)))], 1),
        "rephrase_outcomes": dict(notes),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-phrase", action="store_true")
    args = parser.parse_args()
    config = load_config()
    if not config.enabled:
        sys.exit("Set FINSIGHT_BASE_URL, FINSIGHT_API_KEY, FINSIGHT_MODEL in finsight/.env first.")
    examples = load_eval_set()
    if args.limit:
        examples = examples[: args.limit]
    by_id = {e["id"]: e for e in examples}
    retriever = HybridRetriever()
    done = {}
    if CHECKPOINT.exists():
        for line in CHECKPOINT.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["id"]] = row
    for i, example in enumerate(examples, 1):
        if example["id"] in done:
            continue
        evidence_text, retrieved = _evidence_block(retriever, example["question"])
        record = {"id": example["id"], "retrieved": retrieved, "rows": {}}
        for condition in CONDITIONS:
            evidence = evidence_text if condition == "with_evidence" else None
            for strategy in STRATEGIES:
                out = run(strategy, example["question"], evidence)
                parsed = out["parsed"]
                record["rows"][f"{condition}/{strategy}"] = {
                    "id": example["id"],
                    "failure": classify(example, parsed, out["ok"]),
                    "ok": out["ok"],
                    "agreed": out["agreed"],
                    "gold_cited": _cited_gold(parsed, example),
                    "ms": round(out["ms"], 1),
                    "tokens": out["tokens"],
                    "answer": str((parsed or {}).get("answer", ""))[:300],
                }
        with CHECKPOINT.open("a") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        done[example["id"]] = record
        print(f"{i}/{len(examples)} {example['id']}", flush=True)
    report = {"model": config.model, "endpoint": config.base_url, "max_tokens": MAX_TOKENS, "results": {}}
    for condition in CONDITIONS:
        for strategy in STRATEGIES:
            key = f"{condition}/{strategy}"
            rows = [done[e["id"]]["rows"][key] for e in examples if e["id"] in done]
            report["results"][key] = _summary(rows, by_id)
    if not args.skip_phrase:
        report["agent_phrase"] = _agent_phrase(examples)
    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report["results"], indent=1))
    print("wrote", RESULTS)


if __name__ == "__main__":
    main()
