# Decisions and Open Questions

> Architecture decision records, unresolved founder questions, plan-conflict
> resolutions, and the risk register. Cross-references:
> [AS_IS_AUDIT.md](AS_IS_AUDIT.md) §4 (reconciliation) ·
> [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §4 ·
> [EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md)

## 1. Architecture Decision Records (ADRs)

### ADR-1 — Keep Python/FastAPI/SQLite
- **Decision:** retain the existing stack unchanged.
- **Rationale:** verified working (18 passing tests, 28 endpoints); solo
  founder has zero ops bandwidth; SQLite's write profile matches a single
  operator; local-first satisfies privacy posture.
- **Rejected:** Postgres (ops overhead, no concurrency need), cloud DB
  (cost + egress + account surface), rewriting in another language (zero
  customer value).

### ADR-2 — Playwright for browser agents when needed
- **Decision:** standardize on Playwright; introduce only via the HITL spec.
- **Rationale:** mature Python API, persistent profiles, headless/headed
  switch (needed for CAPTCHA/MFA handoff), auto-waiting reduces brittle scrapes.
- **Rejected:** Selenium (weaker async/profile ergonomics), raw HTTP-only
  (insufficient for login-required permitted reads), Puppeteer (Node toolchain).

### ADR-3 — Python `keyring` for the credential vault
- **Decision:** OS credential store via `keyring`; encrypted-JSON fallback.
- **Rationale:** cross-platform, no external dependency/service, aligns with
  "no mandatory paid SaaS"; see
  [IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md).
- **Rejected:** cloud secret managers (account surface, cost), plaintext
  `.env` for real secrets (git/backup leakage risk), custom crypto (crypto
  at home = no).

### ADR-4 — Local Ollama optional
- **Decision:** LLM features are opt-in via local Ollama; no paid LLM APIs.
- **Rationale:** zero cost, zero data egress, no rate limits; quality is
  adequate for drafting/research assist; mission needs founder-authored
  outreach anyway.
- **Rejected:** hosted LLM APIs (cost + data leakage + dependency) until a
  founder-approved need appears.

### ADR-5 — Direct Python functions, not LangGraph/CrewAI
- **Decision:** agents are plain functions with typed contracts.
- **Rationale:** 7 well-defined roles; every behavior is unit-testable
  (proven by the existing suite); frameworks add abstraction, version churn,
  and opaque control flow — exactly wrong for a safety-gated solo system.
- **Rejected:** agent frameworks (control-loss risk, unneeded features).

### ADR-6 — Incremental agent rollout
- **Decision:** ship the 5 core agents (discovery, classification+scoring,
  proposal copilot, positioning, supervisor/observer) first; browser and HITL
  agents land only after E3/E8.
- **Rationale:** each agent's risk is bounded by its side-effect contract;
  browser agents carry the highest risk and the least Day-1 value (manual
  mode already works — the 10 seeded leads prove it).
- **Rejected:** big-bang browser automation (risk without revenue).

## 2. Open Questions (founder-input required)

| # | Question | Status | Blocks |
|---|---|---|---|
| OQ-1 | **Founder employment/IP status** — does any current employer agreement (non-compete, moonlighting, IP assignment) restrict independent AI/ML consulting? | **BLOCKING** | All external proposals; first paid engagement
  ([MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md) §8) |
| OQ-2 | **Upwork account status** — active, in good standing, connects available? | **BLOCKING for C4** | First submissions |
| OQ-3 | **Pricing floor** — confirm the floor table
  ([MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) §4) | **BLOCKING for C3** | Proposal drafting |
| OQ-4 | **Brave API key availability** — will the founder register for the free tier? | Open | Brave discovery (non-blocking; manual mode works) |
| OQ-5 | **Freelancer OAuth availability** — app registration and token | Open | E9 (non-blocking) |
| OQ-6 | **Campaign start date** — confirm Day-1 anchor for all phase gates | Open | Calendar of
  [EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md) |
| OQ-7 | Founder weekly hours — is 14 h/wk stable for the full 90 days? | Open | Founder-time model |

Rule: BLOCKING questions gate their listed tasks only; nothing else stalls.

## 3. Conflicts with the Earlier Plan — Resolved

| Conflict | Earlier plan | New spec | Resolution |
|---|---|---|---|
| Browser agents | API-and-manual-only | Browser agents with HITL guardrails | **Resolved:** browser agents permitted as P1 (E10) under
  [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md); manual-first unchanged for Day 1–14 |
| Audit counts | "17 tests, 11 offers, 25 sources" | Verified 18 tests, 10 offers, 32 sources | **Resolved by evidence** ([AS_IS_AUDIT.md](AS_IS_AUDIT.md) §4); repository wins |
| Source state | JSON registry only | DB-backed state machine | **Resolved:** E5 migration; JSON stays as seed |
| Credential storage | Ad-hoc `.env` | Keyring vault by reference | **Resolved:** ADR-3; `.env` remains for non-secret config only |
| Lead intake | "Import leads" as one line | C1–C5 with acceptance tests + CASE-001 manual intake | **Resolved:** intake is now the top backlog slice |

## 4. Risk Register

| # | Risk | Likelihood | Impact | Mitigation | Trigger → response |
|---|---|---|---|---|---|
| R1 | **Zero responses** to proposals | Medium | High | EXP-1 A/B testing; problem-specific offers born from real demand clusters; Day-14 review | 10 proposals, 0 responses → retire framing, RCA
  ([MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) §5) |
| R2 | **Engineering time sink** | High | High | C>E priority rule; slices; 2 h/wk system cap; E-tasks need acceptance tests | Any E-task >3 days → stop, re-scope or defer |
| R3 | **Low budgets** in reachable demand | Medium | Medium | Price floors; tiny jobs only as proof-assets (≤2 concurrent); feasibility-assessment upsell | Floor breaches >30% of leads → channel re-rank |
| R4 | **Marketplace competition** (race to bottom) | High | Medium | Differentiate on diagnosis quality + evaluation rigor; agency pipeline reduces platform dependence | Win rate <10% → shift weight to P-B/P-C |
| R5 | **Secret leakage** | Low | High | Vault-by-reference, redaction tests, `.gitignore`, localhost-only | Any leak suspicion → revoke, rotate, incident |
| R6 | **Data loss** (no git, single disk) | Medium | High | E12 daily backups; founder keeps off-machine copies; git installation decision deferred to founder | Any backup-restore drill failure → block all writes until fixed |
| R7 | **Single-source dependency** (all revenue via Upwork) | Medium | High | Multi-pipeline strategy; Freelancer + agency + referrals by Day 30 | Upwork issue → activate next channel within 48 h |
| R8 | **Founder unavailability** (illness, workload) | Medium | Medium | Everything checkpointed; resume runbook; agents never act unattended | >3 days absence → agents idle safely, leads age visibly |

## 5. Decision Log Convention

New decisions append here as ADR-N with date, context, decision, rationale,
and rejected alternatives. Superseded ADRs are marked, never deleted — the
audit chain principle applies to planning too
([AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §4, DECISION
type).
