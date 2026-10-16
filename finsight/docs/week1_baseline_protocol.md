# Week 1 Baseline Protocol

Version: 1.0

## 1. Objective

Measure the hosted 8B model before adding retrieval or agent orchestration. The baseline establishes the minimum result that later system versions must beat.

## 2. Preconditions

- `eval_v1.jsonl` contains 60–100 adjudicated examples.
- The file checksum and freeze date are recorded.
- No baseline result is used to rewrite gold answers.
- All strategies use the same model, temperature policy, and evaluation set.

## 3. Prompt strategies

### A. Structured few-shot

Provide three worked examples and require a JSON response containing `answer`, `citations`, `calculation`, `confidence`, and `refusal_reason`. This tests whether schema constraints improve reliability.

### B. Self-consistency

Generate three independent reasoning paths using the same structured schema. Accept the answer only when at least two paths agree. This tests stability on calculations and comparisons.

### C. Decomposition

First ask for a JSON plan containing the metric, period, required inputs, and formula. Then ask the model to resolve that plan. This tests whether explicit decomposition reduces skipped steps.

## 4. Metrics

Record these values for every strategy:

- Exact or tolerance-based accuracy
- Citation presence
- Schema validity
- Correct refusal rate
- Median and 95th-percentile latency
- Input tokens, output tokens, and estimated cost
- Failure category and representative examples

## 5. Failure categories

| Category | Definition |
|---|---|
| `schema_error` | Output is not valid JSON or misses required fields |
| `reasoning_error` | Evidence is available but the conclusion is wrong |
| `calculation_error` | Inputs are right but arithmetic or scale is wrong |
| `hallucination` | Answer invents a fact or citation |
| `refusal_error` | System refuses a valid request or answers a prohibited one |
| `incomplete` | Required period, unit, formula, or caveat is missing |

## 6. Reporting format

The Week 1 report should include:

1. Dataset size and question-type distribution
2. Model identifier and generation settings
3. One results table for all three strategies
4. Five annotated failures per strategy
5. The selected baseline and the reason for its selection
6. Specific small-model weaknesses to address in Weeks 2–4

## 7. Freeze rule

After the baseline run, tag the commit and record the evaluation checksum. Later prompt improvements may be developed on a separate development split, but the reported test set remains unchanged.
