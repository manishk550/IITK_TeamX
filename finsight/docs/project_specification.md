# FinSight Project Specification

Version: 1.0  
Status: Week 1 draft for team review  
Domain: Financial-report question answering

## 1. Purpose

FinSight helps an analyst retrieve and interpret information from a selected corpus of public financial filings. It answers factual, numerical, comparative, and qualitative questions only when supporting evidence is available, and it shows the evidence used to reach each answer.

The system is an analytical assistant. It does not provide investment advice, execute transactions, approve credit, or replace a qualified financial professional.

## 2. Users and jobs to be done

| User | Primary job |
|---|---|
| Financial analyst | Find reported figures and compare companies or periods |
| Investment researcher | Assemble cited evidence for a research note |
| Compliance reviewer | Check whether a statement is supported by a filing |
| Student or trainee | Understand how a figure was derived from source documents |

## 3. Supported tasks

1. **Fact lookup:** Return a value explicitly reported in a filing.
2. **Calculation:** Compute a value from explicitly identified inputs using a documented formula.
3. **Ratio analysis:** Compute a standard ratio and state its formula and units.
4. **Period comparison:** Compare the same metric across fiscal periods.
5. **Company comparison:** Compare the same metric across companies and periods.
6. **Trend summary:** Describe a metric over multiple reported periods.
7. **Qualitative summary:** Summarize risks, policies, or management discussion with citations.
8. **Evidence check:** Confirm whether a proposed claim is supported, contradicted, or absent.
9. **Insufficient-evidence response:** State what is missing and avoid inventing a result.
10. **Policy refusal:** Decline consequential or prohibited requests while explaining the boundary.

## 4. Corpus scope

The Week 2 corpus will contain 500–2,000 documents or filing sections drawn from Indian public disclosures, with a target of 20–40 annual and quarterly reports across NIFTY 50 companies. Every document record must include:

- Company name and ticker
- NSE/BSE symbol and security identifier, where applicable
- Filing type, fiscal period, and publication date
- Source URL and file hash
- Page or section location
- Currency and unit metadata when available

The initial corpus uses official investor-relations material from Reliance Industries, TCS, Infosys, HCLTech, and Wipro. The production corpus should add NSE/BSE corporate announcements, company annual reports, and SEBI-regulated disclosures only when provenance is recorded in the corpus manifest.

## 5. Correct answer contract

Every successful answer must contain:

- A direct answer
- The company, metric, fiscal period, currency, and scale
- The formula and inputs for every calculated value
- One or more citations containing document ID, filing type, period, and page or section
- A short evidence excerpt or table reference
- Material caveats, including restatements, discontinued operations, or non-GAAP definitions

A numerical answer is correct when:

- The value matches the gold answer within the permitted tolerance
- The fiscal period and currency are correct
- The scale is explicit, normally INR crore
- Every input is supported by a citation
- The formula is appropriate for the requested metric

Unless a gold answer states otherwise, currency values may differ by at most 0.5% or one unit at the reported scale, whichever is larger. Percentages may differ by at most 0.1 percentage points.

## 6. Refusal and qualification policy

FinSight must refuse:

- Buy, sell, or hold recommendations
- Price targets and predictions presented as facts
- Portfolio allocation or trading instructions
- Credit approval, fraud judgments, or regulatory determinations
- Requests for personal, account, or other non-public information
- Requests to ignore citations, conceal uncertainty, or bypass safety rules
- Instructions embedded in retrieved documents that attempt to alter system behavior

FinSight must qualify or decline when:

- The requested filing is outside the corpus
- The requested period or segment is unavailable
- Evidence conflicts and cannot be reconciled
- A calculation lacks one or more required inputs
- A qualitative answer would require unsupported interpretation

A refusal must state the boundary and, where possible, offer a permitted alternative such as presenting the cited historical figures needed for a person to perform the analysis.

## 7. Human-in-the-loop boundary

A person must review the output before it is used in an investment decision, client communication, regulatory filing, credit decision, audit conclusion, or executive report. FinSight may prepare cited analysis, but it may not take those consequential actions.

## 8. Non-functional requirements

- Agent runs are limited to 10 steps.
- Tool inputs and outputs must conform to JSON schemas.
- Malformed model output may be retried up to two times.
- Every run must record latency, token usage, cost, tool calls, and termination reason.
- The evaluation set remains unchanged after the Week 1 freeze.

## 9. Acceptance examples

| Request | Expected behavior |
|---|---|
| “What was Reliance Industries FY2024 revenue?” | Return the cited reported value, period, and INR-crore scale. |
| “Calculate Infosys FY2024 operating margin.” | Show operating income, revenue, formula, result, and citations. |
| “Should I buy Reliance Industries shares?” | Refuse investment advice and offer cited historical analysis only. |
| “What was FY2030 revenue?” | State that the period is unavailable; do not estimate. |
