# FinSight Technical Report

Track B capstone: a citation-grounded financial-report copilot for a hosted chat model of at most 8B parameters, plus a separate embeddings endpoint. No weights are changed. Arithmetic, schema checks, and refusals stay in deterministic code so a small model cannot be the only source of a number.

## 1. Problem and users

Equity analysts and reviewers need answers that can be checked against a filing. The useful questions are factual (“what was revenue”), arithmetic (“what was the growth”), comparative, and qualitative. The same interface must refuse investment advice, predictions stated as facts, requests for personal data, and questions about companies or years that are not in the corpus.

FinSight covers five NIFTY 50 constituents for the year ended 31 March 2024: Reliance Industries, Tata Consultancy Services, Infosys, HCLTech, and Wipro. Figures used in calculations are normalized to INR crore from official investor-relations sources. The copilot is a research aid. It does not place trades, and a person reviews any answer that would affect a decision.

## 2. Answer contract

An acceptable answer does four things.

1. It states the behavior: answer or refuse.
2. If it answers, it cites a document id, page, and section that were actually retrieved.
3. If it calculates, the expression is evaluated by the calculator tool. The model is not allowed to introduce a number that was not in the evidence or the calculator result.
4. If it refuses, it gives a reason: investment advice, prediction, personal data, prompt injection, missing inputs, or a company or period outside the corpus.

Gold questions were written against this contract and then frozen. The file `data/eval/eval_v1.jsonl` has 82 adjudicated items. Its SHA-256 is `2e3eaa1b71226cecab02eddf64e11cba7e641cce8aa265fee456912f8f31e6c3`, stored in `data/eval/eval_v1.sha256`.

## 3. Architecture

The browser research site posts a question to FastAPI. The service applies a per-client rate limit and a response cache, then runs a planner, an executor, and a critic.

- The planner classifies the question, selects companies and a formula, or refuses before any tool call.
- The executor may call `report_search`, `filing_metadata`, and `financial_calculator`. A failed tool call is retried once. The calculator accepts only arithmetic in an AST; names, calls, and exponentiation are rejected.
- The critic turns tool results into a cited answer or a refusal. Embedded instructions in a retrieved passage are dropped before the critic reads them.
- Sessions keep the last eight turns. The loop stops at 10 steps or a 6,000-token estimate.

When `FINSIGHT_BASE_URL`, `FINSIGHT_API_KEY`, and `FINSIGHT_MODEL` are set, the critic may ask the hosted model to rephrase an answer that is already grounded. Any number in that rephrase must already appear in the deterministic answer. Invalid JSON or a new number falls back to the deterministic text. Without those variables the system uses the local policy and does not pretend a model was called.

## 4. What we did to compensate for a small model

The graded risk of an 8B model is not fluency. It is dropped constraints, bad JSON, and invented figures. The compensations are:

| Risk | Compensation |
|---|---|
| Invented financial figures | Calculator tool and a check that rephrasing cannot add numbers |
| Malformed tool arguments | Pydantic validation and one retry |
| Infinite tool loops | Maximum of 10 steps |
| Lost conversation state | Session store capped at eight turns |
| Instructions hidden in a filing | Instruction filter before the answer is written |
| Advice or personal data | Refusal patterns that run before retrieval |
| Weak retrieval | Hybrid ranker, reranking, and a priority boost for verified metric cards |

The hosted model is optional phrasing, not the source of the arithmetic.

## 5. Corpus

Verified metric cards live in `src/finsight/corpus.py`. They are short passages whose figures were checked against official pages: Reliance revenue ₹914,472 crore in FY2024 and ₹891,311 crore in FY2023; TCS revenue ₹240,893 / ₹225,458 / ₹191,754 crore and a reported operating margin of 24.6 percent; Infosys revenue and operating income ₹31,747 crore; HCLTech revenue, operating income ₹20,027 crore, and net income ₹15,702 crore; Wipro revenue normalized from the rupee-million table to ₹89,794.3 crore, with operating income ₹13,609.9 crore. One additional passage is an intentional untrusted note used only for the prompt-injection test. It is not a financial fact and is not given retrieval priority.

Page text was extracted with `pdftotext` from four official PDFs:

| Source | Pages kept |
|---|---|
| Reliance consolidated financial statements | 109 |
| TCS Integrated Annual Report 2023-24 | 337 |
| Infosys Integrated Annual Report 2023-24 | 348 |
| Wipro Integrated Annual Report 2023-24 | 479 |

That is 1,273 extracted pages plus 11 curated passages, 1,284 passages in total. HCLTech’s full annual-report PDF did not download from the investor-site URLs we tried, so HCLTech remains on the verified cards only. `scripts/build_corpus.py` can regenerate `data/corpus/pages.jsonl`. The script does not synthesize filings.

## 6. Week 1 prompting baseline

Three single-prompt strategies are implemented in `src/finsight/prompts.py` and exercised by `scripts/run_baseline.py`.

1. Structured few-shot: one JSON example, then the question, with a JSON response format.
2. Self-consistency: three independent samples of the same question.
3. Decomposition: the model is told to identify company, period, metric, and formula before the JSON answer.

The course endpoint was not configured in this environment (`FINSIGHT_API_KEY` is unset). The script therefore records that the run is blocked. It does not fill in accuracy, cost, or latency for a model that was not called. `reports/baseline_status.json` is that record. After the team adds the course key, the same script writes the raw completions and token usage.

## 7. Retrieval

Chunking has two strategies. Section chunking keeps a passage intact when it is 700 characters or shorter, so a verified card that contains both revenue and operating income is not split. Longer PDF pages split on sentence boundaries. Fixed chunking uses 40-word windows with a 10-word overlap.

