"""OpenTelemetry tracing with a local JSONL exporter.

Spans are real OpenTelemetry spans. The exporter writes them to
data/traces/traces.jsonl so the /traces dashboard survives a process restart.
A LangSmith or Langfuse exporter can be added beside this one when a key exists.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode


ROOT = Path(__file__).resolve().parents[2]
TRACE_PATH = ROOT / "data" / "traces" / "traces.jsonl"


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path: Path = TRACE_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def export(self, spans) -> SpanExportResult:
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                for span in spans:
                    handle.write(json.dumps(_record(span), ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def _record(span) -> dict:
    start = span.start_time / 1_000_000_000
    end = (span.end_time or span.start_time) / 1_000_000_000
    status = "error" if span.status.status_code == StatusCode.ERROR else "ok"
    return {
        "trace_id": format(span.context.trace_id, "032x"),
        "span_id": format(span.context.span_id, "016x"),
        "name": span.name,
        "start_time": start,
        "end_time": end,
        "duration_ms": round((end - start) * 1000, 3),
        "status": status,
        "attributes": dict(span.attributes or {}),
        "events": [
            {"name": event.name, "time": event.timestamp / 1_000_000_000, "attributes": dict(event.attributes or {})}
            for event in span.events
        ],
    }


def _provider() -> TracerProvider:
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        return current
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter()))
    trace.set_tracer_provider(provider)
    return provider


_provider()
_otel = trace.get_tracer("finsight")


class Tracer:
    """Small wrapper so callers keep start / event / end while spans stay in the SDK."""

    def start(self, name: str, attributes: dict | None = None):
        safe = {key: value for key, value in (attributes or {}).items() if isinstance(value, (str, bool, int, float))}
        return _otel.start_span(name, attributes=safe, start_time=time.time_ns())

    def event(self, span, name: str, attributes: dict | None = None) -> None:
        safe = {key: value for key, value in (attributes or {}).items() if isinstance(value, (str, bool, int, float))}
        span.add_event(name, safe)

    def end(self, span, status: str = "ok"):
        if status != "ok":
            span.set_status(Status(StatusCode.ERROR, status))
        span.end()
        return span

    def recent(self, limit: int = 100) -> list[dict]:
        if not TRACE_PATH.exists():
            return []
        lines = TRACE_PATH.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:] if line.strip()]


tracer = Tracer()
