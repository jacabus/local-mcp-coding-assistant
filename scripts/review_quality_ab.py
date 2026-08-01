#!/usr/bin/env python3
"""A/B local_code_review quality: qwen3:8b vs llama3.2:latest on quality fixtures.

Respects the Ollama gate: refuses to run while llama3.2 (or other chat models)
appear busy in /api/ps. Prefer idle embed-only or empty ps.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
QUALITY_DIR = REPO_ROOT / "tests" / "fixtures" / "quality"
EXPECTATIONS_PATH = QUALITY_DIR / "expectations.json"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from server import build_review_prompt, call_ollama, load_config  # noqa: E402

MODELS = ("qwen3:8b", "llama3.2:latest")
IDLE_EMBED_PREFIXES = ("nomic-embed", "mxbai-embed", "all-minilm", "bge-")


def ollama_ps(base_url: str) -> list[dict[str, Any]]:
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{base_url.rstrip('/')}/api/ps")
        response.raise_for_status()
        data = response.json()
    models = data.get("models", [])
    return models if isinstance(models, list) else []


def model_name(entry: dict[str, Any]) -> str:
    return str(entry.get("name") or entry.get("model") or "")


def is_embed_only(name: str) -> bool:
    lower = name.lower()
    return any(lower.startswith(prefix) or prefix in lower for prefix in IDLE_EMBED_PREFIXES)


def is_chat_busy(models: list[dict[str, Any]]) -> bool:
    """True if any non-embed model is loaded (especially llama3.2 / chat models)."""
    for entry in models:
        name = model_name(entry)
        if not name:
            continue
        if is_embed_only(name):
            continue
        # Any non-embed resident model can contend for VRAM; treat as busy.
        return True
    return False


def wait_until_ollama_free(base_url: str, poll_seconds: float, max_wait_seconds: float) -> list[dict[str, Any]]:
    started = time.perf_counter()
    while True:
        models = ollama_ps(base_url)
        names = [model_name(m) for m in models]
        llama_active = any("llama3.2" in n.lower() for n in names)
        busy = is_chat_busy(models)
        print(
            f"ollama_ps: models={names or '[]'} "
            f"llama3.2_active={llama_active} chat_busy={busy}"
        )
        if not busy:
            return models
        elapsed = time.perf_counter() - started
        if elapsed >= max_wait_seconds:
            raise RuntimeError(
                f"Ollama still busy after {elapsed:.0f}s (models={names}). "
                "Refusing to steal Atlas llama3.2 mid-run."
            )
        time.sleep(poll_seconds)


_DENIAL_HINTS = (
    "not present",
    "not applicable",
    "nothing serious",
    "no issues",
    "no findings",
    "do not invent",
    "no tls",
    "no ssl",
    "no http",
    "without tls",
    "without http",
)


def _looks_like_denial(text: str) -> bool:
    lower = text.lower()
    return any(hint in lower for hint in _DENIAL_HINTS) and len(text) < 280


def score_response(fixture: dict[str, Any], text: str) -> dict[str, Any]:
    lower = text.lower()
    required_any = fixture.get("required_any") or []
    required_hit = True
    if required_any:
        required_hit = any(token.lower() in lower for token in required_any)

    forbidden_hits: list[str] = []
    for token in fixture.get("forbidden_substrings") or []:
        if token.lower() in lower:
            forbidden_hits.append(token)

    if fixture.get("forbid_tls_unless_present") and not fixture.get("code_contains_tls"):
        for token in ("TLS", "SSL", "certificate"):
            if token.lower() in lower and token not in forbidden_hits:
                forbidden_hits.append(token)

    # Short "nothing serious / no TLS" replies are allowed even if tokens appear.
    if forbidden_hits and _looks_like_denial(text):
        forbidden_hits = []

    invented_critical = False
    for pattern in (
        r"critical[^\n]{0,120}tls",
        r"critical[^\n]{0,120}ssl",
        r"critical[^\n]{0,120}localhost",
        r"critical[^\n]{0,120}certificate",
        r"critical[^\n]{0,120}https",
        r"high[^\n]{0,120}tls",
        r"high[^\n]{0,120}ssl",
        r"high[^\n]{0,120}localhost",
    ):
        if re.search(pattern, lower):
            invented_critical = True
            break

    return {
        "required_hit": required_hit,
        "forbidden_hits": forbidden_hits,
        "invented_critical": invented_critical,
        "ok": required_hit and not forbidden_hits and not invented_critical,
    }


def run_ab(models: tuple[str, ...] = MODELS) -> dict[str, Any]:
    config = load_config()
    base_url = str(config["ollama_base_url"])
    expectations = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
    fixtures = expectations["fixtures"]

    wait_until_ollama_free(base_url, poll_seconds=45.0, max_wait_seconds=900.0)

    # Force think/num_predict via config already; call_ollama uses config.
    results: dict[str, Any] = {"models": {}, "winner": None, "rationale": ""}

    for model in models:
        model_rows: list[dict[str, Any]] = []
        required_score = 0
        invented_score = 0
        total_latency = 0.0
        for fixture in fixtures:
            code_path = QUALITY_DIR / fixture["path"]
            code = code_path.read_text(encoding="utf-8")
            prompt = build_review_prompt(code, None)
            started = time.perf_counter()
            content = call_ollama(prompt, model, float(config.get("timeout_seconds", 50)), config)
            elapsed = time.perf_counter() - started
            total_latency += elapsed
            scored = score_response(fixture, content)
            if scored["required_hit"] and fixture.get("required_any"):
                required_score += 1
            elif not fixture.get("required_any"):
                required_score += 1 if scored["ok"] else 0
            if scored["forbidden_hits"] or scored["invented_critical"]:
                invented_score += 1
            preview = content.replace("\n", " ").strip()[:220]
            row = {
                "fixture": fixture["id"],
                "elapsed_sec": round(elapsed, 2),
                "required_hit": scored["required_hit"],
                "forbidden_hits": scored["forbidden_hits"],
                "invented_critical": scored["invented_critical"],
                "ok": scored["ok"],
                "preview": preview,
            }
            model_rows.append(row)
            print(
                f"[{model}] {fixture['id']}: ok={scored['ok']} "
                f"elapsed={elapsed:.2f}s forbidden={scored['forbidden_hits']} "
                f"preview={preview}"
            )

        results["models"][model] = {
            "rows": model_rows,
            "required_ok": required_score,
            "invented_count": invented_score,
            "fixture_ok": sum(1 for r in model_rows if r["ok"]),
            "total_latency_sec": round(total_latency, 2),
            "avg_latency_sec": round(total_latency / max(len(model_rows), 1), 2),
        }

    # Prefer qwen when quality is close, to avoid fighting Atlas for llama3.2.
    ranked = sorted(
        results["models"].items(),
        key=lambda item: (
            -item[1]["fixture_ok"],
            item[1]["invented_count"],
            item[1]["avg_latency_sec"],
        ),
    )
    best_model, best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    winner = best_model
    rationale = (
        f"{best_model} leads on fixture_ok={best['fixture_ok']}/"
        f"{len(fixtures)}, invented={best['invented_count']}, "
        f"avg_latency={best['avg_latency_sec']}s."
    )
    if second and best_model.startswith("llama3.2"):
        other_model, other = second
        close = abs(best["fixture_ok"] - other["fixture_ok"]) <= 1 and other["invented_count"] <= best[
            "invented_count"
        ] + 1
        if close and other_model.startswith("qwen"):
            winner = other_model
            if best["fixture_ok"] == other["fixture_ok"] and best["invented_count"] == other["invented_count"]:
                rationale = (
                    f"Quality tied (fixture_ok={best['fixture_ok']}/{len(fixtures)}, invented=0). "
                    f"llama3.2 was faster (avg {best['avg_latency_sec']}s vs "
                    f"{other['avg_latency_sec']}s) but locking {other_model} to avoid Atlas contention on llama3.2."
                )
            else:
                rationale += (
                    f" llama3.2 edges quality but Atlas uses llama3.2; locking {other_model} "
                    f"(fixture_ok={other['fixture_ok']}, invented={other['invented_count']}) "
                    "to avoid contention."
                )
        else:
            rationale += " llama3.2 wins clearly; lock it and note Atlas contention risk."
    elif best_model.startswith("qwen"):
        rationale += " Prefer qwen for review to leave llama3.2 for Atlas when quality is acceptable."

    results["winner"] = winner
    results["rationale"] = rationale
    print("---")
    print(f"WINNER: {winner}")
    print(f"RATIONALE: {rationale}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-json",
        type=Path,
        default=REPO_ROOT / "docs" / "phase2_ab_results.json",
        help="Path to write A/B results JSON",
    )
    parser.add_argument("--skip-wait", action="store_true", help="Do not wait for Ollama free (unsafe)")
    args = parser.parse_args()

    if args.skip_wait:
        print("WARNING: --skip-wait set; may contend with Atlas")
        # monkey-patch wait
        global wait_until_ollama_free

        def wait_until_ollama_free(base_url: str, poll_seconds: float, max_wait_seconds: float):  # type: ignore
            return ollama_ps(base_url)

    try:
        results = run_ab()
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    args.write_json.parent.mkdir(parents=True, exist_ok=True)
    args.write_json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.write_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
