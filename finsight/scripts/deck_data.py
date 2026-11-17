"""Collect every number the v2 deck shows into one JSON file.

Run: PYTHONPATH=src python3 scripts/deck_data.py > reports/deck_data.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from finsight.evaluation import load_eval_set  # noqa: E402
from run_prompt_comparison import CHECKPOINT  # noqa: E402

R = ROOT / "reports"
examples = load_eval_set()
final = json.loads((R / "prompt_comparison_qwen3_8b.json").read_text())
done = [json.loads(l) for l in CHECKPOINT.read_text().splitlines() if l.strip()]
comparison = final["results"]
phrase = final.get("agent_phrase")
by_type = final.get("tolerant_by_type", {})
safety = json.loads((R / "safety_log.json").read_text())
print(json.dumps({
    "questions_scored": len(done),
    "comparison": comparison,
    "by_type": by_type,
    "agent_phrase": phrase,
    "agent": json.loads((R / "agent_eval.json").read_text()),
    "retrieval": json.loads((R / "retrieval_ablation.json").read_text()),
    "safety": {"total": len(safety), "inside": sum(1 for x in safety if x["refused"] and not x["leaked_injection"]),
               "categories": dict(Counter(x["category"] for x in safety))},
    "eval_types": dict(Counter(e["question_type"] for e in examples)),
    "eval_behaviour": dict(Counter(e["expected_behavior"] for e in examples)),
}, indent=1, ensure_ascii=False))
