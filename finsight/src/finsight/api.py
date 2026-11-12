"""FastAPI application for the FinSight copilot."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from finsight.providers import activate, describe, reset, saved_provider, set_saved_provider
from finsight.schemas import ChatRequest, ProviderRequest
from finsight.service import CopilotService
from finsight.tracing import tracer


app = FastAPI(title="FinSight Financial Report Copilot", version="1.0.0")
service = CopilotService()


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path(__file__).with_name("static") / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": service.copilot.model_name, **service.stats}


@app.get("/api/stats")
def stats() -> dict:
    return service.stats


@app.get("/traces")
def traces_page() -> FileResponse:
    return FileResponse(Path(__file__).with_name("static") / "traces.html")


@app.get("/api/provider")
def provider() -> dict:
    active = describe(saved_provider())
    return {**active, "options": [describe("course"), describe("local")]}


@app.post("/api/provider")
def choose_provider(body: ProviderRequest) -> dict:
    set_saved_provider(body.provider)
    return provider()


@app.post("/api/ask")
def ask(body: ChatRequest, request: Request) -> dict:
    client = request.client.host if request.client else "local"
    token = activate(body.provider or saved_provider())
    try:
        response = service.ask(body.question, body.session_id, client)
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    finally:
        reset(token)
    return response.model_dump()


@app.get("/api/traces")
def traces() -> dict:
    durable = list(reversed(tracer.recent(100)))
    return {"traces": service.traces.all(), "spans": durable}
