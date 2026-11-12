"""Score three single-prompt strategies on the frozen evaluation set.

This is the Week 1 comparison: the hosted model sees the question only.
It does not receive retrieved filings or the calculator. Run it before
treating the agent result as an improvement.
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

from finsight.evaluation import load_eval_set
from finsight.llm import chat, load_config
from finsight.prompts import decomposition_plan, decomposition_resolve, self_consistency, structured_few_shot


def parse_json(content: str) -> tuple[dict | None, bool]:
    try:
        return json.loads(content), True
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            return None, False
        try:
            return json.loads(match.group(0)), True
        except json.JSONDecodeError:
            return None, False


def classify(expected: dict, parsed: dict | None, schema_ok: bool) -> str | None:
    if not schema_ok or parsed is None:
        return "schema_error"
    answer = str(parsed.get("answer") or "")
    refusal = parsed.get("refusal_reason")
    refused = bool(refusal) or bool(re.search(r"\b(cannot|can't|refus)", answer, re.I))
    if expected["expected_behavior"] == "refuse":
        return None if refused else "refusal_error"
    if refused:
        return "refusal_error"
    required = expected.get("must_contain") or []
    haystack = f"{answer}\n{parsed.get('calculation') or ''}"
    missing = [token for token in required if token not in haystack]
    if not missing:
        return None
    answer_numbers = set(re.findall(r"\d[\d,]*(?:\.\d+)?", answer))
    expected_numbers = set(re.findall(r"\d[\d,]*(?:\.\d+)?", " ".join(required)))
    if answer_numbers and expected_numbers and answer_numbers.isdisjoint(expected_numbers):
        return "hallucination"
    return "reasoning_error"


def call(messages: list[dict], temperature: float) -> tuple[dict | None, dict, float, bool]:
    started = time.perf_counter()
    wait = 30
    last_error = ""
    for _attempt in range(6):
        try:
            raw = chat(messages, temperature=temperature)
            break
        except RuntimeError as exc:
            last_error = str(exc)
            if "429" not in last_error:
                raise
            if "free-models-per-day" in last_error:
                raise QuotaExceeded(last_error) from exc
            print(f"rate limited, waiting {wait}s", flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 180)
    else:
        raise QuotaExceeded(last_error)
    elapsed = (time.perf_counter() - started) * 1000
    parsed, ok = parse_json(raw["content"])
    return parsed, raw.get("usage") or {}, elapsed, ok


class QuotaExceeded(RuntimeError):
    """The free-tier quota or the upstream pool is still refusing requests."""


def majority(samples: list[dict | None]) -> dict | None:
    usable = [item for item in samples if item]
    if not usable:
        return None
    counts = Counter(json.dumps(item, sort_keys=True) for item in usable)
    chosen, votes = counts.most_common(1)[0]
    if votes < 2:
        return usable[0]
    return json.loads(chosen)


def token_counts(usage: dict) -> dict:
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }


def run_strategy(name: str, question: str) -> tuple[dict | None, bool, float, dict, bool]:
    usage = Counter()
    if name == "structured_few_shot":
        parsed, tokens, elapsed, ok = call(structured_few_shot(question), 0.0)
        return parsed, ok, elapsed, token_counts(tokens), True
    if name == "self_consistency":
        samples = []
        elapsed = 0.0
        ok = True
        for sample in (1, 2, 3):
            parsed, tokens, sample_elapsed, sample_ok = call(self_consistency(question, sample), 0.7)
            samples.append(parsed)
            elapsed += sample_elapsed
            usage.update(token_counts(tokens))
            ok = ok and sample_ok
        agreed = len({json.dumps(item, sort_keys=True) for item in samples if item}) <= 1 and any(samples)
        return majority(samples), ok, elapsed, dict(usage), agreed
    plan, plan_tokens, plan_elapsed, plan_ok = call(decomposition_plan(question), 0.0)
    parsed, tokens, elapsed, ok = call(decomposition_resolve(question, json.dumps(plan or {})), 0.0)
    usage.update(token_counts(plan_tokens))
    usage.update(token_counts(tokens))
    return parsed, plan_ok and ok, plan_elapsed + elapsed, dict(usage), True


def summarize(name: str, rows: list[dict]) -> dict:
    latencies = sorted(row["latency_ms"] for row in rows)
    failures = [row for row in rows if row["failure"]]
    p95_index = min(len(latencies) - 1, int(0.95 * (len(latencies) - 1))) if latencies else 0
    return {
        "strategy": name,
        "examples": len(rows),
        "correct": len(rows) - len(failures),
        "accuracy": round((len(rows) - len(failures)) / len(rows), 3) if rows else 0,
        "schema_valid_rate": round(sum(row["schema_ok"] for row in rows) / len(rows), 3) if rows else 0,
        "citation_rate": round(sum(row["cited"] for row in rows) / len(rows), 3) if rows else 0,
        "agreement_rate": round(sum(row["agreed"] for row in rows) / len(rows), 3) if rows else 0,
        "median_latency_ms": round(latencies[len(latencies) // 2], 1) if latencies else 0,
        "p95_latency_ms": round(latencies[p95_index], 1) if latencies else 0,
        "prompt_tokens": sum(row["usage"].get("prompt_tokens", 0) for row in rows),
        "completion_tokens": sum(row["usage"].get("completion_tokens", 0) for row in rows),
        "failure_taxonomy": dict(Counter(row["failure"] for row in failures)),
        "annotated_failures": [
            {"id": row["id"], "failure": row["failure"], "question": row["question"], "answer": row["answer"][:300]}
            for row in failures[:5]
        ],
    }


def write_report(destination: Path, config, examples: list[dict], strategies: tuple[str, ...], rows: dict, stopped_reason: str) -> None:
    lengths = [len(items) for items in rows.values()]
    completed = min(lengths) if lengths else 0
    report = {
        "model": config.model,
        "provider": "IIT KGP Track B VM04" if "103.42.50.41" in config.base_url else config.base_url,
        "examples_completed": completed,
        "examples_in_frozen_set": len(examples),
        "stopped_reason": stopped_reason,
        "evidence_in_prompt": False,
        "model_cost_per_query_usd": 0.0,
        "temperature": {"structured_few_shot": 0.0, "self_consistency": 0.7, "decomposition": 0.0},
        "strategies": [summarize(name, rows[name][:completed]) for name in strategies],
    }
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")


RECORDED_MODEL = "liquid/lfm-2.5-2.6b:free"


def result_paths(model: str) -> tuple[Path, Path]:
    """Keep each model's checkpoint separate from the recorded free-model run."""
    if model == RECORDED_MODEL:
        return ROOT / "reports" / "baseline_checkpoint.jsonl", ROOT / "reports" / "baseline_results.json"
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    return ROOT / "reports" / f"baseline_checkpoint_{slug}.jsonl", ROOT / "reports" / f"baseline_results_{slug}.json"


