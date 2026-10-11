# Market Positioning and Offers

> What we sell, to whom, at what price, and how we learn fastest whether that
> is right. Cross-references: [AS_IS_AUDIT.md](AS_IS_AUDIT.md) §2.3 (the 10
> seeded leads) · [ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) ·
> [EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md)

## 1. Demand Clustering from the 10 Seeded Leads

Clustering of `lead_candidates_2026-10-10.json` (verified in
[AS_IS_AUDIT.md](AS_IS_AUDIT.md) §2.3):

| Cluster | Count | Evidence (leads) | Signal |
|---|---:|---|---|
| **RAG repair/relevance** | 4 | $50 fix PDF citations · $50 retrieval relevance/hallucination · $300 RAG assistant + agentic API · $700 RAG + classification + workflow | **Dominant pain.** Buyers already deployed RAG and it underperforms |
| **CV / edge ML** | 2 | $1,400 retail checkout tracking prototype · $1,000 local audio classification on edge | Prototype-stage, mid-budget, hardware constraints |
| **Forecasting** | 1 | $25,000 multi-channel demand forecasting | Outlier budget; enterprise-grade requirements likely |
| **NLP / classification** | 2 | $200 constrained recommendation engine · $50 sklearn text-classification micro-project | Small fixed-scope, fast turnaround |
| **Agentic assistant** | 1 | $500 Python AI customer assistant with web UI | Overlaps cluster 1's agentic thread |

**Strategic read:** the market that actually showed up is *broken AI that
needs fixing*, not green-field AI to be built. 4 of 10 postings are RAG
repairs, and two more (assistant, workflow) are RAG-adjacent. This directly
shapes the offer portfolio below — the repair-shaped offer is not a
convenience, it is the demand.

## 2. Offer Portfolio (four testable offers)

Each offer is a hypothesis with an owner (founder), a price band, a proof
requirement, and a kill/review rule. `offer_library.json` remains the
canonical technical catalog (10 offers); these four are the *commercial
packages* sold in month 1.

### Offer 1 — "AI Repair Shop" (primary)
| Field | Value |
|---|---|
| Pitch | Fix a broken or underperforming AI system (RAG retrieval, citations, hallucinations, classification quality) in a bounded engagement |
| Target buyer | Teams/staff whose RAG or ML system exists but disappoints (clusters: RAG repair, NLP quality) |
| Price band | **$500–$5,000** fixed, scoped by diagnosis |
| Proof needed | One reproducible before/after demo: broken retrieval → repaired retrieval with evaluation metrics (built independently, no client data) |
| Experiment | First 5 Upwork proposals on RAG-repair leads use this framing |
| Kill/review rule | Part of Day-14 messaging review; retire if 0 responses after 10 proposals |

### Offer 2 — "White-Label AI Partner" (leverage)
| Field | Value |
|---|---|
| Pitch | Agency retainer: we deliver AI/ML work packages behind the agency's brand |
| Target buyer | 10–50 person software/data agencies (from Clutch/GoodFirms manual lists) |
| Price band | **$75–150/hr** or milestone-priced packages |
| Proof needed | Independently built implementation examples with tests; a 1-page white-label terms sheet |
| Experiment | 20 cold outreach notes over 4 weeks (5/wk); measure reply rate |
| Kill/review rule | <2 replies from 20 sends → rewrite pitch once, then park until Day 45 |

### Offer 3 — "Paid Feasibility Assessment" (de-risker)
| Field | Value |
|---|---|
| Pitch | Fixed-price 1–2 week POC/feasibility study with a go/no-go recommendation and evaluation harness |
| Target buyer | Ops/product teams considering AI but unsure of feasibility (CV, forecasting, doc AI) |
| Price band | **$1,000–$5,000** fixed |
| Proof needed | A template feasibility report + one synthetic-dataset POC demo |
| Experiment | Attach to every larger lead that hesitates at price ($25k forecasting lead is the test case) |
| Kill/review rule | Review at Day 30: if never once selected, fold into Offer 1 as a phase |

