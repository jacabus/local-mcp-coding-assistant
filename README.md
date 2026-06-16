# Local MCP Coding Assistant

Proof-of-concept: can a supervising coding assistant (Claude Desktop) invoke a **local** LLM through MCP and receive a useful code-review response?

## Architecture

```
Claude Desktop
  ↓
MCP Tool (local_code_review)
  ↓
src/server.py (this repo)
  ↓
Ollama
  ↓
qwen3:8b
  ↓
Response back to Claude
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

### Step 5 — Manual proof in Claude

Ask Claude:

```
Use local_code_review on this code:

def divide(a, b):
    return a / b
```

Expected:

- Claude invokes `local_code_review`
- the tool calls qwen3 through Ollama
- Claude displays a plain-text review
- the review should identify division-by-zero risk

## Success criteria

1. Ollama responds locally.
2. MCP server starts.
3. Claude detects the MCP tool.
4. Claude invokes `local_code_review`.
5. qwen3 returns a review.
6. Claude displays the response.
7. No files outside this repository are modified.

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

**Phase 2 — minimal operational proof implemented.** MCP server, Ollama wiring, and connection test are in place. Claude Desktop manual verification (Steps 3–5) is required to complete the proof.
