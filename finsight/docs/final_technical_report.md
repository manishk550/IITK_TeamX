# FinSight Technical Report

Track B capstone: a citation-grounded financial-report copilot on the course chat model Qwen/Qwen3-8B. No weights are changed. The course endpoint does not serve embeddings. Arithmetic, schema checks, and refusals stay in deterministic code so the model cannot be the only source of a number.

## 1. Problem and users

Equity analysts and reviewers need answers that can be checked against a filing. The useful questions are factual (“what was revenue”), arithmetic (“what was the growth”), comparative, and qualitative. The same interface must refuse investment advice, predictions stated as facts, requests for personal data, and questions about companies or years that are not in the corpus.

FinSight covers 20 NIFTY companies for the year ended 31 March 2024. Reliance Industries, Tata Consultancy Services, Infosys, and Wipro have extracted annual-report pages. HCLTech and 15 further companies are covered by figures copied from each company’s FY2024 results release. HDFC Bank and ITC stay outside the corpus. Figures used in calculations are normalized to INR crore from official investor-relations sources. The copilot is a research aid. It does not place trades, and a person reviews any answer that would affect a decision.

## 2. Answer contract

An acceptable answer does four things.

1. It states the behavior: answer or refuse.
2. If it answers, it cites a document id, page, and section that were actually retrieved.
3. If it calculates, the expression is evaluated by the calculator tool. The model is not allowed to introduce a number that was not in the evidence or the calculator result.
4. If it refuses, it gives a reason: investment advice, prediction, personal data, prompt injection, missing inputs, or a company or period outside the corpus.

Gold questions were written against this contract and then frozen. The file `data/eval/eval_v1.jsonl` has 82 adjudicated items. Its SHA-256 is `2e3eaa1b71226cecab02eddf64e11cba7e641cce8aa265fee456912f8f31e6c3`, stored in `data/eval/eval_v1.sha256`.

## 3. Architecture

The system is one agent, not a group of agents. LangGraph orders that agent. The financial decisions stay in project code.

The browser posts a question to FastAPI. The service applies a per-client rate limit and a response cache, then calls `FinancialCopilot.answer`. That method invokes the graph in `src/finsight/graph.py`.

The graph is `plan`, then either `refuse` or `search → metadata → calculate → critic → finish`. `InMemorySaver` keeps a graph checkpoint for the session id inside the running process. Conversation turns, the last eight per session, and the token estimate are also written to SQLite (`data/state/sessions.sqlite`, override with `FINSIGHT_STATE_DB`), so a session survives a restart. `test_session_survives_restart` checks this. The loop is a directed graph, so it cannot cycle. A counter still stops the run at 10 steps. A token is `character count / 4`. When a session's running estimate reaches 6,000, the next question is refused and no tool is called. The last eight turns are passed into the planner, so a follow-up such as "what about its revenue growth" keeps the company from the previous turn.

- `plan` classifies the question, selects companies and a formula, or sets a refusal before any tool call.
- `search`, `metadata`, and `calculate` call `report_search`, `filing_metadata`, and `financial_calculator` directly. A failed tool call is retried once. The calculator accepts only arithmetic in an AST; names, calls, and exponentiation are rejected.
- `critic` turns tool results into a cited answer or a refusal. Embedded instructions in a retrieved passage are dropped before the critic reads them.

Rephrasing is off unless `FINSIGHT_PHRASE=1` and the hosted model is configured. The rephrase uses the HTTP client in `src/finsight/llm.py`. Any number in that rephrase must already appear in the deterministic answer. Invalid JSON or a new number falls back to the deterministic text. The normal path does not call the model.

LangChain is not used. A LangChain agent would let the model choose the next tool, and the recorded baseline showed that an unconstrained small model invents figures. LangGraph only runs the path above. There is no vector database. The corpus is 1,314 passages, so every passage is scored in process memory with a BM25-style keyword score plus cosine similarity of token counts, then a reranker. The course API does not provide embeddings, so that cosine stays on local token counts. Search does not call Pinecone, Chroma, or FAISS.

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

