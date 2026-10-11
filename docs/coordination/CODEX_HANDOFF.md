# Codex P0 handoff — 2026-10-11

## Revision and scope

- Root: `C:\Users\PC\Desktop\acq-codex`; branch: `feat/codex-p0-controls`.
- Base SHA: `3053fd7011d0a946a0dc649308d247999b11fc0d`.
- Interface contract commit: `cf55774cc7d49378e28f6dc5325452cce5d6f585`.
- Verified implementation HEAD before this handoff: `4ae6f81d4a5becac0a577c452720dc37449a7ea5`. The handoff commit's own SHA is available with `git log -1 -- docs/coordination/CODEX_HANDOFF.md` (a committed file cannot contain its own hash).
- Committed implementation paths: `acqsys/core.py`, `acqsys/app.py`, `acqsys/agents.py`, `acqsys/__main__.py`, `tests/test_core.py`, `docs/coordination/INTERFACE_CONTRACT.md`; this handoff adds `docs/coordination/CODEX_HANDOFF.md`. The supplied `.team/` directory remains untracked and was not modified or committed. No Kilo-owned path was edited.

## Implemented and verified

- API read and write routes except `/api/health` require `X-Admin-Token` matching configured `ACQ_ADMIN_TOKEN` (minimum 16 characters). Unset/wrong token fails closed; mutating auth denials are audited. Core founder-only decisions require `founder_session(token)`; request `actor` cannot confer authority. CLI founder commands use the same token. Dashboard token remains in the page input, not local storage.
- `CorePolicyPort().authorize(source_id=..., action=..., target_url=...)` and `policy_check(...)` implement the v1 contract. Each decision is audit logged. Only active/pilot-running, founder-confirmed, unexpired, unrestricted, action-granted, host/path-matched sources with hourly budget may proceed. Messenger/application automation always denies. Brave, Freelancer and RSS check the persisted source policy before each request and use a pinned-IP HTTPS fetch with original TLS hostname, redirect rejection and response-size bounds. Returned search URLs do not inherit the API source's permission.
- Recursive audit redaction masks keyed secrets and credential-like text; lead descriptions and memory statements are stored redacted, with only hashes in their audit events. Credential query parameters are removed from stored lead URLs; URL userinfo is rejected. Historical audit rows remain unchanged and readable.
- Schema migration adds source policy version/scope/account/rate fields, rate usage, customer entities, lead-to-customer link, and commercial events. The paid KPI counts distinct founder-verified customer entities with an agreed scope and positive net founder-recorded payment, including partial refund accounting. A legacy `WON` flag or arbitrary payment reference alone does not count.
- Founder-only `APPLICATION_SUBMITTED`, `PROPOSAL_SENT`, contact, follow-up, reply, discovery, scope, receipt and refund events are recorded without sending anything. Founder manual activity maps relevant actions into commercial events. Checkpoints count actual recorded sends/proposals rather than infer them from stages.

## Verification

- Baseline before edits: `.\.venv\Scripts\python.exe -m pytest -q` → **26 passed**.
- Final focused and full regression (same suite): `.\.venv\Scripts\python.exe -m pytest -q` → **38 passed**, one upstream `starlette.testclient`/`httpx` deprecation warning.
- `git diff --check` passed before the implementation commit. Tests use temporary SQLite databases, fake API responses and dummy tokens; no client contact, real credentials or provider crawl occurred.
- Adversarial cases cover missing/weak/spoofed auth, unauthorized reads, source state/scope/expiry/account/rate denials, no-network connector denial, pinned-IP fetch, nested secrets and URL userinfo, migration of historical audit data, duplicate paid leads for one customer, partial/full refunds, and authenticated commercial/API flows. An independent read-only review found six issues; keyed-secret redaction, DNS rebinding, encoded traversal, existing-customer verification, refund accounting and read authentication were addressed.

## Interface and integration

- Kilo should inject a `PolicyPort` conforming to [INTERFACE_CONTRACT.md](INTERFACE_CONTRACT.md), call it immediately before every actual browser/API operation, and stop on `allowed=False`. Tests should use a fake port; production uses `core.CorePolicyPort`. Do not treat a login, a manual-only source, or a Brave/Freelancer result URL as crawl authorization.
- Built-in service IDs: `brave_search_api` at `api.search.brave.com` path `/res/v1/web/search`; `freelancer_official_api` at `www.freelancer.com` path `/api/projects/0.1/projects/active/`. RSS uses its separately registered source ID and exact reviewed host/path. Founder must register, review, confirm and activate each source through authenticated `/api/source-policies` routes before use; the JSON registry is not authorization. No source was activated during this milestone.
- Each existing lead acts as one deal and links to one `customer_entities` row. Kilo's `POTENTIAL_DEMAND` candidate maps to existing `POTENTIAL_ACCOUNT` and remains unverified until founder action. Migration runs through `core.init_db()` on an existing DB without rewriting old audit events. Integrate on a third test worktree after reviewing both branch handoffs; do not merge directly to `main`.

## Open issues and next action

- No live Brave/Freelancer/RSS smoke test or provider permission activation was performed. The Freelancer read-only endpoint follows the official SDK's `search_projects(active_only=True)` path, but response shape and account permissions still need a founder-authorized live check. The shared README, AGENTS and optional-requirements files still describe the older token/SDK workflow; coordinate edits after integration.
- Payment and independent identity evidence are founder attestations with references, not bank or legal-registry integrations. The founder must reuse one canonical customer key per organization. Historical `WON` rows require explicit evidence backfill before counting. Free-form private text cannot be perfectly classified by regex redaction; avoid importing confidential client material.
- Next commercial action: founder rechecks the dated candidate links in manual-only mode, confirms employment/IP gates and campaign start date, then records viable leads and actual outreach events. No outbound action was taken here.
