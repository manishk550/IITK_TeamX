# Week 1 Deliverables — Specification and Baseline

## Completed artifacts

- Project specification: `docs/project_specification.md`
- Annotation rules: `docs/annotation_guide.md`
- Initial frozen-set schema and 20 examples: `data/eval/eval_v1.jsonl`
- Baseline protocol: `docs/week1_baseline_protocol.md`

## Baseline strategies

| Strategy | Mechanism | Result on the first 51 frozen questions, earlier free model, not Qwen |
|---|---|---|
| Structured few-shot | JSON answer, citations, calculation, and refusal fields | Accuracy 0. Valid JSON. Refused when no filing was supplied |
| Self-consistency | Three sampled answers accepted only on agreement | Accuracy 0. Often empty; sometimes invented a figure |
| Decomposition | Separate planning and resolution steps | Accuracy 0. Final answer text was empty |

## Small-model failure observations

- Tool arguments can be malformed or contain explanatory text.
- The model may confuse operating income with revenue when both appear nearby.
- Long retrieved passages can crowd out the requested period.
- Safety instructions inside a user question or document must be handled outside free-form generation.

## Gate

The evaluation schema is fixed. The frozen file now has 82 adjudicated examples, inside the 60–100 range, and its checksum is `data/eval/eval_v1.sha256`.
