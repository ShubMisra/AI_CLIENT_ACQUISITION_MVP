# AS-IS Audit — Repository Inventory

> Evidence-backed inventory of `ai_client_acquisition_mvp`, re-verified on
> **2026-10-10** by direct inspection (file reads, AST-level grep counts,
> JSON parsing, SQLite queries, and a live pytest run). Where earlier
> planning notes disagreed with the repository, the repository wins; the
> reconciliation is recorded in §6.
> Downstream consumers: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md),
> [EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md),
> [DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md).

## 1. Code Inventory

| File | Lines | Verified contents |
|---|---:|---|
| `acqsys/core.py` | 429 | 12-state lifecycle (`STAGES`), lead scoring, category classification, dedup, SHA-256 audit hash chain, memory store, task queue, artifacts, checkpoints, manual activity logging |
| `acqsys/agents.py` | 310 | Brave/Freelancer/RSS discovery connectors, proposal draft generation, positioning analysis, supervisor cycle, optional LLM client, offer matching, SSRF-guarded HTTP fetching |
| `acqsys/app.py` | 214 | FastAPI app with **28 endpoints** (verified by counting route decorators), HTML dashboard, auth guard (`guard` dependency), batch lead import |
| `acqsys/__main__.py` | 47 | **17 CLI commands** (verified by counting `add_parser` calls) |
| `acqsys/scheduler.py` | 20 | Periodic supervisor invocation |
| `tests/test_core.py` | 171 | **18 tests** (verified by live pytest collection: `18 passed`) |
| `requirements.txt` | 4 | fastapi, uvicorn, httpx, pydantic — no browser automation, no credential vault libs |
| `requirements-optional.txt` | — | Optional extras (Ollama/LLM related) |

### 1.1 The 12-state lifecycle (verified from `core.py`)

```
DISCOVERED → VERIFIED → QUALIFIED → PROPOSAL_DRAFTED → CONTACTED → REPLIED
           → DISCOVERY → PROPOSED → NEGOTIATING → WON | LOST | REJECTED
```

Guard rails (enforced and tested): `WON` requires a payment reference;
unverified leads cannot qualify; agents cannot perform `CONTACTED` transitions.

### 1.2 The 17 CLI commands (verified from `__main__.py`)

`init`, `stats`, `sources`, `audit-verify`, `positioning`, `supervisor`,
`serve`, `import-json`, `add`, `brave`, `freelancer`, `rss`, `checkpoint`,
`leads`, `draft`, `verify`, `transition`.

### 1.3 The 18 tests (verified by running `pytest -q`: **18 passed**)

Business rules: dedup+ingest logging · unverified-cannot-qualify ·
no-agent-external-communications · win-requires-payment · hash-chain tamper
detection · memory evidence rules · demand-type separation · proposal
no-send/no-invented-price · malformed source URL rejection · API roundtrip ·
Brave key missing → logged · feed requires founder policy approval ·
LLM opt-in only · checkpoint small-sample warning · supervisor memory reuse
and task dedup · manual action audited · API denials logged ·
offer matching + source registry.

## 2. Data Assets

| Asset | Verified state |
|---|---|
| `data/acquisition.db` | SQLite; 7 application tables (`leads`, `events`, `memory`, `tasks`, `artifacts`, `sources`, plus internal `sqlite_sequence`). **Every table has 0 rows.** The system has never been fed real data. |
| `source_registry.json` | **32 sources** in 5 categories (§2.1). Policy header: "All new sources disabled until configured and reviewed." |
| `offer_library.json` | **10 offers**, each with `id, title, categories, buyer, problem, outcome, qualify[], proof, metric, risk` (§2.2). |
| `lead_candidates_2026-10-10.json` | **10 real Upwork listings**, all `EXPLICIT_PROJECT`, budgets **USD 50 – 25,000** (§2.3). **Never imported** into the database. |
| `.env.example` | Template only; **no `.env` exists** — no API keys configured. |

### 2.1 Source registry breakdown (32 total)

| Category | Count | Notable entries |
|---|---:|---|
| explicit_marketplace_demand | 11 | Freelancer.com (P0, official_api_oauth), Upwork (P0, approved_api_or_on_platform_alerts), Fiverr, Contra, Guru, PeoplePerHour, Workana, Truelancer, Braintrust, Toptal, Malt |
| rfp_and_procurement | 6 | SAM.gov, TED Europa, UNGM, World Bank, India CPPP, GeM India (all P2) |
| agency_partners | 5 | Clutch (P0), GoodFirms (P0), DesignRush, Google Maps, TopDevelopers |
| startup_and_direct_accounts | 7 | YC directory (P0), LinkedIn (P0, **human_only**), Wellfound, Product Hunt, Techstars, Hacker News, Indie Hackers |
| discovery_infrastructure | 3 | Brave Search API (P0, documented), RSS feeds (P1, per-source approval), founder-provided URL (P0, ready) |

