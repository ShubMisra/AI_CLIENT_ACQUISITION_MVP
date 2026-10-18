"""Fixed CLI invocation plans. Live process execution remains fail-closed."""
from __future__ import annotations

import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .policy import Task, validate_changed_paths
from .store import redact


@dataclass(frozen=True)
class CommandPlan:
    argv: tuple[str, ...]
    cwd: Path
    stdin: str | None
    timeout_seconds: int
    permitted_tools: tuple[str, ...]


@dataclass(frozen=True)
class RunResult:
    head_sha: str
    tokens: int | None
    cost_usd: float | None
    output: str
    exit_code: int = 0


class Runner(Protocol):
    def run(self, task: Task, stop_requested) -> RunResult: ...


class CodexAdapter:
    def __init__(self, executable: Path):
        self.executable = executable.resolve(strict=True)
        if self.executable.name.lower() not in ('codex', 'codex.exe'):
            raise ValueError('unexpected Codex executable')

    def plan(self, task: Task) -> CommandPlan:
        if task.owner != 'codex':
            raise ValueError('wrong runner owner')
        return CommandPlan(
            (str(self.executable), 'exec', '--sandbox', 'workspace-write',
             '--ephemeral', '--json', '-C', task.worktree, '-m', task.model, '-'),
            Path(task.worktree), task.prompt, task.timeout_seconds,
            ('read', 'edit-inside-worktree', 'bounded-shell'),
        )


class KiloAdapter:
    def __init__(self, executable: Path):
        self.executable = executable.resolve(strict=True)
        if self.executable.name.lower() not in ('kilo', 'kilo.exe', 'kilo.cmd'):
            raise ValueError('unexpected Kilo executable')

    def plan(self, task: Task) -> CommandPlan:
        if task.owner != 'kilo':
            raise ValueError('wrong runner owner')
        # No --auto: Kilo's noninteractive permission requests fail closed.
        return CommandPlan(
            (str(self.executable), 'run', '--model', task.model,
             '--format', 'json', '--dir', task.worktree, task.prompt),
            Path(task.worktree), None, task.timeout_seconds,
            ('read',),
        )


class LiveCLIExecutor:
    """Requires a separately reviewed OS sandbox before any real launch.

    CLI flags and tool permissions alone cannot isolate readable secrets or
    arbitrary shell commands. This stub deliberately has no subprocess path.
    """

    def run(self, task: Task, stop_requested) -> RunResult:
        raise PermissionError('live CLI execution is disabled pending OS sandbox review')


class MockRunner:
    def __init__(self, owner: str, result: RunResult):
        self.owner, self.result, self.calls = owner, result, []

    def run(self, task: Task, stop_requested) -> RunResult:
        if task.owner != self.owner:
            raise PermissionError('mock runner owner mismatch')
        self.calls.append(task.issue)
        if stop_requested():
            raise InterruptedError('run stopped')
        return self.result


class FixtureCommitRunner:
    """Mock coding cycle limited to an explicitly marked disposable toy repo."""

    def __init__(self, owner: str, git_executable: str | None = None):
        self.owner = owner
        self.git_executable = git_executable or shutil.which('git')
        if not self.git_executable:
            raise RuntimeError('git unavailable')

    def run(self, task: Task, stop_requested) -> RunResult:
        if task.owner != self.owner or stop_requested():
            raise PermissionError('fixture run denied')
        root = Path(task.worktree).resolve(strict=True)
        marker = root / '.orchestrator-fixture'
        if not marker.is_file() or marker.read_text(encoding='utf-8').strip() != 'TOY_REPO_ONLY':
            raise PermissionError('not a disposable fixture repository')
        target = root / 'orchestrator_fixture' / 'result.txt'
        validate_changed_paths(['orchestrator_fixture/result.txt'], task.paths)
        target.parent.mkdir(exist_ok=True)
        target.write_text('Fixture engineering result for issue ' + str(task.issue) + '\n', encoding='utf-8')
        for args in (('add', '--', 'orchestrator_fixture/result.txt'),
                     ('-c', 'user.name=Fixture Runner', '-c', 'user.email=fixture@example.invalid',
                      'commit', '-m', 'test: fixture orchestrator result')):
            result = subprocess.run([self.git_executable, *args], cwd=root, text=True,
                                    capture_output=True, timeout=20, check=False)
            if result.returncode:
                raise RuntimeError('fixture Git operation failed')
        head = subprocess.run([self.git_executable, 'rev-parse', 'HEAD'], cwd=root,
                              text=True, capture_output=True, timeout=20, check=True).stdout.strip()
        return RunResult(head, 0, 0.0, 'Fixture commit created', 0)


