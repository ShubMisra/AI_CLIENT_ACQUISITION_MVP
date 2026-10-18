"""Deterministic admission rules; GitHub text and model output grant no authority."""
from __future__ import annotations

import hmac
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath

REPOSITORY = 'ShubMisra/AI_CLIENT_ACQUISITION_MVP'
APPROVAL_LABEL = 'approved-for-run'
SHA = re.compile(r'^[0-9a-f]{40}$')
BRANCH = re.compile(r'^feat/[a-z0-9][a-z0-9/_-]{0,79}$')
NODEID = re.compile(r'^tests/[A-Za-z0-9_./-]+\.py::test_[A-Za-z0-9_\[\]-]+$')
FORBIDDEN = {'.git', '.github', '.env', 'data', 'secrets', 'credentials', '.venv',
             'node_modules', 'orchestrator', 'AGENTS.md', 'requirements.txt'}


class Autonomy(str, Enum):
    OFF = 'OFF'
    SUPERVISED = 'SUPERVISED'
    APPROVED_BATCH = 'APPROVED_BATCH'
    UNATTENDED = 'UNATTENDED'


def clean_path(value: str) -> str:
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('invalid scoped path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or any(part in FORBIDDEN or part.startswith('.env') for part in path.parts):
        raise ValueError('forbidden scoped path')
    normalized = str(path)
    if normalized == '.' or normalized != value.rstrip('/'):
        raise ValueError('noncanonical scoped path')
    return normalized


@dataclass(frozen=True)
class Task:
    issue: int
    owner: str
    branch: str
    worktree: str
    source_sha: str
    paths: tuple[str, ...]
    acceptance: tuple[str, ...]
    prompt: str
    max_tokens: int
    max_cost_usd: float
    timeout_seconds: int
    deadline_utc: str
    max_retries: int = 0
    model: str = ''

    @classmethod
    def from_dict(cls, raw: dict, require_future: bool = True) -> 'Task':
        expected = set(cls.__dataclass_fields__)
        if set(raw) - expected:
            raise ValueError('unknown task fields')
        task = cls(**{**{'max_retries': 0, 'model': ''}, **raw})
        task.validate(require_future=require_future)
        return task

    def validate(self, require_future: bool = True) -> None:
        if type(self.issue) is not int or self.issue < 1:
            raise ValueError('invalid issue')
        if self.owner not in ('codex', 'kilo') or not isinstance(self.branch, str) or not BRANCH.fullmatch(self.branch):
            raise ValueError('invalid owner or branch')
        if not isinstance(self.source_sha, str) or not SHA.fullmatch(self.source_sha):
            raise ValueError('invalid source SHA')
        if not isinstance(self.prompt, str) or not self.prompt or len(self.prompt) > 4000 or \
           any(x in self.prompt.lower() for x in ('password=', 'api_key=', 'bearer ')):
            raise ValueError('unsafe trusted prompt')
        if not isinstance(self.paths, (tuple, list)) or not self.paths or len(self.paths) > 20 or \
           any(clean_path(p) != p.rstrip('/') for p in self.paths):
            raise ValueError('invalid paths')
        if not isinstance(self.acceptance, (tuple, list)) or not self.acceptance or len(self.acceptance) > 20 or \
           any(not isinstance(t, str) or not NODEID.fullmatch(t) for t in self.acceptance):
            raise ValueError('acceptance must name local pytest tests')
        for nodeid in self.acceptance:
            file = nodeid.split('::', 1)[0]
            if clean_path(file) != file or not file.startswith('tests/'):
                raise ValueError('acceptance test path escaped tests')
        if type(self.max_tokens) is not int or not 1 <= self.max_tokens <= 100000 or \
           type(self.max_cost_usd) not in (float, int) or not 0 < self.max_cost_usd <= 25:
            raise ValueError('invalid model budget')
        if type(self.timeout_seconds) is not int or not 30 <= self.timeout_seconds <= 3600 or \
           type(self.max_retries) is not int or self.max_retries not in (0, 1):
            raise ValueError('invalid execution budget')
        try:
            deadline = datetime.fromisoformat(self.deadline_utc.replace('Z', '+00:00'))
            if deadline.tzinfo is None or (require_future and deadline <= datetime.now(timezone.utc)):
                raise ValueError('expired deadline')
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid deadline') from exc
        if not isinstance(self.model, str) or not re.fullmatch(r'[a-zA-Z0-9./_-]{1,100}', self.model):
            raise ValueError('invalid model')


@dataclass(frozen=True)
class Settings:
    root: Path
    db_path: Path
    founder_login: str
    daily_tokens: int = 200000
    daily_cost_usd: float = 50.0
    max_active: int = 2
    autonomy: Autonomy = Autonomy.SUPERVISED
    mock_only: bool = True

    def validate(self) -> None:
        if self.autonomy not in (Autonomy.OFF, Autonomy.SUPERVISED):
            raise ValueError('only OFF or SUPERVISED is activated')
        if self.max_active != 2 or self.daily_tokens < 1 or \
           not math.isfinite(self.daily_cost_usd) or self.daily_cost_usd <= 0:
            raise ValueError('invalid controller limits')
        if not self.root.is_absolute() or not self.founder_login:
            raise ValueError('trusted root and founder login required')


def require_founder(token: str | None) -> None:
    configured = os.environ.get('ORCH_ADMIN_TOKEN', '')
    if len(configured) < 16 or not token or not hmac.compare_digest(configured, token):
        raise PermissionError('founder authentication required')


def validate_issue(task: Task, issue: dict, founder_login: str) -> None:
    # Never execute or concatenate the issue body into an agent prompt.
    if issue.get('number') != task.issue or issue.get('state') != 'open':
        raise PermissionError('issue mismatch or closed')
    if issue.get('user', {}).get('login') != founder_login:
        raise PermissionError('untrusted issue author')
    labels = {x.get('name') for x in issue.get('labels', []) if isinstance(x, dict)}
    if APPROVAL_LABEL not in labels:
        raise PermissionError('missing approved-for-run label')


def validate_worktree(task: Task, root: Path, git) -> Path:
    root = root.resolve(strict=True)
    path = Path(task.worktree).resolve(strict=True)
    if path == root or not path.is_relative_to(root):
        raise PermissionError('worktree outside trusted root')
    if Path(git(path, 'rev-parse', '--show-toplevel').strip()).resolve(strict=True) != path:
        raise PermissionError('worktree root mismatch')
    if git(path, 'branch', '--show-current').strip() != task.branch:
        raise PermissionError('branch mismatch')
    if git(path, 'rev-parse', 'HEAD').strip() != task.source_sha:
        raise PermissionError('source SHA changed')
    if git(path, 'status', '--porcelain').strip():
        raise PermissionError('worktree is dirty')
    return path


def validate_changed_paths(paths: list[str], allowed: tuple[str, ...]) -> None:
    if not paths:
        raise PermissionError('no changed files')
    for path in paths:
        clean_path(path)
        if not any(path == scope or path.startswith(scope.rstrip('/') + '/') for scope in allowed):
            raise PermissionError('changed file outside approved scope')
