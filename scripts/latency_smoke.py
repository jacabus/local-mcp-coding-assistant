#!/usr/bin/env python3
"""Timed live smoke: tiny + medium reviews must finish under the Cursor budget."""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "medium_review_fixture.py"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from server import (  # noqa: E402
    build_review_prompt,
    call_ollama,
    load_config,
    resolve_model,
    resolve_timeout,
)

PASS_BAR_SECONDS = 45.0
DIVIDE_SNIPPET = """def divide(a, b):
    return a / b"""


def run_case(label: str, code: str) -> float:
    config = load_config()
    model = resolve_model("local_code_review", config)
    timeout = resolve_timeout("local_code_review", config)
    prompt = build_review_prompt(code, None)
    started = time.perf_counter()
    content = call_ollama(prompt, model, timeout, config)
    elapsed = time.perf_counter() - started
    preview = content.replace("\n", " ").strip()
    if not preview:
        raise RuntimeError(f"{label}: empty response")
    print(f"{label}: elapsed_sec={elapsed:.2f} chars={len(content)} preview={preview[:200]}")
    if elapsed > PASS_BAR_SECONDS:
        raise RuntimeError(
            f"{label}: elapsed {elapsed:.2f}s exceeds pass bar {PASS_BAR_SECONDS:.0f}s"
        )
    return elapsed


def main() -> int:
    if not FIXTURE_PATH.is_file():
        print(f"FAIL: missing fixture {FIXTURE_PATH}")
        return 1
    medium = FIXTURE_PATH.read_text(encoding="utf-8")
    try:
        run_case("tiny_divide", DIVIDE_SNIPPET)
        run_case("medium_fixture", medium)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"PASS: both cases under {PASS_BAR_SECONDS:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
