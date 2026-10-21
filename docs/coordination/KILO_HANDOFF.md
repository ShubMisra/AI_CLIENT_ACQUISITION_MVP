# Kilo Handoff: Acquisition Browser Module

## Summary
Strict HTTPS-only, global host validation, safe absolute per-card URLs, independent authenticated_extraction auth, mandatory policy-bound resume, corrupted checkpoint handling, real historical missing/corrupt failure paths. 63 tests pass including deterministic negative security tests; Kilo CI present.

## Changes
- Policy: HTTPS-only; global IP/private host rejection; None/empty allowlists deny
- Browser: two cards with distinct absolute https URLs and distinct content_evidence_ref per card
- Workflow: restore requires policy_check; corrupted checkpoints reset safely; persist failures raise RuntimeError
- Triage: real historical JSON required; missing/corrupt raise FileNotFoundError
- Tests: tests/test_acquisition_negative_fixes.py added

## Commit
Branch: feat/kilo-acquisition-pilot
SHA: 9f64b19194084cd4d182ad43b010018affd37b48

## Links
- Branch: https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/tree/feat/kilo-acquisition-pilot
- Draft PR #4: https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/4
