# Kilo Handoff: Acquisition Browser Module

## Summary
Permission-aware acquisition module with deterministic multi-card fixture extraction, strict default-deny auth, atomic persisted checkpoints with cross-instance resume semantics, and triage loading the actual historical lead_candidates_2026-10-10.json (no fabricated fallback). Public API compatible with Codex PolicyPort.

## Implemented
- PolicyPort/AccessDecision, DenyAllPolicy (default-deny), AllowFixturePolicy (subdomain-aware, policy_version)
- BrowserWorker: independent authorization at navigate/extract; domain bounds; URL scheme validation; non-empty deterministic extraction
- Source intelligence scaffold, lead_qual (canonicalize, dedup, qualify)
- HITL queue, redacted audit, metrics
- WorkflowState: atomic (os.replace) checkpoint/restore (latest/specific), persisted state; supports fresh policy revalidation on resume
- CLI triage: loads lead_candidates_2026-10-10.json from root/data/fixtures (dedup by URL); preserves original evidence/budget fields
- Worker: discover_from_fixtures with dedup, metrics, audit events; set_policy to rebind after resume
- Fixtures: tests/fixtures/acquisition/listing/a.html, b.html; tests/fixtures/acquisition/lead_candidates_2026-10-10.json

## Tests
45 passed, 1 warning. Includes multi-card extraction (2 distinct listings), independent auth at nav/extract, triage loads real historical JSON, checkpoint atomic persist + resume with fresh policy, dedup/revocation, deny-by-default.

## Commit
Branch: feat/kilo-acquisition-pilot
SHA: TBD after push

## Notes
No edits to core.py/app.py/agents.py or existing Codex-owned tests. No live website access, credentials, or proposals. Extraction is fixture-driven by design.
