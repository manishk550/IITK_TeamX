# FinSight demo transcript

About three minutes. Read the “You” lines. Type the questions exactly. The expected lines are what the app returned on 25 October 2026.

## Before you start

In one terminal, from the `finsight` folder:

```bash
PYTHONPATH=src:.vendor python3 -m uvicorn finsight.api:app --host 127.0.0.1 --port 8020
```

Open the site whose `/health` model is `Qwen/Qwen3-8B`. That is `http://127.0.0.1:8022` while an older process is still holding port 8020. Leave the chat on the screen. Have `/traces` one click away in the left sidebar. Do not turn on model rephrasing.

If a question comes back differently, read the answer that is on the screen. Do not correct it from memory.

## Transcript

**You:** I’ll ask the same system five questions. Three should be answered from the filings. Two should be refused before any search.

**Type this:**

What was Reliance Industries revenue for fiscal 2024?

**You:** The figure to look at is 914,472 crore for fiscal 2024. The passage also carries fiscal 2023, which is why that year is in the answer. On the right, the citation is RIL-AR-2024, page 1, Consolidated Financial Performance. Two tools ran: report search and filing metadata. The calculator did not run, because this is a lookup.

**Type this:**

By what percent did Reliance revenue grow in fiscal 2024?

**You:** The answer is 2.6 percent. The expression is on the screen: 914,472 minus 891,311, divided by 891,311, times 100. That arithmetic is the calculator, not the language model. Same filing, page 1.

**Type this:**

Compare the Infosys and HCLTech operating margins.

**You:** Infosys is higher: 20.7 percent against HCLTech at 18.2 percent. Both are operating income divided by revenue. The citations split across two documents: INFY-AR-2024, page 1, Three Year Financial Overview, and HCLTECH-AR-2024, page 1, FY2024 Financial Results. Search ran once for each company.

**Type this:**

What will Reliance revenue be in FY2030?

**You:** Refused. The reason is that a future year is outside the corpus. There is no citation and no tool call. It did not guess a number.

**Type this:**

Should I buy Reliance shares?

**You:** Refused again. FinSight will not give a buy, sell, or hold recommendation. Same pattern: no search, no citation. A person makes that decision.

**You:** Last thing. I’ll open Traces. Each of those questions is a span, with the tool calls on the ones that answered and none on the two refusals.

Click **Traces** in the left sidebar. Point at the newest spans. Stop.
