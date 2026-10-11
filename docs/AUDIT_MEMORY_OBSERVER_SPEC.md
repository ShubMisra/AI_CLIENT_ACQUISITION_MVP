# Audit, Memory, and Observer Specification

> What the system remembers, how it proves it hasn't lied, and how it notices
> when something is wrong. Cross-references: [AS_IS_AUDIT.md](AS_IS_AUDIT.md)
> §1.3 (tested audit invariants) ·
> [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §6 ·
> [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) scenarios 16–17 ·
> [OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md)

## 1. Current Event Schema (verified in `core.py`)

```
events(id, ts, actor, action, target_type, target_id, detail, prev_hash, hash)
```

- `detail` is a JSON payload; `hash = SHA-256(prev_hash + canonical(record))`
  forms a tamper-evident chain; `verify_audit()` recomputes the chain and
  `test_hash_chain_tampering_is_detected` proves tampering is caught.
- Events are append-only: no code path updates or deletes rows.

## 2. Extended Schema (backlog E6)

New nullable columns — additive, backward compatible:

| Column | Purpose |
|---|---|
| `correlation_id` | Groups events of one logical operation (e.g., a full discovery run) |
| `causation_id` | The event that directly triggered this one |
| `run_id` | Browser/connector execution run (SM-4) |
| `policy_version` | Source-policy snapshot version in force |
| `approval_id` | Links to the founder approval event, when one exists |
| `before_state` / `after_state` | Compact state diff (e.g., `"QUALIFIED"→"PROPOSAL_DRAFTED"`) |
| `error_class` | Bounded taxonomy: `TRANSIENT | POLICY | BUG | EXTERNAL | HUMAN_CANCEL` |
| `latency_ms` / `cost_cents` | Performance and (future) spend accounting |
| `retry_number` | Bounded retry accounting (max 2 per SM-4) |
| `agent_version` | Which agent revision acted |

Migration rule: new columns nullable with no default writes; existing 18
tests must pass unchanged after migration.

## 3. Two Journals, One Table

| Journal | Event classes | Examples |
|---|---|---|
| **Business runtime** | source, lead, proposal, approval | `LEAD_INGESTED`, `CRAWL_DENIED`, `OFFERS_MATCHED`, `APPROVAL_GRANTED`, `MANUAL_ACTIVITY`, `WON` |
| **Engineering harness** | task, test, review, incident | `TASK_CREATED`, `TEST_SUITE_FAILED`, `POLICY_REVIEW_COMPLETED`, `INCIDENT_INJECTION_DETECTED` |

Both append to the same hash chain (one chain = one truth). Distinguishing is
by `actor` (`business_*` vs `harness_*`) and `target_type`, so a single
`audit-verify` proves the whole history.

## 4. Memory Taxonomy

The `memory` table stores typed, evidence-bearing entries. Only the founder
verifies facts; agents propose
(`test_memory_evidence_and_no_agent_verified_memory`).

| Type | Definition | Rule |
|---|---|---|
| **FACT** | Verified observation with source | Requires founder verification + citation |
| **HYPOTHESIS** | Uncertain claim pending evidence | Must carry confidence < 0.9 and a falsification note |
| **LESSON** | Outcome-based conclusion from an experiment/checkpoint | Links to the events that justify it |
| **RULE** | Operating policy | Cites the governing doc section |
| **DECISION** | Founder or ADR decision with rationale | Immutable; superseded, never edited |

## 5. Memory Layers

1. **Evidence/provenance** — the events table itself (what happened).
2. **Hypothesis/insight** — distilled claims ("problem-specific proposals
   reply 2× more" — EXP-1 result as a HYPOTHESIS→FACT pipeline).
3. **Decision/experiment** — ADRs, offer experiments, checkpoint decisions.
4. **Operating state** — current phase, active offers, founder constraints
   (checkpoint summaries).
5. **Agent handoff summaries** — compact session context for a fresh agent
   ([OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md) §4).
6. **Semantic index (optional)** — FTS5 index over memory text; only if
   retrieval pain appears (YAGNI guard).

## 6. Observer: Anomaly Detection Signals

The supervisor/observer evaluates these on every cycle; each signal maps to a
task or warning, never an autonomous fix:

| Signal | Detection | Response |
|---|---|---|
| Stuck leads | No transition for >10 days in an active state | Task: founder review |
| Stale sources | Source untouched >30 days while ACTIVE | Task: re-validate or RETIRE |
| Low-yield sources | ≥20 ingested, 0 VERIFIED | Warning + channel re-rank proposal |
| Duplicate work | Same entity ingested twice across sources | Entity-resolution flag (E11); dedup tested today |
| High founder time | Founder-hour log >16 h/wk | Warning: cut lowest-yield channel |
| Cash vs contract gap | `signed` clients − `collected` > 0 for >14 days | Task: founder payment follow-up |
| Funnel drop-off | Stage conversion < half of Day-30 target | RCA trigger (below) |
| Policy self-auth attempt | Agent calls founder-only transition | Alert + deny (tested path) |

## 7. Redaction Rules

Never logged anywhere (events, memory, tasks, artifacts, logs):
passwords, tokens, OTPs, session cookies, payment credentials, buyer PII
beyond business-necessary fields (name/company/role only).

Credential-adjacent fields appear as `[REDACTED]` (pattern fixed in
[IDENTITY_AND_SECRETS_SPEC.md](IDENTITY_AND_SECRETS_SPEC.md) §5, and in
CASE-001's stored event in
[BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §4).

**Precision:** the hash chain is tamper-*evident*, not tamper-*proof* — it
detects any modification of recorded history but cannot prevent a local
attacker from rewriting the entire chain. Confidence rests on: single-writer
process, daily off-machine backup, and the impracticality of silently
rebuilding a consistent chain.

## 8. Retention and Compaction

- **Keep everything for 90 days** (the full campaign) — the dataset is small.
- **Compaction plan** (post-campaign or if size demands): events older than
  180 days fold into summary entries; the chain re-anchors with a
  `COMPACTION_ANCHOR` event that hashes the compacted digest. Raw detail is
  archived to an append-only export file first; summaries never delete
  business-relevant facts.

## 9. Backup and Recovery

- **Daily SQLite `.backup()`** to `backups/acquisition-YYYYMMDD.db` (E12) —
  the online-backup API gives a consistent snapshot while the app runs.
- **Recovery:** restore the latest backup; run `audit-verify` against it; the
  chain must validate (any gap = the backup itself is suspect; fall back to
  the previous one).
- **Checkpoint replay consistency:** after restore, re-run the checkpoint
  computation (`python -m acqsys checkpoint 30|60|90`) and compare against
  the stored checkpoint artifact; divergence means events were lost —
  reconstruct from the export archive and log a `RECOVERY_DIVERGENCE`
  incident
  ([OPERATIONS_AND_SESSION_RESUME.md](OPERATIONS_AND_SESSION_RESUME.md) §7).

## 10. RCA Mechanism (Observer → Experiment Loop)

Bottleneck → hypotheses → evidence gap → one experiment → founder approves →
execute → evaluate → keep/change/kill.

1. **Bottleneck** — an observer signal fires (e.g., funnel drop-off at
   VERIFIED→QUALIFIED).
2. **Hypotheses** — observer proposes ≤3 candidate explanations as HYPOTHESIS
   memories, each with a falsification check.
3. **Evidence gap** — identify the cheapest measurement that discriminates
   between them; if none exists, the experiment *is* the measurement.
4. **One experiment** — smallest change that tests the leading hypothesis
   (e.g., EXP-1 messaging A/B). Never more than one at a time per funnel
   stage — attribution must stay clean.
5. **Founder approves** — experiments touching external behavior are founder-
   gated like everything else.
6. **Execute → evaluate** — pre-registered metric and horizon; outcome written
   as a LESSON with links to the evidence events.
7. **Keep/change/kill** — the decision updates the strategy docs
   ([MARKET_POSITIONING_AND_OFFERS.md](MARKET_POSITIONING_AND_OFFERS.md) §5)
   and is never silently forgotten.

Scenario 17 of [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) exercises
this loop end-to-end at the Day-30 weak-funnel condition, including the rule
that the observer may not self-authorize policy changes.