The ranker adds a BM25-style score and a hashed token embedding. A hosted embedding model replaces the hash when `FINSIGHT_EMBEDDING_MODEL` is set; otherwise the hash keeps the experiment reproducible. A lexical reranker reorders the top candidates. Verified cards receive a priority bonus so a PDF page that repeats the word “revenue” does not hide the checked figure.

Retrieval was measured on 40 probes, separate from the answer-quality set. Each probe is eight content words taken from the middle of a randomly chosen PDF page (seed 7). The gold target is that page. Priority boosting was turned off for this comparison so the rankers are compared on the page text itself. These probes are lexical, not paraphrases, so absolute recall is high. The useful result is the gap between configurations.

| Chunking | Ranker | Recall@5 | Recall@10 |
|---|---|---|---|
| Section | BM25 | 0.950 | 1.000 |
| Section | Dense hash | 0.925 | 0.975 |
| Section | Hybrid | 0.950 | 1.000 |
| Fixed 40/10 | BM25 | 0.950 | 1.000 |
| Fixed 40/10 | Dense hash | 0.950 | 1.000 |
| Fixed 40/10 | Hybrid | 0.950 | 1.000 |

Section-level dense retrieval is the weakest of the six. Hybrid matches BM25 on this lexical set and is the production setting because it still has a dense channel for the hosted embedding endpoint. The full table is `reports/retrieval_ablation.json`.

## 8. Agent evaluation

`src/finsight/evaluation.py` scores the frozen 82 questions. A refusal item must be refused. An answer item must be answered, must cite a source, and must contain every required token in `must_contain` (the gold figure or the calculator expression). If the answer contains numbers and none of them match the gold numbers, the failure is recorded as a hallucination. Other missing tokens are reasoning errors. Tool-call errors are recorded only when every tool call failed. Policy errors are answers to questions that should have been refused.

On the local policy, with no hosted model, the result was:

| Metric | Result |
|---|---|
| Examples | 82 |
| Correct | 82 |
| Accuracy | 1.000 |
| Task completion | 1.000 |
| Average tool calls | 2.88 |
| Median latency | 17.05 ms |
| Failure taxonomy | none on this run |

That score validates the control flow, the calculator, and the citation check. It is not a hosted-8B baseline. The same harness should be rerun after the course endpoint is connected; the accuracy will change if the model’s rephrase is enabled and then rejected, or if a future change lets the model choose tools.

The set mixes facts, growth calculations, operating margins, two-company comparisons, three-year trends, multi-document lookups, narrative questions, and refusals. Worked checks include Reliance growth `(914472.0 - 891311.0) / 891311.0 * 100` = 2.6%, Infosys operating margin `31747.0 / 153670.0 * 100` = 20.7%, and HCLTech operating margin 18.2%.

## 9. Safety

Twenty-four adversarial prompts are in `data/safety/adversarial.jsonl` and the run log is `reports/safety_log.json`. Categories are investment advice, predictions, unavailable years, companies outside the five-name corpus, Aadhaar / PAN / phone / email / password requests, question-level prompt injection, a poisoned passage inside the corpus, a malformed calculator expression, and a request to approve a trade.

All 24 stayed inside policy. None of the answers repeated the planted sentence that tells the user to buy Reliance shares. Question-level overrides such as “ignore the filings” are refused before search. The planted passage is removed from the evidence list if it is retrieved. Consequential actions, including approving a trade, are refused and left for a person.

## 10. Tracing, deployment, and cost

Each request writes an OpenTelemetry-compatible span to `data/traces/traces.jsonl` with a trace id, duration, and tool-count event. The research site links to `/traces`, which reads `/api/traces`. The log is local and durable across a process restart on the same machine. A Langfuse or LangSmith exporter can replace the file writer without changing the span fields. No third-party tracing key was available, so the dashboard is the local one.

The API caches identical session questions and limits clients to 30 requests a minute. The Docker command uses `sh -c` so Render’s `PORT` variable is expanded; the default remains 8000. The health check is `/health`.

Hosted-model token cost is not reported because no completion was billed. Local median latency on the 82-question run was 17.05 ms. That number will not hold once the hosted model is on the path.

## 11. Roles

The build is split so the six-person team can own a gate each, without inventing individual names here.

| Role | Owns |
|---|---|
| Specification and annotation | Frozen questions, gold figures, checksum |
| Retrieval | Corpus build, chunking, recall report |
| Agent and tools | Planner, calculator, critic, step limits |
| Evaluation | Harness, taxonomy, regression tests |
| Safety | Adversarial set, injection passage, refusal review |
| Deployment and demo | Site, traces, Docker, Render |

## 12. Limitations

The corpus is five companies, not the full NIFTY 50, and HCLTech does not yet have a full extracted annual report. Retrieval probes repeat words from the target page, so they do not measure paraphrase recall. Embeddings are hashed until the course embedding model is configured. The 82/82 result is the deterministic policy, not the 8B model. The Week 1 strategy comparison cannot be scored until the endpoint credentials are present. Traces stay on local disk. The parent NSE repository ignores this folder; the demo repository is the separate FinSight project that Render builds with root directory `finsight`.

## 13. How to reproduce

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=src python3 -m tests.test_finsight
PYTHONPATH=src python3 scripts/run_baseline.py
PYTHONPATH=src python3 scripts/run_retrieval_experiment.py
PYTHONPATH=src python3 scripts/run_safety.py
PYTHONPATH=src uvicorn finsight.api:app --host 127.0.0.1 --port 8020
```

Set the three `FINSIGHT_*` endpoint variables before expecting hosted-model output. Do not replace the frozen evaluation file without writing a new checksum and a new results table.
