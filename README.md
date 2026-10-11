# AI Client Acquisition Mission Control (MVP v0.1)

**AI-first, founder-governed, locally hosted, no mandatory paid subscriptions.** Built for a technical founder seeking a first three paying AI/ML customers. It is a functioning prototype, not a deployed acquisition SaaS and not a guarantee of leads.

## What currently works

1. Local HTML dashboard and REST API (FastAPI).
2. Two distinct intake types: **explicitly advertised projects** and **potential accounts** (unconfirmed need).
3. Founder-added opportunities with provenance, source URLs, deduplication, category classification and conservative scoring.
4. Authorized **Brave Search API** integration when `BRAVE_API_KEY` is provided. Search snippets are candidates, **not proof that a customer is hiring**.
5. **Freelancer.com official API** integration using an OAuth token and the optional official Python SDK. *Adapter not tested against live API due to no credentials; result format/version may require adjustment.*
6. Generic public RSS/Atom import, **only after checking site-specific permission**.
7. Positioning agent: categorizes discovered demand, distinguishes published requests and potential buyers, records its own analysis events.
8. Proposal agent: produces a cautious editable draft that cannot be sent automatically.
9. Optional **local Ollama** reasoning agent; analyze a lead without paid model APIs, separately labels hypotheses, and logs model use.
10. Supervisor agent: reviews local leads and evidence-backed memory, creates founder tasks, records decisions, and runs the day-30 checkpoint.
11. Founder-approved lead progression (payment evidence required to count a paid client).
12. Manual activity logging for calls, messages, buyer objections, decisions and milestones.
13. Durable task records, source-linked memory, artifact versions, timestamped append-only-style audit log with a SHA-256 hash chain, and day-30/60/90 checkpoint diagnoses.
14. Automated tests validating critical gates.

**Not implemented:** autonomous live buyer verification, autonomous client communications, live payment validation, website-specific scraping, contracts/invoices, robust contact enrichment, production security, automatic cloud deployment, or any guarantee of new jobs. These require external access, permissions, engineering and/or human judgment. A founder-entered payment reference is an attestation, not bank verification.

## Quick start

Python 3.10+ recommended. Run in a terminal within this directory.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m acqsys init
python -m acqsys serve
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m acqsys init
python -m acqsys serve
```

Open **http://127.0.0.1:8765**. Nothing is sent to customers, no external costs are triggered just by launching.

### First lead (example is synthetic, not a real opportunity)

```bash
python -m acqsys add --title "Example: AI model evaluation" --url "https://example.org/jobs/demo-001" --description "We need model evaluation and monitoring" --type EXPLICIT_PROJECT
python -m acqsys leads
python -m acqsys positioning
python -m acqsys supervisor
python -m acqsys audit-verify
python -m acqsys checkpoint 30
```

Use **your actual opportunity URL** for production records, and verify the buyer before contacting them. The example URL is deliberately hypothetical.

## Optional integration 1: Brave Search

Requires a Brave API account and key. We have not purchased any service or made live API requests in this environment. Brave lists API search pricing and periodically offered usage credits; confirm its current terms and credit-card requirements yourself.

Linux/macOS:

```bash
export BRAVE_API_KEY="your_private_key"
python -m acqsys brave --type EXPLICIT_PROJECT
python -m acqsys brave --type POTENTIAL_ACCOUNT
```

Windows PowerShell:

```powershell
$env:BRAVE_API_KEY="your_private_key"
python -m acqsys brave --type EXPLICIT_PROJECT
```

Default discovery covers ML, NLP, CV, GenAI/RAG, agentic AI, LLM engineering, data platforms, and AI-related business services. It is **not** a crawler of every marketplace. Searching a web index does not give permission to scrape target pages.

## Optional integration 2: Freelancer.com authorized API

Confirm your developer account/API permission, then:

```bash
pip install freelancersdk
export FREELANCER_OAUTH_TOKEN="your_private_oauth_token"
python -m acqsys freelancer "machine learning"
```

Official SDK example: <https://github.com/freelancer/freelancer-sdk-python/blob/master/examples/search_projects.py>. OAuth permissions and result serialization may vary. Do not assume that possession of an SDK automatically authorizes all actions.

## Optional integration 3: Approved RSS/Atom

```bash
python -m acqsys rss 'https://a-permitted-public-feed.example/rss' --approved
```

This command performs one feed retrieval; the founder's `--approved` means **you checked the provider's policy**. It does not override provider restrictions. The parser limits feed size and entries. No login bypassing, CAPTCHA solving, or anti-bot evasion is included. **Do not use this for Upwork: Upwork RSS is discontinued.**

## Optional integration 4: local AI analysis using Ollama

Install Ollama separately, pull a model you are allowed to use locally, and start the Ollama service. Then:

```bash
export OLLAMA_MODEL="your-installed-model-name"
python -m acqsys serve
```

Use the **Analyze** button next to an opportunity. It calls a locally running model at `http://127.0.0.1:11434`, stores the resulting hypothesis report as an artifact and logs the run. The model gets no tools for sending messages, altering deal states, accessing financial accounts or scraping websites. There is no external LLM requirement for the rest of the MVP.

