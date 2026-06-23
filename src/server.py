"""MCP server exposing local_code_review, local_test_ideas, local_log_summary via Ollama."""

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

Cover happy paths, edge cases, and failure modes. Be concrete -- use actual values, not vague descriptions. Do not modify the code.

{context_block}Code to test:
```
{code}
```"""

LOG_SUMMARY_PROMPT = """You are a senior engineer reading a log or error output. Be brief and direct.

Return exactly four things:
1. What happened (one sentence)
2. The key error, quoted exactly from the log
3. Likely cause
4. What to investigate next

{context_block}Log:
{log_text}"""

ALTERNATIVE_SOLUTION_PROMPT = """You are a senior engineer proposing an alternative implementation. Do not rewrite the code. Propose a different design or algorithm approach and explain the trade-offs versus the current implementation. Be specific and concrete.

{context_block}Current implementation:
```
{code}
```"""


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_model(tool_name: str) -> str:
    config = load_config()
    routing = config.get("routing", {})
    entry = routing.get(tool_name, {})
    if isinstance(entry, dict):
        return entry.get("model", config.get("model", "qwen3:8b"))
    return entry or config.get("model", "qwen3:8b")


def resolve_timeout(tool_name: str) -> float:
    config = load_config()
    routing = config.get("routing", {})
    entry = routing.get(tool_name, {})
    if isinstance(entry, dict):
        return float(entry.get("timeout_seconds", config.get("timeout_seconds", 120)))
    return float(config.get("timeout_seconds", 120))


def build_context_block(context: str | None) -> str:
    if context and context.strip():
        return f"Additional context:\n{context.strip()}\n\n"
    return ""


def build_review_prompt(code: str, context: str | None) -> str:
    return REVIEW_PROMPT.format(context_block=build_context_block(context), code=code)


def build_test_ideas_prompt(code: str, context: str | None) -> str:
    return TEST_IDEAS_PROMPT.format(context_block=build_context_block(context), code=code)


def build_log_summary_prompt(log_text: str, context: str | None) -> str:
    return LOG_SUMMARY_PROMPT.format(context_block=build_context_block(context), log_text=log_text)


def build_alternative_solution_prompt(code: str, context: str | None) -> str:
    return ALTERNATIVE_SOLUTION_PROMPT.format(context_block=build_context_block(context), code=code)


def call_ollama(prompt: str, model: str, timeout: float = 120) -> str:
    config = load_config()
    base_url = config["ollama_base_url"].rstrip("/")

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
    """Review code using a local model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    model = resolve_model("local_code_review")
    timeout = resolve_timeout("local_code_review")
    result = call_ollama(build_review_prompt(code.strip(), context), model, timeout)
    return f"[{model}]\n\n" + result


@mcp.tool(name="local_test_ideas")
def local_test_ideas(code: str, context: str | None = None) -> str:
    """Suggest test cases for code using a local model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    model = resolve_model("local_test_ideas")
    timeout = resolve_timeout("local_test_ideas")
    result = call_ollama(build_test_ideas_prompt(code.strip(), context), model, timeout)
    return f"[{model}]\n\n" + result


@mcp.tool(name="local_log_summary")
def local_log_summary(log_text: str, context: str | None = None) -> str:
    """Summarise terminal or test log output using a local model via Ollama."""
    if not log_text or not log_text.strip():
        raise ValueError("log_text is required")
    model = resolve_model("local_log_summary")
    timeout = resolve_timeout("local_log_summary")
    result = call_ollama(build_log_summary_prompt(log_text.strip(), context), model, timeout)
    return f"[{model}]\n\n" + result


@mcp.tool(name="local_alternative_solution")
def local_alternative_solution(code: str, context: str | None = None) -> str:
    """Suggest an alternative implementation approach using a local model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    model = resolve_model("local_alternative_solution")
    timeout = resolve_timeout("local_alternative_solution")
    result = call_ollama(build_alternative_solution_prompt(code.strip(), context), model, timeout)
    return f"[{model}]\n\n" + result


if __name__ == "__main__":
    mcp.run(transport="stdio")
