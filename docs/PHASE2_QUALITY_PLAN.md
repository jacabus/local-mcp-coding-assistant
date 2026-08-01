# Phase 2 — Review quality

Goal: make `local_code_review` precise on small snippets (catch real bugs, stop inventing TLS/HTTP on clean code) without fighting Atlas for `llama3.2`.

## Done in this branch

1. **Fixtures** — `tests/fixtures/quality/`
   - `divide_zero_bug.py` — must flag zero-division
   - `clean_pure_function.py` — must not invent HTTP/TLS
   - `tiny_http_client.py` — HTTP OK only because present; no invented TLS
   - `shell_no_network.py` — filesystem only; no invented network/TLS
   - `expectations.json` — machine-readable required / forbidden notes
2. **Prompt** — hardened `REVIEW_PROMPT` in `src/server.py` (symbols only; never invent protocols/URLs/TLS/frameworks; say when nothing serious; ≤8 bullets).
3. **A/B** — `scripts/review_quality_ab.py` (`think: false`, `num_predict: 400`) with Ollama gate (wait while chat models / `llama3.2` are loaded).
4. **Regression** — `scripts/quality_regression.py` + offline `tests/test_review_quality.py`.
5. **README** — quality contract + verification commands.

## Ollama gate

Before any live quality/latency run:

```bash
curl -s http://127.0.0.1:11434/api/ps
```

If `llama3.2` (or other chat models) are resident, wait. Idle `nomic-embed-text` alone is acceptable. Do not steal Atlas mid-run.

### Observations this session

1. Start of work: `llama3.2:latest` + `nomic-embed-text:latest` loaded (Atlas likely active). Non-inference work proceeded; inference deferred.
2. Pre-A/B: only `nomic-embed-text:latest` (idle embed). A/B started.
3. Post-A/B: `llama3.2:latest` remained resident from the A/B load; polled ~4.5 minutes until `EMPTY`/`FREE` before regression.
4. Pre-verify: `[]` empty ps; quality regression + connection + latency then ran.

## A/B results

Measured 2026-08-01 with `think: false`, `num_predict: 400`.

| Model | fixture_ok | invented | avg latency |
|---|---|---|---|
| qwen3:8b | 4/4 | 0 | 4.0s |
| llama3.2:latest | 4/4 | 0 | 2.92s |

**Locked review model:** `qwen3:8b` (already set in `config/config.json` → `routing.local_code_review`)

**Rationale:** Quality tied (both caught zero-division; neither invented TLS/HTTP on clean fixtures). llama3.2 was faster, but locking qwen avoids fighting Atlas for llama3.2. Config unchanged for review routing.

Raw JSON: [phase2_ab_results.json](phase2_ab_results.json).

## Residual risks

- qwen sometimes under-rates or misses zero-division on the tiny `divide` snippet (saw "No serious issues" on one latency/connection pass; quality regression on the same model flagged it). Non-determinism at 8B.
- Medium HTTP fixture (`medium_review_fixture.py`) can still draw invented TLS/SSL certificate findings from qwen even with the hardened prompt. Clean / no-network fixtures in `tests/fixtures/quality/` did not.

## Model lock policy

- If qwen wins or is within one fixture of llama3.2 with similar invented-finding rate → keep `config.routing.local_code_review` on `qwen3:8b`.
- If llama3.2 clearly wins on precision → lock it for review and document Atlas contention risk; operators should run quality smokes when Atlas is idle.

## Not in this phase

- Gateway `/generate` client
- Async full-file review jobs
- Any Atlas edits
