"""Issue #9 MOCK_ONLY role routing across three isolated Actions jobs."""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from .hosted_offline import DockerMockRunner, _context_from_environment, _git, make_task, verify_source
from .hosted_policy import (FIXTURE_SHA256, IMAGE, REPOSITORY, HostedContext,
                            canonical, sha256)
from .policy import clean_path

ROLE_SOURCE = 'orchestrator/hosted_mock_roles.py'
ROLE_SHA256 = '85abed578681c08f5cc0767238e889a7ffffe4b798cce01abd4150436ea8a344'
ROLES = ('codex-blocked', 'kilo-diagnostic', 'codex-resume')
JOBS = ('coord-codex', 'coord-kilo', 'coord-codex-resume')
ALLOWED = ('tests/fixtures/hosted_public.json',)
ACCEPTANCE = ('tests/test_hosted_coordination.py::test_blocked_route_and_normal_success',)
USAGE = {'provider_calls': 0, 'tokens': 0, 'charged_cost_usd': 0}
OUTCOMES = {
    'codex-blocked': {'status': 'BLOCKED', 'reason': 'SYNTHETIC_ASSERTION',
                      'failed_attempts': 2,
                      'attempt_codes': ['SYNTHETIC_ASSERTION_A',
                                        'SYNTHETIC_ASSERTION_B']},
    'kilo-diagnostic': {'status': 'FINDING', 'finding': 'CHECK_FIXTURE_ID',
                        'suggested_path': ALLOWED[0]},
    'codex-resume': {'status': 'VERIFIED', 'check': 'FIXTURE_ID_MATCH',
                     'fixture_id': 'hosted-public-v1'},
}


def validate_context(context: HostedContext, role: str) -> None:
    if role not in ROLES or context.job != JOBS[ROLES.index(role)]:
        raise PermissionError('unapproved role or job')
    # The existing hosted context validates repository, immutable run identity,
    # event/ref and workflow identity. Only the job name differs.
    replace(context, job='offline-mock').validate()


def task_spec(context: HostedContext, role: str) -> dict:
    validate_context(context, role)
    for path in ALLOWED:
        if clean_path(path) != path:
            raise PermissionError('unapproved task path')
    return {'mode': 'MOCK_ONLY', 'issue': 9, 'repository': REPOSITORY,
            'assigner': 'chief_architect',
            'source_sha': context.source_sha, 'run_id': context.run_id,
            'run_attempt': context.attempt, 'ref': context.ref,
            'owner': 'kilo' if role == 'kilo-diagnostic' else 'codex',
            'primary_owner': 'codex', 'backup': 'kilo', 'role': role,
            'allowed_paths': list(ALLOWED), 'acceptance': list(ACCEPTANCE),
            'fixture_sha256': FIXTURE_SHA256, 'image_ref': IMAGE,
            'mock_cli_sha256': ROLE_SHA256, 'timeout_seconds': 30,
            'max_attempts': 2 if role == 'codex-blocked' else 1,
            'max_tokens': 0, 'max_cost_usd': 0,
            'founder_approval': 'SIMULATED_ONLY', 'founder_approved_simulated': True,
            'model_spend': False,
            'diagnostic_only': role == 'kilo-diagnostic',
            'diagnostic_finding': 'CHECK_FIXTURE_ID' if role == 'codex-resume' else None}


def expected_report(task: dict) -> dict:
    role = task['role']
    return {'mode': 'MOCK_ONLY', 'role': role, 'owner': task['owner'],
            'source_sha': task['source_sha'], 'task_digest': sha256(canonical(task)),
            'outcome': OUTCOMES[role], 'usage': USAGE}


def _append(ledger: dict, kind: str, data: dict) -> None:
    previous = ledger['events'][-1]['hash'] if ledger['events'] else '0' * 64
    row = {'seq': len(ledger['events']) + 1, 'kind': kind, 'data': data,
           'prev_hash': previous}
    row['hash'] = sha256(canonical(row))
    ledger['events'].append(row)


def expected_ledger(context: HostedContext, through: str) -> dict:
    if through not in ROLES:
        raise PermissionError('unknown coordination state')
    first = task_spec(replace(context, job=JOBS[0]), ROLES[0])
    ledger = {'mode': 'MOCK_ONLY', 'issue': 9, 'source_sha': context.source_sha,
              'run_id': context.run_id, 'run_attempt': context.attempt,
              'primary_owner': 'codex', 'backup': 'kilo',
              'allowed_paths': list(ALLOWED), 'acceptance': list(ACCEPTANCE),
              'founder_approval': 'SIMULATED_ONLY',
              'founder_approved_simulated': True, 'model_spend': False,
              'provider_calls': 0, 'spent_usd': 0, 'events': [],
              'state': 'ASSIGNED', 'handoff_reason': None,
              'ci_evidence': None}
    _append(ledger, 'TASK_ASSIGNED', {'task_digest': sha256(canonical(first)),
                                      'owner': 'codex', 'source_sha': context.source_sha})
    for role, job, kind, state in zip(ROLES, JOBS,
            ('CODEX_BLOCKED', 'KILO_DIAGNOSED', 'CODEX_VERIFIED'),
            ('BLOCKED', 'DIAGNOSED', 'VERIFIED')):
        task = task_spec(replace(context, job=job), role)
        report = expected_report(task)
        _append(ledger, kind, {'task_digest': sha256(canonical(task)),
                               'result_sha256': sha256(canonical(report)),
                               'owner': task['owner'], 'job': job,
                               'attempts': task['max_attempts'],
                               'reason': 'SYNTHETIC_ASSERTION' if role == ROLES[0] else None,
                               'finding': 'CHECK_FIXTURE_ID' if role == ROLES[1] else None})
        ledger['state'] = state
        if role == ROLES[0]:
            ledger['handoff_reason'] = 'SYNTHETIC_ASSERTION'
        if role == ROLES[2]:
            ledger['ci_evidence'] = {'source_sha': context.source_sha,
                                     'job': JOBS[2], 'acceptance': list(ACCEPTANCE),
                                     'run_url': 'https://github.com/' + REPOSITORY +
                                                '/actions/runs/' + context.run_id,
                                     'check': 'FIXTURE_ID_MATCH', 'status': 'MOCK_VERIFIED'}
            _append(ledger, 'MOCK_REVIEW_ACCEPTED',
                    {'actor': 'deterministic_mock_verifier',
                     'source_sha': context.source_sha, 'check': 'FIXTURE_ID_MATCH'})
        if role == through:
            break
    return ledger


