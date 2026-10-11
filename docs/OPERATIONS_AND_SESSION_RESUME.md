# Operations and Session Resume

> The runbook: start, operate, pause, resume, recover. Written for a founder
> with 2 spare hours and an AI agent with none of its previous context.
> Cross-references: `AGENTS.md` (commands) ·
> [EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md) (what to do next) ·
> [AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §9 (backup) ·
> [HARNESS_AND_SKILLS_PLAN.md](HARNESS_AND_SKILLS_PLAN.md) §7 (context loading)

## 1. Startup Runbook

```powershell
# First time (or after a fresh clone/copy)
python -m acqsys init        # creates data/acquisition.db, seeds registry + offers

# Every session
python -m acqsys serve       # dashboard + API on http://127.0.0.1 (localhost only)
```

- **No credentials are needed for basic operation** — import, triage, draft,
  verify, transition, checkpoint, and audit all work offline.
- The `.venv`/`.venv-1` interpreters both run the suite; `.venv-1` has pytest
  installed (`python -m pytest -q` → 18 passed).

### Optional configuration (`.env`, secrets — see
[IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md))

| Variable | Purpose | Required? |
|---|---|---|
| `BRAVE_API_KEY` | Brave Search discovery | No — manual mode suffices |
| `FREELANCER_OAUTH_TOKEN` | Freelancer API connector | No — enables E9 |
| `OLLAMA_MODEL` | Local LLM research assist | No — opt-in only |
| `ACQ_ADMIN_TOKEN` | Guards mutating API endpoints | Recommended once dashboard is used daily |

Secrets belong in the vault, not in `.env`; `.env` carries non-secret config
only once E7 lands.

## 2. Source Onboarding Runbook

1. **Discover** — propose a source (observed demand gap); record in the
   register as UNKNOWN.
2. **Evaluate policy** — ToS/robots analysis with citations
   ([SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md) §3
   template); status → AWAITING_REVIEW → AWAITING_FOUNDER.
3. **Founder decision** — ACTIVATE (ONBOARDING → PILOT_READY → ACTIVE),
   MANUAL_ONLY (CASE-001 posture), or REJECTED. Founder-only, always
   ([BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) SM-1).
4. **Activate or manual-only** — automated sources get connector config +
   rate limits; manual sources get a human-reading cadence and the manual
   intake path for captured leads.

## 3. Supervisor Restart

```powershell
python -m acqsys.scheduler --every-hours 24   # periodic supervisor cycle
python -m acqsys supervisor                   # one manual cycle on demand
```

The supervisor is observer-only: it reads state, uses memory, proposes tasks
(deduplicated — tested), and never performs external actions.

## 4. Session Resume Checklist (fresh context protocol)

1. **Mission status** — `GET /api/dashboard` (or `/mission-status`): phase,
   funnel counts, checkpoint deltas, open observer signals.
2. **Open tasks** — `GET /api/tasks`: HITL approvals, founder actions, stuck
   items; anything WAITING_FOR_HUMAN comes first.
3. **Lead pipeline** — `GET /api/leads`: new since last session, aging leads
   (>10 days without transition = observer flag).
4. **Audit integrity** — `python -m acqsys audit-verify`: must report valid;
   a broken chain means suspected tampering → quarantine + restore
   ([EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) scenario 16).
5. **Recent memory** — read the last handoff summary + active RULE-type
   memories; do not re-derive strategy from raw events.
6. **Next action** — taken from
   [EXECUTION_BACKLOG.md](EXECUTION_BACKLOG.md) execution order (C before E),
   adjusted by any observer signal from step 1.

Produce a **handoff summary** at session end (exported mission memory):

```json
{
  "objective": "3 paying AI/ML clients in 90 days",
  "current_phase": "Days 8-14 - First Live Connector",
  "what_worked": ["EXP-1A reply rate 2x", "2 RAG repair leads verified"],
  "blockers": ["OQ-2 Upwork connects purchase pending"],
  "next_action": "C4: founder submits 3 proposals; E9 OAuth setup",
  "proof": ["events 1021-1044", "checkpoint artifact ckpt_d10"]
}
```

## 5. Daily Brief (founder-facing)

`/daily-brief` or manual assembly: new leads since yesterday · proposals
awaiting founder send · buyer responses to log · HITL tasks due · observer
signals · today's single most important action (per backlog order).

## 6. Incident Recovery

1. **Identify failure** — symptom, component, blast radius (what state changed).
2. **Capture evidence** — relevant events (by correlation_id), task state,
   logs; never edit history.
3. **Isolate root cause** — classify `error_class`:
   `TRANSIENT | POLICY | BUG | EXTERNAL | HUMAN_CANCEL`.
4. **Repair** — smallest change that removes the cause; POLICY-class causes
   route to the register/founder, BUG-class to a test first
   ([EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) regression rule).
5. **Rerun tests** — `python -m pytest -q` must be green (18+ tests).
6. **Verify** — the failed operation re-executes cleanly in a scratch copy.
7. **Document lesson** — LESSON memory +, if reusable, an update to the
   relevant runbook section. Incidents touch the harness journal
   ([AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §3).

## 7. Backup and Restore

- **Backup (daily, E12):** SQLite online `.backup()` →
  `backups/acquisition-YYYYMMDD.db`; verify by opening read-only and running
  `audit-verify` against the copy; founder keeps one copy off-machine.
- **Restore:** stop writers → copy the latest verified backup to
  `data/acquisition.db` → `python -m acqsys audit-verify` → re-run the last
  checkpoint computation and compare with the stored artifact → any
  divergence logged as `RECOVERY_DIVERGENCE` and reconciled from event
  exports ([AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §9).
- **Drill:** monthly restore-into-scratch rehearsal; a failed drill blocks
  further writes until fixed (risk R6 response).

## 8. Quick Reference Card

| Situation | Command / action |
|---|---|
| Fresh machine | `init` → restore backup → `audit-verify` → `serve` |
| Morning start | `serve` → `/daily-brief` |
| New leads | `import-json <file>` or manual intake (CASE-001) |
| Draft a proposal | `draft <lead_id>` → founder reviews → founder sends manually |
| Buyer replied | `manual_activity` note → `transition <lead_id> REPLIED` |
| Weekly close | metrics vs gates → checkpoint decision → handoff summary |
| Anything unclear | checkpoint state → stop → surface to founder (AGENTS.md escalation) |
