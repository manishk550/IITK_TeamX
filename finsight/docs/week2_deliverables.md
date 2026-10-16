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

The current sample contains 10 verified passages across five NIFTY 50 companies. For submission against the course gate, load 500–2,000 real NSE/BSE filings or annual-report sections through the same `Passage` format. Retrieval recall should then be calculated against gold evidence locations in the frozen evaluation set.

## Required measurements

- Recall@5 and recall@10
- Retrieval misses independent of answer correctness
- Latency contribution of retrieval
- Citation coverage

## Gate

Every factual answer must contain at least one document ID, section, and page. Retrieval quality must be reported separately from generation quality.
