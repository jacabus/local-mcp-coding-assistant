# Architecture orientation — network information stack

**Status:** Orientation only. **Not an implementation plan.**  
**Date:** 2026-06-25  
**Context:** Gateway / MCP / Atlas–FinanceBot integration review (this repo’s session).

Active build work belongs in the **FinanceBot** and **Atlas** sessions already in progress. Do not start parallel gateway, substrate, or MCP integration from this document.

---

## Paused scope (this repo and cross-repo)

| Item | Decision | Rationale |
|------|----------|-----------|
| **local-mcp-coding-assistant → Ollama direct** (`:11434`) | **Paused** | Isolated PoC; bypasses `local-ai-gateway`. Not on the network-information path. |
| **Unified v2 task router** (`task` / `input` / `require_local` single endpoint) | **Paused** | Premature before Atlas orchestrates multi-source context. Would force Atlas adapter rewrite without payoff yet. |
| **Corpus substrate / cross-domain indexing** | **Not started here** | Architecture gap; implementation tracked in Atlas / FinanceBot sessions — see canonical refs below. |

### What stays in production (do not redesign)

**`local-ai-gateway` v1** on port **5930** — `GET /health`, `POST /embed`, `POST /chat`, `POST /generate`.

Atlas Ask Atlas already depends on this (`atlas/app/backend/app/services/local_ai_gateway.py`). FinanceBot live integration does **not** replace it; it adds a separate **data** path.

Contract reference: `~/Projects/local-ai-gateway/docs/integration-contract.md`

---

## Three layers (do not merge)

```
You / automation
       │
       ▼
┌──────────────────────────────────────┐
│  ATLAS (orchestrator + UI)           │
│  Ask Atlas, retrieval policy,        │
│  context assembly                    │
└───────┬──────────────────┬───────────┘
        │                  │
        │ search / cite    │ synthesise (LLM)
        ▼                  ▼
┌──────────────────┐  ┌─────────────────────┐
│ CORPUS SUBSTRATE │  │ local-ai-gateway    │
│ cross-domain     │  │ :5930               │
│ indexing layer   │  │ embed / generate    │
└────────┬─────────┘  └─────────────────────┘
         │ reads (does not own truth)
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
 FinanceBot  email     Atlas DB   JM Vault docs
 :5880       (future)  (pages…)   (indexed files)
```

| Layer | Job | Owns truth? |
|-------|-----|-------------|
| **Domain apps** | Store specialist data (txns, messages, music metadata) | **Yes** |
| **Corpus substrate** | Normalise into `CorpusObject`, index, embed, provenance, cross-domain search | **No** — read model only |
| **local-ai-gateway** | Run embedding and generation models | **No** — model boundary only |
| **Atlas** | Classify query, retrieve evidence, assemble prompt, call gateway, ground answer | **No** for domain truth |

**Common mistake:** routing FinanceBot HTTP through the gateway. FinanceBot is a **data source** (`ATLAS_FINANCEBOT_BASE_URL`, default `http://192.168.0.72:5880`). The gateway is a **model executor** (`http://localhost:5930`).

---

## Corpus substrate — what it is

A **shared indexing and provenance layer** between domain systems and Atlas/JM Vault synthesis.

- Wraps objects from FinanceBot, email, Atlas, etc. in one envelope (`CorpusObject`) so Ask Atlas can search and cite across domains **without** owning underlying databases.
- **Cross-domain indexing** = ingest/normalise from each `source_system`, embed searchable text, keep lineage (`source_system`, `source_id`, `provenance`).

It is **not**: the LLM gateway, JM Vault, a replacement for FinanceBot, or Atlas becoming the universal backend.

### Canonical design (read these; don’t duplicate here)

| Document | Location |
|----------|----------|
| Concept brief | `~/Projects/JM Vault/wiki/concepts/atlas_corpus_substrate.md` |
| Envelope contract v1 | `~/Projects/atlas/docs/archive/CORPUS_SUBSTRATE_CONTRACT_V1.md` |
| Object ownership rules | `~/Projects/JM Vault/docs/OBJECT_OWNERSHIP_AND_METADATA_RULES_v0_1.md` |

### What exists today (Atlas)

| Piece | Status |
|-------|--------|
| `CorpusObject` schema | `atlas/app/backend/app/schemas/corpus.py` |
| Atlas-native corpus read model | `atlas/app/backend/app/services/corpus.py` (`source_system=atlas`, home property) |
| Reference library + hybrid retrieval (Ask Atlas) | Indexed filesystem docs → segments → gateway `/embed` |
| `financebot_adapter` (live txn fetch) | `atlas/app/backend/app/services/financebot_adapter.py` — **exists, unplugged** |
| `source_system=financebot` corpus indexing | **Specified, not wired** |

Ask Atlas today answers mainly from **indexed documents**. FINANCE domain classification exists; live FinanceBot data is not yet in the retrieval path.

### Future Ask Atlas flow (orientation only)

1. Domain classify (`FINANCE`, `EMAIL`, …) — exists  
2. Retrieve from **corpus index** (substrate) + **live adapter** when freshness required  
3. Assemble context with per-source provenance  
4. Gateway `POST /generate` (v1 contract; `require_local` is a future addition for financial synthesis)  
5. Grounding / citations — exists  

---

## Gateway v1 — Atlas touchpoints (frozen reference)

Client: `atlas/app/backend/app/services/local_ai_gateway.py`  
Override: env `ATLAS_LOCAL_AI_GATEWAY_URL` (default `http://localhost:5930`)

| Endpoint | Atlas use |
|----------|-----------|
| `GET /health` | Settings UI via `/ai/gateway/health` |
| `POST /embed` | Indexing, hybrid retrieval, segmentation |
| `POST /generate` | Ask Atlas synthesis (`retrieval_backed_generation_service.py`) |
| `POST /chat` | Debug/proxy route only |

Atlas sends extra embed fields (`options.num_ctx`, `truncate`); gateway currently ignores them — documented mismatch, not a blocker for v1 freeze.

---

## This repo (`local-mcp-coding-assistant`)

- **Purpose:** MCP proof-of-concept — Cursor/Claude/Codex → Ollama `:11434` directly.  
- **Isolation:** Explicitly separate from Atlas, FinanceBot, and `local-ai-gateway` (see README).  
- **Phase 2 status:** Complete and **paused** before expansion. No gateway wiring planned until network architecture sessions deliver FinanceBot/Atlas integration.

---

## When to revisit paused items

| Trigger | Revisit |
|---------|---------|
| Atlas session wires `financebot_adapter` + corpus `source_system=financebot` | Whether synthesis needs `require_local` on `/generate` |
| FinanceBot batch automation needs shared routing | Thin v1 gateway client in FinanceBot only — not v2 task router |
| Ask Atlas reliably assembles multi-source financial context | v2 task router design — still behind v1 compatibility |

Until then: **keep v1 gateway stable**, **build substrate/adapters in Atlas/FinanceBot sessions**, **leave this MCP repo paused**.