Status distribution: **25 `requires_review`**, 5 `documented`, 1 `ready`
(founder URL), 1 `depends_on_source` (RSS). Only Brave API and manual entry
are immediately usable; everything else needs the review flow in
[SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md).

### 2.2 Offer library (10 offers)

`agency_ml_capacity` · `workflow_ai` · `rag_knowledge` · `predictive_ml` ·
`computer_vision` · `ocr_doc_ai` · `llm_evaluation` · `inference_ops` ·
`customer_analytics` · `data_for_ai`.

`agents.match_offers()` loads exactly this file (no hardcoded extra offers —
verified), scores category overlap + keyword hints, and logs
`OFFERS_MATCHED` to the audit chain.

### 2.3 The 10 real leads (unimported)

| # | Demand | Budget (USD) | Title (abridged) |
|---|---|---|---|
| 1 | RAG + classification + workflow | 700 | AI/ML engineer for RAG, request classification and workflow integration |
| 2 | RAG + agentic | 300 | Python RAG assistant and agentic API integration |
| 3 | RAG repair | 50 | Fix RAG PDF retrieval and citation failures |
| 4 | RAG repair | 50 | Improve Python RAG retrieval relevance and hallucination behavior |
| 5 | Computer vision | 1,400 | Retail checkout computer vision tracking prototype |
| 6 | Forecasting | 25,000 | Demand forecasting and inventory optimization, multi-channel e-commerce |
| 7 | Edge ML (audio) | 1,000 | Local audio classification on edge device |
| 8 | NLP/constraint optimization | 200 | Improve structured recommendation and constrained selection engine |
| 9 | NLP classification | 50 | Simple sklearn NLP text-classification micro-project |
| 10 | Agentic assistant | 500 | Python AI customer assistant with web UI |

All carry `source_url` links to live Upwork postings — the highest-leverage
untapped asset in the repo (first action C1 in
[EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md)).

## 3. What Is NOT Present (verified absent)

- `AGENTS.md` at repo root → **created alongside this audit**.
- `.codex/` custom skills/commands; any SKILL.md files.
- `.git/` repository — git is not initialized (and git is not installed on
  this host). Version control is a real operational risk (risk R6).
- `.env` — no BRAVE_API_KEY, no Freelancer OAuth token, no admin token.
- Browser automation (no Playwright in any requirements file).
- Credential vault (no keyring; spec in
  [IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md)).
- Source state tables with data; entity resolution; HITL coordinator.

## 4. Reconciliation Against Earlier Planning Notes

Earlier drafts of this audit recorded different counts. Direct verification
on 2026-10-10 resolves every discrepancy in favor of the repository:

| Item | Earlier note | Verified today | Resolution |
|---|---|---|---|
| Tests | "17 passing (not 18)" | **18 collected, 18 passed** (live pytest run) | 18 is current truth; the earlier run predated `test_offer_matching_and_source_registry` |
| Offers | "11 offers (not 10)" | **10 offers** in `offer_library.json`; `match_offers` loads only this file | 10 is current truth; no 11th offer exists in code or data |
| Sources | "25 sources" | **32 total**, of which **25 `requires_review`** | The "25" figure was the `requires_review` subset; 32 is the full registry |
| Endpoints | 28 | 28 (route-decorator count) | Confirmed |
| Lifecycle states | 12 | 12 (`STAGES` tuple) | Confirmed |
| CLI commands | 17 | 17 (`add_parser` count) | Confirmed |
| Database | 7 tables, empty | 7 app tables, 0 rows each | Confirmed |

## 5. Reuse Decisions

| Component | Decision | Rationale |
|---|---|---|
| `core.py` | **REUSE + EXTEND** | Lifecycle, scoring, audit chain are sound; extend with 14-state funnel, entity resolution hooks, source state (E3–E6) |
| `agents.py` | **REUSE** | Connectors + SSRF guard work; add browser agent only when a source justifies it (E10) |
| `app.py` | **REUSE + EXTEND** | 28 endpoints cover the funnel; add HITL queue, source review, backup endpoints (E3, E8, E12) |
| `source_registry.json` | **REPLACE with DB** | JSON cannot hold per-source state transitions; migrate into `sources` table (E5), keep file as seed |
| `offer_library.json` | **REUSE + EXTEND** | Add pricing hypotheses, experiment tracking, win/loss fields per offer (§4 of positioning doc) |
| `tests/test_core.py` | **EXTEND** | 18 tests guard the invariants; add enforcement tests from
  [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) (7 tests for CASE-001/HITL) |

## 6. Audit Conclusion

The system is **functionally complete and correctly conservative** — a working
lead CRM with hard safety rails — but it is an empty factory: zero leads in
the database while 10 real, budgeted Upwork opportunities sit in a JSON file.
The fastest path to revenue is operational (import → verify → draft → founder
sends), not architectural. All engineering tasks exist only to make that
operational loop repeatable and auditable.
