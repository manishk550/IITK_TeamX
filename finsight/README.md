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

## Deploy with the group API key

```bash
cp .env.example .env          # then set FINSIGHT_API_KEY to the group key
docker compose up -d --build
curl http://localhost:8000/health   # expect "model_configured": true and "provider": "course"
```

Open http://localhost:8000. Answers show "Phrased with the course API key." when Qwen3-8B was used.

- The key is read from `.env` at container start (`env_file`). `.env` is git-ignored and listed in `.dockerignore`, so it never enters the image or the repo.
- FinSight uses Qwen3-8B through the group key by default, in Docker and when run locally with `uvicorn` or Streamlit. Set `FINSIGHT_DEFAULT_PROVIDER=local` to run the FastAPI agent only, with no model calls. The Course API / FastAPI toggle on the page still switches per browser. If no key is configured, answers fall back to the FastAPI agent and say so.
- Unit tests pin `FINSIGHT_DEFAULT_PROVIDER=local` (`tests/conftest.py`) so they never call the hosted model.
- On a hosting platform (Render, Railway, a VM without compose), build the `Dockerfile` and set `FINSIGHT_BASE_URL`, `FINSIGHT_API_KEY`, `FINSIGHT_MODEL`, `FINSIGHT_CA_CERT=/app/certs/vm04-ca.crt` and `FINSIGHT_DEFAULT_PROVIDER=course` as environment variables or secrets. Do not upload `.env`.
- The host must be able to reach the course endpoint (`103.42.50.41:1034`). The CA certificate for it ships in `certs/`.

## Documentation

- [Week 1](docs/week1_deliverables.md)
- [Week 2](docs/week2_deliverables.md)
- [Week 3](docs/week3_deliverables.md)
- [Week 4](docs/week4_deliverables.md)
- [Technical report](docs/final_technical_report.md) and [Word report](docs/FinSight_Technical_Report.docx), about 14 pages
- [Presentation deck](docs/FinSight_Final_Presentation.pptx) (rebuild with `PYTHONPATH=src:.vendor python3 scripts/build_deck.py`) and [speaker outline](docs/final_presentation.md)

## Important data note

The corpus has 1,314 passages: 40 verified cards, one planted injection note, and 1,273 pages extracted from the official Reliance, TCS, Infosys, and Wipro FY2024 PDFs. HCLTech and 15 further NIFTY companies are verified cards only. The frozen evaluation set has 82 questions (`data/eval/eval_v1.sha256`). Hosted-model baseline scores are written only when `FINSIGHT_BASE_URL`, `FINSIGHT_API_KEY`, and `FINSIGHT_MODEL` are set.
