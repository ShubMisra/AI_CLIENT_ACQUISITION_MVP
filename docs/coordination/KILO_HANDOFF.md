# Kilo Handoff: Acquisition Browser Module

## Summary
HTTPS/global host checks, distinct per-card evidence, mandatory policy-checked resume with corruption handling, genuine historical-data failure handling, two cards from one HTML with distinct URLs, independent auth. 56 tests pass, Kilo CI present.

## Changes
- Policy: HTTPS-only, global IP/private host rejection, None/empty allowlists deny
- Browser: distinct per-card URLs and distinct content_evidence_ref per card; independent nav/extract auth; scheme/domain/host security
- Workflow: restore requires policy_check; corrupted checkpoints handled (reset safely); atomic persist failures raise RuntimeError
- Triage: real historical JSON required; missing/corrupt raise FileNotFoundError with context

## Commit
Branch: feat/kilo-acquisition-pilot
SHA: fbe116d59a10bca579382ddfdee6fccf1d66cc31

## Links
- Branch: https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/tree/feat/kilo-acquisition-pilot
- Draft PR #4: https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/4
