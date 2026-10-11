# Execution Plan — 90 Days

> Phase gates, weekly rhythm, and the founder-time model. Cross-references:
> [MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md) §9 (metric gates) ·
> [EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md) (task level) ·
> [ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) (channel level) ·
> [MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) (offer level)

## Phase 0 — Planning (COMPLETED)

- Verified all assets end-to-end ([AS_IS_AUDIT.md](AS_IS_AUDIT.md)): 12-state
  lifecycle, 28 endpoints, 17 CLI commands, 18 passing tests, 32-source
  registry, 10 offers, 10 unimported real leads, empty database.
- Produced the planning corpus (all `docs/`), architecture decisions
  ([DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md)), and
  the ordered backlog ([EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md)).
- Deliberately wrote no application code: the system works; it needs data,
  outreach, and a handful of enforcement features.

## Days 1–7 — Commercial Bootstrap

**Commercial (founder-led, primary):**
1. Import the 10 seeded leads (C1) and triage/verify the two RAG repair leads
   plus the $1,400 CV prototype first (C2).
2. Draft 3 proposals with EXP-1 A/B framing (C3); founder reviews and
   submits on Upwork (C4).
3. Send 5 personal network notes (pipeline P-C).
4. Import 10+ new leads from continued manual Upwork reading (C5).

**Engineering (supporting, parallel):**
- E1 `docs/` corpus (this set), E2 `AGENTS.md` — done with Phase 0.
- E3 CASE-001 manual intake workflow + enforcement tests.
- E12 daily backup (small, protects everything).

**Day-7 gate:** ≥5 proposals drafted, ≥1 sent, ≥1 buyer response OR 10+ new
leads imported. Miss → strategy review before more engineering.

## Days 8–14 — First Live Connector

- Freelancer.com API live: founder OAuth setup, vault storage (E7 minimal),
  smoke test, first queries; policy flipped CONFIRMED in the register.
- RSS feeds: 2–3 approved feeds on AI consulting demand; hourly cap.
- Extended funnel metrics live (stage conversion dashboard).
- Agency target list (20 names from Clutch/GoodFirms manual reading);
  first 5 white-label pitches sent (C6/C7, EXP-2 starts).
- Day-14 review: EXP-1 verdict, channel re-rank
  ([ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) §4).

**Day-14 gate:** ≥1 qualified conversation (any pipeline), ≥1 agency
conversation, Freelancer connector active.

## Days 15–30 — Repeatable Lead-to-Proposal

- Multi-source triage normalized (Upwork manual + Freelancer API + RSS +
  offline) with entity resolution (E11) for cross-platform duplicates.
- Browser agent foundation (E10) for ONE permitted source only, per the HITL
  spec — if and only if a source justifies it; manual mode remains acceptable.
- Proposal queue: steady 5 drafts/week; founder sends 3–5/week.
- Positioning experiments continue; observer RCA live on funnel data.
- Day-30 checkpoint: metrics vs
  [MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md) §9; RCA on the
  weakest stage ([AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §10).

**Day-30 gate:** ≥15 drafts, ≥8 sent, ≥2 qualified conversations. Aspiration:
first paid engagement signed (feasibility assessment or repair job).

## Days 31–60 — Conversion and Delivery

- Double down on the single proven channel/offer; retire zero-response
  offers per the 10-proposal rule.
- Delivery copilot: scoped assistance for the first paid engagement
  (scaffolding, evaluation harnesses, reporting — founder owns client
  communication).
- Agency pipeline: convert EXP-2 conversations into a first white-label
  package, however small.
- Ask every active buyer for one referral (scripted, explicit).
- Day-60 gate: 1–2 clients signed, ≥1 collected; delivery reference usable.

## Days 61–90 — Three-Client Objective

- Referral-led growth: referrals into the same funnel; proven channels on
  repeat; no new experiments except on the weakest stage.
- Delivery quality: every engagement ends with a written outcome summary
  (proof asset for the next pitch).
- Day-90 audit: full funnel review, cash-vs-signed reconciliation, system
  audit (`audit-verify`), and the continue/pivot/scale decision:

| Outcome | Decision |
|---|---|
| 3 collected | Continue: repeat the machine next quarter with higher prices |
| 1–2 collected | Pivot: re-weight to the winning pipeline; extend 30 days with founder approval |
| 0 collected but strong funnel | Diagnose pricing/offer via RCA before any new channel |
| 0 collected, weak funnel | Stop and re-plan: the problem is upstream (positioning or market) |

## Founder Time Model (14 hrs/week ≈ 2 hrs/day)

| Block | Hours/wk | Content |
|---|---|---|
| Research + outreach | 5 | Reading sources manually, sending proposals/pitches/network notes, verification calls |
| Conversations + proposals | 4 | Buyer calls, proposal review/send, follow-ups |
| Delivery | 3 | Paid client work (grows with clients, capped by price discipline) |
| System + admin | 2 | Checkpoints, backups verification, approvals, this repo |

Rules: outreach block never yields to system work; engineering (E-tasks)
happens in the 2-hour system block or gets explicitly deferred — the backlog's
execution order enforces this
([EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md)). If delivery exceeds ~6 h/wk
(good problem), acquisition blocks are protected first.

## Weekly Rhythm

- **Mon:** `/daily-brief` → pick week's lead targets; import/verify batch.
- **Tue–Thu:** outreach + conversations; drafts queued for founder send.
- **Fri:** metrics review vs gates; observer signals; next-week experiment
  decision; backup verification
  ([OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md)).
- **Checkpoint weeks (4/8/12):** replace Fri review with the full checkpoint
  + RCA ritual.
