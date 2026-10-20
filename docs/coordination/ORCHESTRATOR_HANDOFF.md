# Supervised engineering orchestrator handoff — 2026-10-18

## Assignment and branch

Implement the bounded controller from [Issue #6](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/issues/6)
in `C:\Users\PC\Desktop\acq-orchestrator`, branch
`feat/supervised-orchestrator`, based on `9813c0ec0b998b9fb4d2ba297b4b0113d0a9a90e`.
No Kilo worktree or acquisition application file was changed.

## Review artifact

- Implementation commit: `19c222f3e9c9ecdaafa7febdf293bb826ce14f3c`.
- [Draft PR #7](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/7)
  targets `feat/codex-p1-integration` for an isolated review. No merge was made.
- [Push CI](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39110550843)
  and [PR CI](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39110566380)
  both completed successfully for implementation SHA `19c222f3e9c9ecdaafa7febdf293bb826ce14f3c`.
- Final handoff-only commit follows the implementation commit; its CI result is
  recorded in the PR checks and final review report.

## Executable delivery

- `orchestrator/policy.py`: trusted task schema; founder, GitHub issue,
  branch/SHA/worktree, path, acceptance-test and autonomy gates.
- `orchestrator/store.py`: separate SQLite task/run/log/checkpoint/decision
  history, SHA-256 event chain, atomic concurrency and daily budget reservations.
- `orchestrator/runners.py`: distinct fixed Codex/Kilo CLI command plans,
  fail-closed live executor, toy fixture runner, read-only Git verifier.
- `orchestrator/github.py`: bounded GitHub issue queue, SHA, CI, issue-comment
  and draft-PR calls; no merge operation.
- `orchestrator/architect.py` and `instructions/chief_architect.md`: official
  Responses API boundary with external instructions and persisted review
  decisions; real API use disabled, mock review active.
- `orchestrator/controller.py`, `web.py`, `__main__.py`: one-run supervised
  state machine, founder dashboard, pause/reject/start/publish/emergency gates,
  loopback-only server.
- `tests/test_orchestrator.py`: offline toy-repository cycle and adversarial
  cases. `.github/workflows/ci.yml` runs the full suite on this branch;
  `.github/workflows/orchestrator-dry-run.yml` provides a manual mock-only
  workflow. `orchestrator/README.md` is the operating and enable/disable guide.

## Verification and observed limits

- Pre-change regression: `python -m pytest -q` → **58 passed**.
- Focused controller tests: `.\.venv\Scripts\python.exe -m pytest -q tests/test_orchestrator.py`
  → **16 passed**. Full regression: `.\.venv\Scripts\python.exe -m pytest -q`
  → **74 passed**, one upstream Starlette/httpx deprecation warning.
  `python -m compileall -q acqsys orchestrator tests` and `git diff --check`
  passed. Push and PR CI passed at the implementation commit above.
- Mock cycle: one founder-approved toy issue routes to its owner, makes a
  scoped toy commit, checks acceptance test identity and mocked CI, records
  independent review, then creates a draft PR only after founder approval.
  No model call, marketplace access, buyer contact or real GitHub issue/PR
  was made by that test. Observed model spend: **$0**.
- Negative tests deny absent approval, wrong label/author, closed issue,
  changed SHA, unsafe path/command, wrong worktree, excess budget, missing
  credentials, untrusted CI check, and unattended mode. Concurrency is two
  overall and one per owner. Audit mutation is detected.
- Live CLI remains disabled. In this shell `codex --version` reported
  `0.162.0-alpha.17.2`, differing from the stated `0.163.0`; the installed
  Kilo wrapper could not start because `node` was not on `PATH`. No CLI model
  inference or real API key was used. Codex/Kilo command plans are unexecuted.

## Open issues and integration requirements

The mock GitHub/CI cycle proves controller policy, not real GitHub task
execution. A live runner still needs an approved OS sandbox, sanitized
worktree, protected CI configuration, scoped credentials, metered model cost,
process cancellation and Kilo permissions review. The current dashboard is
local-only and the SQLite hash chain cannot resist privileged DB replacement.
Free-form log redaction is limited. No unattended mode or merge path exists.
Founder and Chief Architect review is required before any live activation.

## Follow-up to Chief Architect review 5562089579

The [review](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/7#pullrequestreview-5562089579)
accepted the earlier mock prototype and withheld live-agent and merge approval.
This follow-up remains mock-only on `feat/supervised-orchestrator`.
Implementation commit: `15c4696f632af8bf4b5d5c7fbc0d117a27369995`.

- **Trusted CI:** `orchestrator/github.py` now requires workflow ID `381492575`
  and pinned source workflow blob `1f69460e79086f27003ce5270f6958408a67fe23`.
  It checks repository, branch, exact result SHA, push event, workflow path,
  workflow run and the single `test` job. Missing CI waits until task deadline;
  changed workflow identity or failed CI cannot pass.
- **Independent evidence:** `orchestrator/runners.py` supplies the actual
  bounded patch and SHA-256, changed paths, per-file findings and selected
  pytest outcomes from a marked disposable fixture. Sensitive added lines are
  redacted and block review. Selected acceptance test files cannot change in
  the candidate commit. `orchestrator/architect.py` receives the complete
  packet or declines an oversized request. Review instructions were updated.
- **Publication:** `orchestrator/controller.py` repeats local approval, issue
  state/author/label, branch, patch, selected tests, workflow and exact CI-run
  checks immediately before founder-approved draft PR creation.
- **Recovery and cancellation:** `orchestrator/store.py` idempotently converts
  orphaned `RUNNING` rows to audited `RECOVERY_REQUIRED` with reservations
  retained. `orchestrator/cancellation.py` provides a tested process-tree
  stop/deadline primitive, disconnected from the disabled live executor.
- **Disposable dispatch:** `tests/test_orchestrator_dispatch.py` creates an
  isolated working Git repository and bare remote, routes a founder-approved
  issue through production GitHub gateway methods with mocked HTTP responses,
  waits for an actual toy branch push, verifies trusted CI, reviews evidence,
  and publishes only a mocked draft PR. No real GitHub task or model is run.
  `tests/test_orchestrator_cancellation.py` exercises child-process stop and
  timeout. `tests/test_orchestrator.py` adds revocation, CI spoof, audit,
  patch and failing-acceptance cases. The manual dry-run workflow includes
  all orchestrator test files.

### Verification for this follow-up

- Full local regression: `.\.venv\Scripts\python.exe -m pytest -q` **88 passed,
  1 upstream Starlette/httpx deprecation warning**. `compileall` and
  `git diff --check` passed.
- A read-only call through the new `GitHubGateway.ci_evidence()` returned
  `SUCCESS` for the previous exact PR head `8d30f401263d8c94079131baf0d89d3b4bb4cc40`,
  trusted workflow ID `381492575`, blob SHA `1f69460e79086f27003ce5270f6958408a67fe23`,
  push run `39110622324` and job `117625802740`. No GitHub write was made.
- Changed files: `.github/workflows/orchestrator-dry-run.yml`,
  `orchestrator/README.md`, `__main__.py`, `architect.py`, `cancellation.py`,
  `controller.py`, `github.py`, `instructions/chief_architect.md`, `runners.py`,
  `store.py`, `tests/test_orchestrator.py`,
  `tests/test_orchestrator_cancellation.py`,
  `tests/test_orchestrator_dispatch.py`, and this handoff.
- [Push CI](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39112177073)
  and [PR CI](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39112180075)
  both passed on the exact implementation SHA above. The PR job log reports
  **88 passed, 1 warning** on Python 3.11.17. The final documentation-only
  commit is checked separately in the PR before review.

### Runner environment investigation

`codex` resolves only to
`C:\Users\PC\.vscode\extensions\openai.chatgpt-26.1007.21434-win32-x64\bin\windows-x86_64\codex.exe`
in this PowerShell shell and reports `codex-cli 0.162.0-alpha.17.2`, not the
reported `0.163.0`. `kilo.cmd` at `C:\Users\PC\AppData\Roaming\npm\kilo.cmd`
is package version `7.8.12`, but its wrapper invokes `node`, which is absent
from this shell's PATH. `C:\Program Files\nodejs\node.exe` exists and reports
`v24.20.0`; a temporary, process-local PATH prefix made `kilo.cmd --version`
report `7.8.12`. No installation, persistent environment change, model call
or authentication test occurred. Before any future live activation, the
founder must choose and pin the intended CLI binaries and restricted runtime.

### Remaining activation limits

Selected pytest tests are executable code and are run only in marked toy
repositories; the marker and scrubbed environment are not an OS sandbox.
The process cancellation primitive has no durable PID ownership across
service crashes and is not wired to a live runner. The real GitHub publisher,
scoped credentials, actual model metering, restricted egress and OS isolation
remain unimplemented. No unattended execution or merge path is active.

## Issue #8 read-only pilot follow-up — 2026-10-18

Implementation commit `afb65947548fcca24f58eb8157ded0349689ccbf`
continues on `feat/supervised-orchestrator` for [Issue #8](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/issues/8).
The existing 88 mock-controller tests remain green. PR #7 remains draft,
targets `feat/codex-p1-integration`, and is not merged.

### Delivery and exact evidence

- `orchestrator/readonly_policy.py` pins per-owner image/CLI and Kilo Node
  identities, validates one-shot Issue #8 specs and public toy Git fixtures,
  stages only allowlisted public files, and builds fixed Docker read-only
  command plans without a shell or host secret mounts.
- `orchestrator/readonly.py` supplies founder-gated one-use approval,
  owner/provider caps, preflight probe, source revalidation, strict report
  and measured-usage validation, mock-only execution, stop/revoke and
  startup recovery. `execute_live()` denies all calls.
- `orchestrator/store.py` adds durable approvals and pilot runs, hash-chain
  events, atomic shared budgets/concurrency, emergency stop and orphan
  recovery. `orchestrator/policy.py` rejects nonfinite daily costs.
- `orchestrator/__main__.py` and `web.py` expose the optional local pilot
  dashboard only when a founder-controlled local profile config is present.
  No default profile or real backend is configured.
- `tests/test_orchestrator_readonly.py` covers two owner profiles and toy
  repositories, malicious fixture content, no secret staging, wrong
  executable/version/Node/auth/model, missing or expired approval, budget
  denial, false model output/meter, source drift, child-process stop and
  timeout, restart recovery, emergency latch and dashboard auth. The manual
  dry-run workflow now includes these tests. The operating guide and
  [security risk report](READONLY_PILOT_SECURITY.md) document activation limits.

Local implementation validation: `.\.venv\Scripts\python.exe -m pytest -q`
reported **109 passed, 1 upstream Starlette/httpx deprecation warning**;
`compileall` and `git diff --check` passed. At the exact implementation SHA,
[push CI](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39115075840)
and [PR CI](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39115079191)
both concluded **success**. The PR job `117639125072` log reports
**109 passed, 1 warning** on Python 3.11.17. No model credits were used.
After the final defensive checks and emergency-stop child test, the complete
local suite reported **110 passed, 1 warning**; `compileall` and
`git diff --check` remained clean. The final branch-head CI is reported in
PR #7 after this handoff commit.

Changed files in the implementation commit: `.github/workflows/orchestrator-dry-run.yml`,
`orchestrator/README.md`, `orchestrator/__main__.py`, `orchestrator/policy.py`,
`orchestrator/readonly.py`, `orchestrator/readonly_policy.py`,
`orchestrator/store.py`, `orchestrator/web.py`,
`tests/test_orchestrator_readonly.py`, and
`docs/coordination/READONLY_PILOT_SECURITY.md`. This handoff follows as a
documentation update with small final defensive checks.

### Open issues and integration requirements

Docker CLI 28.3.2 is installed, but the Windows target host's Docker Linux
engine named pipe was unavailable. The command plan and staged filesystem
were tested offline; no live container boundary, escape denial, CLI permission
prompt, provider auth, hard usage meter or actual paid/free model endpoint
was exercised. The pinned in-container CLI and image digests remain
founder-supplied configuration, not attested binaries. `--network=none`
intentionally prevents remote inference. Live Codex/Kilo launch stays
disabled, including after an approved mock run.

The target shell still resolves Codex to the VS Code extension's
`0.162.0-alpha.17.2`, whereas a separate environment reported `0.163.0`.
Kilo `7.8.12` still needs the existing Node `v24.20.0` added to its
process-local PATH. No installation or persistent PATH change occurred.
Before any separately authorized live call, the founder and independent
reviewer must choose a functioning isolation host and pinned image, prove
real filesystem/egress and process-tree controls, configure separate minimal
auth plus provider-side hard cost caps, and verify the exact target CLI
versions and noninteractive permission behavior. GitHub writes remain in
the separate founder-approved publisher; no pilot GitHub write or merge
path was added.

## Issue #8 validation update — 2026-10-20

Implementation commit `9f822e4df6c1cdfd188a468a7eacf3c9d072de84` on
`feat/supervised-orchestrator` keeps PR #7 draft and real execution disabled.
The final handoff SHA and GitHub CI runs are recorded in PR #7 after this
documentation commit. No main merge, real model call, customer contact,
image pull or container launch occurred.

Changed files: `orchestrator/readonly_policy.py`, `orchestrator/readonly.py`,
`orchestrator/store.py`, `orchestrator/cancellation.py`,
`tests/test_orchestrator_readonly.py`,
`tests/test_orchestrator_cancellation.py`, `orchestrator/README.md`, and
`docs/coordination/READONLY_PILOT_SECURITY.md`. The mock probe now identifies
its evidence as synthetic; the only success state emitted by the pilot is
`MOCK_VERIFIED_READ_ONLY`. The store rejects the ambiguous prior success
label for new results. A non-mock probe is rejected before admission. Failed
Windows `taskkill /T /F` now raises rather than treating a parent-only kill
as complete tree cancellation.

Validation order: offline mock/adversarial baseline **24 passed**; focused
new-case and cancellation checks **4 passed**; complete local suite **112
passed, 1 upstream Starlette/httpx deprecation warning**; final focused
probe rerun **4 passed**; `compileall` and `git diff --check` passed. All
tests used mock model execution or harmless local child processes. The
disposable Git remote test remains part of the full suite.

Target runtime observation: Docker client **28.3.2** selected context
`desktop-linux`, but `docker version` and `docker info` returned HTTP 500
from the Docker Desktop Linux engine pipe. Host `codex` now resolves through
the global npm shim and reports **0.163.0**; host `kilo` reports **7.8.12**;
`node.exe` resolves from `C:\Program Files\nodejs`. This supersedes the
earlier PATH observation. These are host checks only; no pinned image or
in-image CLI/Node digest was attested.

Open activation blockers: a functioning Linux isolation engine and actual
container escape/egress drill; approved pinned image and CLI/Node hashes;
noninteractive prompt behavior; isolated provider credentials and an
externally enforced model spend limit with measured usage; durable ownership
and stop verification of a real container; and a reviewed endpoint-only
egress design. `--network=none` currently prevents remote inference. Each
live call still requires independent security review and an express founder
instruction. A separate least-privilege GitHub publisher and human draft-PR
approval remain required for any future publication flow.
