# Mission and Constraints

> Governing document for the 90-day acquisition campaign. Every other plan in
> `docs/` defers to this file when priorities conflict.
> Cross-references: [ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) ·
> [MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) ·
> [EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md) ·
> [EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md)

## 1. North Star

**Acquire 3 independent paying AI/ML clients within 90 days.**

- The clock starts on the confirmed campaign start date (see
  [DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md), OQ-6).
- Measured in *paying* clients, not proposals sent, conversations held, or
  contracts signed. Revenue without collected cash does not count toward the
  objective (see §4).
- Everything else — tooling, agents, documents, infrastructure — is
  subordinate to moving real buyers toward paid engagements.

## 2. Founder Context and Operating Model

| Constraint | Value | Consequence |
|---|---|---|
| Team size | 1 (solo founder) | No parallel workstreams; every hour is scarce |
| Time budget | ~14 hrs/week (provisional) | ~180 founder-hours over 90 days |
| Employment status | Provisional, unverified | BLOCKING gate before first paid engagement (OQ-1) |
| Budget | No mandatory paid SaaS | Free tiers and manual workflows only, unless founder approves a purchase |
| AI posture | AI-first | Agents do discovery, research, drafting; founder does approvals, outreach, delivery |

**Division of labor (invariant):**

- **Agents:** discovery, normalization, dedup, classification, scoring,
  proposal drafting, positioning analysis, observation, reporting.
- **Founder:** all external communications, verification of buyer intent,
  approval of every outbound artifact, delivery of paid work, payment
  reconciliation.

## 3. Business Scope

In scope — services the founder can credibly sell within 90 days:

- Machine learning (predictive modeling, forecasting, classification)
- Deep learning applications
- Computer vision (detection, inspection, tracking prototypes)
- NLP and text classification
- OCR and document AI
- RAG (retrieval-augmented generation) systems and repair
- GenAI application engineering
- Agentic systems with human approval gates
- LLM engineering: fine-tuning, evaluation, inference optimization
- AI security review (prompt injection, output safety)
- MLOps and data engineering for AI (pipelines, evaluation, serving)
- Analytics with decision impact (propensity, forecasting)

Out of scope for delivery: anything requiring capabilities the founder cannot
demonstrate on request. Positioning docs must not claim otherwise (§7).

## 4. What Counts as a "Paying Client"

A client counts toward the 3-client objective **only when all three hold**:

1. **Independent buyer** — an arm's-length external party (not the founder,
   a friend doing a favor, or a related entity).
2. **Agreed paid scope** — a written (email is fine) statement of work,
   fixed bid, or hourly engagement with agreed compensation.
3. **Founder-confirmed payment evidence** — the founder has personally
   verified a payment, deposit, or escrow release.

**Signed revenue ≠ cash collected.** The funnel tracks both:

- `signed` — contract/SOW agreed, invoice issued.
- `collected` — funds received and reconciled by the founder.

The 90-day objective is evaluated on clients with **collected** payment;
checkpoints report both figures and the gap between them (see
[AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md), observer
signal `cash_vs_contract_gap`).

## 5. Non-Goals

Explicitly out of scope for the 90-day window:

- **Building a SaaS product.** Services only; no product development sprints.
- **Autonomous outreach.** No agent sends anything externally, ever.
- **A web-scraping empire.** Collection breadth is not a goal; a small set of
  policy-approved sources beats an unreviewed crawl fleet.
- **Hiring or subcontracting** before client #3 is collected.
- **Paid advertising** as a primary channel.

## 6. Founder Decision Rights

The founder exclusively decides:

1. All external communications (messages, proposals, applications, posts)
2. Account creation and credential management on any platform
3. Pricing, discounts, and payment terms
4. Contracts and legal commitments
5. Source activation/deactivation (policy reviews → AWAITING_FOUNDER)
6. Policy overrides, including any exception to this document
7. Purchases of tools, data, or services
8. Acceptance of new clients and delivery commitments

Agents may *recommend* on any of these; agents may never *execute* them.

## 7. Safety Rules

Hard rules enforced in code where possible, in policy everywhere:

1. **No auto-send.** The proposal pipeline ends at `PROPOSAL_DRAFTED`; moving
   to `CONTACTED` requires a founder-performed external action (tested in
   `tests/test_core.py::test_no_agent_external_communications`).
2. **No scraping prohibited sites.** Sources live or die by
   [SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md);
   LinkedIn automation is PROHIBITED, Upwork is MANUAL_ONLY.
3. **No credential exposure.** Secrets stay out of prompts, logs, memory,
   audit payloads, and git ([IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md)).
4. **No false claims in proposals.** Drafts may only reference verified
   proof assets; unverifiable claims are stripped by the proposal-quality
   review ([HARNESS_AND_SKILLS_PLAN.md](HARNESS_AND_SKILLS_PLAN.md), skill
   `proposal-quality`).
5. **No destructive local operations** without checkpoint
   ([OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md)).
6. **No policy self-authorization.** Agents cannot upgrade a source's access
   policy; only the founder can (observer signal `policy_self_auth`, tested
   in scenario 17 of [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md)).

## 8. Legal Gates

Before the **first paid engagement**, the founder must confirm:

- [ ] **Employment status** — no non-compete, moonlighting clause, or
      employer IP claim covers independent AI/ML consulting (OQ-1, BLOCKING).
- [ ] **IP originality** — all proof assets offered to clients are owned or
      licensed; no employer-derived code or data.
- [ ] **Contract baseline** — a simple SOW template covering scope, IP
      assignment, confidentiality, and payment terms.
- [ ] **Invoicing capability** — a way to issue invoices and receive payment
      (bank/processor) consistent with local tax obligations.

No proposal may be submitted externally until the first two boxes are checked.

## 9. Success Metrics and Checkpoints

| Metric | Day 30 | Day 60 | Day 90 |
|---|---|---|---|
| Leads in pipeline (DISCOVERED+) | ≥ 30 | ≥ 60 | ≥ 90 |
| Founder-verified (VERIFIED+) | ≥ 8 | ≥ 20 | ≥ 30 |
| Proposals drafted | ≥ 15 | ≥ 30 | ≥ 45 |
| Proposals sent (founder-sent) | ≥ 8 | ≥ 18 | ≥ 25 |
| Qualified conversations | ≥ 2 | ≥ 6 | ≥ 10 |
| Clients signed | 0–1 | 1–2 | 3 |
| Clients collected | 0–1 | 1–2 | 3 |

Checkpoints at days 30/60/90 (`python -m acqsys checkpoint {30,60,90}`) feed
the observer's RCA loop; missed gates trigger strategy review, not silent
slippage ([EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md)).