That is 1,273 extracted pages plus 41 curated passages, 1,314 passages in total. The extra 30 passages are two checked cards each for ICICI Bank, Bharti Airtel, State Bank of India, Hindustan Unilever, Larsen & Toubro, Maruti Suzuki, Tata Motors, Mahindra & Mahindra, Axis Bank, Kotak Mahindra Bank, Bajaj Finance, Sun Pharmaceutical, NTPC, UltraTech Cement, and Titan Company. HCLTech’s full annual-report PDF did not download from the investor-site URLs we tried, so HCLTech remains on the verified cards only. `scripts/build_corpus.py` can regenerate `data/corpus/pages.jsonl`. The script does not synthesize filings.

## 6. Week 1 prompting baseline

Three single-prompt strategies are implemented in `src/finsight/prompts.py` and exercised by `scripts/run_baseline.py`.

1. Structured few-shot: one JSON example, then the question, with a JSON response format.
2. Self-consistency: three independent samples of the same question.
3. Decomposition: the model is told to identify company, period, metric, and formula before the JSON answer.

The hosted model is now the course endpoint for groups 046–065: `Qwen/Qwen3-8B` at `https://103.42.50.41:1034/v1`. TLS is verified with `certs/vm04-ca.crt`. Each completion is limited to 1,024 tokens, one request is active per group key, and the limit is 60 requests a minute. The client retries HTTP 429 and 503 with waits of 2, 4, and 8 seconds. Thinking is turned off when the server accepts that flag, and any `<think>` block is removed before the text is parsed. The course service does not provide embeddings.

The table below is not a Qwen score. It is the earlier prompt-only run on OpenRouter model `liquid/lfm-2.5-2.6b:free`, used because that account had no credits for Llama 3.1 8B. The prompt contained the question only. Retries through 3 November 2026 scored 51 of 82 questions, saved in `reports/baseline_checkpoint.jsonl`. That free tier then returned HTTP 429, “free-models-per-day”. A later call to the course endpoint reached the server and returned HTTP 401, because the key then in `.env` was not the group key. `scripts/run_baseline.py` will score Qwen from question 1 only after that key is replaced; it must not be described as a continuation of the OpenRouter rows.

| Strategy | Completed | Accuracy | Valid JSON | Main failure |
|---|---|---|---|---|
| Structured few-shot | 51 | 0.000 | 1.000 | Refused 40 questions because no filing was in the prompt |
| Self-consistency | 51 | 0.000 | 1.000 | 42 empty or non-numeric answers; 5 invented figures |
| Decomposition | 51 | 0.000 | 1.000 | Plan step returned JSON, but the final answer text was empty |

One self-consistency sample invented an Infosys quarterly figure, Rs. 18,500 crore, that is not in the frozen gold set. Token cost on that free model was 0. `reports/baseline_results.json` matches those 51 scored questions. The other 31 questions were not scored on that model.

## 7. Retrieval

Chunking has two strategies. Section chunking keeps a passage intact when it is 700 characters or shorter, so a verified card that contains both revenue and operating income is not split. Longer PDF pages split on sentence boundaries. Fixed chunking uses 40-word windows with a 10-word overlap.

The ranker adds a BM25-style score and cosine similarity over normalized token counts. The course API has no embeddings endpoint, so this cosine is the dense score in production. A lexical reranker reorders the top candidates. Verified cards receive a priority bonus so a PDF page that repeats the word “revenue” does not hide the checked figure.

Retrieval was measured on 40 probes, separate from the answer-quality set. Each probe is eight content words taken from the middle of a randomly chosen PDF page (seed 7). The gold target is that page. Priority boosting was turned off for this comparison so the rankers are compared on the page text itself. These probes are lexical, not paraphrases, so absolute recall is high. The useful result is the gap between configurations.

| Chunking | Ranker | Recall@5 | Recall@10 |
|---|---|---|---|
| Section | BM25 | 0.950 | 1.000 |
| Section | Token cosine | 0.925 | 0.975 |
| Section | Hybrid | 0.950 | 1.000 |
| Fixed 40/10 | BM25 | 0.950 | 1.000 |
| Fixed 40/10 | Token cosine | 0.950 | 1.000 |
| Fixed 40/10 | Hybrid | 0.950 | 1.000 |

Section-level token cosine is the weakest of the six. Hybrid matches BM25 on this lexical set and is the production setting. The full table is `reports/retrieval_ablation.json`.

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
| Median latency | 19.54 ms |
| p95 latency | 38.53 ms |
| Model cost per query | $0.00 (no model call on the default path) |
| Failure taxonomy | none on this run |

