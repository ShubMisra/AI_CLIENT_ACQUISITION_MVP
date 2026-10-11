# AGENTS.md — AI Client Acquisition MVP

Operating rules for AI agents working in this repository. The human founder
approves every external action; agents never act externally on their own.

## Mission
Acquire **3 independent paying AI/ML clients within 90 days** with a solo,
part-time founder (~14 hrs/week). Revenue over infrastructure: engineering
hours must move leads toward paying conversations. Full constraints in
`docs/MISSION_AND_CONSTRAINTS.md`; sequencing in `docs/EXECUTION_PLAN_90_DAYS.md`.

## Scope
Lead discovery, qualification, proposal, conversion, and audit across ML,
NLP, CV, GenAI, RAG, agentic systems, LLM engineering, data/MLOps, analytics.

## Security Invariants (non-negotiable)
1. **No auto-send.** Agents never transmit proposals, messages, applications,
   or emails. Founder approves; founder sends.
2. **No unauthorized scraping.** Only sources confirmed in
   `docs/SOURCE_ACCESS_POLICY_REGISTER.md`; respect robots.txt and site terms.
3. **Founder gates all external actions.** Account creation, purchases,
   credentials, and policy overrides are founder-only decisions.
4. **SSRF protection.** Never fetch localhost/private-range/internal URLs;
   use the guarded HTTP client in `acqsys/agents.py`.
5. **Secret redaction.** Keys, tokens, and passwords never enter prompts,
   logs, memory, audit events, or git. Reference secrets by vault key ID only.
6. **Tamper-evident audit.** Material actions append to the SHA-256 hash
   chain in the `events` table. History is never mutated or deleted.

## Source of Truth
| Artifact | Role |
|---|---|
| `docs/` | Plans, specs, runbooks (this governance layer) |
| `data/acquisition.db` | Operational state: leads, events, tasks, artifacts |
| `source_registry.json` | Source catalog (to migrate into DB, backlog E5) |
| `offer_library.json` | Service offers with buyer profiles and proof needs |

## Test
```
python -m pytest -q
```

## Quick Start
```
python -m acqsys init
python -m acqsys serve
```
Default bind is 127.0.0.1 (localhost only). No credentials needed to start.

## Key Commands
| Command | Purpose |
|---|---|
| `init` | Initialize DB, seed registry + offers |
| `serve` | FastAPI dashboard/API on http://127.0.0.1 |
| `import-json <file>` | Bulk-import lead candidates from JSON |
| `add` | Record a single lead manually |
| `brave` | Brave Search API discovery (needs BRAVE_API_KEY) |
| `freelancer <query>` | Freelancer.com API discovery (needs OAuth) |
| `rss <url> --approved` | Fetch a founder-approved RSS/Atom feed |
| `draft <lead_id>` | Generate proposal draft (never auto-sent) |
| `verify <lead_id> --note` | Record founder verification of a lead |
| `transition <lead_id> <status>` | Move lead through 12-state lifecycle |
| `leads` | List leads |
| `positioning` | Rank offers against a lead |
| `supervisor` | One local observation/drafting cycle |
| `checkpoint <30|60|90>` | Save a campaign checkpoint |
| `audit-verify` | Re-verify audit hash-chain integrity |
| `stats` / `sources` | Funnel statistics / source catalog |

## Escalation
Anything not covered here: stop, checkpoint state, and surface the decision
to the founder. Never guess on policy, money, identity, or external actions.
