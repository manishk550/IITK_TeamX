"""OpenAI-compatible client for the course Qwen3-8B endpoint.

Groups 046–065 use https://103.42.50.41:1034/v1 and certs/vm04-ca.crt.
The endpoint does not serve embeddings. Output is capped at 1,024 tokens.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    embedding_model: str

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def _load_dotenv() -> None:
    """Load finsight/.env without overriding variables already set in the shell."""
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config() -> LLMConfig:
    _load_dotenv()
    api_key = os.getenv("FINSIGHT_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if api_key.startswith("replace-"):
        api_key = ""
    base_url = (os.getenv("FINSIGHT_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").rstrip("/")
    if "your-course-endpoint" in base_url:
        base_url = ""
    model = os.getenv("FINSIGHT_MODEL") or os.getenv("OPENAI_MODEL") or ""
    if model == "hosted-8b-compatible" and not (base_url and api_key):
        model = ""
    return LLMConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        embedding_model=os.getenv("FINSIGHT_EMBEDDING_MODEL", ""),
    )


def _ca_file() -> str:
    _load_dotenv()
    configured = os.getenv("FINSIGHT_CA_CERT", "")
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return str(path)
    default = Path(__file__).resolve().parents[2] / "certs" / "vm04-ca.crt"
    return str(default) if default.exists() else ""


def _ssl_context() -> ssl.SSLContext:
    ca_file = _ca_file()
    if ca_file:
        return ssl.create_default_context(cafile=ca_file)
    return ssl.create_default_context()


def _output_limit(max_tokens: int | None) -> int:
    raw = max_tokens if max_tokens is not None else int(os.getenv("FINSIGHT_MAX_TOKENS", "1024"))
    return max(1, min(raw, 1024))


def _answer_text(message: dict) -> str:
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return re.sub(r"<think>.*?</think>", "", str(content), flags=re.S).strip()


def chat(messages: list[dict], temperature: float = 0.0, timeout: int = 120, json_mode: bool = True, max_tokens: int | None = None, attempts: int = 5) -> dict:
    """Call the course chat-completions endpoint and return content plus usage."""
    config = load_config()
    if not config.enabled:
        raise RuntimeError("Hosted model is not configured. Set FINSIGHT_BASE_URL, FINSIGHT_API_KEY, and FINSIGHT_MODEL.")
    limit = _output_limit(max_tokens)
    use_json = json_mode
    disable_thinking = True
    delay = 2
    context = _ssl_context()
    body = None
    for attempt in range(max(1, attempts)):
        payload = {"model": config.model, "messages": messages, "temperature": temperature, "max_tokens": limit}
        if use_json:
            payload["response_format"] = {"type": "json_object"}
        if disable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        request = urllib.request.Request(
            f"{config.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                body = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            if exc.code in {400, 404, 422} and (use_json or disable_thinking):
                use_json = False
                disable_thinking = False
                continue
            if exc.code in {429, 502, 503} and attempt < attempts - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Hosted model returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            if attempt < attempts - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Hosted model connection failed after retries: {getattr(exc, 'reason', exc)}") from exc
    else:
        raise RuntimeError("Hosted model did not respond after retries.")
    message = body["choices"][0]["message"]
    return {"content": _answer_text(message), "usage": body.get("usage", {}), "model": config.model}


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
    with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
        body = json.loads(response.read().decode())
    rows = sorted(body["data"], key=lambda item: item["index"])
    return [row["embedding"] for row in rows]
