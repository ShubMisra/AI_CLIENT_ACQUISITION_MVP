# Human-supervised engineering controller

This service is separate from `acqsys` and stores state in `data/orchestrator.db`
by default. It never reads the acquisition database. It does not start agents at
startup, send buyer messages, visit acquisition sources, or merge branches.

## Run the mock controller

Use Python 3.11. Install `requirements.txt` and pytest. Set a founder-owned
`ORCH_ADMIN_TOKEN` of at least 16 characters, then run
`python -m orchestrator serve`. The dashboard binds only to
`http://127.0.0.1:8091`. The token is supplied in the page input and request
header; it is not stored in browser storage. Set `ORCH_WORKTREE_ROOT` to the
absolute directory containing disposable, isolated agent worktrees; the
default is a sibling `acq-agent-runs` directory. `ORCH_FOUNDER_LOGIN` defaults
to `ShubMisra`. `ORCH_AUTONOMY=OFF` disables starts; `SUPERVISED` is the only
level that can start a mock run.

Register a founder-authored task JSON via the dashboard. The task must name a
GitHub issue, owner (`codex` or `kilo`), exact feature branch and reviewed SHA,
worktree under the trusted root, approved path prefixes, local pytest node IDs,
model, deadline, and per-run token, cost, runtime and retry caps. The issue
must be open, created by the configured founder account, and have the
`approved-for-run` label. Its body and comments are never passed to a runner.
The founder separately approves the local task and starts each mock run.

Mock runs require a disposable Git repository with a tracked
`.orchestrator-fixture` file containing `TOY_REPO_ONLY` and an approved
`orchestrator_fixture/` path. The fixture runner makes one fixed test commit.
CI must pass before independent review; the founder must then approve draft PR
publication. `python -m pytest -q tests/test_orchestrator.py` demonstrates the
entire offline cycle with fake GitHub and model interfaces. The optional
`Supervised orchestrator dry run` GitHub workflow runs only this mock suite.

The CI gateway pins GitHub Actions workflow ID `381492575`, the Git blob SHA
`1f69460e79086f27003ce5270f6958408a67fe23` for
`.github/workflows/ci.yml`, repository/ref, exact result SHA, push event,
workflow run and its single `test` job. A changed workflow or check identity
fails closed. A missing run waits until the task deadline; it never grants
review or publication. The selected pytest node IDs run only inside a marked
disposable fixture repository, with a scrubbed environment. Their output,
actual bounded patch, patch hash and per-file security findings are included
in review evidence. Sensitive added lines are redacted and block review.
The selected acceptance test files must remain unchanged from the reviewed
source SHA, even if the task's path scope otherwise includes `tests/`.
The API reviewer receives complete bounded evidence or declines the call;
it never receives a truncated review packet.

At publication, the controller rechecks founder approval, issue state/author/
label, branch head, local patch, selected tests, workflow blob and exact CI run.
On service restart, orphaned `RUNNING` mock rows become `RECOVERY_REQUIRED`,
retain their budget reservation, and are audited once. A founder must create
or approve a new bounded task to continue. The process-tree cancellation
primitive in `cancellation.py` is tested with harmless child processes; it is
not connected to the disabled live CLI executor.

## Controls and activation boundary

Four levels are named: `OFF`, `SUPERVISED`, `APPROVED_BATCH`, `UNATTENDED`.
Only `OFF` and `SUPERVISED` validate, and only supervised mock execution is wired. The dashboard
can set daily token and USD reservation caps, approve/reject tasks, start a
mock run, review CI, approve a draft PR, pause, and emergency stop. Retry
requires a fresh founder review decision; at most two runs may be active,
one per owner. Emergency stop denies new runs until the founder clears it.

`CodexAdapter` and `KiloAdapter` build fixed argv plans without a shell.
`LiveCLIExecutor` always rejects. Before any live execution, the founder and
Chief Architect must separately approve an OS-isolated runner, a sanitized
checkout without readable secrets, scoped GitHub credentials, egress rules,
verified CLI versions/auth, deterministic token/cost metering, and an explicit
live activation change. Kilo `--auto` is intentionally absent; Kilo's official
documentation warns it auto-approves permissions not explicitly denied.
This repository does not make that activation change.

