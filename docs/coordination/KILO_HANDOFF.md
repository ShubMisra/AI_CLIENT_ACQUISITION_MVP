# Kilo Handoff: Acquisition Browser Module

## Summary
Strict HTTPS/global host validation, safe absolute per-card URLs, independent authenticated_extraction auth, mandatory policy-bound resume, corrupted checkpoint handling, real historical missing/corrupt failure paths. 56 tests pass, Kilo CI present.

## Changes
- Policy: HTTPS/global IP, private host rejection, None/empty allowlists deny
- Browser: two cards with distinct absolute URLs and distinct content_evidence_ref per card; scheme/host security
- Workflow: restore requires policy_check; corrupted checkpoints reset; atomic persist failures raise RuntimeError
- Triage: real historical JSON required; missing/corrupt raise FileNotFoundError
- Tests/CI: negative/security coverage

## Commit
Branch: feat/kilo-acquisition-pilot
SHA: 153f98fb3f4284375c78181370d530f6b7c3af07

## Links
- Branch: https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/tree/feat/kilo-acquisition-pilot
- Draft PR #4: https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/4
