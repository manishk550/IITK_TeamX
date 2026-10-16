"""Run the three Week 1 prompting strategies when a hosted model is configured."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finsight.llm import load_config
from finsight.prompts import decomposition, self_consistency, structured_few_shot


def main() -> None:
    question = "What was Reliance Industries revenue for fiscal 2024? Use only supplied evidence."
    prompts = {
        "structured_few_shot": structured_few_shot(question),
        "self_consistency": [self_consistency(question, sample) for sample in (1, 2, 3)],
        "decomposition": decomposition(question),
    }
    destination = ROOT / "reports" / "baseline_status.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    config = load_config()
    status = {
        "model_configured": config.enabled,
        "model": config.model or None,
        "strategies": list(prompts),
        "prompt_messages": {name: len(value) if name != "self_consistency" else len(value) for name, value in prompts.items()},
        "scores": None,
        "note": "Hosted baseline scores are recorded only after a live call. No scores are estimated.",
    }
    if not config.enabled:
        status["note"] = "Blocked: set FINSIGHT_BASE_URL, FINSIGHT_API_KEY, and FINSIGHT_MODEL, then rerun this script. Prompt strategies are implemented and checked, but scores are not invented."
        destination.write_text(json.dumps(status, indent=2), encoding="utf-8")
        print(status["note"])
        return
    from finsight.llm import chat
    scores = {}
    for name, messages in (("structured_few_shot", prompts["structured_few_shot"]), ("decomposition", prompts["decomposition"])):
        raw = chat(messages)
        scores[name] = {"raw": raw["content"][:500], "usage": raw["usage"]}
    samples = [chat(messages)["content"][:300] for messages in prompts["self_consistency"]]
    scores["self_consistency"] = {"samples": samples}
    status["scores"] = scores
    destination.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print("wrote", destination)


if __name__ == "__main__":
    main()
