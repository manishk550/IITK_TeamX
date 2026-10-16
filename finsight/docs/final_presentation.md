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

Show the specification, the frozen 82-question set and its checksum, and the three baseline strategies. Say clearly that hosted-model scores are not filled in until the course endpoint is configured.

## Slide 5 — Architecture

User → Planner → Executor tools → Critic → Cited answer

Tools: `report_search`, `filing_metadata`, `financial_calculator`

## Slide 6 — Retrieval experiments

Compare fixed chunks, section chunks, BM25, dense retrieval, and hybrid. On 40 lexical page probes, section dense recall@5 was 0.925 and the other five runs were 0.950. Recall@10 was 1.000 except section dense at 0.975.

## Slide 7 — Controlling a small model

Show JSON validation, retry, 10-step limit, token budget, and deterministic arithmetic.

## Slide 8 — Evaluation

Local policy on the frozen 82 questions: 82 correct, 2.88 tool calls on average, 17.05 ms median latency. This is not a hosted-8B score. Cost stays unreported until the endpoint is called. The taxonomy is retrieval miss, reasoning error, tool-call error, hallucination, and policy error.

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

Show the repository, the `/traces` dashboard, and the container. The corpus is already 1,284 passages and the eval set is 82 questions. The remaining step is to connect the course endpoint and rerun the three prompting strategies.
