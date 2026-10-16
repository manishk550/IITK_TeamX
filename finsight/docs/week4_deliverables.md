# Week 4 Deliverables — Deployment, Safety, and Demo

## Deployment

- FastAPI application: `src/finsight/api.py`
- Streamlit demo: `app.py`
- Container and Compose files: `Dockerfile`, `docker-compose.yml`
- Environment template: `.env.example`
- In-memory response cache and per-client rate limit: `src/finsight/service.py`

## Run locally

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=src uvicorn finsight.api:app --reload
PYTHONPATH=src streamlit run app.py
```

## Responsible AI

- Investment advice, guarantees, hidden personal-data requests, and instruction bypasses are refused.
- The human boundary is stated in the project specification.
- The calculator cannot execute arbitrary code.
- Retrieved content is treated as evidence, not as instructions to change policy.
- Figures are normalized to INR crore from official company sources and retain provenance links.

## Demo script

1. Show a cited fact lookup.
2. Show a growth calculation and its formula.
3. Compare two companies.
4. Ask for unavailable FY2030 data.
5. Ask for a buy recommendation and show the refusal.
6. Open `/api/traces` and identify tool calls, latency, and termination reason.

## Final package

- Technical report: `docs/final_technical_report.md`
- Presentation: `docs/final_presentation.md`
- Automated tests: `tests/test_finsight.py`
