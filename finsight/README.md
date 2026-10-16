# FinSight

FinSight is a Track B capstone project: a citation-grounded financial-report copilot built for a hosted instruction model of at most 8B parameters.

The development corpus covers five NIFTY 50 constituents—Reliance Industries, Tata Consultancy Services, Infosys, HCLTech, and Wipro—using FY2024 figures from official company investor-relations sources. Values are normalized to INR crore.

## What is included

- Week 1 specification, annotation guide, baseline protocol, and evaluation seed
- Hybrid retrieval with chunking, reranking, filters, and citations
- Planner → executor → critic workflow with three validated tools
- Persistent sessions, retries, step limits, and trace data
- FastAPI, Streamlit, Docker, cache, and rate limiting
- Safety tests, technical report, and 12-slide presentation

## Quick start

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=src python3 -m tests.test_finsight
PYTHONPATH=src uvicorn finsight.api:app --reload
PYTHONPATH=src streamlit run app.py
```

## Documentation

- [Week 1](docs/week1_deliverables.md)
- [Week 2](docs/week2_deliverables.md)
- [Week 3](docs/week3_deliverables.md)
- [Week 4](docs/week4_deliverables.md)
- [Technical report](docs/final_technical_report.md)
- [Presentation](docs/final_presentation.md)

## Important data note

The bundled corpus contains 10 verified excerpts from five official annual-report/result sources. Expand it to the required 500–2,000 NSE/BSE filings or annual-report sections and extend `data/eval/eval_v1.jsonl` from 20 to 60–100 adjudicated questions before final submission.