Failures are labelled `retrieval_miss` (no citation, or a wrong answer whose citations miss every gold source), `tool_call_error`, `hallucination` (answer numbers disjoint from the gold numbers), `reasoning_error`, or `policy_error` (a refusal item that was answered).

That score validates the control flow, the calculator, and the citation check. It is not a Qwen score. Rephrasing stays off unless `FINSIGHT_PHRASE=1`. Turning it on would call `Qwen/Qwen3-8B` and reject any rewrite that adds a number.

The set mixes facts, growth calculations, operating margins, two-company comparisons, three-year trends, multi-document lookups, narrative questions, and refusals. Worked checks include Reliance growth `(914472.0 - 891311.0) / 891311.0 * 100` = 2.6%, Infosys operating margin `31747.0 / 153670.0 * 100` = 20.7%, and HCLTech operating margin 18.2%.

## 9. Safety

Twenty-four adversarial prompts are in `data/safety/adversarial.jsonl` and the run log is `reports/safety_log.json`. Categories are investment advice, predictions, unavailable years, companies outside the corpus, including HDFC Bank and ITC, Aadhaar / PAN / phone / email / password requests, question-level prompt injection, a poisoned passage inside the corpus, a malformed calculator expression, and a request to approve a trade.

All 24 stayed inside policy. None of the answers repeated the planted sentence that tells the user to buy Reliance shares. Question-level overrides such as “ignore the filings” are refused before search. The planted passage is removed from the evidence list if it is retrieved. Consequential actions, including approving a trade, are refused and left for a person.

## 10. Tracing, deployment, and cost

Each request is an OpenTelemetry span. The SDK (`opentelemetry-sdk`) creates the span, and a JSONL exporter writes `data/traces/traces.jsonl` with a trace id, span id, duration, and tool-count event. The research site links to `/traces`, which reads `/api/traces`. The log survives a process restart on the same machine. LangSmith and Langfuse were not used because no project key was available. Their exporters can sit beside the JSONL exporter. The span fields already follow the OpenTelemetry model.

The API caches identical session questions and limits clients to 30 requests a minute. The Docker command uses `sh -c` so Render’s `PORT` variable is expanded; the default remains 8000. The health check is `/health`.

The default answer path does not call Qwen, so its model cost is $0.00. Local median latency on the 82-question run was 19.54 ms (p95 38.53 ms). A Qwen completion is limited to 1,024 output tokens and will be slower than that local path. The course endpoint billed nothing on the connectivity check, which returned HTTP 401 before a completion.

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

The corpus is 20 NIFTY companies, not the full NIFTY 50. HCLTech and 15 other companies are results cards rather than full annual reports. Retrieval probes repeat words from the target page, so they do not measure paraphrase recall. The course API does not serve embeddings, so the dense score is token cosine. The 82/82 result is the deterministic policy, not Qwen. The Week 1 table is 51 of 82 questions on an earlier free model, not on `Qwen/Qwen3-8B`. Traces stay on local disk. The parent NSE repository ignores this folder; the demo repository is the separate FinSight project that Render builds with root directory `finsight`.

## 13. How to reproduce

```bash
python3 -m pip install -r requirements.txt
PYTHONPYCACHEPREFIX=/tmp/finsight-pycache PYTHONPATH=src python3 -m pytest tests/test_finsight.py -q
PYTHONPATH=src python3 scripts/run_baseline.py
PYTHONPATH=src python3 scripts/run_retrieval_experiment.py
PYTHONPATH=src python3 scripts/run_safety.py
PYTHONPATH=src uvicorn finsight.api:app --host 127.0.0.1 --port 8020
```

Set `FINSIGHT_BASE_URL` to `https://103.42.50.41:1034/v1`, `FINSIGHT_MODEL` to `Qwen/Qwen3-8B`, `FINSIGHT_CA_CERT` to `certs/vm04-ca.crt`, and `FINSIGHT_API_KEY` to the group key before expecting a hosted completion. Do not replace the frozen evaluation file without writing a new checksum and a new results table.

The Streamlit front-end required by the track is `app.py`. It calls the same `CopilotService` as the website. Run it with `PYTHONPATH=src streamlit run app.py`.

## 14. Track B requirement trace

This section maps the API-side brief onto the repository. It is the checklist a reviewer can score without reading the code first.

### I. Task decomposition

