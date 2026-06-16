# Local MCP Coding Assistant

Proof-of-concept: can a supervising coding assistant (Claude Code, Claude Desktop, or Codex) invoke a **local** LLM through MCP and receive a useful code-review response?

## Architecture (target)

```
Claude
  ↓
MCP Tool (local_code_review)
  ↓
Local MCP Coding Assistant (this repo)
  ↓
Ollama
  ↓
qwen3
  ↓
Response back to Claude
```

This repository is **completely isolated** from Atlas, FinanceBot, RetirementModel, local-ai-gateway, and all other projects under `~/Projects`.

## V1 scope

- **One MCP tool:** `local_code_review`
- **One model:** `qwen3` via Ollama
- **Read-only:** no file modifications, shell execution, repository access, commits, or pushes
- **No cloud calls:** no DeepSeek or other remote APIs
- **No routing:** no model selection, committee workflows, or multi-tool orchestration
- **No Atlas integration**

The proof question:

> Can Claude successfully invoke a local MCP tool, have that tool call qwen3 through Ollama, and receive a useful code-review response?

## Success criteria

1. Ollama responds locally.
2. MCP server starts.
3. Claude detects the MCP tool.
4. Claude invokes `local_code_review`.
5. qwen3 returns a review.
6. Claude displays the response.
7. No files outside this repository are modified.

When all seven pass, the proof is complete.

## Out of scope (V1)

- Multiple tools or models
- Model routing or load balancing
- DeepSeek or other cloud providers
- Secret redaction pipelines
- Logging systems beyond a `logs/` directory placeholder
- Committee-style or multi-agent workflows
- Integration with Atlas, FinanceBot, RetirementModel, or local-ai-gateway
- Modifications to any repository other than this one

Additional capabilities are deferred until the minimal loop above is proven.

## Repository structure

```
local-mcp-coding-assistant/
├── src/
│   └── server.py          # placeholder
├── config/
│   └── config.json        # placeholder
├── tests/
│   └── test_connection.py # placeholder
├── logs/
├── README.md
├── requirements.txt
└── .gitignore
```

## Current status

**Phase 1 — repository scaffold only.** Placeholder files exist; MCP server, Ollama integration, package installation, and Claude configuration are not implemented yet.

## Next phase (not started)

1. Implement `src/server.py` as a stdio MCP server exposing `local_code_review`.
2. Wire Ollama (`qwen3`) via HTTP.
3. Add a real connection test in `tests/test_connection.py`.
4. Register the server in Claude/Cursor MCP settings and run the seven success criteria.
