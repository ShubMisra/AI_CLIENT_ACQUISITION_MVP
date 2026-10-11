# Acquisition Strategy

> How demand is found, ranked, and converted into founder-led conversations.
> Cross-references: [MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md) ·
> [MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) ·
> [SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md) ·
> [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) ·
> [EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md)

## 1. Three Demand Pipelines

### P-A. Explicit demand (published projects)
Buyers who have already written down what they need and what they'll pay:
marketplace postings (Upwork, Freelancer.com), RFP portals, job boards,
"Hiring help" posts. **Highest intent, fastest feedback, most competition.**
This is the only pipeline with proven inventory in the repo (10 live Upwork
leads). Strategy: win small fixed-scope jobs fast to buy credibility and
referrals.

### P-B. Potential demand (agencies and companies)
Buyers with AI work but unstaffed capacity: software agencies holding client
requests they can't fill, SaaS teams with a stalled AI feature, data teams
without ML depth. **Slower to open, higher contract value, repeatable.**
Strategy: white-label partnership pitch (offer `agency_ml_capacity`), sourced
from Clutch/GoodFirms directories (manual reading only) and founder research.

### P-C. Offline/manual demand (network and referrals)
Direct contacts, past colleagues, community acquaintances, referrals from
delivered work. **Smallest volume, highest trust, best close rates.** Strategy:
founder sends 5 personal notes in week 1; every delivered project generates an
explicit referral ask (scripted in
[EXECUTION_PLAN_90_DAYS.md](EXECUTION_PLAN_90_DAYS.md) §4).

Pipeline weighting by phase: Days 1–30 ≈ 70/20/10 (A/B/C); Days 31–60 ≈
50/35/15; Days 61–90 ≈ 40/35/25 as referrals from delivered work compound.

## 2. Source Universe Map

Tiering from [SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md)
(32 registered sources; statuses live there, strategy lives here):

### Tier 1 — P0, activate first
| Source | Mode | Why first |
|---|---|---|
| Upwork | MANUAL_ONLY (no automation) | 10 real leads already identified; largest explicit-demand pool |
| Founder network | Manual | Zero policy risk, fastest first conversation |
| Freelancer.com | Official API (OAuth) | Code exists in `agents.py`; free tier; official SDK |
| Brave Search API | API key | Powers discovery across all other pipelines |

### Tier 2 — P1, second wave
| Source | Mode | Role |
|---|---|---|
| RSS/Atom feeds | Per-feed founder approval | Low-cost ambient monitoring of niche boards/blogs |
| Contra, PeoplePerHour, Guru | Manual / requires review | Marketplace diversification after funnel metrics exist |
| Clutch, GoodFirms | Public directory, manual reading | Agency prospect lists for P-B |
| LinkedIn | MANUAL_ONLY — automation PROHIBITED | Founder reads manually; never scraped |

### Tier 3 — P2, opportunistic
Toptal, Braintrust (screened networks), RFP portals (SAM.gov, TED, UNGM),
AI-specific job boards, YC/Wellfound directories. Review only if Tiers 1–2
stall at the Day-30 checkpoint.

### REJECTED outright (never, at any tier)
- Automated LinkedIn / Upwork / Fiverr scraping
- CAPTCHA evasion, anti-bot circumvention, stealth/farm accounts
- Mass email or automated messaging of any kind
- Buying lead lists of unknown provenance

Rationale: account bans destroy the primary revenue channel; ToS violations
create legal exposure; and the mission requires *founder-led* trust, which
spam corrodes. See [MISSION_AND_CONSTRAINTS.md](MISSION_AND_CONSTRAINTS.md) §7.

## 3. First Connector: Freelancer.com API

Selected as the first automated connector because:

1. **Code exists** — `agents.py` ships a Freelancer discovery path.
2. **Official route** — documented OAuth + official Python SDK
   (`search_projects`), so access is sanctioned, not scraped.
3. **Free tier** — no purchase decision required (constraint: no mandatory
   paid SaaS).
4. **Complementary** — different inventory than Upwork; immediate A/B signal
   on which marketplace yields qualified conversations.

Activation steps: founder registers an app → OAuth token stored via the
credential vault ([IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md))
→ `python -m acqsys freelancer "<query>"` smoke test → policy entry flipped to
CONFIRMED in the register → daily query schedule (respecting rate limits).

## 4. Channel Ranking by Expected Qualified-Conversation Yield

"Qualified conversation" = a live human exchange where the buyer confirms
budget, scope, and timeline. Estimates are hypotheses to be replaced by
observed data at the Day-14 review:

| Rank | Channel | Est. yield / wk* | Effort / wk | Confidence |
|---|---|---|---|---|
| 1 | Upwork manual (10 seeded + new) | 1–3 | 3 h | High — real postings exist today |
| 2 | Founder network | 0–2 early | 1 h | Medium — unknown until asked |
| 3 | Freelancer.com API | 0–2 | 0.5 h | Medium — inventory unverified |
| 4 | Agency outreach (Clutch/GoodFirms lists) | 0–1 | 2 h | Medium — longer cycle |
| 5 | RSS/boards ambient | 0–1 | 0.5 h | Low–medium |
| 6 | RFP portals | 0–1 / month | 1 h | Low — slow, high-friction |

\* Yield = qualified conversations, not raw leads. Reviewed and re-ranked at
Day 7 and Day 14; channels with zero responses after 10 proposals are retired
([MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) §5).

## 5. Agency Partnership Playbook (P-B)

**Offer:** white-label AI/ML engineering partner — the agency keeps the
client relationship; we deliver the AI work package behind the scenes
(`agency_ml_capacity` in `offer_library.json`).

**Target profile:** 10–50 person software/data agencies with AI-adjacent
client work, visible on Clutch/GoodFirms, no in-house ML lead.

**Cadence (founder-executed, ~2 h/week):**
1. Build a list of 20 agencies (manual directory reading; logged as manual
   leads with `demand_type=AGENCY_PARTNER`).
2. Prioritize 5/week by fit signals (AI case studies, hiring ML roles).
3. Founder sends a 5-sentence pitch: who we are, one concrete AI package we
   deliver, white-label terms, ask for a 20-minute call.
4. Log every send/reply as manual activity; never auto-follow-up more than
   once.

**Success metric:** ≥1 agency discovery call by Day 14; ≥1 active white-label
collaboration (even a small subcontract) by Day 60.

## 6. Client Acquisition Economics

Assumptions to be validated against real funnel data (updated at checkpoints):

| Parameter | Planning value | Basis |
|---|---|---|
| Proposals → qualified conversation | 20% | Marketplace norms, small sample |
| Qualified conversation → client | 30% | Founder-led, niche expertise |
| Avg. first engagement value | $800–$2,500 | Seeded-lead budget distribution |
| Founder cost/opportunity | ~1.5 h research+proposal | 14 h/wk model |
| Effective hourly value | $150–$500/hr-equivalent | Value ÷ hours |
| Referral coefficient | 0.3–0.5 per delivered client | Explicit ask, scripted |

Break-even on effort is trivial (3 clients × $1,500 ≈ $4,500 against ~40
founder-hours of acquisition work); the real constraint is **pipeline
throughput**, which is why the backlog prioritizes lead intake over
infrastructure ([EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md) Slice A).

Economics rule: if the Day-30 observed close rate is <10% from qualified
conversations, pricing or targeting is wrong — run the RCA loop in
[AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §6 before
sending more proposals.
