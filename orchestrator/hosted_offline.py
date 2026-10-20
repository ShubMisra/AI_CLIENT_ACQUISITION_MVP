"""One-shot GitHub-hosted MOCK Codex demonstration. No inference path exists."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path, PurePosixPath

from .hosted_policy import (FIXTURE, FIXTURE_ID, FIXTURE_SHA256, IMAGE,
                            MOCK_CLI_SHA256, REPOSITORY, WORKFLOW,
                            HostedContext, HostedLedger, HostedTask, canonical,
                            sha256, simulate_founder_approval, utc_now)

MOCK_SOURCE = 'orchestrator/hosted_mock_codex.py'
REVIEW_SOURCE = 'docs/coordination/HOSTED_PILOT_SECURITY.md'
MAX_OUTPUT_BYTES = 4096


class HostedCancelled(Exception):
    pass


class TerminationUnverified(RuntimeError):
    pass


class MockExecutionFailure(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(['git', *args], cwd=root, capture_output=True,
                            timeout=10, check=False)
    if result.returncode:
        raise PermissionError('source Git verification failed')
    return result.stdout.strip() if args[:1] == ('rev-parse',) else result.stdout


def verify_source(root: Path, context: HostedContext) -> tuple[bytes, bytes, bytes]:
    context.validate()
    if _git(root, 'rev-parse', 'HEAD').decode() != context.source_sha:
        raise PermissionError('checked-out SHA differs from workflow SHA')
    files = []
    for relative, maximum in ((FIXTURE, 1024), (MOCK_SOURCE, 8192), (REVIEW_SOURCE, 30000)):
        path = root / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise PermissionError('untrusted source path')
        data = path.read_bytes()
        if len(data) > maximum or _git(root, 'show', context.source_sha + ':' + relative) != data:
            raise PermissionError('source file differs from immutable SHA')
        files.append(data)
    if sha256(files[0]) != FIXTURE_SHA256 or sha256(files[1]) != MOCK_CLI_SHA256:
        raise PermissionError('fixture or mock executable pin mismatch')
    public = json.loads(files[0])
    if public != {'fixture_id': FIXTURE_ID, 'company': 'Synthetic Example Co',
                  'note': 'Public toy task only'}:
        raise PermissionError('public fixture content drift')
    return tuple(files)


def make_task(context: HostedContext, review_bytes: bytes) -> HostedTask:
    context.validate()
    return HostedTask(
        mode='MOCK', issue=9, owner='codex', repository=REPOSITORY,
        source_sha=context.source_sha, fixture_id=FIXTURE_ID,
        fixture_sha256=FIXTURE_SHA256, image_ref=IMAGE,
        cli_path='/usr/local/bin/python3', cli_sha256=MOCK_CLI_SHA256,
        cli_version='mock-codex/1', provider='offline', model='mock-codex',
        max_input_tokens=0, max_output_tokens=0, max_cost_usd=0,
        timeout_seconds=30, nonce=secrets.token_hex(16),
        expires_at=(utc_now() + timedelta(minutes=5)).isoformat(),
        founder='SIMULATED_FOUNDER', review_digest=sha256(review_bytes),
        run_id=context.run_id, attempt=context.attempt)


def stage_public(path: Path, task: HostedTask, files: tuple[bytes, bytes, bytes]) -> None:
    task.validate()
    path.mkdir(mode=0o755)
    facts = {'source_sha': task.source_sha, 'fixture_sha256': task.fixture_sha256}
    staged = {'hosted_public.json': files[0], 'mock_codex.py': files[1],
              'facts.json': canonical(facts)}
    for name, data in staged.items():
        destination = path / name
        destination.write_bytes(data)
        destination.chmod(0o444)
    path.chmod(0o755)
    if {p.name for p in path.iterdir()} != set(staged):
        raise PermissionError('sandbox staging contains unexpected files')


def _json_no_duplicates(raw: str) -> object:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('duplicate result field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def verify_mock_result(raw: bytes, task: HostedTask) -> dict:
    if len(raw) > MAX_OUTPUT_BYTES:
        raise PermissionError('mock output too large')
    try:
        result = _json_no_duplicates(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PermissionError('invalid mock output') from exc
    expected = {
        'mode': 'MOCK', 'status': 'MOCK_VERIFIED_READ_ONLY',
        'source_sha': task.source_sha, 'fixture_sha256': task.fixture_sha256,
        'fixture': {'fixture_id': FIXTURE_ID, 'company': 'Synthetic Example Co',
                    'note': 'Public toy task only'},
        'cli_version': 'mock-codex/1',
        'checks': {'private_paths_absent': True, 'secret_env_absent': True,
                   'write_denied': True, 'network_denied': True},
        'usage': {'input_tokens': 0, 'output_tokens': 0, 'charged_cost_usd': 0,
                  'provider_calls': 0, 'evidence': 'OFFLINE_NO_PROVIDER'},
    }
    if type(result) is not dict or result != expected:
        raise PermissionError('mock report, containment or usage mismatch')
    for key in ('input_tokens', 'output_tokens', 'charged_cost_usd', 'provider_calls'):
        if type(result['usage'][key]) is not int:
            raise PermissionError('invalid measured mock usage')
    return result


class DockerMockRunner:
    """No model transport. Only a pinned Python image and pinned mock script."""

    def __init__(self, docker: str = '/usr/bin/docker'):
        if not PurePosixPath(docker).is_absolute():
            raise ValueError('absolute Docker path required')
        self.docker = docker

    def command(self, task: HostedTask, stage: Path) -> list[str]:
        task.validate()
        if not stage.is_dir() or stage.is_symlink():
            raise PermissionError('missing public staging directory')
        return [self.docker, 'run', '--rm', '--pull=never', '--name',
                'hosted-mock-' + task.nonce[:16], '--network=none', '--read-only',
                '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                '--pids-limit=16', '--memory=128m', '--cpus=1',
                '--user=65532:65532', '--mount',
                'type=bind,src=' + str(stage.resolve()) + ',dst=/fixture,readonly',
                '--tmpfs', '/tmp:rw,noexec,nosuid,size=8m', '--workdir=/fixture',
                '--env', 'HOME=/tmp', '--env', 'PATH=/usr/local/bin:/usr/bin:/bin',
                '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint',
                task.cli_path, task.image_ref, '/fixture/mock_codex.py',
                'exec', '--sandbox', 'read-only', '--fixture', '/fixture']

    def _call(self, args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
        # Docker client receives no inherited provider, GitHub or host secret env.
        return subprocess.run(args, capture_output=True, timeout=timeout,
                              env={'PATH': '/usr/bin:/bin', 'HOME': '/tmp'}, check=False)

    def _not_running(self, name: str) -> bool:
        result = self._call([self.docker, 'ps', '--format', '{{.Names}}',
                             '--filter', 'name=^/' + name + '$'])
        if result.returncode:
            raise TerminationUnverified('container status cannot be verified')
        return not result.stdout.strip()

    def _kill_and_verify(self, name: str) -> None:
        self._call([self.docker, 'kill', name])
        if not self._not_running(name):
            raise TerminationUnverified('container still running')

    def run(self, task: HostedTask, stage: Path, stop_requested=lambda: False) -> bytes:
        task.validate()
        if stop_requested():
            raise HostedCancelled('mock run stopped before launch')
        identity = self._call([self.docker, 'image', 'inspect', '--format',
                               '{{json .RepoDigests}}', task.image_ref])
        try:
            digests = json.loads(identity.stdout)
        except (ValueError, TypeError) as exc:
            raise PermissionError('image identity unavailable') from exc
        expected_digest = task.image_ref.split('@', 1)[1]
        valid_refs = {'python@' + expected_digest,
                      'docker.io/library/python@' + expected_digest}
        if identity.returncode or not isinstance(digests, list) or \
           not any(ref in valid_refs for ref in digests):
            raise PermissionError('pinned image unavailable')
        command = self.command(task, stage)
        name = 'hosted-mock-' + task.nonce[:16]
        try:
            completed = self._call(command, timeout=task.timeout_seconds)
        except (subprocess.TimeoutExpired, HostedCancelled, KeyboardInterrupt):
            self._kill_and_verify(name)
            raise HostedCancelled('mock container cancelled or timed out') from None
        if not self._not_running(name):
            self._kill_and_verify(name)
            raise TerminationUnverified('mock container did not stop')
        if stop_requested():
            raise HostedCancelled('mock run stopped')
        if completed.returncode:
            code = 'MOCK_EXIT_' + str(completed.returncode) if 0 <= completed.returncode <= 255 \
                else 'MOCK_EXIT_UNKNOWN'
            if len(completed.stdout) <= MAX_OUTPUT_BYTES:
                try:
                    checks = json.loads(completed.stdout).get('checks', {})
                    for name in ('private_paths_absent', 'secret_env_absent',
                                 'write_denied', 'network_denied'):
                        if checks.get(name) is False:
                            code += '_' + name.upper()
                except (ValueError, AttributeError, TypeError):
                    pass
            raise MockExecutionFailure(code)
        return completed.stdout


def run_offline(root: Path, context: HostedContext, output: Path,
                runner: DockerMockRunner | None = None,
                stop_requested=lambda: False) -> dict:
    fixture, mock, review = verify_source(root, context)
    task = make_task(context, review)
    key = secrets.token_bytes(32)  # Local simulation only; never staged or persisted.
    approval = simulate_founder_approval(task, key)
    output.mkdir(parents=True, exist_ok=True)
    ledger = HostedLedger(output / 'mock-ledger.sqlite')
    ledger.claim(task, approval, key, context)
    phase = 'prelaunch'
    try:
        if stop_requested():
            raise HostedCancelled('mock run cancelled before launch')
        with tempfile.TemporaryDirectory(prefix='hosted-mock-', dir=output) as temporary:
            Path(temporary).chmod(0o755)
            stage = Path(temporary) / 'public'
            stage_public(stage, task, (fixture, mock, review))
            phase = 'container'
            raw = (runner or DockerMockRunner()).run(task, stage, stop_requested)
            if stop_requested():
                raise HostedCancelled('mock run cancelled after process exit')
            phase = 'report'
            report = verify_mock_result(raw, task)
        result_sha = sha256(canonical(report))
        audit_sha = ledger.finish(task, 'ACCEPT_MOCK', result_sha)
        result = {'review': 'ACCEPT_MOCK', 'mode': 'MOCK',
                  'status': 'MOCK_VERIFIED_READ_ONLY', 'source_sha': task.source_sha,
                  'fixture_sha256': task.fixture_sha256, 'cli_sha256': task.cli_sha256,
                  'cli_version': task.cli_version, 'image_ref': task.image_ref,
                  'repository': task.repository, 'workflow': WORKFLOW,
                  'task_digest': task.digest(), 'review_digest': task.review_digest,
                  'fixture': report['fixture'], 'exit_code': 0,
                  'run_id': context.run_id, 'job': context.job,
                  'run_url': 'https://github.com/' + task.repository + '/actions/runs/' + context.run_id,
                  'report_sha256': result_sha, 'audit_sha256': audit_sha,
                  'audit_events': ledger.public_events(),
                  'usage': report['usage'], 'checks': report['checks']}
        (output / 'hosted-mock-result.json').write_bytes(canonical(result) + b'\n')
        return result
    except BaseException as exc:
        ledger.finish(task, 'BLOCKED', None)
        # Raw subprocess output and exception text are never published.
        safe_codes = {'pinned image unavailable',
                      'mock report, containment or usage mismatch',
                      'mock output too large', 'invalid measured mock usage'}
        code = exc.code if type(exc) is MockExecutionFailure else (
            str(exc) if type(exc) is PermissionError and str(exc) in safe_codes
            else type(exc).__name__)
        raise PermissionError('hosted mock blocked during ' + phase + ': ' + code) from None


def run_real(*_args, **_kwargs):
    raise PermissionError('real Codex inference is disabled pending separate review')


def _context_from_environment() -> HostedContext:
    return HostedContext(os.getenv('GITHUB_REPOSITORY', ''), os.getenv('GITHUB_SHA', ''),
                         os.getenv('GITHUB_RUN_ID', ''),
                         int(os.getenv('GITHUB_RUN_ATTEMPT', '0')),
                         os.getenv('GITHUB_JOB', ''),
                         os.getenv('GITHUB_EVENT_NAME', ''),
                         os.getenv('GITHUB_REF', ''),
                         os.getenv('GITHUB_WORKFLOW_REF', ''))


def main() -> int:
    if sys.argv[1:] != ['offline-mock']:
        raise SystemExit('only offline-mock is available')
    def cancelled(_signum, _frame):
        raise HostedCancelled('workflow cancellation')
    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    context = _context_from_environment()
    root = Path.cwd().resolve()
    output = Path(os.environ['RUNNER_TEMP']) / 'hosted-pilot-result'
    result = run_offline(root, context, output)
    print(json.dumps({'status': result['status'], 'source_sha': result['source_sha'],
                      'result_sha256': result['report_sha256'],
                      'provider_calls': result['usage']['provider_calls']}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
