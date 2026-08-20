# Local MCP Coding Assistant

Bounded local second-opinion tools for Cursor / Claude Desktop / Codex via MCP → Ollama.

This is **not** a replacement for the supervising cloud agent. It wins only when it is fast, bounded, and reliable on small snippets.

## Architecture

```
Cursor / Claude Desktop / Codex
  ↓
MCP tools (local_code_review, local_test_ideas, local_log_summary, local_alternative_solution)
  ↓
src/server.py
  ↓
Ollama :11434  (direct; gateway not wired in Phase 1)
  ↓
qwen2.5-coder:7b / qwen3:8b / llama3.2:latest
```

Isolated from Atlas, FinanceBot, RetirementModel, and `local-ai-gateway` for Phase 1. House contract prefers the gateway; that is Phase 2 only after this sync path is proven.

## Bounded sync contract

| Constraint | Value | Why |
|---|---|---|
| Max input | `max_input_chars` **5000** | Larger payloads time out in Cursor |
| Output cap | `num_predict` **400** | Keeps latency down |
| Thinking | `think: false` | Qwen3 default thinking blew past ~60s |
| Server timeout | **50s** per tool | Fail before typical Cursor MCP ~60s ceiling |
| Latency pass bar | **45s** for tiny + medium smoke | Measured with `scripts/latency_smoke.py` |

Oversized input is rejected immediately with a clear error (no silent hang).

## Setup

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) running locally
- Models: `qwen2.5-coder:7b`, `qwen3:8b`, `llama3.2:latest` (`ollama list`)

### 2. Install dependencies

```bash
cd ~/Projects/local-mcp-coding-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration

See [config/config.json](config/config.json):

- top-level `model` fallback: `qwen2.5-coder:7b` (unrouted-tool safety net; matches the code-specialised model validated for the two core code tools — see rationale below)
- per-tool `routing`: `local_code_review` and `local_test_ideas` → `qwen2.5-coder:7b`; `local_alternative_solution` → `qwen3:8b`; `local_log_summary` → `llama3.2:latest`
- `timeout_seconds`, `max_input_chars`, `num_predict`, `temperature`, `think`

### 4. Cursor MCP configuration (prefer a single registration)

Use the project file [`.cursor/mcp.json`](.cursor/mcp.json). In **Settings → Tools & MCP**:

1. Enable `local-mcp-coding-assistant` from this workspace.
2. **Disable any duplicate user-level** registration of the same server name so only one instance runs.
3. Toggle the server off/on (or restart Cursor) after changing `src/server.py`. Cursor keeps a long-lived stdio process; until you toggle it, calls still hit the **old** code (slow `think` path, old prompts, timeouts).

After a toggle, prove the live path with `scripts/mcp_stdio_smoke.py` (fresh process) or a Cursor `local_code_review` on `tests/fixtures/medium_review_fixture.py`.

```json
{
  "mcpServers": {
    "local-mcp-coding-assistant": {
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["${workspaceFolder}/src/server.py"]
    }
  }
}
```

Cursor talks to Ollama on `11434` directly in Phase 1.

### 5. Claude Desktop / Codex

Same absolute paths as before. For Codex, keep `tool_timeout_sec` at least **60** (server aims to finish under 50s).

Claude Desktop:

```json
{
  "mcpServers": {
    "local-mcp-coding-assistant": {
      "command": "/Users/julian/Projects/local-mcp-coding-assistant/.venv/bin/python",
      "args": [
        "/Users/julian/Projects/local-mcp-coding-assistant/src/server.py"
      ]
    }
  }
}
```

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.local-mcp-coding-assistant]
command = "/Users/julian/Projects/local-mcp-coding-assistant/.venv/bin/python"
args = ["/Users/julian/Projects/local-mcp-coding-assistant/src/server.py"]
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 60
```

## Verification

```bash
cd ~/Projects/local-mcp-coding-assistant
.venv/bin/python tests/test_connection.py
# expect: PASS

.venv/bin/python -m pytest tests -v
# expect: all passed (unit tests do not need Ollama; connection test is separate)

.venv/bin/python scripts/latency_smoke.py
# expect: tiny + medium under 45s, PASS

.venv/bin/python scripts/mcp_stdio_smoke.py
# expect: fresh MCP stdio medium review under 45s, PASS

# Only when Ollama /api/ps shows no llama3.2 (Atlas free):
.venv/bin/python scripts/quality_regression.py
# expect: PASS
```

