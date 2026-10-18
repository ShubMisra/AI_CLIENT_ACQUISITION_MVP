"""Exercise the future runner's kill primitive using harmless local processes."""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

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
