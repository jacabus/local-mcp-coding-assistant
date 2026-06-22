# Local MCP Coding Assistant

Proof-of-concept: can a supervising coding assistant (Claude Desktop or Codex) invoke a **local** LLM through MCP and receive a useful code-review response?

## Architecture

```
Claude Desktop / Codex
  ↓
MCP Tool (local_code_review)
  ↓
src/server.py (this repo)
  ↓
Ollama
  ↓
qwen3:8b
  ↓
Response back to the supervising agent
```

This repository is isolated from Atlas, FinanceBot, RetirementModel, local-ai-gateway, and all other projects under `~/Projects`.

## V1 scope

- **One MCP tool:** `local_code_review`
- **One model:** `qwen3:8b` via Ollama
- **Read-only:** no file modifications, shell execution, repository access, commits, or pushes from the MCP tool
- **No cloud calls, routing, or extra tools**

## Setup

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) running locally
- Model installed: `qwen3:8b` (verify with `ollama list`)

### 2. Install dependencies

```bash
cd ~/Projects/local-mcp-coding-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration

Edit `config/config.json` if needed:

```json
{
  "ollama_base_url": "http://127.0.0.1:11434",
  "model": "qwen3:8b",
  "timeout_seconds": 120
}
```

Use the exact model tag shown by `ollama list`.

### 4. Claude Desktop MCP configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

Use absolute paths. Merge with any existing `mcpServers` entries rather than replacing the whole file.

Restart Claude Desktop after saving.

### 5. Codex MCP configuration

Add to `~/.codex/config.toml` (merge with existing content; do not remove other servers):

```toml
[mcp_servers.local-mcp-coding-assistant]
command = "/Users/julian/Projects/local-mcp-coding-assistant/.venv/bin/python"
args = ["/Users/julian/Projects/local-mcp-coding-assistant/src/server.py"]
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120
```

`tool_timeout_sec = 120` allows time for local inference. Restart Codex after saving.

Verify with:

```bash
codex mcp get local-mcp-coding-assistant
```

## Test procedure

### Step 1 — Confirm Ollama model

```bash
ollama list
```

Record the exact `qwen3` model tag (expected: `qwen3:8b`).

### Step 2 — Run connection test

```bash
cd ~/Projects/local-mcp-coding-assistant
source .venv/bin/activate
python3 tests/test_connection.py
```

Expected output: `PASS`

The test confirms:

- Ollama is reachable
- the configured model is installed
- a review response is returned

### Step 3 — Configure Claude Desktop

Add the MCP server block shown in Setup step 4.

### Step 4 — Restart Claude Desktop

Fully quit and reopen Claude Desktop.

### Step 5 — Manual proof in Claude or Codex

Ask the supervising agent:

```
Use local_code_review on this code:

def divide(a, b):
    return a / b
```

This snippet is a **test payload only** — it is not part of any other repository.

Expected:

- the agent invokes `local_code_review`
- the tool calls qwen3 through Ollama
- the agent displays a plain-text review
- the review should identify division-by-zero risk

## Success criteria

All seven criteria were met during Phase 2 proof:

1. Ollama responds locally. ✅
2. MCP server starts. ✅
3. Supervising agent detects the MCP tool. ✅
4. Supervising agent invokes `local_code_review`. ✅
5. qwen3 returns a review. ✅
6. Supervising agent displays the response. ✅
7. No files outside this repository are modified. ✅

## MCP tool

**Name:** `local_code_review`

**Inputs:**

- `code` (required)
- `context` (optional)

**Output:** plain-text code review covering bugs, logic issues, security concerns, simplification opportunities, and missing tests.

## Out of scope

- Multiple tools or models
- Model routing
- DeepSeek or other cloud providers
- Secret redaction pipelines
- File editing, shell execution, git operations from the MCP tool
- Atlas, FinanceBot, RetirementModel, or local-ai-gateway integration

## Current status

**Phase 2 complete — operational proof succeeded.**

- MCP server, Ollama wiring, and connection test are in place.
- Claude Desktop connector verified (`local-mcp-coding-assistant` enabled).
- Codex connector verified (`local-mcp-coding-assistant` enabled in MCP settings).

**Paused before Phase 3.** The next step is a design decision on whether any expansion is justified. No additional tools, routing, or integrations are planned until that decision is made.
