# FinSight

FinSight is a Track B capstone project: a citation-grounded financial-report copilot on the course model `Qwen/Qwen3-8B` (8B parameters), reached through the group API with the CA certificate in `certs/`.

The development corpus covers 20 NIFTY companies. Reliance Industries, Tata Consultancy Services, Infosys, and Wipro include extracted annual-report pages. HCLTech and 15 further companies use FY2024 figures copied from each company’s own results release. HDFC Bank and ITC stay outside the corpus because the frozen evaluation still expects those names to be refused. Values are normalized to INR crore.

## What is included

- Week 1 specification, annotation guide, three prompting strategies, and a frozen 82-question set
- Hybrid retrieval with chunking, reranking, filters, and citations
- LangGraph planner → executor → critic workflow. Search, filing metadata, and the calculator are called directly
- Persistent sessions, retries, step limits, and trace data
- FastAPI, Streamlit, Docker, cache, and rate limiting
- Safety tests, technical report, and 12-slide presentation

## Quick start

```bash
python3 -m pip install -r requirements.txt
PYTHONPYCACHEPREFIX=/tmp/finsight-pycache PYTHONPATH=src python3 -m pytest tests/test_finsight.py -q
PYTHONPATH=src uvicorn finsight.api:app --reload
PYTHONPATH=src streamlit run app.py
```

## Documentation

- [Week 1](docs/week1_deliverables.md)
- [Week 2](docs/week2_deliverables.md)
- [Week 3](docs/week3_deliverables.md)
- [Week 4](docs/week4_deliverables.md)
- [Technical report](docs/final_technical_report.md) and [Word report](docs/FinSight_Technical_Report.docx), about 14 pages
- [Presentation deck](docs/FinSight_Final_Presentation.pptx) (rebuild with `PYTHONPATH=src:.vendor python3 scripts/build_deck.py`) and [speaker outline](docs/final_presentation.md)

## Important data note

The corpus has 1,314 passages: 40 verified cards, one planted injection note, and 1,273 pages extracted from the official Reliance, TCS, Infosys, and Wipro FY2024 PDFs. HCLTech and 15 further NIFTY companies are verified cards only. The frozen evaluation set has 82 questions (`data/eval/eval_v1.sha256`). Hosted-model baseline scores are written only when `FINSIGHT_BASE_URL`, `FINSIGHT_API_KEY`, and `FINSIGHT_MODEL` are set.
