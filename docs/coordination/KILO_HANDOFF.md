# Kilo Handoff: Acquisition Browser Module

## Summary
Permission-aware, action-oriented acquisition module (new files only). Default-deny, fixture-based extraction producing non-empty candidates, durable checkpoint restore with policy revalidation semantics, triage reads real historical candidates when present.

## Implemented
- PolicyPort/AccessDecision + DenyAllPolicy (default-deny) + AllowFixturePolicy (subdomain-aware, policy_version)
- BrowserWorker with fixture loading, domain bounds, permission checks, non-empty candidate extraction
- Source intelligence scaffold, lead qualification/dedup, HITL queue
- Redacted audit, metrics counters
- WorkflowState with checkpoint/restore (latest/specific), persisted state
- CLI triage reads historical candidates from data/fixtures; falls back to 10 items (all UNVERIFIED, current_opening UNKNOWN)
- AcquisitionWorker orchestrator; audit_events exposed

## Tests
40 passed (26 existing + 14 acquisition-related). New tests: policy gating, fixture extraction non-empty, worker triage/discovery, audit redaction, metrics, HITL, workflow restore, deny-all default.

## Commit/branch
Branch: feat/kilo-acquisition-pilot
Commit: (to be added after push)

## Evidence
- Non-empty fixture extraction verified; worker returns candidates when authorized
- DenyAll blocks by default; negative cases covered
- Checkpoint restore (latest and specific) with state persistence
- Triage returns unverified candidates with current_opening UNKNOWN
- No edits to core.py/app.py/agents.py or existing Codex-owned tests

## Next
Await Chief Architect review; integrate to Codex PolicyPort contract as published; expand fixture coverage if approved.
