"""MCP server exposing local coding tools via Ollama (bounded sync path)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "config.json"
LOG_PATH = REPO_ROOT / "logs" / "requests.ndjson"

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT_SECONDS = 50.0
DEFAULT_MAX_INPUT_CHARS = 5000
DEFAULT_NUM_PREDICT = 400
DEFAULT_TEMPERATURE = 0.2

REVIEW_PROMPT = """You are a code reviewer. Reply in plain text only.

Rules:
- Rank findings by severity (Critical, High, Medium, Low).
- At most 8 bullets. No preamble, no closing summary.
- Cite exact symbol names from the code.
- Do not invent dependencies, frameworks, or TLS/SSL issues for plain http://localhost unless TLS is actually present.
- Do not modify or rewrite the code.

{context_block}Code to review:
```
{code}
```"""

TEST_IDEAS_PROMPT = """You are a test engineer. Suggest concrete test cases in plain text.

Rules:
- At most 8 cases. Rank by importance.
- For each case: what to test, exact input values, expected behavior, why it matters.
- Cover happy path, edge cases, and failure modes.
- Cite exact symbol names. Do not invent APIs that are not in the code.
- Do not modify the code.

{context_block}Code to test:
```
{code}
```"""

LOG_SUMMARY_PROMPT = """You are a senior engineer reading a log or error output. Be brief and direct.

Return exactly four things:
1. What happened (one sentence)
2. The key error, quoted exactly from the log (or "none" if no error)
3. Likely cause
4. What to investigate next

Do not invent errors that are not in the log.

{context_block}Log:
{log_text}"""

ALTERNATIVE_SOLUTION_PROMPT = """You are a senior engineer proposing an alternative implementation.

Rules:
- Do not rewrite the full code.
- Propose one different design or algorithm approach.
- Explain trade-offs versus the current implementation in at most 8 bullets.
- Cite exact symbol names from the code. Do not invent dependencies.

{context_block}Current implementation:
```
{code}
```"""


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_model(tool_name: str, config: dict[str, Any] | None = None) -> str:
    cfg = config if config is not None else load_config()
    routing = cfg.get("routing", {})
    entry = routing.get(tool_name, {})
    if isinstance(entry, dict):
        return str(entry.get("model", cfg.get("model", DEFAULT_MODEL)))
    if entry:
        return str(entry)
    return str(cfg.get("model", DEFAULT_MODEL))


def resolve_timeout(tool_name: str, config: dict[str, Any] | None = None) -> float:
    cfg = config if config is not None else load_config()
    routing = cfg.get("routing", {})
    entry = routing.get(tool_name, {})
    if isinstance(entry, dict):
        return float(entry.get("timeout_seconds", cfg.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    return float(cfg.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))


def resolve_max_input_chars(config: dict[str, Any] | None = None) -> int:
    cfg = config if config is not None else load_config()
    return int(cfg.get("max_input_chars", DEFAULT_MAX_INPUT_CHARS))


def resolve_num_predict(config: dict[str, Any] | None = None) -> int:
    cfg = config if config is not None else load_config()
    return int(cfg.get("num_predict", DEFAULT_NUM_PREDICT))


def resolve_temperature(config: dict[str, Any] | None = None) -> float:
    cfg = config if config is not None else load_config()
    return float(cfg.get("temperature", DEFAULT_TEMPERATURE))


def resolve_think(config: dict[str, Any] | None = None) -> bool:
    cfg = config if config is not None else load_config()
    return bool(cfg.get("think", False))


def enforce_input_limit(text: str, label: str, config: dict[str, Any] | None = None) -> str:
    cleaned = text.strip()
    limit = resolve_max_input_chars(config)
    size = len(cleaned)
    if size > limit:
        raise ValueError(
            f"{label} is {size} chars; max_input_chars is {limit}. "
            "Trim the snippet and retry."
        )
    return cleaned


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


def append_request_log(event: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def call_ollama(
    prompt: str,
    model: str,
    timeout: float,
    config: dict[str, Any] | None = None,
) -> str:
    cfg = config if config is not None else load_config()
    base_url = str(cfg["ollama_base_url"]).rstrip("/")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": resolve_think(cfg),
        "options": {
            "num_predict": resolve_num_predict(cfg),
            "temperature": resolve_temperature(cfg),
        },
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


def run_tool(
    tool_name: str,
    input_text: str,
    prompt: str,
) -> str:
    config = load_config()
    model = resolve_model(tool_name, config)
    timeout = resolve_timeout(tool_name, config)
    input_chars = len(input_text)
    started = time.perf_counter()
    ok = False
    error: str | None = None
    try:
        result = call_ollama(prompt, model, timeout, config)
        ok = True
        return f"[{model}]\n\n" + result
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        append_request_log(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "tool": tool_name,
                "model": model,
                "input_chars": input_chars,
                "elapsed_ms": elapsed_ms,
                "ok": ok,
                "error": error,
            }
        )


mcp = FastMCP("local-mcp-coding-assistant")


@mcp.tool(name="local_code_review")
def local_code_review(code: str, context: str | None = None) -> str:
    """Review code using a local model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    cleaned = enforce_input_limit(code, "code")
    return run_tool(
        "local_code_review",
        cleaned,
        build_review_prompt(cleaned, context),
    )


@mcp.tool(name="local_test_ideas")
def local_test_ideas(code: str, context: str | None = None) -> str:
    """Suggest test cases for code using a local model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    cleaned = enforce_input_limit(code, "code")
    return run_tool(
        "local_test_ideas",
        cleaned,
        build_test_ideas_prompt(cleaned, context),
    )


@mcp.tool(name="local_log_summary")
def local_log_summary(log_text: str, context: str | None = None) -> str:
    """Summarise terminal or test log output using a local model via Ollama."""
    if not log_text or not log_text.strip():
        raise ValueError("log_text is required")
    cleaned = enforce_input_limit(log_text, "log_text")
    return run_tool(
        "local_log_summary",
        cleaned,
        build_log_summary_prompt(cleaned, context),
    )


@mcp.tool(name="local_alternative_solution")
def local_alternative_solution(code: str, context: str | None = None) -> str:
    """Suggest an alternative implementation approach using a local model via Ollama."""
    if not code or not code.strip():
        raise ValueError("code is required")
    cleaned = enforce_input_limit(code, "code")
    return run_tool(
        "local_alternative_solution",
        cleaned,
        build_alternative_solution_prompt(cleaned, context),
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
