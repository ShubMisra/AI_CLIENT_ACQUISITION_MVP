# System Architecture

> How the system is built, why, and what it must never become.
> Cross-references: [AS_IS_AUDIT.md](AS_IS_AUDIT.md) ·
> [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) ·
> [IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md) ·
> [AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) ·
> [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md)

## 1. Stack Decision

**Python 3.11 + FastAPI + SQLite, local-first.** Verified appropriate for a
solo founder (see ADR-1 in
[DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md)):

- Single operator, single machine, zero concurrent-write pressure → SQLite is
  not a compromise, it is the correct tool.
- FastAPI gives the dashboard, API, and auth guard in 214 lines of proven
  code ([AS_IS_AUDIT.md](AS_IS_AUDIT.md)).
- Local-first means: default bind 127.0.0.1, no cloud services, no data
  egress beyond sanctioned source APIs. Data loss is the main local risk,
  mitigated by daily backup (E12).

## 2. End-to-End Data Flow

```
Sources (32 in registry; see SOURCE_ACCESS_POLICY_REGISTER.md)
   │  explicit demand / potential demand / offline (manual entry)
   ▼
Ingestion  ── normalize → dedup → classify categories → score (0–100)
   │                          (core.py; tested: dedup, malformed URL,
   ▼                           demand-type separation)
SQLite (data/acquisition.db)  ── leads · events · memory · tasks ·
   │                             artifacts · checkpoints · sources
   ▼
Qualification ── founder verifies buyer intent (VERIFIED → QUALIFIED)
   │              agents only recommend; test_unverified_cannot_qualify
   ▼
Proposal Drafting ── agents.match_offers + draft generation
   │                 (never sends, never invents price — tested)
   ▼
★ Founder Approval Gate ── the ONLY path from DRAFT to the outside world
   │
   ▼
Manual Outreach ── founder posts/sends on Upwork, email, LinkedIn by hand
   │
   ▼
Activity Logging ── manual_activity() events appended to hash chain
   │                (tested: test_manual_action_audited)
   ▼
Checkpoints (day 30/60/90) ── diagnosis + next actions for the founder
```

The ★ gate is architectural, not procedural: no code path writes to any
external system. Every outbound action is a human hand on a web browser.

## 3. Agent Roles (contract-based)

Each agent has a typed contract (inputs, outputs, side-effect budget) and is
invoked as a plain function — no agent framework
([DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md) ADR-5).

| Agent | Contract | Side effects |
|---|---|---|
| **Discovery** | source config → candidate leads | ingest() into DB + audit events |
| **Classification + Scoring** | raw lead → categories, score, reasons | enriches lead row |
| **Proposal Copilot** | lead id + verified facts → draft text + offer ranking | artifact + PROPOSAL_DRAFTED event |
| **Positioning** | lead id → ranked offers with reasoning | OFFERS_MATCHED event |
| **Supervisor / Observer** | current state → next-best tasks + warnings | tasks, memory reads, warnings |
| **Offer Matcher** | lead + offer library → scored shortlist | part of positioning |
| **LLM Research (optional)** | prompt + redacted context → analysis | opt-in only (test_llm_opt_in_only); local Ollama, no data egress |

Contract rule: an agent that cannot fulfill its contract without an external
write returns a task for the founder instead. Future browser/HITL agents
follow [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md).

## 4. Architecture Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Keep FastAPI + SQLite | 18 passing tests, zero ops overhead (ADR-1) |
| 2 | Playwright when a browser is required | Headless/headed, per-site scoped profiles, mature Python API (ADR-2); introduced only via the HITL spec |
| 3 | `keyring` for credentials | Cross-platform encrypted storage, no external service (ADR-3) |
| 4 | Ollama optional, opt-in | No cost, no data leakage; off by default (ADR-4) |
| 5 | Direct Python functions, no LangGraph/CrewAI | 7 roles, testable, debuggable; framework would add dependency risk without owner value |
| 6 | SQLite for source state (E5) | Registry JSON → DB migration keeps status transitions auditable |
| 7 | Existing scheduler extended | `scheduler.py` already runs supervisor cycles; no new job system |

## 5. Explicitly NOT Building

Any proposal touching these is rejected by default (override requires founder
decision with written rationale):

- Microservices / API gateway / service mesh
- Kubernetes, Docker orchestration, cloud deployment
- Distributed queues (Kafka/RabbitMQ/Celery)
- Vector databases (a `WHERE` clause and FTS in SQLite is sufficient at this
  scale; revisit only past ~10k documents)
- Paid LLM APIs (local Ollama covers optional research)
- Multi-tenant anything

## 6. Threat Model

| Threat | Vector | Mitigation | Status |
|---|---|---|---|
| SSRF | Agent fetches attacker-influenced URL into internal network | Scheme/host allowlist, private-range + localhost denial in `agents.py` fetch guard | **Mitigated** (tested: malformed URL rejection) |
| Audit tampering | Silent edit of past actions | SHA-256 chained hashes; `audit-verify` recomputes | **Mitigated** (tested: tamper detection) |
| Secret leakage | Keys in prompts, logs, git, memory | Vault-by-reference design
  ([IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md)); `.gitignore` | Partial — vault not yet built (E7) |
| Unauthorized transitions | Lead jumps lifecycle (e.g., straight to WON) | Transition guard + payment reference requirement | **Mitigated** (tested: denials logged, win-requires-payment) |
| API key exposure over network | Admin endpoints reachable from LAN | Bind 127.0.0.1; admin token guard on mutations | **Mitigated** by default; token optional in `.env` |
| Data loss | Disk failure, accidental deletion | Daily SQLite `.backup()` + restore runbook | **Gap** — E12 |
| Prompt injection | Web page content instructs an LLM-enabled agent | DOM sanitization before LLM, instruction firewall, secrets never in context (§7) | **Design** — enforced when browser agents land |
| Policy self-authorization | Agent upgrades source access without founder | Status transitions to ACTIVE/CONFIRMED are founder-only API paths | **Design** — E3/E8 enforcement tests |

## 7. Prompt-Injection Defense (browser agents)

1. Page content is data, never instructions: extracted text passes through a
   sanitizer that strips/escapes directive-like patterns before any LLM call.
2. The LLM context never contains credentials, cookies, or tokens — nothing
   to steal by injection.
3. Agent outputs from LLM analysis are treated as *recommendations*; any
   state-changing action requires the HITL task flow with founder approval.
4. Incidents (detected injection attempts) are logged as audit events with
   redacted evidence ([AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md)).
   Test scenario 10 in [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md).

## 8. Rate Limits, Domain Scope, Scheduling

- **Per-source rate limits** recorded in the source register and enforced by
  the browser/connector layer (min delay between requests, daily request
  budget, quiet hours).
- **Domain scope:** a connector run may only touch domains listed for that
  source in the register; cross-domain redirects abort the run (SSRF guard
  double-checks).
- **Scheduling:** `scheduler.py` runs supervisor cycles (default daily via
  `python -m acqsys.scheduler --every-hours 24`); connectors run on demand or
  on approved schedules recorded as tasks. No always-on services beyond the
  local dashboard.
