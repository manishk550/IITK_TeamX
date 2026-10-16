"""Application service, trace log, cache, and rate limiting."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque

from finsight.agent import FinancialCopilot, SessionStore
from finsight.retrieval import HybridRetriever
from finsight.schemas import CopilotResponse
from finsight.tools import ToolRegistry


class RateLimiter:
    def __init__(self, limit: int = 30, window_seconds: int = 60):
        self.limit = limit
        self.window = window_seconds
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] > self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


class ResponseCache:
    def __init__(self, max_items: int = 500):
        self.max_items = max_items
        self._items = {}
        self._order = deque()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            return self._items.get(key)

    def put(self, key: str, value: CopilotResponse) -> None:
        with self._lock:
            if key not in self._items:
                self._order.append(key)
            self._items[key] = value
            while len(self._order) > self.max_items:
                self._items.pop(self._order.popleft(), None)


class TraceStore:
    def __init__(self):
        self._traces = deque(maxlen=1000)
        self._lock = threading.Lock()

    def add(self, response: CopilotResponse, question: str) -> None:
        with self._lock:
            self._traces.append({"question": question, **response.model_dump()})

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._traces)


class CopilotService:
    def __init__(self):
        retriever = HybridRetriever(strategy=os.getenv("FINSIGHT_CHUNKING", "section"))
        self.copilot = FinancialCopilot(
            ToolRegistry(retriever),
            SessionStore(),
            model_name=os.getenv("FINSIGHT_MODEL", "hosted-8b-compatible"),
        )
        self.cache = ResponseCache()
        self.limiter = RateLimiter(int(os.getenv("FINSIGHT_RATE_LIMIT", "30")))
        self.traces = TraceStore()

    def ask(self, question: str, session_id: str, client_key: str) -> CopilotResponse:
        if not self.limiter.allow(client_key):
            raise PermissionError("Rate limit exceeded. Wait one minute and try again.")
        cache_key = hashlib.sha256(f"{session_id}\n{question}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        response = self.copilot.answer(question, session_id)
        self.cache.put(cache_key, response)
        self.traces.add(response, question)
        return response