Then in Cursor (after toggling the MCP server so it loads current `src/server.py`), run `local_code_review` on `tests/fixtures/medium_review_fixture.py`. Expect a severity-ranked review with no `MCP error -32001`.

Request telemetry (ignored by git): `logs/requests.ndjson` — one line per call with `tool`, `model`, `input_chars`, `elapsed_ms`, `ok`.

## MCP tools

| Tool | Model (default routing) | Input |
|---|---|---|
| `local_code_review` | `qwen2.5-coder:7b` | `code`, optional `context` |
| `local_test_ideas` | `qwen2.5-coder:7b` | `code`, optional `context` |
| `local_log_summary` | `llama3.2:latest` | `log_text`, optional `context` |
| `local_alternative_solution` | `qwen3:8b` | `code`, optional `context` |

### Fallback model decision (2026-08-20)

`config.model` / `server.DEFAULT_MODEL` moved from `qwen3:8b` to `qwen2.5-coder:7b`. This fallback only fires for a tool name absent from `routing` (e.g. a future tool added without an explicit entry) — normal calls always resolve through the per-tool `routing` table above. With the validated routing in place, the two core code-facing tools (`local_code_review`, `local_test_ideas` — the majority of routed tools, and this project's primary purpose per its name) now run on the code-specialised `qwen2.5-coder:7b`. A future unrouted tool on a "coding assistant" server is more likely to be code-shaped than general-reasoning-shaped, so the safety-net default now matches that model rather than the general-purpose `qwen3:8b`, which remains explicitly routed for `local_alternative_solution` only.

## Review quality contract (Phase 2)

`local_code_review` must stay useful on small snippets:

- Cite only symbols present in the code
- Never invent protocols, URLs, TLS/SSL, frameworks, or APIs that are not in the snippet
- If nothing serious is wrong, say so briefly
- At most 8 severity-ranked bullets

Fixtures and expectations: [tests/fixtures/quality/](tests/fixtures/quality/). Offline scoring lives in `tests/test_review_quality.py`. Live checks (Ollama must be free — do not steal Atlas `llama3.2`):

```bash
.venv/bin/python scripts/review_quality_ab.py   # A/B qwen3:8b vs llama3.2:latest
.venv/bin/python scripts/quality_regression.py  # locked review model vs fixtures
```

Results and model lock notes: [docs/PHASE2_QUALITY_PLAN.md](docs/PHASE2_QUALITY_PLAN.md).

## Out of scope

- Atlas / FinanceBot / gateway wiring (Phase 1–2 quality work stays direct Ollama)
- Full-file or multi-file reviews
- Streaming / async job tools
- Cloud models

## Current status

**Phase 1 — bounded sync path.** Reliable local second opinion under Cursor’s MCP timeout wall.

**Phase 2 — review quality.** Hardened `REVIEW_PROMPT`, quality fixtures, A/B + regression scripts. The Phase 2 A/B (`docs/PHASE2_QUALITY_PLAN.md`, `docs/phase2_ab_results.json`) locked `local_code_review` on `qwen3:8b` vs `llama3.2:latest`, avoiding Atlas contention on `llama3.2`; that A/B result is preserved as historical evidence. **Phase 3 model validation** superseded that lock: `local_code_review` and `local_test_ideas` now route to `qwen2.5-coder:7b` (see [Fallback model decision](#fallback-model-decision-2026-08-20) above); `local_alternative_solution` stays on `qwen3:8b`; `local_log_summary` stays on `llama3.2:latest`.

**Cursor IDE note:** if `local_code_review` still times out on medium snippets, the IDE is still running a stale MCP process. Toggle the project MCP server off/on (and disable the user-level duplicate).

Still deferred (pick from measured need):

1. Thin client to gateway `POST /generate` (house-contract alignment; this repo only; no Atlas edits)
2. Async `start` + `status` tools for full-file reviews

Architecture orientation (read-only): [docs/ARCHITECTURE_ORIENTATION.md](docs/ARCHITECTURE_ORIENTATION.md).