class GitReader:
    """Only fixed read-only Git operations; never shell=True or issue commands."""

    def __init__(self, executable: str | None = None):
        self.executable = executable or shutil.which('git')
        if not self.executable:
            raise RuntimeError('git unavailable')

    def __call__(self, cwd: Path, *args: str) -> str:
        allowed = {('rev-parse', '--show-toplevel'), ('branch', '--show-current'),
                   ('rev-parse', 'HEAD'), ('status', '--porcelain')}
        if tuple(args) not in allowed and not (len(args) == 3 and args[:2] == ('diff', '--name-only')
                                               and re.fullmatch(r'[0-9a-f]{40}\.\.[0-9a-f]{40}', args[2])):
            raise PermissionError('Git command not allowlisted')
        result = subprocess.run([self.executable, *args], cwd=cwd, text=True,
                                capture_output=True, timeout=20, check=False)
        if result.returncode:
            raise RuntimeError('read-only Git check failed')
        return result.stdout

    def patch(self, cwd: Path, base: str, head: str) -> str:
        if not all(re.fullmatch(r'[0-9a-f]{40}', item) for item in (base, head)):
            raise PermissionError('invalid patch refs')
        result = subprocess.run([self.executable, 'diff', '--no-ext-diff', '--no-textconv',
                                 '--unified=3', base + '..' + head], cwd=cwd, text=True,
                                capture_output=True, timeout=20, check=False)
        if result.returncode or len(result.stdout.encode('utf-8')) > 12_000:
            raise PermissionError('patch unavailable or exceeds review budget')
        return result.stdout


class Verifier:
    """Independently validate changed scope and test names; CI runs the tests."""

    def __init__(self, git: GitReader):
        self.git = git

    def check(self, task: Task, head_sha: str) -> list[str]:
        if not re.fullmatch(r'[0-9a-f]{40}', head_sha):
            raise PermissionError('invalid result SHA')
        cwd = Path(task.worktree)
        if self.git(cwd, 'branch', '--show-current').strip() != task.branch:
            raise PermissionError('result branch changed')
        if self.git(cwd, 'rev-parse', 'HEAD').strip() != head_sha:
            raise PermissionError('runner reported wrong SHA')
        if self.git(cwd, 'status', '--porcelain').strip():
            raise PermissionError('runner left a dirty worktree')
        changed = self.git(cwd, 'diff', '--name-only', task.source_sha + '..' + head_sha).splitlines()
        validate_changed_paths(changed, task.paths)
        protected_tests = {nodeid.split('::', 1)[0] for nodeid in task.acceptance}
        if protected_tests.intersection(changed):
            raise PermissionError('task-specific acceptance tests changed')
        for nodeid in task.acceptance:
            relative, name = nodeid.split('::', 1)
            file = (cwd / relative).resolve(strict=True)
            if not file.is_relative_to(cwd.resolve(strict=True)):
                raise PermissionError('acceptance file escaped worktree')
            tree = ast.parse(file.read_text(encoding='utf-8'))
            if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name.split('[')[0]
                       for n in ast.walk(tree)):
                raise PermissionError('acceptance test missing')
        return changed

    def collect(self, task: Task, head_sha: str) -> dict:
        changed = self.check(task, head_sha)
        patch = self.git.patch(Path(task.worktree), task.source_sha, head_sha)
        if not patch or 'diff --git ' not in patch:
            raise PermissionError('actual patch missing')
        if 'GIT binary patch' in patch or 'Binary files ' in patch:
            raise PermissionError('binary patch cannot be reviewed')
        findings = []
        for path in changed:
            findings.append({'path': path, 'severity': 'INFO',
                             'finding': 'Approved scope; patch included for review'})
        current_path = ''
        safe_lines = []
        for line in patch.splitlines():
            if line.startswith('+++ b/'):
                current_path = line[6:]
            if line.startswith('+') and not line.startswith('+++') and re.search(
                    r'(?i)(password|secret|api[_-]?key|token)\s*[:=]\s*[\'\"]?[^\s\'\"]{8,}', line):
                findings.append({'path': current_path, 'severity': 'HIGH',
                                 'finding': 'Potential credential in added line'})
                safe_lines.append('+[REDACTED SENSITIVE LINE]')
                continue
            if line.startswith('+') and not line.startswith('+++') and re.search(
                    r'(?i)\b(subprocess|os\.system|shell\s*=\s*True|requests\.|httpx\.|urllib\.|socket\.)', line):
                findings.append({'path': current_path, 'severity': 'REVIEW',
                                 'finding': 'Added process or network access requires human review'})
            safe_lines.append(line)
        fixture = Path(task.worktree) / '.orchestrator-fixture'
        if not fixture.is_file() or fixture.read_text(encoding='utf-8').strip() != 'TOY_REPO_ONLY':
            raise PermissionError('acceptance execution is restricted to disposable fixture repos')
        clean_env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'SYSTEMDRIVE')
                     if key in os.environ}
        clean_env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONNOUSERSITE='1',
                         PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryDirectory(prefix='orchestrator-acceptance-') as home:
            clean_env.update({key: home for key in ('HOME', 'USERPROFILE', 'APPDATA',
                                                     'LOCALAPPDATA', 'TMP', 'TEMP')})
            result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider',
                                     '--no-header', '-v', *task.acceptance],
                                    cwd=task.worktree, env=clean_env,
                                    text=True, capture_output=True,
                                    timeout=min(task.timeout_seconds, 120), check=False)
        output = redact((result.stdout + '\n' + result.stderr)[:8000])
        outcome = {'selected': list(task.acceptance), 'passed': result.returncode == 0,
                   'exit_code': result.returncode, 'output': output,
                   'output_sha256': hashlib.sha256(output.encode()).hexdigest()}
        return {'changed_paths': changed, 'patch': redact('\n'.join(safe_lines) + '\n'),
                'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
                'security_findings': findings,
                'security_passed': not any(x['severity'] in ('HIGH', 'REVIEW') for x in findings),
                'acceptance': outcome}
