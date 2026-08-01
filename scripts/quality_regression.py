#!/usr/bin/env python3
"""Live quality regression for local_code_review.

Fails if clean / no-HTTP fixtures receive invented TLS / localhost Criticals,
or if the divide fixture misses zero-division.
Respects Ollama gate (wait while llama3.2/chat models are loaded).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
QUALITY_DIR = REPO_ROOT / "tests" / "fixtures" / "quality"
EXPECTATIONS_PATH = QUALITY_DIR / "expectations.json"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from server import (  # noqa: E402
    build_review_prompt,
    call_ollama,
    load_config,
    resolve_model,
    resolve_timeout,
)

# Reuse scoring + gate from A/B script
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from review_quality_ab import (  # noqa: E402
    score_response,
    wait_until_ollama_free,
)

PASS_BAR_SECONDS = 45.0


def main() -> int:
    config = load_config()
    base_url = str(config["ollama_base_url"])
    model = resolve_model("local_code_review", config)
    timeout = resolve_timeout("local_code_review", config)
    expectations = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))

    print(f"regression model={model}")
    wait_until_ollama_free(base_url, poll_seconds=45.0, max_wait_seconds=900.0)

    failures: list[str] = []
    for fixture in expectations["fixtures"]:
        code = (QUALITY_DIR / fixture["path"]).read_text(encoding="utf-8")
        prompt = build_review_prompt(code, None)
        started = time.perf_counter()
        content = call_ollama(prompt, model, timeout, config)
        elapsed = time.perf_counter() - started
        scored = score_response(fixture, content)
        preview = content.replace("\n", " ").strip()[:200]
        print(
            f"{fixture['id']}: ok={scored['ok']} elapsed={elapsed:.2f}s "
            f"forbidden={scored['forbidden_hits']} preview={preview}"
        )
        if elapsed > PASS_BAR_SECONDS:
            failures.append(f"{fixture['id']}: latency {elapsed:.2f}s > {PASS_BAR_SECONDS:.0f}s")
        if not scored["ok"]:
            failures.append(
                f"{fixture['id']}: required_hit={scored['required_hit']} "
                f"forbidden={scored['forbidden_hits']} invented_critical={scored['invented_critical']}"
            )

    if failures:
        print("FAIL:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("PASS: quality regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
