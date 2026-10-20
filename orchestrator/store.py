"""Durable, append-only controller evidence and atomic budget admission."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .policy import Autonomy, Settings, Task


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def compact(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if re.search(r'(?i)token|secret|password|cookie|credential|api.?key|authorization', str(k)) else redact(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)\b(bearer|basic)\s+\S+', '[REDACTED]', value)
        return re.sub(r'(?i)\b(password|token|secret|api[_-]?key|cookie)\s*[:=]\s*\S+', '[REDACTED]', value)
    return value


class Store:
    def __init__(self, settings: Settings):
        settings.validate()
        self.settings = settings
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, issue INTEGER NOT NULL UNIQUE, owner TEXT NOT NULL,
                spec TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
                owner TEXT NOT NULL, status TEXT NOT NULL, mode TEXT NOT NULL,
                source_sha TEXT NOT NULL, head_sha TEXT, started_at TEXT NOT NULL,
                finished_at TEXT, reserved_tokens INTEGER NOT NULL,
                reserved_cost REAL NOT NULL, used_tokens INTEGER,
                used_cost REAL, ci_state TEXT, pr_url TEXT,
                stop_requested INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
                action TEXT NOT NULL, run_id TEXT, payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                at TEXT NOT NULL, text TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                at TEXT NOT NULL, stage TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                at TEXT NOT NULL, actor TEXT NOT NULL, decision TEXT NOT NULL,
                reason TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY, at TEXT NOT NULL, body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING');
            CREATE TABLE IF NOT EXISTS pilot_approvals (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                spec TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                used_run_id TEXT);
            CREATE TABLE IF NOT EXISTS pilot_runs (
                id TEXT PRIMARY KEY, approval_id TEXT NOT NULL UNIQUE REFERENCES pilot_approvals(id),
                owner TEXT NOT NULL, status TEXT NOT NULL, source_sha TEXT NOT NULL,
                head_sha TEXT, started_at TEXT NOT NULL, finished_at TEXT,
                reserved_tokens INTEGER NOT NULL, reserved_cost REAL NOT NULL,
                input_tokens INTEGER, output_tokens INTEGER, charged_cost REAL,
                report TEXT, report_sha256 TEXT, error_code TEXT,
                container_name TEXT NOT NULL, stop_requested INTEGER NOT NULL DEFAULT 0);
            ''')
            db.execute("INSERT OR IGNORE INTO settings VALUES('emergency_stop','0')")
            db.execute("INSERT OR IGNORE INTO settings VALUES('daily_tokens',?)",
                       (str(settings.daily_tokens),))
            db.execute("INSERT OR IGNORE INTO settings VALUES('daily_cost_usd',?)",
                       (str(settings.daily_cost_usd),))

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.settings.db_path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _event(self, db, action: str, payload: dict, run_id: str | None = None):
        payload = compact(redact(payload))
        previous = db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        prev = previous['hash'] if previous else 'GENESIS'
        at = utc()
        digest = hashlib.sha256((prev + '|' + compact([at, action, run_id, json.loads(payload)])).encode()).hexdigest()
        db.execute('INSERT INTO events(at,action,run_id,payload,prev_hash,hash) VALUES(?,?,?,?,?,?)',
                   (at, action, run_id, payload, prev, digest))

    def event(self, action: str, payload: dict, run_id: str | None = None):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._event(db, action, payload, run_id)

    def verify_events(self) -> bool:
        with self._db() as db:
            rows = db.execute('SELECT * FROM events ORDER BY seq').fetchall()
        prev = 'GENESIS'
        for row in rows:
            digest = hashlib.sha256((prev + '|' + compact([row['at'], row['action'], row['run_id'],
                                                         json.loads(row['payload'])])).encode()).hexdigest()
            if row['prev_hash'] != prev or row['hash'] != digest:
                return False
            prev = digest
        return True

    def recover(self) -> int:
        """On restart, fail closed on orphaned mock runs; retain reservations."""
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            stale = db.execute("SELECT id,source_sha FROM runs WHERE status='RUNNING'").fetchall()
            for row in stale:
                db.execute("UPDATE runs SET status='RECOVERY_REQUIRED',stop_requested=1,finished_at=? "
                           "WHERE id=? AND status='RUNNING'", (utc(), row['id']))
                self._event(db, 'RUN_RECOVERED', {'source_sha': row['source_sha'],
                                                  'result': 'RECOVERY_REQUIRED'}, row['id'])
        return len(stale)

    def add_task(self, task: Task) -> str:
        task.validate()
        task_id = str(uuid.uuid4())
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?)',
                       (task_id, task.issue, task.owner, compact(asdict(task)), 0, utc()))
            self._event(db, 'TASK_REGISTERED', {'issue': task.issue, 'owner': task.owner,
                                                 'source_sha': task.source_sha})
        return task_id

    def task(self, task_id: str) -> tuple[Task, bool]:
        with self._db() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise ValueError('task not found')
        return Task.from_dict(json.loads(row['spec']), require_future=False), bool(row['approved'])

    def list_tasks(self):
        with self._db() as db:
            return [dict(row) for row in db.execute(
                'SELECT id,issue,owner,approved,created_at FROM tasks ORDER BY created_at DESC').fetchall()]

    def budgets(self) -> dict:
        with self._db() as db:
            rows = db.execute("SELECT key,value FROM settings WHERE key IN ('daily_tokens','daily_cost_usd','emergency_stop')").fetchall()
        values = {row['key']: row['value'] for row in rows}
        return {'daily_tokens': int(values['daily_tokens']),
                'daily_cost_usd': float(values['daily_cost_usd']),
                'emergency_stop': values['emergency_stop'] == '1',
                'autonomy': self.settings.autonomy.value,
                'live_execution': False}

    def set_budgets(self, tokens: int, cost: float):
        if not isinstance(tokens, int) or isinstance(tokens, bool) or not 1 <= tokens <= 1_000_000:
            raise ValueError('invalid token cap')
        if not isinstance(cost, (float, int)) or isinstance(cost, bool) or \
           not math.isfinite(cost) or not 0 < cost <= 1000:
            raise ValueError('invalid cost cap')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE settings SET value=? WHERE key='daily_tokens'", (str(tokens),))
            db.execute("UPDATE settings SET value=? WHERE key='daily_cost_usd'", (str(cost),))
            self._event(db, 'BUDGET_UPDATED', {'daily_tokens': tokens, 'daily_cost_usd': cost})

    def approve_task(self, task_id: str, approved: bool, reason: str):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM tasks WHERE id=?', (task_id,)).fetchone():
                raise ValueError('task not found')
            db.execute('UPDATE tasks SET approved=? WHERE id=?', (int(approved), task_id))
            self._event(db, 'TASK_APPROVED' if approved else 'TASK_REJECTED',
                        {'task_id': task_id, 'reason': reason[:300]})

    def admit(self, task_id: str, mode: str) -> str:
        if mode != 'mock':
            raise PermissionError('only mock execution is activated')
        task, _ = self.task(task_id)
        run_id = str(uuid.uuid4())
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT value FROM settings WHERE key='emergency_stop'").fetchone()['value'] != '0':
                raise PermissionError('emergency stop active')
            approved = db.execute('SELECT approved FROM tasks WHERE id=?', (task_id,)).fetchone()
            if not approved or not approved['approved']:
                raise PermissionError('founder has not approved task')
            active = [row['owner'] for row in db.execute("SELECT owner FROM runs WHERE status='RUNNING'")]
            active += [row['owner'] for row in db.execute("SELECT owner FROM pilot_runs WHERE status='RUNNING'")]
            if len(active) >= self.settings.max_active or task.owner in active:
                raise PermissionError('concurrency limit')
            attempts = db.execute('SELECT COUNT(*) n FROM runs WHERE task_id=?', (task_id,)).fetchone()['n']
            if attempts > task.max_retries:
                raise PermissionError('retry budget exhausted')
            if attempts:
                last = db.execute('SELECT id FROM runs WHERE task_id=? ORDER BY started_at DESC LIMIT 1',
                                  (task_id,)).fetchone()
                review = db.execute("SELECT 1 FROM decisions WHERE run_id=? AND actor='founder' "
                                    "AND decision='ACCEPT' LIMIT 1", (last['id'],)).fetchone()
                if not review:
                    raise PermissionError('retry requires founder review decision')
            today = datetime.now(timezone.utc).date().isoformat()
            spent = db.execute('SELECT COALESCE(SUM(reserved_tokens),0) tokens, '
                               'COALESCE(SUM(reserved_cost),0) cost FROM runs WHERE started_at LIKE ?',
                               (today + '%',)).fetchone()
            pilot_spent = db.execute('SELECT COALESCE(SUM(reserved_tokens),0) tokens, '
                                     'COALESCE(SUM(reserved_cost),0) cost FROM pilot_runs '
                                     'WHERE started_at LIKE ?', (today + '%',)).fetchone()
            caps = {row['key']: float(row['value']) for row in db.execute(
                "SELECT key,value FROM settings WHERE key IN ('daily_tokens','daily_cost_usd')")}
            if spent['tokens'] + pilot_spent['tokens'] + task.max_tokens > caps['daily_tokens'] or \
               spent['cost'] + pilot_spent['cost'] + task.max_cost_usd > caps['daily_cost_usd']:
                raise PermissionError('daily budget exceeded')
            db.execute('INSERT INTO runs(id,task_id,owner,status,mode,source_sha,started_at,reserved_tokens,reserved_cost) '
                       'VALUES(?,?,?,?,?,?,?,?,?)',
                       (run_id, task_id, task.owner, 'RUNNING', mode, task.source_sha,
                        utc(), task.max_tokens, task.max_cost_usd))
            self._event(db, 'RUN_ADMITTED', {'task_id': task_id, 'issue': task.issue,
                                            'owner': task.owner, 'source_sha': task.source_sha,
                                            'max_tokens': task.max_tokens,
                                            'max_cost_usd': task.max_cost_usd,
                                            'timeout_seconds': task.timeout_seconds,
                                            'mode': mode}, run_id)
        return run_id

    def run(self, run_id: str) -> dict:
        with self._db() as db:
            row = db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise ValueError('run not found')
        return dict(row)

    def list_runs(self):
        with self._db() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM runs ORDER BY started_at DESC LIMIT 100').fetchall()]

    def log(self, run_id: str, text: str):
        with self._db() as db:
            db.execute('INSERT INTO logs(run_id,at,text) VALUES(?,?,?)',
                       (run_id, utc(), redact(text[:4000])))

    def checkpoint(self, run_id: str, stage: str, payload: dict):
        safe = compact(redact(payload))
        with self._db() as db:
            db.execute('INSERT INTO checkpoints(run_id,at,stage,payload) VALUES(?,?,?,?)',
                       (run_id, utc(), stage, safe))
            self._event(db, 'CHECKPOINT', {'stage': stage}, run_id)

    def latest_checkpoint(self, run_id: str, stage: str) -> dict | None:
        with self._db() as db:
            row = db.execute('SELECT payload FROM checkpoints WHERE run_id=? AND stage=? '
                             'ORDER BY id DESC LIMIT 1', (run_id, stage)).fetchone()
        return json.loads(row['payload']) if row else None

    def finish(self, run_id: str, status: str, head_sha: str | None,
               used_tokens: int | None, used_cost: float | None, ci_state: str):
        if status not in ('FAILED', 'WAITING_CI', 'AWAITING_REVIEW', 'PAUSED', 'STOPPED'):
            raise ValueError('invalid finish status')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if not row or row['status'] != 'RUNNING':
                raise ValueError('run not active')
            if used_tokens is not None and (used_tokens < 0 or used_tokens > row['reserved_tokens']):
                status = 'FAILED'
            if used_cost is not None and (used_cost < 0 or used_cost > row['reserved_cost']):
                status = 'FAILED'
            db.execute('UPDATE runs SET status=?,head_sha=?,finished_at=?,used_tokens=?,used_cost=?,ci_state=? WHERE id=?',
                       (status, head_sha, utc(), used_tokens, used_cost, ci_state, run_id))
            self._event(db, 'RUN_FINISHED', {'status': status, 'head_sha': head_sha,
                                            'used_tokens': used_tokens, 'used_cost': used_cost,
                                            'ci_state': ci_state}, run_id)

    def update_ci(self, run_id: str, ci_state: str, status: str):
        if status not in ('WAITING_CI', 'AWAITING_REVIEW', 'FAILED'):
            raise ValueError('invalid CI transition')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status FROM runs WHERE id=?', (run_id,)).fetchone()
            if not row or row['status'] != 'WAITING_CI':
                raise ValueError('run is not awaiting CI')
            db.execute('UPDATE runs SET status=?,ci_state=? WHERE id=?', (status, ci_state, run_id))
            self._event(db, 'CI_UPDATED', {'ci_state': ci_state, 'status': status}, run_id)

    def decide(self, run_id: str, actor: str, decision: str, reason: str):
        if actor not in ('founder', 'chief_architect') or decision not in ('ACCEPT', 'REJECT', 'PAUSE', 'PUBLISH'):
            raise ValueError('invalid decision')
        with self._db() as db:
            db.execute('INSERT INTO decisions(run_id,at,actor,decision,reason) VALUES(?,?,?,?,?)',
                       (run_id, utc(), actor, decision, redact(reason[:1000])))
            self._event(db, 'REVIEW_DECISION', {'actor': actor, 'decision': decision,
                                                'reason': reason[:300]}, run_id)

    def decisions(self, run_id: str):
        with self._db() as db:
            return [dict(row) for row in db.execute('SELECT * FROM decisions WHERE run_id=? ORDER BY id',
                                                     (run_id,)).fetchall()]

    def review_packet(self, run_id: str) -> dict:
        result = self.run(run_id)
        with self._db() as db:
            logs = [dict(row) for row in db.execute(
                'SELECT at,text FROM logs WHERE run_id=? ORDER BY id', (run_id,)).fetchall()]
            checkpoints = [dict(row) for row in db.execute(
                'SELECT at,stage,payload FROM checkpoints WHERE run_id=? ORDER BY id',
                (run_id,)).fetchall()]
        return {'run': result, 'decisions': self.decisions(run_id),
                'logs': logs, 'checkpoints': checkpoints,
                'audit_valid': self.verify_events()}

    def request_stop(self, run_id: str, emergency: bool = False):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            if emergency:
                db.execute("UPDATE settings SET value='1' WHERE key='emergency_stop'")
                db.execute("UPDATE runs SET stop_requested=1 WHERE status='RUNNING'")
                db.execute("UPDATE pilot_runs SET stop_requested=1 WHERE status='RUNNING'")
            else:
                db.execute('UPDATE runs SET stop_requested=1 WHERE id=? AND status=\'RUNNING\'', (run_id,))
            self._event(db, 'EMERGENCY_STOP' if emergency else 'STOP_REQUESTED', {}, run_id)

    def clear_emergency(self):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM pilot_runs WHERE status='RUNNING' LIMIT 1").fetchone() or \
               db.execute("SELECT 1 FROM runs WHERE status='RUNNING' LIMIT 1").fetchone():
                raise PermissionError('active run must be recovered before clearing stop')
            db.execute("UPDATE settings SET value='0' WHERE key='emergency_stop'")
            self._event(db, 'EMERGENCY_CLEARED', {})

    def save_pr(self, run_id: str, url: str):
        with self._db() as db:
            db.execute('UPDATE runs SET pr_url=? WHERE id=?', (url, run_id))
            self._event(db, 'DRAFT_PR_CREATED', {'url': url}, run_id)

    def add_proposal(self, body: dict) -> str:
        proposal_id = str(uuid.uuid4())
        with self._db() as db:
            db.execute('INSERT INTO proposals VALUES(?,?,?,?)',
                       (proposal_id, utc(), compact(redact(body)), 'PENDING'))
            self._event(db, 'TASK_PROPOSED', {'proposal_id': proposal_id})
        return proposal_id

    def proposal(self, proposal_id: str) -> dict:
        with self._db() as db:
            row = db.execute('SELECT * FROM proposals WHERE id=?', (proposal_id,)).fetchone()
        if not row:
            raise ValueError('proposal not found')
        return dict(row)

    def list_proposals(self):
        with self._db() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM proposals ORDER BY at DESC LIMIT 100').fetchall()]

    def mark_proposal(self, proposal_id: str, status: str):
        if status not in ('PUBLISHED', 'REJECTED'):
            raise ValueError('invalid proposal status')
        with self._db() as db:
            db.execute('UPDATE proposals SET status=? WHERE id=? AND status=\'PENDING\'',
                       (status, proposal_id))
            if not db.total_changes:
                raise ValueError('proposal not pending')
            self._event(db, 'PROPOSAL_' + status, {'proposal_id': proposal_id})

    def pilot_approve(self, spec: dict) -> str:
        approval_id = str(uuid.uuid4())
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO pilot_approvals(id,created_at,expires_at,spec) VALUES(?,?,?,?)',
                       (approval_id, utc(), spec['expires_at'], compact(spec)))
            self._event(db, 'PILOT_APPROVED', {'approval_id': approval_id,
                                               'owner': spec['owner'],
                                               'source_sha': spec['source_sha'],
                                               'provider': spec['provider'],
                                               'model': spec['model'],
                                               'expires_at': spec['expires_at']})
        return approval_id

    def pilot_approval(self, approval_id: str) -> dict:
        with self._db() as db:
            row = db.execute('SELECT * FROM pilot_approvals WHERE id=?',
                             (approval_id,)).fetchone()
        if not row:
            raise ValueError('pilot approval not found')
        result = dict(row)
        result['spec'] = json.loads(result['spec'])
        return result

    def pilot_revoke(self, approval_id: str) -> str | None:
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT used_run_id FROM pilot_approvals WHERE id=?',
                             (approval_id,)).fetchone()
            if not row:
                raise ValueError('pilot approval not found')
            db.execute('UPDATE pilot_approvals SET revoked=1 WHERE id=?', (approval_id,))
            if row['used_run_id']:
                db.execute("UPDATE pilot_runs SET stop_requested=1 WHERE id=? AND status='RUNNING'",
                           (row['used_run_id'],))
            self._event(db, 'PILOT_REVOKED', {'approval_id': approval_id}, row['used_run_id'])
        return row['used_run_id']

    def pilot_admit(self, approval_id: str) -> str:
        if self.settings.autonomy != Autonomy.SUPERVISED or not self.settings.mock_only:
            raise PermissionError('pilot requires supervised mock mode')
        run_id = str(uuid.uuid4())
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM pilot_approvals WHERE id=?',
                             (approval_id,)).fetchone()
            if not row:
                raise ValueError('pilot approval not found')
            spec = json.loads(row['spec'])
            expiry = datetime.fromisoformat(row['expires_at'].replace('Z', '+00:00'))
            if row['revoked'] or row['used_run_id'] or expiry <= datetime.now(timezone.utc):
                raise PermissionError('pilot approval revoked, used or expired')
            if db.execute("SELECT value FROM settings WHERE key='emergency_stop'").fetchone()['value'] != '0':
                raise PermissionError('emergency stop active')
            active = [x['owner'] for x in db.execute("SELECT owner FROM runs WHERE status='RUNNING'")]
            active += [x['owner'] for x in db.execute("SELECT owner FROM pilot_runs WHERE status='RUNNING'")]
            if len(active) >= self.settings.max_active or spec['owner'] in active:
                raise PermissionError('pilot concurrency limit')
            today = datetime.now(timezone.utc).date().isoformat() + '%'
            normal = db.execute('SELECT COALESCE(SUM(reserved_tokens),0) tokens, '
                                'COALESCE(SUM(reserved_cost),0) cost FROM runs WHERE started_at LIKE ?',
                                (today,)).fetchone()
            prior = db.execute('SELECT COALESCE(SUM(reserved_tokens),0) tokens, '
                               'COALESCE(SUM(reserved_cost),0) cost FROM pilot_runs WHERE started_at LIKE ?',
                               (today,)).fetchone()
            caps = {x['key']: float(x['value']) for x in db.execute(
                "SELECT key,value FROM settings WHERE key IN ('daily_tokens','daily_cost_usd')")}
            if normal['tokens'] + prior['tokens'] + spec['max_tokens'] > caps['daily_tokens'] or \
               normal['cost'] + prior['cost'] + spec['max_cost_usd'] > caps['daily_cost_usd']:
                raise PermissionError('pilot daily budget exceeded')
            name = 'orch-ro-' + run_id.replace('-', '')
            db.execute('INSERT INTO pilot_runs(id,approval_id,owner,status,source_sha,started_at,'
                       'reserved_tokens,reserved_cost,container_name) VALUES(?,?,?,?,?,?,?,?,?)',
                       (run_id, approval_id, spec['owner'], 'RUNNING', spec['source_sha'],
                        utc(), spec['max_tokens'], spec['max_cost_usd'], name))
            db.execute('UPDATE pilot_approvals SET used_run_id=? WHERE id=?',
                       (run_id, approval_id))
            self._event(db, 'PILOT_ADMITTED', {'approval_id': approval_id,
                                               'owner': spec['owner'],
                                               'source_sha': spec['source_sha'],
                                               'reserved_tokens': spec['max_tokens'],
                                               'reserved_cost': spec['max_cost_usd'],
                                               'container_name': name}, run_id)
        return run_id

    def pilot_run(self, run_id: str) -> dict:
        with self._db() as db:
            row = db.execute('SELECT * FROM pilot_runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise ValueError('pilot run not found')
        return dict(row)

    def pilot_runs(self) -> list[dict]:
        with self._db() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM pilot_runs ORDER BY started_at DESC LIMIT 100').fetchall()]

    def pilot_finish(self, run_id: str, status: str, head_sha: str | None,
                     input_tokens: int | None, output_tokens: int | None,
                     charged_cost: float | None, report: dict | None,
                     report_sha256: str | None, error_code: str | None):
        if status not in ('MOCK_VERIFIED_READ_ONLY', 'FAILED', 'STOPPED'):
            raise ValueError('invalid pilot result')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM pilot_runs WHERE id=?', (run_id,)).fetchone()
            if not row or row['status'] != 'RUNNING':
                raise ValueError('pilot run not active')
            if row['stop_requested']:
                status = 'STOPPED'
            if status == 'MOCK_VERIFIED_READ_ONLY' and (input_tokens is None or output_tokens is None or
                    charged_cost is None or report is None or head_sha != row['source_sha'] or
                    input_tokens < 0 or output_tokens < 0 or charged_cost < 0 or
                    input_tokens + output_tokens > row['reserved_tokens'] or
                    charged_cost > row['reserved_cost']):
                status = 'FAILED'
                error_code = 'METER_OR_HEAD_INVALID'
            db.execute('UPDATE pilot_runs SET status=?,head_sha=?,finished_at=?,input_tokens=?, '
                       'output_tokens=?,charged_cost=?,report=?,report_sha256=?,error_code=? WHERE id=?',
                       (status, head_sha, utc(), input_tokens, output_tokens,
                        charged_cost, compact(report) if report else None,
                        report_sha256, error_code, run_id))
            self._event(db, 'PILOT_FINISHED', {'status': status, 'head_sha': head_sha,
                                               'input_tokens': input_tokens,
                                               'output_tokens': output_tokens,
                                               'charged_cost': charged_cost,
                                               'error_code': error_code}, run_id)

    def pilot_stop(self, run_id: str):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE pilot_runs SET stop_requested=1 WHERE id=? AND status='RUNNING'",
                       (run_id,))
            self._event(db, 'PILOT_STOP_REQUESTED', {}, run_id)

    def pilot_orphans(self) -> list[dict]:
        with self._db() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,container_name FROM pilot_runs WHERE status='RUNNING'").fetchall()]

    def pilot_mark_recovered(self, run_id: str):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute("UPDATE pilot_runs SET status='RECOVERY_REQUIRED',stop_requested=1,"
                                 "finished_at=? WHERE id=? AND status='RUNNING'",
                                 (utc(), run_id)).rowcount
            if changed:
                self._event(db, 'PILOT_RECOVERED', {'result': 'RECOVERY_REQUIRED'}, run_id)
        return bool(changed)
