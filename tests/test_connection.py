"""Verify Ollama is reachable and the review model returns a response."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from server import (  # noqa: E402
    build_review_prompt,
    call_ollama,
    load_config,
    resolve_model,
    resolve_timeout,
)

SAMPLE_CODE = """def divide(a, b):
    return a / b"""


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> None:
    config = load_config()
    base_url = str(config.get("ollama_base_url", "")).rstrip("/")
    model = resolve_model("local_code_review", config)
    timeout = resolve_timeout("local_code_review", config)

    if not base_url:
        fail("ollama_base_url is not set in config/config.json")
    if not model:
        fail("model could not be resolved for local_code_review")

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

        prompt = build_review_prompt(SAMPLE_CODE, None)
        started = time.perf_counter()
        content = call_ollama(prompt, model, timeout, config)
        elapsed = time.perf_counter() - started
    except httpx.HTTPError as exc:
        fail(f"Ollama request failed: {exc}")
    except OSError as exc:
        fail(f"Ollama unreachable at {base_url}: {exc}")
    except Exception as exc:
        fail(str(exc))

    if not isinstance(content, str) or not content.strip():
        fail("Ollama returned an empty response")

    print("PASS")
    print(f"Ollama URL: {base_url}")
    print(f"Model: {model}")
    print(f"Elapsed seconds: {elapsed:.2f}")
    print("Response preview:")
    preview = content.strip().replace("\n", " ")
    print(preview[:300] + ("..." if len(preview) > 300 else ""))


if __name__ == "__main__":
    main()
