"""OpenTelemetry-compatible local trace exporter.

Spans are persisted as JSON Lines so the trace dashboard survives a process
restart on the local machine. A Langfuse exporter can replace this writer
without changing the span schema.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACE_PATH = ROOT / "data" / "traces" / "traces.jsonl"


class Tracer:
    def __init__(self, path: Path = TRACE_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def start(self, name: str, attributes: dict | None = None) -> dict:
        return {
            "trace_id": uuid.uuid4().hex,
            "span_id": uuid.uuid4().hex,
            "name": name,
            "start_time": time.time(),
            "attributes": attributes or {},
            "events": [],
        }

    def event(self, span: dict, name: str, attributes: dict | None = None) -> None:
        span["events"].append({"name": name, "time": time.time(), "attributes": attributes or {}})

    def end(self, span: dict, status: str = "ok") -> dict:
        span["end_time"] = time.time()
        span["duration_ms"] = round((span["end_time"] - span["start_time"]) * 1000, 3)
        span["status"] = status
        record = dict(span)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def recent(self, limit: int = 100) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:] if line.strip()]


tracer = Tracer()
