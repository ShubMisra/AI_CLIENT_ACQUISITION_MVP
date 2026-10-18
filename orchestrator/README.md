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