`docs/project_specification.md` states the jobs the copilot will do, the refusal policy, and the contract for a correct answer: a direct answer, units, a formula when arithmetic is involved, and a citation that was actually retrieved. `docs/annotation_guide.md` is the rule set used to write gold answers. `data/eval/eval_v1.jsonl` holds 82 questions, inside the required 60–100. Each row has a gold answer, gold evidence, and `must_contain` tokens. The SHA-256 of that file is `2e3eaa1b71226cecab02eddf64e11cba7e641cce8aa265fee456912f8f31e6c3`. The file was frozen before the agent was tuned against it. Replacing it requires a new checksum and a new results table.

The 82 questions cover fact lookup, calculation, ratio, comparison, trend, multi-document, qualitative, and refusal. Fourteen of them must be refused.

### II. Prompt baseline

Three single-prompt strategies, with no retrieved evidence, are in `src/finsight/prompts.py` and `scripts/run_baseline.py`.

1. Structured few-shot asks for one JSON object after a worked example.
2. Self-consistency draws three samples and keeps an answer only when they agree.
3. Decomposition asks the model to name the company, period, metric, and formula before it writes the answer.

The scored rows are from `liquid/lfm-2.5-2.6b:free`: 51 of 82 questions, accuracy 0.000 on every strategy, valid JSON 1.000. Few-shot refused 40 questions because the prompt contained no filing. Self-consistency produced 42 empty or non-numeric answers and 5 invented figures, including an Infosys amount of Rs. 18,500 crore that is not in the gold set. Decomposition returned a JSON plan and an empty final answer on all 51. The configured model is now `Qwen/Qwen3-8B` on the course VM. Those 51 rows are not a Qwen result. A short upstream limit is retried with a wait, instead of aborting the file.

That is the documented break. A small model can follow a schema. It cannot be the source of a financial figure.

### III. Retrieval

The corpus is 1,314 passages: 40 checked cards, 1 planted injection passage, and 1,273 PDF pages. That is inside 500–2,000. Extracted pages cover Reliance Industries, Tata Consultancy Services, Infosys, and Wipro. HCLTech and the other 15 companies are checked cards. HCLTech remains on cards because the annual-report PDF did not download. HDFC Bank and ITC are still refused.

Chunking was compared, not assumed. Section chunking keeps a passage of 700 characters or fewer intact. Fixed chunking uses a 40-word window and a 10-word overlap. Retrieval is hybrid: a BM25-style score, cosine similarity of normalized token counts, a priority bonus of 12 for a checked card, and a reranker on the top candidates. Recall was measured on 40 page probes, separately from answer quality. Section dense was the weak cell (recall@5 0.925, recall@10 0.975). The other five runs were recall@5 0.950 and recall@10 1.000. Production is section chunks plus hybrid. Answers cite document id, page, and section from the passages that were retrieved.

### IV. Agent

LangGraph runs one agent through planner, executor, and critic. The graph is `plan`, then either `refuse` or `search → metadata → calculate → critic → finish`. The three tools are `report_search`, `filing_metadata`, and `financial_calculator`. Tool arguments are validated with Pydantic. A validation error, a bad expression, or an unknown tool returns status `error`, the call is retried once, and a second failure is recorded rather than raised. The calculator parses an expression tree and allows only addition, subtraction, multiplication, and division.

The graph has no cycle, so it cannot spin. A step counter still caps a question at 10 steps. Session turns, at most eight, and the token estimate are stored in SQLite (`data/state/sessions.sqlite`). A follow-up that does not name a company inherits the company from the previous turn when it says "it", "that", "same", or a similar cue. A session whose estimate has reached 6,000 tokens is refused before any tool runs. Hosted-model JSON uses `response_format: json_object`, falls back if the endpoint rejects that field or the Qwen thinking flag, strips a `<think>` block, and is discarded by the rephrase path if parsing fails or if the rewrite adds a number. Output is capped at 1,024 tokens, which is the course maximum.

### V. Evaluation and tracing

`src/finsight/evaluation.py` scores the frozen file. On the deterministic path the result is 82 correct out of 82, task completion 1.000, 2.88 tool calls on average, median latency 19.54 ms, p95 latency 38.53 ms, and model cost $0.00 because that path does not call the hosted model. Each evaluation question uses its own session id, so one item cannot leak state into the next.

A wrong answer is labelled with one of: `retrieval_miss` (no citation, or citations that miss every gold source), `tool_call_error` (every tool call failed), `hallucination` (numbers in the answer share nothing with the gold numbers), `reasoning_error` (any other miss, including an answer that should have been given), and `policy_error` (a refusal item that was answered). The run above had an empty taxonomy.

