# FinSight: A Multi-Agent Financial Report Copilot

## 1. Problem

Financial analysts need answers that identify the filing, period, currency, scale, and calculation behind every figure. A hosted instruction model of at most 8B parameters can discuss financial concepts, but it can omit evidence, confuse nearby numbers, or produce invalid tool calls. FinSight improves reliability without changing model weights.

## 2. Scope

The copilot answers fact lookups, calculations, ratios, comparisons, trends, and qualitative questions over a public-filing corpus. It refuses investment advice, predictions presented as facts, unavailable periods, personal-data requests, and attempts to bypass evidence requirements.

## 3. Data

The development corpus contains 10 verified excerpts for five NIFTY 50 constituents: Reliance Industries, Tata Consultancy Services, Infosys, HCLTech, and Wipro. Each passage has company, NSE ticker, document type, fiscal period, page, section, and an official investor-relations source URL. Financial values are normalized to INR crore. The production expansion path uses company annual reports, NSE/BSE corporate announcements, and SEBI-regulated disclosures with the same passage schema.

## 4. System design

A planner classifies intent and identifies companies, periods, metrics, and formulas. An executor calls three validated tools: filing search, filing metadata, and a deterministic calculator. A critic checks evidence, calculations, citations, and policy. Session history persists across turns. Runs have a 10-step limit, token accounting, schema validation, and one repair retry.

## 5. Retrieval

The retriever supports fixed-size and section-aware chunks. It combines BM25-style lexical ranking with normalized hashed embeddings and reranks the candidate pool by query overlap. Company and period metadata constrain retrieval. This permits recall to be measured separately from answer quality.

## 6. Small-model compensation

The design does not depend on a frontier model. It compensates by:

- constraining output with explicit response fields
- moving arithmetic to verified code
- requiring citations
- validating JSON before tool execution
- retrying malformed calls once
- separating policy checks from free-form generation
- capping loops and token budgets

## 7. Evaluation

The harness in `src/finsight/evaluation.py` scores the frozen JSONL set and classifies failures as retrieval, reasoning, tool-call, citation, or policy errors. It reports accuracy, completion, average tool calls, and median latency. The automated test suite covers calculations, citations, refusals, injection, retrieval, persistence, rate limiting, and the API contract.

## 8. Deployment and safety

FastAPI serves `/health`, `/api/ask`, and `/api/traces`. Streamlit provides the demo interface. Docker Compose packages the API. Caching and rate limiting protect the shared endpoint. The responsible-AI review defines permitted use, refusals, human approval, and data limitations.

## 9. Results and limitations

The local development run completes all 20 NIFTY 50 seed questions, with 100% task completion, an average of 3.05 tool calls, and median latency below 1 ms on the compact corpus. Verified outputs include Reliance Industries FY2024 revenue growth of 2.6%, Infosys FY2024 operating margin of 20.7%, HCLTech FY2024 operating margin of 18.2%, and the Infosys-versus-Wipro margin comparison. Investment advice and unavailable future periods are refused.

These results validate the control flow, not the final academic benchmark. The corpus must be expanded to 500–2,000 NSE/BSE filings or annual-report sections and the evaluation expanded to 60–100 adjudicated questions before final scoring. Hosted-model cost and latency must be measured separately against the course endpoint.

## 10. Team contributions

Domain and evaluation own the gold set and refusal policy. Prompt engineering owns the three-strategy baseline. Retrieval owns chunking and recall experiments. Agent engineering owns tools and control flow. Observability and safety own traces and adversarial tests. Frontend and deployment own the demo, container, cache, and rate limiting.
