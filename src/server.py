"""Minimal MCP server exposing local_code_review via Ollama."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "config.json"

REVIEW_PROMPT = """You are a code reviewer. Review the code below and respond in plain text.

Cover:
- bugs
- logic issues
- security concerns
- simplification opportunities
- missing tests

Be concise and specific. Do not modify the code.

{context_block}Code to review:
```
{code}
```"""


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_review_prompt(code: str, context: str | None) -> str:
    context_block = ""
    if context and context.strip():
        context_block = f"Additional context:\n{context.strip()}\n\n"
    return REVIEW_PROMPT.format(context_block=context_block, code=code)


def call_ollama(code: str, context: str | None) -> str:
    config = load_config()
    base_url = config["ollama_base_url"].rstrip("/")
    model = config["model"]
    timeout = float(config.get("timeout_seconds", 120))

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": build_review_prompt(code, context),
            }
        ],
        "stream": False,
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{base_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

    message = data.get("message", {})
    content = message.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama returned an empty review response")
    return content.strip()


mcp = FastMCP("local-mcp-coding-assistant")


@mcp.tool(name="local_code_review")
def local_code_review(code: str, context: str | None = None) -> str:
    """Review code using the local qwen3 model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    return call_ollama(code.strip(), context)


if __name__ == "__main__":
    mcp.run(transport="stdio")