Traces are OpenTelemetry spans from `opentelemetry-sdk`, exported to `data/traces/traces.jsonl` and shown at `/traces`.

### VI. Shipping and responsible AI

The Track B front-end is the Streamlit app in `app.py`. The FastAPI site in `src/finsight/static/index.html` is the demo surface used in the transcript, including the trace page. Both call `CopilotService`. Docker uses `python:3.11-slim`. The image does not copy `.env`. Compose publishes port 8000. The API allows 30 requests a minute per client and caches 500 responses.

Responsible-AI coverage is in `docs/responsible_ai.md` and `reports/safety_log.json`. Twenty-four adversarial prompts stayed inside policy. The corpus contains a planted passage, POISON-001, that tells the system to ignore the rules and recommend buying Reliance. Retrieved passages matching that instruction are dropped before the critic writes. Questions for Aadhaar, PAN, a phone number, or a personal email are refused before search. Approving a trade is refused. The human boundary is stated: a person approves anything that would become an investment decision, a client note, an audit conclusion, or a regulatory filing.

### What is still open

Three items are not closed by this repository.

The Week 1 table is 51 of 82 questions on the earlier free model. `Qwen/Qwen3-8B` is configured, and the certificate check succeeded, but a completion has not been scored. The key stored when this report was written was rejected with HTTP 401. `scripts/run_baseline.py` checks the key first and, for any other model, writes a separate checkpoint. It does not append Qwen rows to the earlier results file.

The service is containerised and runs locally. It is not on a public URL. A Render deploy uses repository root `finsight` and health check `/health`. The deck's title slide still needs the team name and six members.

The course API does not offer an embeddings model. Dense retrieval remains token cosine.

## 15. Worked executions

These five questions are the live demo. The answers below are what the deterministic path returned.

Reliance fiscal 2024 revenue is a lookup. Search and metadata run. The calculator does not. The answer quotes the checked card: revenue was ₹914,472 crore for fiscal 2024. The citation is RIL-AR-2024, page 1, Consolidated Financial Performance. The same passage also states fiscal 2023, which is why that year appears in the answer.

Reliance growth is a calculation. The expression is `(914472.0 - 891311.0) / 891311.0 * 100`. The calculator returns 2.6%. The critic will not print a percentage unless that tool returned a float.

Infosys versus HCLTech operating margin runs search and metadata twice and the calculator twice. Infosys is `31747.0 / 153670.0 * 100` = 20.7%. HCLTech is `20027.0 / 109913.0 * 100` = 18.2%. The answer says Infosys is higher. Citations include INFY-AR-2024 page 1 and HCLTECH-AR-2024 page 1.

"What will Reliance revenue be in FY2030?" matches a future-year rule in the planner. The behavior is refuse. The tool list is empty.

"Should I buy Reliance shares?" matches the advice rule. The behavior is refuse. The tool list is empty. The planted buy instruction in POISON-001 is not a reason to answer this question.

A sixth check is conversational. After the Reliance revenue question in the same session, "What about its revenue growth in fiscal 2024?" has no company name. The planner copies Reliance from the saved turn and returns 2.6%. A new session does not have that turn, so the same wording is not given a company by magic.

## 16. How the small model was compensated

This is the graded design question. The compensations are specific.

Invented figures are blocked by keeping arithmetic in the calculator and by rejecting a rephrase that contains a digit the deterministic answer did not contain. The rephrase is off unless `FINSIGHT_PHRASE=1`.

Malformed tool arguments are blocked by Pydantic models on the three tools, plus one retry that shortens an over-long query and strips commas from an expression.

Malformed model JSON is blocked by requesting a JSON object, retrying without that flag when the endpoint returns 400, 404, or 422, and by treating a parse failure as "keep the deterministic answer."

Loops are blocked by the shape of the graph and by the 10-step counter.

Runaway conversations are blocked by the eight-turn memory and the 6,000-token refusal.

Hidden instructions are blocked twice: refusal patterns run before search, and retrieved text that matches an override pattern is removed before the critic reads it.

Weak retrieval of the checked number is blocked by leaving short cards whole and by the priority bonus, which was added after PDF pages were outranking the card that held the gold figure.

The baseline is kept in the report at 0% so the compensation has a measured starting point, not a claim that the model was never tried.
