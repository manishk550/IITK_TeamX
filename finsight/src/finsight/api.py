"""FastAPI application for the FinSight copilot."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from finsight.schemas import ChatRequest
from finsight.service import CopilotService


app = FastAPI(title="FinSight Financial Report Copilot", version="1.0.0")
service = CopilotService()


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path(__file__).with_name("static") / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": service.copilot.model_name}


@app.post("/api/ask")
def ask(body: ChatRequest, request: Request) -> dict:
    client = request.client.host if request.client else "local"
    try:
        response = service.ask(body.question, body.session_id, client)
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return response.model_dump()


@app.get("/api/traces")
def traces() -> dict:
    return {"traces": service.traces.all()}
