# Execution Backlog

> Ordered, acceptance-tested work items. Commercial (C) tasks move leads;
> engineering (E) tasks make that repeatable and safe. C always outranks E at
> equal effort ([MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md),
> "revenue over infrastructure"). Cross-references:
> [EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md) (phases) ·
> [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) (acceptance) ·
> [AS_IS_AUDIT.md](AS_IS_AUDIT.md) (starting point)

## Effort and Impact Scale

- **Effort:** S (< 2 h) · M (2–8 h) · L (1–3 days)
- **Acquisition impact:** ★ = indirect · ★★ = enables outreach · ★★★ = direct lead/proposal movement

## Commercial Tasks (C)

### C1 — Import the 10 seeded leads — S — ★★★
- **Preconditions:** database initialized (`python -m acqsys init`).
- **Deliverable:** `python -m acqsys import-json lead_candidates_2026-10-10.json`; all 10 rows in `leads` with correct demand types and budgets; dedup clean.
- **Acceptance:** `python -m acqsys leads` shows 10; each has `source_url`; audit shows 10 `LEAD_INGESTED` events; `pytest -q` green.
- **Note:** the single highest-leverage action in the repo
  ([AS_IS_AUDIT.md](AS_IS_AUDIT.md) §6).

### C2 — Triage and verify top leads — M — ★★★
- **Preconditions:** C1.
- **Deliverable:** founder verification notes on ≥5 leads (prioritize: two RAG repairs, $1,400 CV prototype, $700 RAG+classification, $300 RAG+agentic); status → VERIFIED/REJECTED with evidence notes.
- **Acceptance:** ≥5 `VERIFIED` (or REJECTED) with notes; no unverified lead past VERIFIED (existing test guards this).

### C3 — Draft three proposals — M — ★★★
- **Preconditions:** C2; pricing floor confirmed (OQ-3).
- **Deliverable:** `python -m acqsys draft <lead_id>` ×3 with EXP-1 A/B/A framing
  ([MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) §3); drafts end at PROPOSAL_DRAFTED; founder personalizes.
- **Acceptance:** 3 artifacts exist; no invented prices (tested); no T3 proof claims; founder review recorded.

### C4 — Submit on Upwork (founder) — S — ★★★
- **Preconditions:** C3; Upwork account in good standing (OQ-2).
- **Deliverable:** founder posts 3 proposals manually; records `MANUAL_ACTIVITY(APPLICATION_SUBMITTED)` per lead
  ([EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) scenario 14).
- **Acceptance:** 3 events logged; leads → CONTACTED; follow-up reminders created.

### C5 — Import 10+ new leads — M — ★★★
- **Preconditions:** founder continues manual Upwork reading (registered MANUAL_ONLY).
- **Deliverable:** new candidates JSON (same schema) imported; total pipeline ≥ 20.
- **Acceptance:** ≥20 DISCOVERED+ leads by Day 7; dedup handles overlaps with C1 set.

### C6 — Identify 20 agency targets — M — ★★
- **Preconditions:** none (manual reading of Clutch/GoodFirms public pages, human-paced per
  [SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md) §2.8).
- **Deliverable:** 20 leads typed AGENCY_PARTNER with fit notes; top 5 ranked.
- **Acceptance:** rows carry source URL + rationale; ≥5 VERIFIED-worthy on inspection.

### C7 — Contact agencies (founder) — M — ★★
- **Preconditions:** C6; EXP-2 pitch drafted and founder-approved.
- **Deliverable:** 5 pitches/week sent manually; replies logged as manual activities.
- **Acceptance:** send/reply events auditable; ≥1 discovery call targeted by Day 14.

### C8 — Day-7 review — S — ★★
- **Preconditions:** C1–C5 done.
- **Deliverable:** gate check vs [EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md) Days 1–7; channel re-rank; written LESSON memory.
- **Acceptance:** gate verdict recorded; any miss converted into an RCA task, not silent slippage.

## Engineering Tasks (E)

### E1 — Create docs/ planning corpus — M — ★
- **Deliverable:** the 15 documents in `docs/` (this set). **Status: DONE (2026-10-10).**
- **Acceptance:** all files present, cross-linked, consistent with verified audit numbers.

### E2 — Create AGENTS.md — S — ★
- **Deliverable:** root governance file (mission, invariants, commands). **Status: DONE (2026-10-10).**
- **Acceptance:** ≤80 lines; matches verified CLI commands; test/quick-start correct.

