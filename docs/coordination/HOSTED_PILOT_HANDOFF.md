# Issue #9 hosted mock pilot handoff — 2026-10-20

## Review target

- Isolated worktree: `C:\Users\PC\Desktop\acq-hosted-readonly`, branch
  `feat/hosted-readonly-pilot`, based on reviewed orchestrator commit
  `c27607c7767d5b090d71bd945a04228c696cd3e2`.
- [Draft PR #10](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/10)
  targets `feat/supervised-orchestrator`. PR #7 and the integration/Kilo
  worktrees were not changed or merged.
- Verified implementation head before this handoff:
  `25abea5096fe745e01d7bb0bc22aae5f559f67fe`. The final documentation
  SHA and its exact-head CI are recorded in PR #10 after this file is pushed.

## Delivered path

Simulated founder approval -> SHA-bound GitHub workflow -> pinned public
Python image and mock Codex script -> no-network, read-only container with
only three staged public files -> exact deterministic report and zero-usage
checks -> SHA-256 audit events and `ACCEPT_MOCK` -> STOP. Result status is
`MOCK_VERIFIED_READ_ONLY`, never `LIVE_VERIFIED_READ_ONLY`. The real workflow
template is outside `.github/workflows`, hard-disabled, and `run_real()`
always raises. No real Codex/Kilo invocation, provider call, credential,
customer data or model spending occurred.

Changed files in the implementation: `.github/workflows/hosted-readonly-mock.yml`,
`orchestrator/hosted_policy.py`, `orchestrator/hosted_offline.py`,
`orchestrator/hosted_mock_codex.py`, `tests/fixtures/hosted_public.json`,
`tests/test_hosted_offline.py`,
`docs/coordination/HOSTED_PILOT_SECURITY.md`, and
`docs/coordination/hosted-readonly-real.workflow-template.yml`. This handoff
is the additional documentation file.

## Exact verification at implementation head

- Local complete suite: **136 passed, 1 skipped** (Windows symlink creation
  unavailable), **1 upstream Starlette/httpx warning**. Compile and
  whitespace checks passed.
- [Hosted push workflow 39432211479](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39432211479):
  **success** at `25abea5096fe745e01d7bb0bc22aae5f559f67fe`, job
  `118659859021`; Linux log: **136 passed, 1 skipped** (Windows-only
  cancellation branch), one warning. The sanitized log reports
  `MOCK_VERIFIED_READ_ONLY`, `provider_calls: 0`, source SHA equal to the
  branch head and report SHA-256
  `af4998c281ec0753b6d909449ede711ca9fbeef3c36bf48bc3ba440daa8d4145`.
- [Hosted PR workflow 39432220335](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39432220335):
  **success** at the same PR head; job `118659894588`. It checked out the
  GitHub-generated merge SHA `4b9ed479dfca70943546311f5d12565a5f2e2170`
  and reported `MOCK_VERIFIED_READ_ONLY`, `provider_calls: 0`. Separate
  [Python PR checks 39432220293](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39432220293)
  also succeeded.
- The push run uploaded a sanitized `hosted-mock-result` artifact, ID
  `12268083535`, 1,140 bytes, digest
  `sha256:d2555fee068dae3d13aa36ba9d6f498e7aca511f2078cf34e136a72f6de7710c`,
  with one-day retention. PR run artifact ID `12268487437` was also uploaded.
  Artifact bytes were not independently downloaded in this session because
  the connector's storage endpoint was unavailable; job logs, artifact
  metadata and the deterministic verifier are the observed evidence.

The initial hosted attempts failed closed before artifact publication while
the sandbox's private-path read probe was being corrected. The final exact
implementation-head push and PR jobs above completed successfully. No failed
attempt made a provider call.

## Open activation blockers

The offline signer is an explicit simulation, and its SQLite ledger is local
to the ephemeral run. A real one-shot approval needs an external durable
transactional store and founder-controlled signature. The current image pins
Python plus a mock script, not a real Codex binary. Real CLI permissions,
model endpoint egress, credential separation, provider hard spending controls,
billed-USD reconciliation and post-cancel spend termination remain unproven.
The host uses network for checkout/dependencies/image/artifact; only the mock
container has `--network=none`. Hosted CI is not itself a complete live-agent
sandbox. See [security report](HOSTED_PILOT_SECURITY.md) for the founder
bootstrap and per-run activation checklist. PR #7's trusted-CI merge conflict
remains a separate review decision. No default-branch merge or live workflow
dispatch is requested.