### Offer 4 — "Opportunistic ML/CV/NLP" (catch-all)
| Field | Value |
|---|---|
| Pitch | Per-project delivery for well-specified small ML/CV/NLP jobs (clusters: CV/edge, NLP micro-projects) |
| Target buyer | Direct marketplace buyers with clear specs |
| Price band | Per-project, anchored to posting budget ($200–$2,500 typical) |
| Proof needed | Existing repo demos per category (`offer_library.json` proof fields) |
| Experiment | Default proposal mode for non-RAG leads |
| Kill/review rule | Reviewed only via aggregate proposal-response metrics |

## 3. Messaging Experiments

### EXP-1: Problem-specific vs generic proposals (Upwork)
- **A (treatment):** proposal names the buyer's exact failure mode ("citation
  mismatch in PDF RAG usually means chunk-metadata drift; here's the 3-step
  fix") — Offer 1 framing.
- **B (control):** competent generic proposal ("experienced ML engineer, here
  are relevant projects") — Offer 4 framing.
- **Design:** alternate A/B across the first 10 proposals; identical founder
  profile and rate. Metric: response rate within 7 days.
- **Decision (Day 14):** if A ≥ 2× B response rate, Offer 1 becomes the
  default opener; if indistinguishable, keep both and test price anchoring.

### EXP-2: Agency partnership cold outreach
- 20 notes over 4 weeks per the playbook
  ([ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) §5). Metrics: reply
  rate, call-booked rate. Decision at Day 30: ≥1 call → continue; 0 calls →
  park until referrals exist as social proof.

## 4. Pricing Hypotheses and Floor

| Offer | Opening price | Floor (below which we decline) | Rationale |
|---|---|---|---|
| AI Repair Shop | $750 scoped | **$200** | Below floor, diagnosis alone exceeds revenue |
| White-Label Partner | $95/hr opener | $60/hr | Agency rates must clear solo delivery overhead |
| Feasibility Assessment | $1,500 opener | $750 | 1–2 weeks of founder time minimum |
| Opportunistic | posting budget | $150 | Tiny jobs accepted only for review-material reviews |

Floor breaches require explicit founder override (decision right 6,
[MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md) §6). Tiny-budget
leads ($50 cluster) are accepted **only** when they double as proof assets or
relationship seeds — never more than 2 at a time.

## 5. Decision Rules

- **Day 14:** review EXP-1/EXP-2; re-rank channels
  ([ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) §4).
- **Day 30:** double down on the single offer with the best
  response-to-proposal rate; the other offers remain passive.
- **Retirement:** any offer/channel with **zero responses after 10 proposals**
  is retired for the campaign (log `OFFER_RETIRED` to the audit trail;
  reasoning in memory as a LESSON).

## 6. Portfolio Proof Requirements

Proof claims are tiered and must be labeled honestly in every proposal:

| Tier | Definition | Allowed claim |
|---|---|---|
| **T1 — Demo** | Built independently on synthetic/public data, reproducible in repo | "Here is a working demonstration of the approach" |
| **T2 — Client experience** | Delivered under a real engagement, referenceable or verifiable | "Delivered for a client in <domain>" |
| **T3 — Unverified** | Claimed experience without artifacts or references | **Prohibited in proposals** |

The proposal-quality skill ([HARNESS_AND_SKILLS_PLAN.md](HARNESS_AND_SKILLS_PLAN.md))
strips T3 claims. Until the first T2 exists, all proposals lead with T1 demos
— which is precisely what Offer 1/3 proof requirements are designed to
produce. This satisfies the no-false-claims safety rule
([MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md) §7.4).

## 7. Offer Library Extension Plan

`offer_library.json` stays the canonical catalog. When offers are traded
commercially, the following fields are added per offer at position time:
`commercial_package` (one of the 4 offers), `opening_price`,
`floor_price`, `experiment_tag` (EXP-1A/1B/2), and win/loss outcomes recorded
as manual activities on the lead — never invented by agents (test:
`test_proposal_does_not_send_or_invent_price`).
