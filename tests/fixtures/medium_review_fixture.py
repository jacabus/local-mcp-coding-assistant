"""Helpers for a downstream consumer smoke test."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_GATEWAY_URL = "http://localhost:5930"


class ConsumerSmokeError(RuntimeError):
    """Raised when the downstream smoke path fails."""


@dataclass(frozen=True)
class ConsumerSmokeSummary:
    """Summary of a successful downstream smoke run."""

    chat_length: int
    embedding_length: int
    generate_length: int


def run_consumer_smoke(base_url: str = DEFAULT_GATEWAY_URL, timeout_seconds: float = 30.0) -> ConsumerSmokeSummary:
    """Verify that a downstream application can use the gateway contract."""

    health = _request_json(base_url, "GET", "/health", None, timeout_seconds)
    if health.get("status") != "ok":
        error = health.get("error", "unknown_error")
        raise ConsumerSmokeError(f"Gateway health check failed: {error}")

    ollama = health.get("ollama")
    if not isinstance(ollama, dict) or not ollama.get("reachable"):
        raise ConsumerSmokeError("Gateway health check failed: Ollama is not reachable through the gateway")

    chat_payload = {"message": "Reply with one short sentence confirming the gateway consumer smoke test worked."}
    chat = _request_json(base_url, "POST", "/chat", chat_payload, timeout_seconds)
    response_text = chat.get("response")
    if not isinstance(response_text, str) or not response_text.strip():
        raise ConsumerSmokeError("Gateway chat response did not include non-empty text")

    embed_payload = {"text": "Gateway consumer smoke test embedding request"}
    embed = _request_json(base_url, "POST", "/embed", embed_payload, timeout_seconds)
    vector = embed.get("embedding")
    if not isinstance(vector, list) or not vector:
        raise ConsumerSmokeError("Gateway embed response did not include a vector")
    if not all(isinstance(value, (int, float)) for value in vector):
        raise ConsumerSmokeError("Gateway embed response included non-numeric values")

    generate_request_id = "consumer-smoke-generate"
    generate_payload = {
        "prompt": "Reply with one short sentence confirming the gateway generate smoke test worked.",
        "request_id": generate_request_id,
    }
    generate = _request_json(base_url, "POST", "/generate", generate_payload, timeout_seconds)
    generated_text = generate.get("text")
    if not isinstance(generated_text, str) or not generated_text.strip():
        raise ConsumerSmokeError("Gateway generate response did not include non-empty text")
    if generate.get("request_id") != generate_request_id:
        raise ConsumerSmokeError("Gateway generate response did not echo the request_id")

    return ConsumerSmokeSummary(
        chat_length=len(response_text.strip()),
        embedding_length=len(vector),
        generate_length=len(generated_text.strip()),
    )


def _request_json(
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_text = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ConsumerSmokeError(f"Gateway request failed for {path}: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ConsumerSmokeError(
            f"Could not reach local-ai-gateway at {base_url}. Start the gateway on port 5930 before running this smoke test."
        ) from exc

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ConsumerSmokeError(f"Gateway returned invalid JSON for {path}") from exc
    if not isinstance(data, dict):
        raise ConsumerSmokeError(f"Gateway returned an unexpected payload type for {path}")
    return data