def _read_exact(path: Path, expected: dict) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise PermissionError('missing or unsafe handoff artifact')
    try:
        actual = json.loads(path.read_bytes())
    except (ValueError, UnicodeDecodeError) as exc:
        raise PermissionError('invalid handoff artifact') from exc
    if actual != expected or path.read_bytes() != canonical(expected) + b'\n':
        raise PermissionError('handoff state, SHA or audit chain mismatch')
    return actual


def run_stage(root: Path, context: HostedContext, role: str, output: Path,
              incoming: Path | None = None, runner: DockerMockRunner | None = None) -> dict:
    validate_context(context, role)
    if (role == ROLES[0] and incoming is not None) or (role != ROLES[0] and incoming is None):
        raise PermissionError('wrong handoff input')
    base = replace(context, job='offline-mock')
    fixture, _, review = verify_source(root, base)
    role_path = root / ROLE_SOURCE
    if role_path.is_symlink() or not role_path.is_file() or not role_path.resolve().is_relative_to(root.resolve()):
        raise PermissionError('untrusted mock role executable')
    role_bytes = role_path.read_bytes()
    if len(role_bytes) > 8192 or sha256(role_bytes) != ROLE_SHA256 or \
       _git(root, 'show', context.source_sha + ':' + ROLE_SOURCE) != role_bytes:
        raise PermissionError('mock role executable pin mismatch')
    prior = {ROLES[1]: ROLES[0], ROLES[2]: ROLES[1]}.get(role)
    handoff = None
    if prior:
        handoff = _read_exact(incoming, expected_ledger(context, prior))
    task = task_spec(context, role)
    if role == ROLES[2] and handoff['events'][-1]['data']['finding'] != task['diagnostic_finding']:
        raise PermissionError('diagnostic finding changed')
    sandbox_task = make_task(base, review)  # Existing pinned Docker sandbox contract.
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'coordination-ledger.json').exists():
        raise PermissionError('duplicate role execution')
    with tempfile.TemporaryDirectory(prefix='coord-public-', dir=output) as directory:
        stage = Path(directory) / 'public'
        stage.mkdir(mode=0o755)
        staged_task = {**task, 'task_digest': sha256(canonical(task))}
        for name, value in {'hosted_public.json': fixture,
                            'mock_roles.py': role_bytes,
                            'task.json': canonical(staged_task)}.items():
            target = stage / name
            target.write_bytes(value)
            target.chmod(0o444)
        stage.chmod(0o755)
        if {p.name for p in stage.iterdir()} != {'hosted_public.json', 'mock_roles.py', 'task.json'}:
            raise PermissionError('unexpected sandbox file')
        raw = (runner or DockerMockRunner()).run(sandbox_task, stage,
                                                  script='mock_roles.py', role=role)
    if len(raw) > 4096:
        raise PermissionError('oversized mock role result')
    try:
        report = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PermissionError('invalid mock role result') from exc
    if raw != canonical(expected_report(task)) and raw.strip() != canonical(expected_report(task)):
        raise PermissionError('untrusted mock role result or usage')
    ledger = expected_ledger(context, role)
    (output / 'coordination-ledger.json').write_bytes(canonical(ledger) + b'\n')
    return ledger


def normal_success(context: HostedContext) -> dict:
    """Normal Codex success has no backup handoff or Kilo assignment."""
    first = task_spec(replace(context, job=JOBS[0]), ROLES[0])
    ledger = {'mode': 'MOCK_ONLY', 'source_sha': context.source_sha,
              'owner': 'codex', 'state': 'VERIFIED', 'backup_routed': False,
              'provider_calls': 0, 'spent_usd': 0, 'task_digest': sha256(canonical(first)),
              'check': 'FIXTURE_ID_MATCH'}
    return ledger


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in ROLES:
        raise SystemExit('one approved mock role and artifact paths required')
    role = sys.argv[1]
    context = _context_from_environment()
    incoming = None if sys.argv[3] == '-' else Path(sys.argv[3])
    result = run_stage(Path.cwd().resolve(), context, role, Path(sys.argv[2]), incoming)
    print(json.dumps({'mode': 'MOCK_ONLY', 'state': result['state'],
                      'source_sha': result['source_sha'], 'provider_calls': 0}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
