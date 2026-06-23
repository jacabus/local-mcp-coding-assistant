"""MCP server exposing local_code_review and local_test_ideas via Ollama."""

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

TEST_IDEAS_PROMPT = """You are a test engineer. Suggest specific test cases for the code below and respond in plain text.

For each test case, include:
- what to test
- the input to use
- the expected output or behavior
- why this case matters

Cover happy paths, edge cases, and failure modes. Be concrete — use actual values, not vague descriptions. Do not modify the code.

{context_block}Code to test:
```
{code}
```"""


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_context_block(context: str | None) -> str:
    if context and context.strip():
        return f"Additional context:\n{context.strip()}\n\n"
    return ""


def build_review_prompt(code: str, context: str | None) -> str:
    return REVIEW_PROMPT.format(context_block=build_context_block(context), code=code)


def build_test_ideas_prompt(code: str, context: str | None) -> str:
    return TEST_IDEAS_PROMPT.format(context_block=build_context_block(context), code=code)


def call_ollama(prompt: str) -> str:
    config = load_config()
    base_url = config["ollama_base_url"].rstrip("/")
    model = config["model"]
    timeout = float(config.get("timeout_seconds", 120))

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{base_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

    message = data.get("message", {})
    content = message.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama returned an empty response")
    return content.strip()


mcp = FastMCP("local-mcp-coding-assistant")


@mcp.tool(name="local_code_review")
def local_code_review(code: str, context: str | None = None) -> str:
    """Review code using the local qwen3 model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    return call_ollama(build_review_prompt(code.strip(), context))


@mcp.tool(name="local_test_ideas")
def local_test_ideas(code: str, context: str | None = None) -> str:
    """Suggest test cases for code using the local qwen3 model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    return call_ollama(build_test_ideas_prompt(code.strip(), context))


if __name__ == "__main__":
    mcp.run(transport="stdio")
