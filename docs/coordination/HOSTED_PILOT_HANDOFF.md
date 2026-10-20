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

## Issue #9 follow-up: three-role MOCK_ONLY handoff

The newer Chief Architect dispatch on Issue #9 asked for a compact coordination
proof. The existing `offline-mock` job remains the normal Codex success path.
Three additional ordered, ephemeral Actions jobs demonstrate the blocked path:
`coord-codex` emits a deterministic `BLOCKED` result after two simulated failed
attempts; `coord-kilo` accepts only that exact artifact and emits one
diagnostic-only finding; `coord-codex-resume` accepts only the exact finding,
runs the task-specific test at the checked-out SHA, and emits `VERIFIED`.

The single hash-chained `coordination-ledger.json` carries source SHA, run and
attempt, original Codex ownership, Kilo backup ownership, allowed public fixture
path, acceptance test, simulated founder approval, handoff reason, CI check,
and zero provider calls/cost. Each job stages only the fixture, pinned mock
role script, and fixed task JSON into the pre-existing no-network/read-only
Docker runner. Cross-job artifacts are validated byte-for-byte against the
expected state and SHA before the next role starts. Issue text or role output
never becomes shell or an executable task. The Kilo role cannot edit files or
take over Codex integration. `MOCK_ONLY` is present in every ledger and role
result; this is not a real CLI session or live model authorization.

Follow-up files: `.github/workflows/hosted-readonly-mock.yml`,
`orchestrator/hosted_offline.py`, `orchestrator/hosted_coordination.py`,
`orchestrator/hosted_mock_roles.py`, and `tests/test_hosted_coordination.py`.
Exact new commit SHA, complete test count, and push/PR workflow run links are
published in draft PR #10 after the final exact-head CI run.

### Verified follow-up implementation

- Implementation commit: `01e56d54e906f750383a21eae622b5a5637e3687`.
  Local full suite using the project venv: **152 passed, 1 skipped**, one
  existing Starlette/httpx deprecation warning. The system Python's user-site
  pytest was unavailable to the existing isolated verifier subprocess; using
  the project venv resolved that local environment issue.
- [Hosted push run 39448861234](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39448861234):
  **success at the exact implementation SHA**, including all four jobs.
  `offline-mock` ran the complete Linux suite: **152 passed, 1 skipped**.
  `coord-codex-resume` ran the selected coordination acceptance file:
  **16 passed**. Its log reported `MOCK_ONLY`, `VERIFIED`, source SHA equal
  to the implementation SHA, and `provider_calls: 0`.
- [Hosted PR run 39448870713](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39448870713):
  **success**, all four jobs; the PR checkout used GitHub merge SHA
  `58b9e3432aa1dd89ef94756fb1a4e66c40831281`. The separate
  [Python PR checks 39448870754](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39448870754)
  also succeeded.
- Push run final artifact `coordination-mock-verified` ID `12277463782`,
  one-day retention, digest
  `sha256:aa53f371aad8394ca923adc90128dc6be58240ff35d7be430a93cd13c3731024`.
  The blocked Codex and Kilo finding artifacts were uploaded as IDs
  `12276789361` and `12276079804`. Job logs and artifact metadata were
  inspected; the ZIP contents were not independently opened in this session.

This is an offline simulation only. The simulated founder flag and public
artifact chain cannot authorize or authenticate a live agent; the real
activation blockers above remain open. Chief Architect review is the next
decision. No real CLI, provider inference, secrets, spending, customer action,
or merge occurred.