def main() -> None:
    config = load_config()
    if not config.enabled:
        status = {
            "model_configured": False,
            "scores": None,
            "note": "Set FINSIGHT_BASE_URL, FINSIGHT_API_KEY, FINSIGHT_MODEL, and FINSIGHT_CA_CERT in finsight/.env. Then rerun this script.",
        }
        (ROOT / "reports" / "baseline_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        print(status["note"])
        return
    try:
        chat([{"role": "user", "content": "Reply with the word ok."}], json_mode=False, max_tokens=8, timeout=45)
    except RuntimeError as exc:
        message = str(exc)
        if "401" in message:
            print("The course API rejected FINSIGHT_API_KEY. Put the group key in finsight/.env and rerun. No results file was changed.")
            return
        raise
    destination_parent = ROOT / "reports"
    destination_parent.mkdir(parents=True, exist_ok=True)
    checkpoint, destination = result_paths(config.model)
    examples = load_eval_set()
    strategies = ("structured_few_shot", "self_consistency", "decomposition")
    rows = {name: [] for name in strategies}
    done = set()
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            saved = json.loads(line)
            recorded = saved.get("model") or RECORDED_MODEL
            if recorded != config.model:
                continue
            done.add(saved["id"])
            for name in strategies:
                rows[name].append(saved["rows"][name])
        print(f"resuming {config.model} after {len(done)} completed questions", flush=True)
    stopped = ""
    try:
        for index, example in enumerate(examples, start=1):
            if example["id"] in done:
                continue
            for name in strategies:
                parsed, schema_ok, elapsed, usage, agreed = run_strategy(name, example["question"])
                answer = "" if not parsed else str(parsed.get("answer") or "")
                citations = [] if not parsed else parsed.get("citations") or []
                rows[name].append({
                    "id": example["id"],
                    "question": example["question"],
                    "failure": classify(example, parsed, schema_ok),
                    "schema_ok": schema_ok,
                    "cited": bool(citations),
                    "agreed": agreed,
                    "latency_ms": round(elapsed, 1),
                    "usage": usage,
                    "answer": answer,
                })
            with checkpoint.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"id": example["id"], "model": config.model, "rows": {name: rows[name][-1] for name in strategies}}) + "\n")
            print(f"{index}/{len(examples)}", flush=True)
            write_report(destination, config, examples, strategies, rows, "in progress")
    except QuotaExceeded as exc:
        stopped = str(exc)[:500]
        print("stopped on quota:", stopped[:180], flush=True)
    lengths = [len(items) for items in rows.values()]
    completed = min(lengths) if lengths else 0
    if completed >= len(examples):
        stopped = ""
    write_report(destination, config, examples, strategies, rows, stopped)
    print(json.dumps([{key: item[key] for key in ("strategy", "accuracy", "schema_valid_rate", "failure_taxonomy")} for item in json.loads(destination.read_text())["strategies"]], indent=2))
    print("wrote", destination)


if __name__ == "__main__":
    main()
