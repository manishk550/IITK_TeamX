from __future__ import annotations
from typing import Any, Literal, Optional

"""Shared request and response contracts."""



from pydantic import BaseModel, Field


QuestionType = Literal[
    "fact_lookup",
    "calculation",
    "ratio",
    "comparison",
    "trend",
    "multi_document",
    "qualitative",
    "refusal",
]


class Evidence(BaseModel):
    document_id: str
    company: str
    fiscal_period: str
    page: int
    section: str
    excerpt: str
    score: float = 0.0


class Citation(BaseModel):
    document_id: str
    company: str
    fiscal_period: str
    page: int
    section: str


class ToolCallRecord(BaseModel):
    tool: str
    arguments: dict[str, Any]
    status: Literal["ok", "error", "retried"]
    detail: str = ""


class CopilotResponse(BaseModel):
    answer: str
    behavior: Literal["answer", "refuse"]
    citations: list[Citation] = Field(default_factory=list)
    calculation: Optional[str] = None
    confidence: Literal["high", "medium", "low"] = "medium"
    refusal_reason: Optional[str] = None
    caveats: list[str] = Field(default_factory=list)
    trace_id: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    latency_ms: float
    token_estimate: int
    termination_reason: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    session_id: str = "default"
