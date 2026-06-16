"""Verify Ollama is reachable and qwen3 returns a review response."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "config.json"
SAMPLE_CODE = """def divide(a, b):
    return a / b"""


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        fail(f"config not found at {CONFIG_PATH}")
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    config = load_config()
    base_url = config.get("ollama_base_url", "").rstrip("/")
    model = config.get("model", "")
    timeout = float(config.get("timeout_seconds", 120))

    if not base_url:
        fail("ollama_base_url is not set in config/config.json")
    if not model:
        fail("model is not set in config/config.json")

    try:
        with httpx.Client(timeout=timeout) as client:
            tags_response = client.get(f"{base_url}/api/tags")
            tags_response.raise_for_status()
            tags = tags_response.json().get("models", [])
            model_names = [entry.get("name", "") for entry in tags]
            if model not in model_names:
                fail(
                    f"model '{model}' not found in Ollama; installed models: {', '.join(model_names)}"
                )

            chat_response = client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Review this Python code briefly for bugs and security issues:\n"
                                f"```\n{SAMPLE_CODE}\n```"
                            ),
                        }
                    ],
                    "stream": False,
                },
            )
            chat_response.raise_for_status()
            content = chat_response.json().get("message", {}).get("content", "")
    except httpx.HTTPError as exc:
        fail(f"Ollama request failed: {exc}")
    except OSError as exc:
        fail(f"Ollama unreachable at {base_url}: {exc}")

    if not isinstance(content, str) or not content.strip():
        fail("Ollama returned an empty response")

    print("PASS")
    print(f"Ollama URL: {base_url}")
    print(f"Model: {model}")
    print("Response preview:")
    preview = content.strip().replace("\n", " ")
    print(preview[:300] + ("..." if len(preview) > 300 else ""))


if __name__ == "__main__":
    main()
