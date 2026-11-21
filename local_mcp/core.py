"""Deliberately constrained local diagnostics and check runner.

No arbitrary command, shell, external network, Upwork action, or agent launch
is exposed as an MCP tool. Running an allowlisted check requires local opt-in.
"""
from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_OUTPUT = 10_000
CHECKS = {
    "tests": ("-m", "pytest", "-q"),
    "audit": ("-m", "acqsys", "audit-verify"),
}


def _short(text: str) -> str:
    return text[-MAX_OUTPUT:]


def _child_env() -> dict[str, str]:
    # Do not forward API keys, cloud credentials, Upwork tokens, or LLM secrets.
    safe = (
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA", "VIRTUAL_ENV", "PYTHONHOME",
        "LANG", "LC_ALL", "PYTHONUTF8", "PYTHONIOENCODING", "PATHEXT",
    )
    return {key: os.environ[key] for key in safe if key in os.environ}


def _run_fixed(args: list[str], timeout: int) -> dict[str, Any]:
    if not (REPO_ROOT / "AGENTS.md").is_file():
        return {"ok": False, "error": "Repository root not identified; no command run"}
    options: dict[str, Any] = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
    }
    process = subprocess.Popen(
        args, cwd=str(REPO_ROOT), shell=False, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True,
        encoding="utf-8", errors="replace", env=_child_env(), **options,
    )
    try:
        output, _ = process.communicate(timeout=timeout)
        return {"ok": process.returncode == 0, "exit_code": process.returncode,
                "output_tail": _short(output), "timed_out": False}
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                           shell=False, capture_output=True, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        return {"ok": False, "exit_code": process.returncode,
                "output_tail": _short(output), "timed_out": True}


def machine_status() -> dict[str, Any]:
    disk = shutil.disk_usage(REPO_ROOT)
    return {
        "python": platform.python_version(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "repo_disk_free_gb": round(disk.free / 1024**3, 2),
        "codex_cli_found": shutil.which("codex") is not None,
        "kilo_cli_found": shutil.which("kilo") is not None,
        "repo_has_agents_md": (REPO_ROOT / "AGENTS.md").is_file(),
        "execution_enabled": os.environ.get("ACQ_ENABLE_CHECKS") == "1",
        "transport": "stdio/local only",
    }


def repository_status() -> dict[str, Any]:
    branch = _run_fixed(["git", "branch", "--show-current"], 10)
    changes = _run_fixed(["git", "status", "--short"], 10)
    return {"branch": branch, "working_tree": changes,
            "repo_root": str(REPO_ROOT), "warning": "Inspect the branch before running any tests"}


def check_plan(name: str) -> dict[str, Any]:
    if name not in CHECKS:
        return {"ok": False, "error": "Unknown check; only tests and audit are supported"}
    return {"ok": True, "name": name, "command": [sys.executable, *CHECKS[name]],
            "cwd": str(REPO_ROOT), "timeout_seconds": 120 if name == "tests" else 45,
            "executes": False}


def run_check(name: str, execute: bool = False) -> dict[str, Any]:
    plan = check_plan(name)
    if not plan["ok"]:
        return plan
    if not execute:
        return {**plan, "status": "preview_only"}
    if os.environ.get("ACQ_ENABLE_CHECKS") != "1":
        return {**plan, "ok": False, "status": "denied",
                "error": "Locally set ACQ_ENABLE_CHECKS=1 to opt into allowlisted checks"}
    result = _run_fixed(plan["command"], int(plan["timeout_seconds"]))
    return {"name": name, "status": "completed" if result["ok"] else "failed", **result}
