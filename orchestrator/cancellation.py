"""Process-tree cancellation primitive for a future isolated runner.

The controller does not launch real Codex or Kilo processes. This module only
supervises a process already started by a separately reviewed launch policy.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time


class TerminationUnverified(RuntimeError):
    """The parent was stopped, but descendants may still exist."""


def isolated_process_flags() -> dict:
    if os.name == 'nt':
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    return {'start_new_session': True}


def terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == 'nt':
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=10, check=False)
        if result.returncode != 0:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            raise TerminationUnverified('process-tree termination unverified')
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def supervise(process: subprocess.Popen, stop_requested, timeout_seconds: float,
              poll_seconds: float = 0.05) -> int:
    if timeout_seconds <= 0 or poll_seconds <= 0:
        raise ValueError('invalid process deadline')
    deadline = time.monotonic() + timeout_seconds
    while True:
        if stop_requested():
            terminate_tree(process)
            raise InterruptedError('process tree stopped')
        if time.monotonic() >= deadline:
            terminate_tree(process)
            raise TimeoutError('process tree exceeded deadline')
        code = process.poll()
        if code is not None:
            return code
        time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))
