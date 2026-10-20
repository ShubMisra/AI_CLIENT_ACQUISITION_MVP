"""Exercise the future runner's kill primitive using harmless local processes."""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

import orchestrator.cancellation as cancellation
from orchestrator.cancellation import isolated_process_flags, supervise, terminate_tree


def test_stop_terminates_process_tree_before_child_side_effect(tmp_path):
    ready = tmp_path / 'child-started'
    late = tmp_path / 'late-side-effect'
    child = f'import time; from pathlib import Path; time.sleep(1.5); Path({str(late)!r}).write_text("late")'
    parent = ('import subprocess,sys,time; from pathlib import Path; '
              f'subprocess.Popen([sys.executable,"-c",{child!r}]); '
              f'Path({str(ready)!r}).write_text("ready"); time.sleep(30)')
    proc = subprocess.Popen([sys.executable, '-c', parent], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, **isolated_process_flags())
    try:
        with pytest.raises(InterruptedError, match='stopped'):
            supervise(proc, ready.exists, 8)
        assert proc.poll() is not None
        time.sleep(1.7)
        assert not late.exists()
    finally:
        terminate_tree(proc)


def test_deadline_terminates_blocked_process():
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            **isolated_process_flags())
    try:
        with pytest.raises(TimeoutError, match='deadline'):
            supervise(proc, lambda: False, 0.2)
        assert proc.poll() is not None
    finally:
        terminate_tree(proc)


def test_windows_tree_kill_failure_is_not_reported_as_success(monkeypatch):
    if cancellation.os.name != 'nt':
        pytest.skip('Windows taskkill branch')

    class Process:
        pid = 12345
        killed = False

        def poll(self):
            return 1 if self.killed else None

        def kill(self):
            self.killed = True

        def wait(self, timeout):
            return 1

    monkeypatch.setattr(cancellation.subprocess, 'run',
                        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1))
    process = Process()
    with pytest.raises(RuntimeError, match='unverified'):
        terminate_tree(process)
    assert process.killed
