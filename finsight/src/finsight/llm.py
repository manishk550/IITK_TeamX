"""OpenAI-compatible client for the hosted <=8B chat and embeddings endpoints."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    embedding_model: str

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def load_config() -> LLMConfig:
    return LLMConfig(
        base_url=os.getenv("FINSIGHT_BASE_URL", "").rstrip("/"),
        api_key=os.getenv("FINSIGHT_API_KEY", ""),
        model=os.getenv("FINSIGHT_MODEL", ""),
        embedding_model=os.getenv("FINSIGHT_EMBEDDING_MODEL", ""),
    )


def chat(messages: list[dict], temperature: float = 0.0, timeout: int = 60) -> dict:
    """Call the hosted chat-completions endpoint and return content plus usage."""
    config = load_config()
    if not config.enabled:
        raise RuntimeError("Hosted model is not configured. Set FINSIGHT_BASE_URL, FINSIGHT_API_KEY, and FINSIGHT_MODEL.")
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Hosted model returned HTTP {exc.code}: {detail}") from exc
    choice = body["choices"][0]["message"]["content"]
    usage = body.get("usage", {})
    return {"content": choice, "usage": usage, "model": config.model}


def embed(texts: list[str], timeout: int = 60) -> list[list[float]] | None:
    """Return hosted embeddings, or None when the embedding endpoint is not configured."""
    config = load_config()
    if not (config.enabled and config.embedding_model):
        return None
    payload = {"model": config.embedding_model, "input": texts}
    request = urllib.request.Request(
        f"{config.base_url}/embeddings",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode())
    rows = sorted(body["data"], key=lambda item: item["index"])
    return [row["embedding"] for row in rows]
