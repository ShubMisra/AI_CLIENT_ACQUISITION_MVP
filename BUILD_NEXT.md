# Implementation backlog and architecture decisions

## Core economic hypothesis

The system exists to discover, qualify and win **three independent paying AI/ML clients in 90 days**. Its purpose is not agent count, scraping volume, autonomous messaging volume or dashboard complexity.

## Build order by marginal value

**P0 — already implemented locally:**
- Provenance-linked lead intake, dedup and classification
- Explicit requests vs potential accounts
- Controlled optional official source adapters
- Conservative ranking, founder state gates and proposal drafts
- Audit trace, semantic memory notes, tasks, checkpoints and lightweight supervisor

**P1 — after genuine buyer samples exist:**
- Licensed search query planner with budget quotas and dedup across equivalent source links
- Freelancer official adapter live integration and regression tests
- Email-alert ingestion from an owned/authorized inbox, with provider-specific terms
- Entity resolution across company domains, multiple project URLs and contact roles
- Timed workflow queue using APScheduler or Celery, bounded retries and per-source rate budgets
- LLM evaluation harness and regression cases to measure classification, buyer-extraction and proposal truthfulness
- Local model ranker contextualized on real responses rather than assumed win scores
- First-week conversion dashboard with responses and meetings from manually logged activities

**P2 — once qualified demand converts:**
- Partner-intelligence agent with reasoned mapping of agencies to specialist delivery gaps
- Offer experimentation engine, A/B tests with small-sample safeguards
- Outreach review queue with consent, suppression and platform compliance records
- Delivery workbench, signed-scope intake and project acceptance test templates
- Monthly sales economics from recorded cash receipts, labor and acquisition costs

**P3 — after revenue:**
- Paid enrichment API, API quota monitoring and provider-specific permissions
- Secure production hosting, SSO, credential vault, append-only remote audit backup
- A/B-proven outreach templates, additional allowed sources, contractor access controls

## Agent responsibilities and tool boundaries

1. **Discovery Agent:** Calls only explicitly approved API/feed/search adapters; records candidate, source, query and timestamp. Cannot scrape unapproved sources.
2. **Verification Agent:** Produces a *provisional* evidence summary. Founder verifies identity and commercial intent. No invention of employer/buyer information.
3. **Positioning Agent:** Uses aggregate source signals plus founder-approved memory; evaluates services and two acquisition offers. No unsupported market-wide inference.
4. **Solution/Capability Agent:** Maps real needs to a catalog of independently demonstrable technical assets; highlights missing experience, data dependencies and evaluation risks.
5. **Proposal Agent:** Drafts accurate, scoped recommendations. Cannot promise price, send messages, or claim fabricated case studies.
6. **Supervisor/Observer:** Reads persistent memory, tasks, event log, lead stages; creates review tasks and records explicit hypothesis changes.
7. **Founder:** Approves external outreach, partner commitments, contract terms, payment claims, data access and hiring.

## Agent memory contract

Store three layers:
- **Operational events:** chronological immutable-style action trail; source of truth for what was done.
- **Evidence memory:** facts, hypotheses, sources and founder-verification flags; prevents unsubstantiated claims being promoted to facts.
- **Decision memory:** experiment hypotheses, actions, success criteria, results and lessons; supports observer RCA.

Never train on hidden/private client data without authorization; never store platform passwords as memory facts.

## Commercial segmentation and evidence

- **Supply partner track:** software shops, data consultancies, product studios, cloud integrators and boutique agencies. Need: hard-to-hire specialist AI capacity, bid preparation, risk assessment, delivery subcontracting. Offer: private white-label engineering work package.
- **Explicit demand track:** published ML, CV, RAG, agent, NLP, analytics, evaluation and deployment projects. Offer: fixed-milestone and technically scoped delivery.
- **Direct enterprise/startup account track:** companies with potential needs (not confirmed work); founder verifies buying intent. Offer: technical scoping and then a paid pilot if budget supports it.
- **Long-tail content track:** demonstrations and public technical proof, only after initial high-intent sales work.

## Acceptance criteria

- At least 95% of imported test URLs deduplicated correctly against normalized forms; manually verify false merges.
- 100% of accepted leads preserve original source, ingestion timestamp and demand type.
- 100% of founder-approved actions have a linked audit event.
- No automatic external messaging, contract signing, payment handling, or platform access policy bypass.
- Stage-based win count excludes non-paying or unverified deals.
- Every agent recommendation distinguishes evidenced facts and hypotheses.
- Every day-30/60/90 report identifies uncertainty, stage counts and suggested investigation.

## Root-cause decision logic (conservative)

- Ingestion failure -> inspect source authorization, adapter errors, quota, authentication, query relevance.
- Many discovered leads, few verifiable buyers -> change discovery sources and evidence requirements.
- Many verified leads, few approaches -> founder bottleneck; improve concise approval queue and proposal automation.
- Many approaches, few replies -> analyze target relevance and message; not simply send more.
- Calls without proposals -> buyer urgency/budget/authority may be weak.
- Proposals without wins -> analyze acceptance criteria, proof, terms, timing and competing options.
- Contracts without collected payment -> classify separately; do not prematurely count clients.
- Project overruns -> reduce WIP and scope, do not acquire obligations beyond founder capacity.

## Hard limitation

It is impossible to guarantee that broad internet scraping will identify every client/project; access limitations, indexing delays, legal policies and offline demand prevent completeness. Success requires a measured acquisition funnel, not a claim of full web coverage.
