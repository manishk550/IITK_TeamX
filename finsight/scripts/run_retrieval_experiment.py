"""Measure retrieval recall separately from answer quality."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finsight.retrieval import HybridRetriever


def recall_at(retriever: HybridRetriever, queries: list[dict], k: int, mode: str, use_priority: bool) -> float:
    hits = 0
    for item in queries:
        found = retriever.search(item["query"], k=k, company=item.get("company"), mode=mode, use_priority=use_priority)
        if any(row.document_id == item["document_id"] and row.page == item["page"] for row in found):
            hits += 1
    return round(hits / len(queries), 3) if queries else 0.0


def page_queries(limit: int = 40) -> list[dict]:
    pages = [json.loads(line) for line in (ROOT / "data" / "corpus" / "pages.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    random.seed(7)
    chosen = []
    for page in random.sample(pages, limit):
        words = [word for word in page["text"].split() if len(word) > 5][20:28]
        if len(words) < 6:
            continue
        chosen.append({
            "query": " ".join(words),
            "company": page["company"],
            "document_id": page["document_id"],
            "page": page["page"],
        })
    return chosen


def main() -> None:
    queries = page_queries()
    report = {"queries": len(queries), "runs": []}
    for strategy in ("section", "fixed"):
        retriever = HybridRetriever(strategy=strategy)
        for mode in ("bm25", "dense", "hybrid"):
            row = {
                "strategy": strategy,
                "mode": mode,
                "recall_at_5": recall_at(retriever, queries, 5, mode, False),
                "recall_at_10": recall_at(retriever, queries, 10, mode, False),
            }
            report["runs"].append(row)
            print(row)
    destination = ROOT / "reports" / "retrieval_ablation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", destination)


if __name__ == "__main__":
    main()