`OpenAIArchitect` implements the official [Responses API](https://developers.openai.com/api/docs/guides/text)
with `store=false`, no tools, a bounded output, and instructions loaded from
`instructions/chief_architect.md` on each call. Its API expenditure is disabled
by default; the mock reviewer uses only test evidence. Decision history is
persisted in SQLite. No ChatGPT conversation is available to this service.

Logs and events are redacted and hash-chained, but regex redaction is not a
complete confidentiality boundary. Do not place repository secrets in a
worktree exposed to a free third-party model. SQLite history is tamper-evident
against row edits, not privileged database replacement.

## Runner environment observed on 2026-10-18

This PowerShell runner resolves `codex.exe` from the VS Code extension at
`C:\Users\PC\.vscode\extensions\openai.chatgpt-26.1007.21434-win32-x64\bin\windows-x86_64\codex.exe`;
it reports `codex-cli 0.162.0-alpha.17.2`. The separately reported `0.163.0`
binary is not on this shell's PATH. `kilo.cmd` is installed at
`C:\Users\PC\AppData\Roaming\npm\kilo.cmd` and its package reports `7.8.12`.
Its wrapper invokes `node`, which is missing from this shell's PATH. Node
`v24.20.0` exists at `C:\Program Files\nodejs\node.exe`; a temporary PATH
prefix let `kilo.cmd --version` report `7.8.12`. No install, persistent PATH
change, authentication test or model inference was performed.

## Issue #8 synthetic read-only pilot

The optional `ORCH_PILOT_CONFIG` points to a founder-controlled local JSON
file with `profiles` (one `RuntimePin` per owner) and `tariffs` (one
`ProviderTariff` per allowed owner/provider/model). Without this file, pilot
dashboard endpoints are absent. Each profile pins an absolute Docker client,
an image digest, the in-image CLI path, CLI SHA-256 and version. Kilo also pins
its own Node path and version; Codex has no Node setting. The config contains
no credentials and is never sent to either model. A local test double probes
the pins; it does not attest a real image or auth state.

The founder registers a complete Issue #8 spec under `/api/pilot/approvals`
with `issue`, `owner`, `worktree`, `branch`, `source_sha`, `provider`, `model`,
`max_input_tokens`, `max_output_tokens`, `max_tokens`, `max_cost_usd`,
`timeout_seconds`, and `expires_at`. The disposable worktree must sit under
`ORCH_WORKTREE_ROOT`, be clean and pinned to the exact branch/SHA, and contain
a tracked `public_fixture.txt` plus `.orchestrator-fixture` marker. Only the
public file and three deterministic facts are staged in a temporary snapshot.
The approval is one-use and expires within 24 hours. The founder separately
starts `/api/pilot/approvals/{id}/run-mock`, can revoke the approval or stop
its run, and can use the emergency stop. Startup recovery stops orphan names
before marking them `RECOVERY_REQUIRED`; a failed stop latches the global gate.

`run-mock` builds a fixed Docker plan with a pinned image, a read-only
container and fixture mount, no network, no capabilities, a private temporary
directory, no host secret mounts, and bounded CPU, memory and process count.
Codex receives `exec --sandbox read-only --ephemeral --ignore-user-config`;
Kilo receives `run --pure` and never `--auto`. The selected CLI, Node and PATH
are independent per owner. The mock backend never launches that plan, Docker,
Codex, Kilo or a provider call. Real CLI execution always raises
`PermissionError`. Only exact deterministic public facts and measured mock
usage pass validation; raw model output is never persisted. Both the old
controller and pilot share atomic daily budget and concurrency reservations.

Docker Desktop's Linux engine was unavailable in the reviewed Windows shell,
so the OS restrictions are verified as a command plan and fixture snapshot,
not as an observed kernel boundary. There is no approved image digest, actual
in-image CLI hash, provider broker, authenticated model probe or verified live
cost meter. With `--network=none`, a real remote-model CLI call cannot work;
that is deliberate while execution remains disabled. An independent review
and a separately authorized activation change are required before any model
credit can be spent.
