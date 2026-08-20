# Model routing validation — qwen2.5-coder:7b

**Status:** Local controlled validations, not production-volume benchmarks.
**Date:** 2026-08-20
**Implements:** routing on branch `routing/qwen2.5-coder-validated-routing` (see [config/config.json](../config/config.json), [src/server.py](../src/server.py)).

These are small, fixture-driven comparisons run against a handful of cases per tool — not statistically powered, not measured under production volume or concurrency. They are sufficient to justify a routing choice between a short list of locally available models, not a general claim about model quality.

## `local_code_review`

`qwen2.5-coder:7b` matched or improved on `qwen3:8b` on the tested coding-review cases:

- Correctly rated the divide-by-zero defect as Critical.
- Faster overall than `qwen3:8b`.
- Slightly narrower finding coverage on some borderline HTTP code (fewer secondary findings on cases near the HTTP/TLS boundary, though no invented findings observed).

**Routed to:** `qwen2.5-coder:7b`.

## `local_test_ideas`

`qwen2.5-coder:7b` produced comparable quality and correct test ideas, and ran faster than `qwen3:8b`.

**Routed to:** `qwen2.5-coder:7b`.

## `local_alternative_solution`

Dedicated 6-fixture validation, scored on compliance with the "do not rewrite the full code" instruction in `ALTERNATIVE_SOLUTION_PROMPT`:

| Model | Compliance (no full rewrite) | Notes |
|---|---|---|
| `qwen3:8b` | 6/6 | Complied on every fixture. |
| `qwen2.5-coder:7b` | 0/6 | Repeatedly emitted full rewrites instead of a bounded alternative-approach summary. |
| `llama3.2` | 0/6 | Also non-compliant, tested as a candidate replacement. |
| `gemma4:12b` | 6/6 | Complied on every fixture, but exceeded the current 50s production timeout (`timeout_seconds`) on 3/6 fixtures. |

**Routed to:** `qwen3:8b` — the only model that both complied with the prompt contract and stayed inside the current timeout budget on all fixtures.

## `gpt-oss:20b` — evaluated, not routed

Under this server's current request shape (`think: false`, `num_predict: 400`, per `call_ollama` in [src/server.py](../src/server.py)), `gpt-oss:20b` frequently consumed the `num_predict=400` budget in reasoning output and returned an empty `message.content`. This makes it unsuitable for these MCP tools under the current contract (fixed prediction budget, no reasoning-token allowance). Not adopted for any tool; not present in `config.json` `routing`.

## Summary

| Tool | Model routed | Why |
|---|---|---|
| `local_code_review` | `qwen2.5-coder:7b` | Matched/improved quality, faster, no invented findings |
| `local_test_ideas` | `qwen2.5-coder:7b` | Comparable quality, faster |
| `local_alternative_solution` | `qwen3:8b` | Only model compliant with the rewrite-avoidance instruction within the timeout budget |
| `local_log_summary` | `llama3.2:latest` (unchanged) | Not part of this validation round |

See also: [PHASE2_QUALITY_PLAN.md](PHASE2_QUALITY_PLAN.md) and [phase2_ab_results.json](phase2_ab_results.json) for the earlier, superseded `qwen3:8b` vs `llama3.2:latest` review-quality lock — preserved as historical evidence, not current routing.
