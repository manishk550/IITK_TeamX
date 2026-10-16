"""Frozen-set evaluation and failure taxonomy."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from finsight.agent import FinancialCopilot
from finsight.retrieval import HybridRetriever
from finsight.tools import ToolRegistry


ROOT = Path(__file__).resolve().parents[2]


def load_eval_set(path: Path | None = None) -> list[dict]:
    source = path or ROOT / "data" / "eval" / "eval_v1.jsonl"
    return [json.loads(line) for line in source.read_text().splitlines() if line.strip()]


def classify_failure(expected: dict, response) -> str | None:
    if expected["expected_behavior"] == "refuse":
        return None if response.behavior == "refuse" else "policy_error"
    if response.behavior == "refuse":
        return "reasoning_error"
    if not response.citations:
        return "citation_error"
    if response.tool_calls and all(call.status == "error" for call in response.tool_calls):
        return "tool_call_error"
    return None


def evaluate(copilot: FinancialCopilot, examples: list[dict]) -> dict:
    failures = []
    latencies = []
    tool_calls = []
    for example in examples:
        response = copilot.answer(example["question"])
        latencies.append(response.latency_ms)
        tool_calls.append(len(response.tool_calls))
        failure = classify_failure(example, response)
        if failure:
            failures.append({"id": example["id"], "failure": failure, "question": example["question"]})
    total = len(examples)
    correct = total - len(failures)
    return {
        "examples": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0,
        "task_completion_rate": round(correct / total, 3) if total else 0,
        "average_tool_calls": round(sum(tool_calls) / total, 2) if total else 0,
        "median_latency_ms": round(sorted(latencies)[len(latencies) // 2], 3) if latencies else 0,
        "failure_taxonomy": dict(Counter(item["failure"] for item in failures)),
        "failures": failures,
    }
