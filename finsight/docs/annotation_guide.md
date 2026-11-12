# Evaluation Annotation Guide

Version: 1.0  
Applies to: `data/eval/eval_v1.jsonl`

## 1. Annotation workflow

1. Select a source document already intended for the project corpus.
2. Read the relevant page, section, or table before writing the question.
3. Write a realistic question that a financial analyst might ask.
4. Record the minimal evidence required to answer it.
5. Calculate the gold answer independently from that evidence.
6. Assign a question type, difficulty, and expected system behavior.
7. Have a second team member review the evidence and calculation.
8. Mark the example `adjudicated` only after both reviewers agree.

## 2. Required fields

| Field | Rule |
|---|---|
| `id` | Stable ID in the form `FIN-001` |
| `question` | Complete, unambiguous user request |
| `question_type` | One value from the taxonomy below |
| `difficulty` | `easy`, `medium`, or `hard` |
| `company` | Company or companies referenced |
| `fiscal_period` | Period required to answer |
| `expected_behavior` | `answer` or `refuse` |
| `gold_answer` | Concise final answer |
| `acceptable_variants` | Equivalent formats or wording |
| `formula` | Required for calculations; otherwise `null` |
| `evidence` | Source IDs, locations, and short excerpts |
| `tolerance` | Numerical tolerance or `null` |
| `review_status` | `draft` or `adjudicated` |

## 3. Question taxonomy

| Type | Target count | Difficulty guidance |
|---|---:|---|
| `fact_lookup` | 20 | Answer appears in one location |
| `calculation` | 15 | Requires two or more inputs and one formula |
| `ratio` | 10 | Requires a defined financial formula |
| `comparison` | 10 | Compares companies or periods |
| `trend` | 10 | Uses at least three periods |
| `multi_document` | 5 | Requires two or more filings |
| `qualitative` | 5 | Summarizes cited narrative disclosures |
| `refusal` | 5 | Must be refused or qualified |

The initial file contains 20 representative records. The team must expand it to 60–100 records before the Week 1 gate.

## 4. Difficulty rubric

- **Easy:** One document and one explicit value or policy statement.
- **Medium:** One calculation, comparison, or multi-paragraph summary.
- **Hard:** Multiple documents, multiple calculations, conflicting evidence, or a subtle refusal.

## 5. Gold-answer rules

- Include currency, scale, period, and sign.
- Preserve negative values in parentheses or with a minus sign as an acceptable variant.
- Do not round differently from the source unless the requested format requires it.
- For qualitative answers, list the required facts rather than mandating one exact paragraph.
- For refusals, define the required refusal reason rather than one exact sentence.

## 6. Evidence rules

Evidence must be sufficient for a third person to verify the answer without searching the entire filing. Include the document title, filing type, fiscal period, page or section, and a short excerpt. Do not mark an item adjudicated if the evidence location is unknown.

## 7. Reviewer checklist

- The question has one clear interpretation.
- The source period and company match the question.
- All formula inputs are visible in the evidence.
- Units and scale are explicit.
- Citations support every factual claim.
- Refusal items do not accidentally request permitted analysis.
- No personal or non-public information appears in the example.

## 8. Disagreement process

If reviewers disagree, record both interpretations in the weekly review notes and either rewrite the question or remove it. Do not resolve ambiguity by accepting both substantially different answers.
