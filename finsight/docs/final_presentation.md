# FinSight Final Presentation (10 minutes)

## Slide 1 — Title

**FinSight: Multi-Agent Financial Report Copilot**  
Track B — hosted model of at most 8B parameters  
Team name, members, and date

## Slide 2 — User problem

Analysts need auditable answers from long filings. Small models lose context, confuse figures, and make weak tool calls.

## Slide 3 — What FinSight does

- Answers with citations and units
- Calculates ratios in code
- Compares companies and periods
- Refuses advice, predictions, and missing evidence

## Slide 4 — Week 1 gate

Show the specification, 20-question seed set, annotation guide, and three baseline strategies. Explain why the test set is frozen first.

## Slide 5 — Architecture

User → Planner → Executor tools → Critic → Cited answer

Tools: `report_search`, `filing_metadata`, `financial_calculator`

## Slide 6 — Retrieval experiments

Compare fixed chunks, section chunks, BM25, dense retrieval, hybrid fusion, and reranking. Report recall separately from answer accuracy.

## Slide 7 — Controlling a small model

Show JSON validation, retry, 10-step limit, token budget, and deterministic arithmetic.

## Slide 8 — Evaluation

Show accuracy, completion, tool calls, latency, cost, and the five-class failure taxonomy.

## Slide 9 — Live demo

1. Reliance Industries FY2024 revenue
2. Reliance year-over-year growth calculation
3. Infosys versus HCLTech operating margin
4. FY2030 unavailable-data refusal
5. Buy-recommendation refusal

## Slide 10 — Responsible AI

Explain human review, PII refusal, prompt injection, and provenance from official Indian company sources.

## Slide 11 — Results and lessons

Highlight the measured gain from baseline to RAG to agent. State what failed and what control fixed it.

## Slide 12 — Close

Show repository, trace dashboard, container, and the next step: expand to 500–2,000 NSE/BSE filings or annual-report sections and 60–100 adjudicated questions.
