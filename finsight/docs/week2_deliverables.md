# Week 2 Deliverables — Retrieval

## Implementation

- Corpus loader: `src/finsight/corpus.py`
- Fixed-size and section-aware chunking: `src/finsight/retrieval.py`
- BM25-style lexical score plus normalized token embedding
- Lexical-overlap reranking
- Metadata filters for company and fiscal period
- Page, section, and document citations

## Experiment design

| Configuration | Purpose |
|---|---|
| Fixed 40-word chunks with 10-word overlap | Tests recall when facts cross chunk boundaries |
| Section-aware chunks | Preserves financial statement context |
| Dense only | Diagnostic baseline |
| BM25 only | Diagnostic baseline |
| Hybrid plus reranking | Required production configuration |

The loaded corpus contains 1,284 passages, including 1,273 pages extracted from official Reliance, TCS, Infosys, and Wipro FY2024 PDFs. Recall on 40 lexical page probes, measured separately from answer quality:

| Chunking | Ranker | Recall@5 | Recall@10 |
|---|---|---|---|
| Section | BM25 | 0.950 | 1.000 |
| Section | Dense hash | 0.925 | 0.975 |
| Section | Hybrid | 0.950 | 1.000 |
| Fixed 40/10 | BM25 | 0.950 | 1.000 |
| Fixed 40/10 | Dense hash | 0.950 | 1.000 |
| Fixed 40/10 | Hybrid | 0.950 | 1.000 |

Source: `reports/retrieval_ablation.json`. These probes reuse words from the target page, so the comparison across rankers matters more than the absolute recall.

## Required measurements

- Recall@5 and recall@10
- Retrieval misses independent of answer correctness
- Latency contribution of retrieval
- Citation coverage

## Gate

Every factual answer must contain at least one document ID, section, and page. Retrieval quality must be reported separately from generation quality.
