# Week 3 Deliverables — Agent and Observability

## Agent loop

`src/finsight/graph.py` runs a LangGraph `StateGraph` with a checkpoint per session; turns are also persisted to SQLite so they survive a restart. The graph calls `report_search`, `filing_metadata`, and `financial_calculator` directly. `src/finsight/agent.py` owns the rules:

1. Planner: intent, company, period, metric, formula, and refusal detection
2. Executor: `report_search`, `filing_metadata`, and `financial_calculator`
3. Critic: evidence, calculation, citation, and policy checks
4. Persistent session history across turns
5. Maximum 10 steps, token accounting, retry, and explicit termination reason

## Tool safety

- Pydantic validates every tool argument.
- The calculator accepts only arithmetic expressions.
- Malformed calls are recorded and retried once with normalized arguments.
- Unknown tools and divide-by-zero conditions return structured errors.

## Observability

Every response includes:

- Trace ID
- Tool name, arguments, status, and error detail
- Latency and token estimate
- Termination reason
- Citations and refusal reason

The API exposes recent executions at `/api/traces`.

## Failure taxonomy

- Retrieval miss
- Reasoning error
- Tool-call error
- Citation error
- Policy error

## Gate

No query can run indefinitely, and a malformed tool call cannot crash the request.
