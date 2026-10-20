# Issue #9 hosted read-only pilot — offline security report

## Current authority and trust zones

This branch demonstrates **MOCK** execution only. The public fixture, mock
Codex script and security report are bound to the checked-out commit SHA.
The host controller creates an ephemeral `MOCK_ONLY` approval, checks exact
task fields, admits the nonce once in a local audit ledger, and launches one
container. This simulated signer is not founder authentication. A real run
requires a separate founder-controlled approval service with durable external
replay protection, protected-branch workflow deployment, and independent
security review. `run_real()` unconditionally denies execution.

The host job checks out the public repository with read-only token permission
and no persisted checkout credential. It stages only `hosted_public.json`,
`facts.json` and the pinned mock executable into a new directory outside the
checkout. The mock process receives that directory as a read-only bind mount;
it receives no repository tree, `.git`, acquisition database, host home,
GitHub token, provider credential or issue text. The output artifact contains
only allowlisted deterministic fields and zero-use counters. Raw process
output and exception messages are discarded after verification. The local
SQLite ledger records admission and result in a SHA-256 event chain; the
GitHub Actions run ID, attempt and checked-out SHA bind the published report.

## Offline containment proof and limits

The GitHub-hosted Ubuntu job pulls the pinned public Python image before the
sandbox starts. The mock container uses `--network=none`, a read-only root and
fixture mount, non-root UID, dropped capabilities, no new privileges, limited
CPU/memory/PIDs and a tiny temporary filesystem. The mock checks that private
paths and secret environment markers are absent, fixture writes fail and a
TEST-NET connection fails. The host verifies every check, the exact public
facts, zero provider calls and zero charged USD before writing the artifact.
`docker image inspect` must identify the pinned digest; no `latest` pull or
provider/model call occurs in the agent step. The mock executable hash and
version are pinned in code, and its runtime image is pinned by digest.

GitHub-hosted VMs are ephemeral, but that alone does not isolate model-controlled
tools. This proof covers only the fixed Python mock inside this container.
It does not establish a safe real Codex process, prompt/tool permissions,
endpoint-only egress, credential separation, or billing limits. Local Windows
Docker remains unavailable; the container boundary is tested in GitHub Actions.
The host job needs network for checkout, Python dependencies, image pull and
artifact upload; only the mock container has no network. Workflow actions are
pinned by commit; Python dependencies retain the existing repository ranges.
Public GitHub Actions minutes/storage may be metered under the repository's
plan, even though model usage and provider charges are zero.

The offline approval ledger is discarded with the ephemeral runner. Replay in
this lane is also blocked by exact GitHub run ID, `run_attempt == 1`, a unique
nonce and one-use admission; a rerun attempt is denied. **This is not durable
cross-run authorization for a real call.** A future real approval must live in
an external founder-controlled transactional store, bind one GitHub run ID,
source SHA and nonce, and be atomically consumed before launch. Cancellation
uses Actions' job stop plus host-side container kill/status verification and
timeout. Failed kill/status verification blocks the result. A future real
session additionally needs provider-side cancellation and proof that spend
cannot continue after job termination.

## Dormant real-inference design

The separate `hosted-readonly-real.workflow-template.yml` lives under
`docs/coordination/`, outside `.github/workflows`, and has a hard-false job.
It cannot currently run. Later design requires two founder decisions:

1. Independently review and manually merge a trusted workflow to the
   protected default branch. GitHub's normal `workflow_dispatch` UI requires
   the workflow on that branch. Configure a restricted deployment environment
   and required reviewers if the repository plan supports them.
2. Authorize exactly one call through an externally signed, one-use manifest
   bound to source SHA, public fixture hash, reviewed CLI image/binary/version,
   provider/model, input/output token ceilings, charged-USD ceiling, expiry,
   run ID and founder identity. A GitHub actor name or issue label alone is
   insufficient. No credentials or environment have been configured here.

Before a real invocation, prove the pinned Codex CLI's actual noninteractive
read-only and permission behavior in the intended image, with no dangerous
bypass flags, shell/tool escalation, plugins, MCP, writes or subagents. The
current mock Python hash is **not** a Codex CLI hash. Obtain a separate scoped
provider identity and a reviewed egress broker that only permits the chosen
model endpoint while keeping credentials outside model-controlled processes.
If the CLI cannot use that separation, live execution remains blocked. The
provider/project must impose an independent hard spend ceiling; reconcile
provider-reported usage and actual billed USD afterward. CLI self-reported
tokens or a ChatGPT subscription do not establish a billing ceiling. Permit
one concurrent attempt, no automatic retry or resume, and no GitHub write
token in the inference job. The publisher remains a separate later milestone.

## Founder activation checklist (future, no action taken now)

- Review this PR, exact offline CI run and sanitized result with an independent
  security reviewer; verify the mock's no-network/no-secret evidence.
- Resolve PR #7's separate CI conflict through its own integration decision.
- Pin and attest a real Codex image, binary digest, version and permission
  semantics; prove host and container egress/secret boundaries.
- Establish a founder-controlled external approval/replay store, provider
  hard cap and independent usage reconciliation. Review Actions/environment
  feature availability and any Actions/storage costs before enabling them.
- Separately authorize deployment of a live workflow to the default branch,
  then separately authorize one exact real run. Stop after that run for review.

References: [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[manual workflow default-branch rule](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow),
[hosted runners](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners),
[artifact retention](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/remove-workflow-artifacts).
