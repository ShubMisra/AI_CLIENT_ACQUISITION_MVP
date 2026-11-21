# Local MCP Compute Pilot — Acquisition MVP

**Purpose:** expose a minimal, local STDIO MCP server to Codex CLI. It reads non-sensitive machine/repository status and, only with local opt-in, executes two fixed verification commands. It cannot execute arbitrary shell, launch Codex/Kilo, scrape Upwork, send proposals, purchase Connects, or access Upwork credentials.

## v0.1 tools

- `get_machine_status`: OS, Python, logical CPUs, free disk, Codex/Kilo command availability. No API keys, environment dumps, or private files.
- `get_repository_status`: git branch and short working-tree status in this repository.
- `preview_check`: show fixed tests or audit command, no execution.
- `execute_check`: run one fixed command with timeout and truncated output. Denied unless operator explicitly starts MCP with `ACQ_ENABLE_CHECKS=1`. `execute=false` is preview-only even when enabled.
- Transport: local STDIO only. No listening port/tunnel.

## Windows PowerShell installation

From an existing trusted checkout of this repository:

```powershell
git fetch origin
git switch feat/local-mcp-compute-pilot
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-local-mcp.txt
python -m pip install -r requirements.txt
python -m pytest tests/test_local_mcp_core.py -q

# Register the server using absolute paths:
$pythonExe = (Resolve-Path .\.venv\Scripts\python.exe).Path
$serverPath = (Resolve-Path .\local_mcp\server.py).Path
codex mcp add acq-compute -- $pythonExe $serverPath
codex mcp list
```

Default: the MCP reports plans but refuses execution. To enable checks locally, start Codex in a PowerShell session in which you intentionally set `$env:ACQ_ENABLE_CHECKS = '1'`. Closing that session disables its setting. The MCP itself only offers tests and audit.

**Important:** Only enable checks on reviewed code. Python tests can themselves run arbitrary code. The pilot is **not** a hardened OS sandbox. Use a disposable worktree/VM for untrusted code.

## ChatGPT connection

Codex CLI supports local STDIO MCP. This does not automatically grant ChatGPT web access to your machine. ChatGPT custom MCP connections are remote-server based and subject to product/workspace eligibility. On eligible setups, use the official Secure MCP Tunnel for a private server with authentication and approval controls. Never expose unauthenticated HTTP, forward SSH, use Upwork browser cookies or copy tokens into GitHub.

## Boundaries and next iteration

- Checks run in the fixed repo with 120-second test and 45-second audit timeouts, 10,000-character output limit; child environment forwards selected OS variables only.
- No autonomous agent execution, arbitrary commands, background jobs, payments, proposals or browser scraping.
- After locally validating STDIO integration, build a **separate** approved-task runner for Codex/Kilo, with worktrees, task manifest, execution budgets, audit output and human gates. Do not enable it in this pilot.
- Do not merge until the operator verifies the installed SDK, Codex MCP transport and local tests. Passing tests in a separate environment is not Windows compatibility evidence.
