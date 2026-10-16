# FinSight

FinSight is a Track B capstone project: a citation-grounded financial-report copilot built for a hosted instruction model of at most 8B parameters.

The development corpus covers five NIFTY 50 constituents—Reliance Industries, Tata Consultancy Services, Infosys, HCLTech, and Wipro—using FY2024 figures from official company investor-relations sources. Values are normalized to INR crore.

## What is included

- Week 1 specification, annotation guide, three prompting strategies, and a frozen 82-question set
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

The corpus has 1,284 passages: 10 verified metric and narrative cards, one planted injection note, and 1,273 pages extracted from the official Reliance, TCS, Infosys, and Wipro FY2024 PDFs. HCLTech is still the verified card only. The frozen evaluation set has 82 questions (`data/eval/eval_v1.sha256`). Hosted-model baseline scores are written only when `FINSIGHT_BASE_URL`, `FINSIGHT_API_KEY`, and `FINSIGHT_MODEL` are set.
