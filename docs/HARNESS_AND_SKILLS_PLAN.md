# Harness and Skills Plan

> How the agent harness (subagents, skills, commands, permissions) is organized
> around the mission. Cross-references: `AGENTS.md` (root, operating rules) ·
> [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) ·
> [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) ·
> [OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md)

## 1. Verified Harness Capabilities

Present in the operating environment (verified 2026-10-10):

- **Subagents:** coding, research, verify, code-review, browser, debug —
  dispatched per task; each ends with a summary to the coordinator.
- **Memory system:** long-term memories + codebase knowledge modules, with
  search/fetch and explicit create/update/delete
  ([AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §4–5 maps
  DB memory to this).
- **MCP tools:** present in the environment; individual servers unverified —
  verify before first use, never assume capabilities.
- **Skills:** better-harness, canvas, create-plugin, create-skill,
  create-subagent, front-design, schedule, vercel-deploy (all invoked via
  slash command).

**Not present (verified):** no `.codex/` directory, no custom skills/commands
in the repo — everything below is *proposed*, to be created via
`create-skill`/`create-subagent` as backlog permits. Priority stays commercial:
skills are built only when they unblock C-tasks
([EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md)).

## 2. AGENTS.md

The root `AGENTS.md` is the load-bearing governance file: mission, scope, six
security invariants, source-of-truth table, test command, quick start, key
commands, escalation rule. Fresh sessions load it first; conflict resolution
is: `AGENTS.md` > docs/ plans > memory > improvisation.

## 3. Proposed Skills (12)

| Skill | Purpose | Permission tier |
|---|---|---|
| `source-discovery` | Propose new sources from observed demand gaps (never auto-add) | READ_PUBLIC + WRITE_LOCAL proposals |
| `source-access-review` | Draft the register review template with ToS/robots evidence | READ_PUBLIC + WRITE_LOCAL |
| `source-onboarding-hitl` | Drive SM-1 onboarding; raise AWAITING_FOUNDER tasks | REQUEST_FOUNDER_APPROVAL |
| `browser-research-permitted` | Run scoped read-only extraction per the HITL spec | READ_AUTHORIZED + WRITE_LOCAL |
| `lead-extraction-triage` | Normalize/classify/score new leads (existing tested path) | WRITE_LOCAL |
| `buyer-verification` | Assemble verification dossier for founder; founder confirms | WRITE_LOCAL + founder gate |
| `market-positioning` | Rank offers for a lead; maintain pricing hypotheses | WRITE_LOCAL |
| `proposal-quality` | Review drafts: no invented price, no T3 claims, structure per offer | WRITE_LOCAL |
| `approval-gates` | Package pending external actions for founder decision | REQUEST_FOUNDER_APPROVAL |
| `observer-rca` | Run the RCA loop; propose one experiment | WRITE_LOCAL + founder gate |
| `audit-validation` | Run `audit-verify` + redaction scans; report integrity | READ_AUTHORIZED |
| `session-resume` | Execute the resume checklist; produce handoff summary | READ_AUTHORIZED + WRITE_LOCAL |

Creation order follows the backlog: `lead-extraction-triage` and
`approval-gates` first (they serve C1–C4), browser skills last (E10+).

## 4. Proposed Commands (16)

| Command | Effect |
|---|---|
| `/mission-status` | Dashboard summary + checkpoint deltas + open blockers |
| `/discover-sources` | Propose + queue source candidates for review |
| `/review-source <id>` | Produce policy review draft for founder decision |
| `/activate-source <id>` | Founder-approved activation (founder-only) |
| `/collect-permitted <id>` | Run a permitted collection job within budgets |
| `/triage-leads` | Normalize/classify/score the intake queue |
| `/research-buyer <lead>` | Assemble public buyer dossier (redacted storage) |
| `/position-offer <lead>` | Rank offers + recommended package + price |
| `/draft-proposal <lead>` | Generate draft; ends at DRAFT, never sends |
| `/founder-approvals` | List pending approvals with evidence bundles |
| `/manual-intake` | CASE-001 flow: founder-supplied lead entry + audit |
| `/daily-brief` | Morning summary: new leads, tasks, responses, risks |
| `/checkpoint-30` | Run the Day-30 checkpoint + RCA report |
| `/audit-verify` | Chain integrity + redaction report |
| `/resume-paused` | Resume WAITING_FOR_HUMAN jobs after founder input |
| `/incident-rca <id>` | Structured incident analysis + lesson capture |

Commands are thin wrappers over skills + CLI; nothing new computes state —
the DB remains the only truth.

## 5. Tool Permission Tiers

| Tier | Grants | Examples |
|---|---|---|
| `READ_PUBLIC` | Fetch public pages/APIs within register scope | source research |
| `READ_AUTHORIZED` | Read local DB, vault key IDs (not values), audit | observer, resume |
| `WRITE_LOCAL` | Insert/update local DB rows, artifacts, tasks | ingestion, drafting |
| `REQUEST_FOUNDER_APPROVAL` | Raise HITL/approval tasks; wait | onboarding, proposals |
| `WRITE_EXTERNAL_FOUNDER_APPROVED` | Execute an externally-visible write — **reserved; nothing qualifies today** | none |
| `DENY` | Hard-deny regardless of context | auto-send, scraping prohibited sources, policy self-upgrade, secret exfiltration |

Default-deny: an action not covered by an explicit tier is DENY. The
founder-approval tier never escalates itself: approval tasks are created,
never self-answered.

## 6. Loop Engineering

Runaway agents are a real risk; controls:

1. **Iteration budgets** — every loop task carries `max_iterations` (default
   3); budget exhaustion stops with a checkpoint, not improvisation.
2. **Tests as loop guards** — after each implementation iteration run
   `python -m pytest -q`; a failing suite halts the loop
   ([EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md)).
3. **Failure classification** — errors map to `error_class` taxonomy
   (§2 above); only TRANSIENT retries (max 2, backoff).
4. **Independent verification** — work products that gate external actions
   (proposals, source reviews) get a second reviewer pass by a different
   subagent before reaching the founder.
5. **Regression suite** — the 18-test core suite is sacred; new features
   extend, never weaken, it.
6. **Kill switches** — any loop writing events faster than 60/min, or
   touching a DENY tier, is halted and audited; `/incident-rca` reviews it.

## 7. Context-Loading Strategy for Fresh Sessions

A fresh session loads, in order:

1. `AGENTS.md` (rules)
2. `/mission-status` output (where we are)
3. Open HITL/approval tasks (`/api/tasks`)
4. The one governing doc for today's work
   (e.g., [EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md) for implementation
   days, [ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) for outreach days)
5. Relevant memory entries (last handoff summary + active RULES)

Everything else is fetched on demand. No session should re-derive strategy
from scratch — the handoff summary exists precisely to prevent that
([OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md) §4).
