"""Offline quality-contract tests (no live Ollama)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUALITY_DIR = REPO_ROOT / "tests" / "fixtures" / "quality"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import server  # noqa: E402
from review_quality_ab import score_response  # noqa: E402


def test_review_prompt_forbids_invented_protocols() -> None:
    prompt = server.build_review_prompt("def f():\n    pass", None)
    lower = prompt.lower()
    assert "never invent" in lower or "do not invent" in lower or "never invent protocols" in lower
    assert "tls" in lower
    assert "symbol" in lower
    assert "8 bullets" in prompt
    assert "nothing serious" in lower


def test_quality_fixtures_exist_and_match_expectations() -> None:
    expectations = json.loads((QUALITY_DIR / "expectations.json").read_text(encoding="utf-8"))
    assert len(expectations["fixtures"]) >= 3
    for fixture in expectations["fixtures"]:
        path = QUALITY_DIR / fixture["path"]
        assert path.is_file(), f"missing {path}"
        assert path.read_text(encoding="utf-8").strip()


def test_score_flags_invented_tls_critical_on_clean_fixture() -> None:
    fixture = {
        "required_any": [],
        "forbidden_substrings": ["TLS", "SSL", "localhost"],
    }
    bad = "- Critical: Missing TLS on localhost connection\n- High: add HTTPS"
    scored = score_response(fixture, bad)
    assert scored["invented_critical"] is True
    assert scored["ok"] is False


def test_score_allows_nothing_serious_on_clean_fixture() -> None:
    fixture = {
        "required_any": [],
        "forbidden_substrings": ["TLS", "SSL", "localhost"],
    }
    good = "Nothing serious. Pure clamp() with clear bounds; no findings."
    scored = score_response(fixture, good)
    assert scored["ok"] is True
    assert scored["invented_critical"] is False


def test_score_requires_zero_division_on_divide_fixture() -> None:
    fixture = {
        "required_any": ["zero", "ZeroDivision", "division by zero", "divide by"],
        "forbidden_substrings": ["TLS", "SSL"],
    }
    miss = "- Medium: prefer type hints on divide\n- Low: rename a and b"
    hit = "- Critical: divide() divides by b with no zero check (ZeroDivisionError)"
    assert score_response(fixture, miss)["required_hit"] is False
    assert score_response(fixture, hit)["ok"] is True