## Supervisor with persistent memory

```bash
python -m acqsys supervisor
python -m acqsys checkpoint 30
python -m acqsys checkpoint 60
python -m acqsys checkpoint 90
```

Run once manually or, **only if you want a long-running local process**, use:

```bash
python -m acqsys.scheduler --every-hours 24
```

Scheduler limitations: this process must stay running, and it only creates tasks/recommendations from leads already in the system. It will not independently discover new buyers or send outreach. This is intentional; add controlled collection jobs once providers and usage permissions are configured.

## Audit model

Each meaningful state-changing action (source request/response, candidate created/duplicate, human verification, stage change, proposal artifact, memory write, supervisor decision, manual activity and connector failure) produces an audit event. Each event includes:

- Event ID, UTC timestamp, actor, action, target and correlation ID
- Structured details, previous event hash and current SHA-256 hash
- Result of validation and approval, captured as successful action or control denial

The audit hash chain is **tamper-evident, not tamper-proof**. A privileged attacker with local filesystem access could replace the entire database; production deployment requires encrypted storage, access isolation, external append-only backups, and off-host hash anchoring.

The application avoids storing unnecessary personal details. Don't import confidential client information or sensitive personal data without lawful permission and appropriate protections.

## Founder-controlled lead states

`DISCOVERED -> VERIFIED -> QUALIFIED -> CONTACTED -> REPLIED -> DISCOVERY -> PROPOSED -> NEGOTIATING -> WON` (plus branch states, proposal drafting, rejection or loss).

Only the founder can verify a buyer or approve meaningful external/commercial steps. `WON` requires the founder to record a payment reference. The system does not independently confirm settlement.

## Production security priorities

- Keep dashboard bound to `127.0.0.1` (default). **Never expose unauthenticated demo endpoints to the public internet.**
- Configure `ACQ_ADMIN_TOKEN` if using the API beyond personal localhost testing; add TLS, sessions, authorization and rate limits before any shared/cloud deployment.
- Apply encrypted backups and rotate secrets. No API keys should be committed.
- Apply strict allowlists, vendor terms and rate limits to each external source; DNS-checking alone is not complete SSRF protection, so feed fetching needs further hardening before running against untrusted user-supplied URLs in production.
- Authenticate provider webhook events and never trust external text as agent instructions.

## Platform permissions (verified source examples)

- Freelancer official API: <https://developer.freelancer.com/> and <https://github.com/freelancer/freelancer-sdk-python>
- Upwork automation approval: <https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly>
- Upwork RSS discontinued: <https://support.upwork.com/hc/en-us/articles/52052528243731-RSS-deprecation>
- Fiverr terms: <https://www.fiverr.com/legal-portal/legal-terms/terms-of-service>
- LinkedIn automation restrictions: <https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software>
- Brave API: <https://brave.com/search/api/>

## Tests

```bash
pip install pytest
python -m pytest -q
```

Source expansion is tracked in `source_registry.json`. A row in the registry is a **research target**, not a working API connector or proof of current opportunities.

## 30-day build-and-sell program

- **Days 1–7:** Start UI, log real buyer/project sources, set two current offers, verify first 10 candidate opportunities, draft and founder-send tailored approaches using provider-approved channels.
- **Days 8–14:** Add access to one compliant high-yield external source, record 15–20 more candidates, verify, qualify and pursue meetings. Positioning agent identifies demand categories, founder checks evidence.
- **Days 15–21:** Review response funnel and buyer objections, refine offers, prepare demos only for qualified demand. Enable optional local Ollama analysis.
- **Days 22–30:** Make 30-day evidence-based decision: if discovery is low, broaden permitted sources; if leads exist without responses, improve positioning; if proposals fail, investigate scope, credibility, economics.

**Outreach should begin on Day 1, not when V1 is feature-complete.**

## Included October 10, 2026 research candidates

The archive contains `lead_candidates_2026-10-10.json`, a dated list of **10 real publicly indexed opportunity links**, primarily from Upwork. These are **unverified candidates**, not guaranteed available jobs, winning proposals or validated buyers. Their titles, short scopes and posted budgets come from public search results at the research date; details may change. The public job links should be revisited manually before applying on the platform.

```bash
python -m acqsys import-json lead_candidates_2026-10-10.json
python -m acqsys leads
python -m acqsys supervisor
```

The import logs source URLs and duplicate decisions, assigns cautious heuristic scores and records an audit event for each candidate. **Do not infer a high likelihood of winning from an automated score.** Some candidates are intentionally low-budget or beyond current founder capacity to validate filtering behavior; such leads should often be rejected or negotiated into paid discovery only.
