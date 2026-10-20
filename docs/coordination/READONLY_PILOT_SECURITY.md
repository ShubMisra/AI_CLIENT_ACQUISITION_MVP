# Issue #8 read-only pilot security evidence

This milestone implements the synthetic, founder-supervised control path.
The actual Codex and Kilo CLIs remain disabled. The only executable pilot
backend is an offline mock. No repository checkout, GitHub issue body, model
output or provider response can supply runner flags or grant permission.

## Validation update — 2026-10-20

- The mock success state is now `MOCK_VERIFIED_READ_ONLY`. The store rejects
  the former ambiguous `VERIFIED_READ_ONLY` state for new results. Probe
  evidence must explicitly be `mock`; a claimed live attestation is rejected
  before admission. `execute_live()` still always denies execution.
- Windows process-tree cancellation now fails closed when `taskkill /T /F`
  returns an error. Killing the parent alone is not accepted as evidence that
  its descendants stopped. The adversarial failure test and existing stop,
  emergency and timeout tests use harmless local processes only. Durable
  ownership of a real container/process tree remains unproven.
- On the target Windows host, Docker client 28.3.2 selected `desktop-linux`,
  but both `docker version` and `docker info` received HTTP 500 from the
  Docker Desktop Linux-engine pipe. No image was inspected or started; the
  planned kernel sandbox has not been validated.
- The current host shell resolves `codex` through the global npm shim and
  reports `codex-cli 0.163.0`; `kilo` reports `7.8.12`; Node resolves from
  `C:\Program Files\nodejs\node.exe`. This supersedes the older host PATH
  observation in the prior handoff. Host shims are not the proposed in-image
  pinned executables. Image digest, CLI hashes/versions, Kilo Node pin,
  noninteractive permissions and provider hard limits remain unattested.
- The static plan denies network access, so it cannot contact a remote model
  endpoint. An egress design that permits only an approved model endpoint,
  with separately scoped authentication and externally enforced spend limits,
  still needs independent review before any live activation.

## Enforced in code

- One-use founder approval binds Issue #8, owner, disposable worktree,
  branch, SHA, provider/model, token and USD caps, runtime, expiry, profile
  fingerprint and tariff fingerprint. Admission is atomic with existing
  mock-run budgets, owner concurrency and emergency stop.
- A clean synthetic Git worktree is rechecked before admission and after
  the mock result. Only a marked, tracked, at most 4096-byte public fixture
  and three public facts enter a temporary staging directory. Tracked
  executable files, host environment variables, `.git`, credentials and
  customer data are excluded. Only the staging directory is in the fixed
  read-only Docker bind plan.
- The per-owner plan pins an image digest and in-image CLI SHA-256/version;
  Kilo pins Node separately. It specifies no network, read-only root,
  dropped capabilities, no new privileges, non-root UID, process/memory/CPU
  caps and fixed CLI arguments. No shell is invoked or chosen by model text.
- A mock result must provide exact public facts and numeric usage. Missing,
  nonfinite or over-cap usage fails. Only the allowlisted report, its digest,
  counters and an error class reach the hash-chained SQLite history. The
  raw output and exception message are not stored.
- Stop/revoke signal the durable row and terminate the fixed container name.
  Startup recovery does the same for orphan rows and is idempotent. An
  unverified termination latches the global emergency stop. Real CLI launch
  is rejected independent of configuration.

## Test scope and activation boundary

`tests/test_orchestrator_readonly.py` uses two independently configured
synthetic Git repositories and backend doubles. It tests one-shot approval,
owner-specific argv, fixture exclusion, founder auth, dirty and changed
source, expiry, profile/probe/price drift, model-output injection, missing or
invalid metering, stop/revoke, restart recovery, and failed termination.
The existing process-tree cancellation tests continue to verify kill and
timeout with harmless local children. No test spends model credits.

Docker Linux engine was not available in the reviewed Windows environment.
The planned flags have not been exercised against a live kernel, and a mock
probe does not verify a real image, CLI digest, auth state or provider limit.
The present network-denied container could not perform a remote model call.
Real provider cost control requires an independently enforced broker or
account-level hard cap and a measured usage feed. A future activation must
be a separate reviewed change with a pinned image, a functioning isolated
host, actual stop/recovery drill and explicit founder authorization. It must
keep the separate GitHub publisher, no auto-merge, and acquisition egress
denied.