### E3 — CASE-001 manual intake workflow — M — ★★
- **Preconditions:** E1/E2 context.
- **Deliverable:** manual-intake path for founder-supplied leads with provenance `FOUNDER_SUPPLIED`, redaction pattern, and `CRAWL_DENIED` auditing for MANUAL_ONLY sources
  ([BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §4, §8).
- **Acceptance:** the 7 enforcement tests of the HITL spec §6 pass; scenarios 1, 7, 18 green.

### E4 — Extend lifecycle to 14 states — M — ★★
- **Deliverable:** add `FEASIBILITY_SENT` and `NEGOTIATION_STAGE` (or founder-approved equivalents) between QUALIFIED and PROPOSED to track the offers
  ([MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) §2); transition guard updated.
- **Acceptance:** 18 existing tests unchanged; new transitions audited; invalid jumps denied+logged (scenario 3/13 pattern).

### E5 — Source DB tables + registry migration — M — ★★
- **Deliverable:** migrate `source_registry.json` into the `sources` table with SM-1/SM-2 state, per-action permissions, review dates; JSON remains the seed
  ([SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md) §5).
- **Acceptance:** 32 rows migrated; status transitions auditable; `/api/sources` unchanged shape (existing test).

### E6 — Audit schema extensions — M — ★
- **Deliverable:** nullable columns per
  [AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §2 (correlation_id, causation_id, run_id, policy_version, approval_id, before/after_state, error_class, latency_ms, cost_cents, retry_number, agent_version).
- **Acceptance:** 18 tests pass unchanged; new columns populated by new code paths only.

### E7 — Credential vault — M — ★★
- **Deliverable:** `keyring`-based vault per
  [IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md) §2–6 (interface, audit by key ID, expiry tasks, redaction test).
- **Acceptance:** §11 checklist all checked; secret-value leak test green; Brave/Freelancer keys stored by reference only.

### E8 — HITL coordinator — L — ★★
- **Deliverable:** HITL task queue (raise/evidence/choices/timeout/checkpoint), `/api` endpoints, resume-after-founder flow
  ([BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §3).
- **Acceptance:** scenarios 5, 8, 9 green; timed-out task force-aborts; founder resolution audited.

### E9 — Freelancer live test — S — ★★★
- **Preconditions:** founder OAuth app + E7 vault.
- **Deliverable:** `python -m acqsys freelancer "<query>"` against live API; results imported and deduped.
- **Acceptance:** ≥1 real query cycle end-to-end within rate limits; register entry CONFIRMED with citations.

### E10 — Browser agent foundation — L — ★★
- **Preconditions:** E3, E8, a source that justifies browser access.
- **Deliverable:** Playwright runner with budgets/rate limits/profile isolation per
  [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §1, §5.
- **Acceptance:** scenarios 2, 3, 6, 10 green; run on ONE permitted source only.

### E11 — Entity resolution — M — ★★
- **Deliverable:** cross-source duplicate detection (URL canonicalization + title/org fuzzy match), merge/link with correlation_id
  ([EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) scenario 11).
- **Acceptance:** planted duplicates across Upwork/Freelancer fixtures resolve; false-positive rate <5% on the seeded corpus.

### E12 — Daily backup — S — ★★
- **Deliverable:** scheduled SQLite `.backup()` to `backups/` + restore runbook
  ([OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md) §8; [AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §9).
- **Acceptance:** restore-into-scratch drill passes; `audit-verify` valid on restored copy.

## Execution Order

```
Week 1:  C1 → C2 → C3 → C4        (commercial spine, founder in the loop)
         ∥ E1, E2 (done) → E3 → E12
Week 2:  C5, C6 → C7               (keep pipeline full; open P-B)
         ∥ E9 (needs founder OAuth) → E5 → E6
Week 3–4: C8 review; drafts ×5/wk; first conversations
         ∥ E7 → E4 → E11 → E8 (E10 last, only with a justified source)
```

Rationale: every E-task in the first two weeks either protects the commercial
spine (E3, E12) or unlocks a connector (E9, E5); everything else waits.

## Implementation Slices

- **Slice A — Import → Proposal (commercial, no code changes):** C1–C4 on the
  unmodified system. Proves the funnel end-to-end with founder hands. Highest
  priority; starts immediately.
- **Slice B — Source discovery → connector (P1):** E9 + E5 + E6; makes the
  second channel real and the registry stateful.
- **Slice C — CASE-001 policy foundation (P0 engineering):** E3 + E12 +
  E7-minimal; makes manual-everything safe and durable before any automation.

Slice A runs regardless of engineering progress; Slices B/C are interruptible
without harming outreach.
