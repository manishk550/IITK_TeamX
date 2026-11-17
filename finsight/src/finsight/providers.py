"""Runtime switch between the course API key and the local FastAPI agent."""

from __future__ import annotations

import contextvars
import os
import threading

PROVIDERS = ("local", "course")



def _default_provider() -> str:
    """Startup provider: Qwen3-8B via the course key unless FINSIGHT_DEFAULT_PROVIDER=local."""
    name = os.getenv("FINSIGHT_DEFAULT_PROVIDER", "course").strip().lower()
    return name if name in PROVIDERS else "course"


_saved = _default_provider()
_lock = threading.Lock()
_active = contextvars.ContextVar("finsight_provider", default=_saved)


def saved_provider() -> str:
    with _lock:
        return _saved


def set_saved_provider(name: str) -> str:
    if name not in PROVIDERS:
        raise ValueError("provider must be local or course")
    global _saved
    with _lock:
        _saved = name
    return name


def current_provider() -> str:
    return _active.get()


def activate(name: str | None):
    chosen = name or saved_provider()
    if chosen not in PROVIDERS:
        chosen = "course"
    return _active.set(chosen)


def reset(token) -> None:
    _active.reset(token)


def describe(name: str) -> dict:
    if name == "course":
        return {
            "provider": "course",
            "label": "Course API",
            "model": "Qwen/Qwen3-8B",
            "detail": "Uses the group API key. The FastAPI agent still retrieves and checks the figures.",
        }
    return {
        "provider": "local",
        "label": "FastAPI",
        "model": "FastAPI local agent",
        "detail": "The original FastAPI planner, tools, and critic. No call to the course model.",
    }
