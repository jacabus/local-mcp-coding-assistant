"""Unit tests for bounded sync MCP server helpers (no live Ollama)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import server  # noqa: E402


def test_enforce_input_limit_rejects_oversized_input() -> None:
    limit = server.resolve_max_input_chars()
    oversized = "x" * (limit + 1)
    with pytest.raises(ValueError) as exc_info:
        server.enforce_input_limit(oversized, "code")
    message = str(exc_info.value)
    assert "max_input_chars" in message
    assert str(limit) in message
    assert str(limit + 1) in message


def test_enforce_input_limit_accepts_bounded_input() -> None:
    cleaned = server.enforce_input_limit("  def ok():\n    return 1  ", "code")
    assert cleaned.startswith("def ok()")


def test_review_prompt_requires_severity_ranking() -> None:
    prompt = server.build_review_prompt("def f():\n    pass", None)
    assert "severity" in prompt.lower() or "Critical" in prompt
    assert "8 bullets" in prompt
    assert "symbol" in prompt.lower()


def test_test_ideas_prompt_requires_concrete_cases() -> None:
    prompt = server.build_test_ideas_prompt("def f():\n    pass", None)
    assert "8 cases" in prompt
    assert "exact input" in prompt.lower() or "exact input values" in prompt.lower()


def test_config_routes_all_tools_to_installed_models() -> None:
    """deepseek-r1 is not installed; routing must not point at it."""
    config = server.load_config()
    allowed = {"qwen2.5-coder:7b", "qwen3:8b", "llama3.2:latest", "llama3.2"}
    for tool_name in (
        "local_code_review",
        "local_test_ideas",
        "local_log_summary",
        "local_alternative_solution",
    ):
        model = server.resolve_model(tool_name, config)
        assert model in allowed, f"{tool_name} resolved to unexpected model {model}"
        assert "deepseek" not in model.lower()


def test_top_level_model_present_for_fallback() -> None:
    config = server.load_config()
    assert config.get("model") == "qwen2.5-coder:7b"


def test_call_ollama_payload_includes_think_and_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": "ok review"}}

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, json: dict) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(server.httpx, "Client", FakeClient)
    result = server.call_ollama("prompt", "qwen3:8b", 50.0, server.load_config())
    assert result == "ok review"
    assert captured["json"]["think"] is False
    assert captured["json"]["options"]["num_predict"] == 400
    assert captured["json"]["options"]["temperature"] == 0.2
