"""Offline-only Issue #9 contract. Mock approval is never live authority."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPOSITORY = 'ShubMisra/AI_CLIENT_ACQUISITION_MVP'
WORKFLOW = '.github/workflows/hosted-readonly-mock.yml'
FIXTURE = 'tests/fixtures/hosted_public.json'
FIXTURE_ID = 'hosted-public-v1'
FIXTURE_SHA256 = 'd8fd7ed67fe04cd1c7286738ea9a73637e4c612fbef1c3f2538757e225240835'
MOCK_CLI_SHA256 = '76aa807a36eb35ad4d2734f9fcd79e53c56b1ed5505992e762e575f07dedae73'
IMAGE = 'python@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d'
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
SHA64 = re.compile(r'[0-9a-f]{64}\Z')
NONCE = re.compile(r'[0-9a-f]{32}\Z')


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class HostedContext:
    repository: str
    source_sha: str
    run_id: str
    attempt: int
    job: str
    event: str
    ref: str
    workflow_ref: str

    def validate(self) -> None:
        if self.repository != REPOSITORY or not SHA40.fullmatch(self.source_sha):
            raise PermissionError('untrusted repository or source SHA')
        if not self.run_id.isdecimal() or int(self.run_id) < 1 or self.attempt != 1:
            raise PermissionError('missing run identity or replayed attempt')
        if self.job != 'offline-mock' or self.event not in ('push', 'pull_request'):
            raise PermissionError('untrusted job or event')
        if self.event == 'push' and self.ref != 'refs/heads/feat/hosted-readonly-pilot':
            raise PermissionError('unapproved push branch')
        if self.event == 'pull_request' and not re.fullmatch(r'refs/pull/[1-9][0-9]*/merge', self.ref):
            raise PermissionError('unapproved pull request ref')
        if self.workflow_ref != REPOSITORY + '/' + WORKFLOW + '@' + self.ref:
            raise PermissionError('unexpected workflow identity')


@dataclass(frozen=True)
class HostedTask:
    mode: str
    issue: int
    owner: str
    repository: str
    source_sha: str
    fixture_id: str
    fixture_sha256: str
    image_ref: str
    cli_path: str
    cli_sha256: str
    cli_version: str
    provider: str
    model: str
    max_input_tokens: int
    max_output_tokens: int
    max_cost_usd: int
    timeout_seconds: int
    nonce: str
    expires_at: str
    founder: str
    review_digest: str
    run_id: str
    attempt: int

    @classmethod
    def from_dict(cls, raw: dict) -> 'HostedTask':
        if type(raw) is not dict or set(raw) != set(cls.__dataclass_fields__):
            raise PermissionError('task schema changed')
        task = cls(**raw)
        task.validate()
        return task

    def validate(self) -> None:
        if type(self.issue) is not int or type(self.attempt) is not int or \
           type(self.max_input_tokens) is not int or type(self.max_output_tokens) is not int or \
           type(self.max_cost_usd) is not int:
            raise PermissionError('invalid task limit types')
        if (self.mode, self.issue, self.owner, self.repository, self.fixture_id,
            self.image_ref, self.cli_path, self.cli_sha256, self.cli_version,
            self.provider, self.model, self.max_input_tokens, self.max_output_tokens,
            self.max_cost_usd, self.founder, self.attempt) != (
            'MOCK', 9, 'codex', REPOSITORY, FIXTURE_ID, IMAGE,
            '/usr/local/bin/python3', MOCK_CLI_SHA256, 'mock-codex/1',
            'offline', 'mock-codex', 0, 0, 0, 'SIMULATED_FOUNDER', 1):
            raise PermissionError('offline mock policy mismatch')
        if not (isinstance(self.source_sha, str) and SHA40.fullmatch(self.source_sha)
                and self.fixture_sha256 == FIXTURE_SHA256
                and isinstance(self.review_digest, str) and SHA64.fullmatch(self.review_digest)
                and isinstance(self.nonce, str) and NONCE.fullmatch(self.nonce)
                and isinstance(self.run_id, str) and self.run_id.isdecimal()
                and type(self.timeout_seconds) is int and 1 <= self.timeout_seconds <= 30):
            raise PermissionError('invalid immutable task fields')
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as exc:
            raise PermissionError('invalid mock approval expiry') from exc
        if expiry.tzinfo is None or not utc_now() < expiry <= utc_now() + timedelta(minutes=10):
            raise PermissionError('mock approval expired or overlong')

    def digest(self) -> str:
        self.validate()
        return sha256(canonical(asdict(self)))


@dataclass(frozen=True)
class MockApproval:
    task_digest: str
    authority: str
    signature: str

    def verify(self, task: HostedTask, key: bytes, context: HostedContext) -> None:
        context.validate()
        if task.repository != context.repository or task.source_sha != context.source_sha or \
           task.run_id != context.run_id or task.attempt != context.attempt:
            raise PermissionError('approval context drift')
        expected = hmac.new(key, task.digest().encode(), hashlib.sha256).hexdigest()
        if self.authority != 'MOCK_ONLY' or self.task_digest != task.digest() or \
           not hmac.compare_digest(self.signature, expected):
            raise PermissionError('missing or changed mock approval')


def simulate_founder_approval(task: HostedTask, key: bytes) -> MockApproval:
    """Ephemeral CI simulation key; public code never grants live authority."""
    return MockApproval(task.digest(), 'MOCK_ONLY',
                        hmac.new(key, task.digest().encode(), hashlib.sha256).hexdigest())


class HostedLedger:
    """Atomic per-run mock admission. Live replay needs an external ledger."""

    def __init__(self, path: Path):
        self.path = path
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (nonce TEXT PRIMARY KEY, '
                       'run_id TEXT NOT NULL, attempt INTEGER NOT NULL, '
                       'task_digest TEXT NOT NULL, status TEXT NOT NULL, result_sha TEXT, '
                       'UNIQUE(run_id,attempt))')
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, '
                       'kind TEXT NOT NULL, data TEXT NOT NULL, prev_hash TEXT NOT NULL, '
                       'hash TEXT NOT NULL)')

    def _db(self):
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def _event(db, kind: str, data: dict) -> str:
        row = db.execute('SELECT hash FROM events ORDER BY id DESC LIMIT 1').fetchone()
        previous = row[0] if row else '0' * 64
        payload = canonical({'kind': kind, 'data': data, 'prev_hash': previous})
        value = sha256(payload)
        db.execute('INSERT INTO events(kind,data,prev_hash,hash) VALUES(?,?,?,?)',
                   (kind, canonical(data).decode(), previous, value))
        return value

    def claim(self, task: HostedTask, approval: MockApproval, key: bytes,
              context: HostedContext) -> None:
        approval.verify(task, key, context)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('INSERT INTO runs VALUES(?,?,?,?,?,NULL)',
                           (task.nonce, task.run_id, task.attempt,
                            task.digest(), 'RUNNING'))
            except sqlite3.IntegrityError as exc:
                raise PermissionError('mock approval replay') from exc
            self._event(db, 'MOCK_ADMITTED', {'nonce': task.nonce,
                                             'task_digest': task.digest()})

    def finish(self, task: HostedTask, status: str, result_sha: str | None) -> str:
        if status not in ('ACCEPT_MOCK', 'BLOCKED'):
            raise ValueError('invalid mock review')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute('UPDATE runs SET status=?,result_sha=? '
                                 'WHERE nonce=? AND status=\'RUNNING\'',
                                 (status, result_sha, task.nonce)).rowcount
            if changed != 1:
                raise PermissionError('mock run already completed')
            return self._event(db, status, {'nonce': task.nonce,
                                            'result_sha': result_sha})

    def verify_events(self) -> bool:
        previous = '0' * 64
        with self._db() as db:
            for kind, data, prev_hash, value in db.execute(
                    'SELECT kind,data,prev_hash,hash FROM events ORDER BY id'):
                if prev_hash != previous or sha256(canonical({
                    'kind': kind, 'data': json.loads(data),
                    'prev_hash': previous})) != value:
                    return False
                previous = value
        return True

    def public_events(self) -> list[dict]:
        if not self.verify_events():
            raise PermissionError('mock audit chain invalid')
        with self._db() as db:
            return [{'kind': kind, 'data': json.loads(data),
                     'prev_hash': previous, 'hash': value}
                    for kind, data, previous, value in db.execute(
                        'SELECT kind,data,prev_hash,hash FROM events ORDER BY id')]
