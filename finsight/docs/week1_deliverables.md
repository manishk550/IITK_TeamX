# Week 1 Deliverables — Specification and Baseline

## Completed artifacts

- Project specification: `docs/project_specification.md`
- Annotation rules: `docs/annotation_guide.md`
- Initial frozen-set schema and 20 examples: `data/eval/eval_v1.jsonl`
- Baseline protocol: `docs/week1_baseline_protocol.md`

## Baseline strategies

| Strategy | Mechanism | Result on development set |
|---|---|---|
| Structured few-shot | JSON answer, citations, calculation, and refusal fields | Reliable schema, but the small model may omit evidence |
| Self-consistency | Three sampled answers accepted only on agreement | More stable numerically, but three times the token cost |
| Decomposition | Separate planning and resolution steps | Best control point for later planner/executor/critic design |

## Small-model failure observations

- Tool arguments can be malformed or contain explanatory text.
- The model may confuse operating income with revenue when both appear nearby.
- Long retrieved passages can crowd out the requested period.
- Safety instructions inside a user question or document must be handled outside free-form generation.

## Gate

The evaluation schema is fixed. Expand the 20 examples to 60–100 adjudicated examples before reporting final academic results.
