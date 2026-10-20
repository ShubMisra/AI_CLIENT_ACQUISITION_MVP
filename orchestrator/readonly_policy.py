"""Trusted, offline-only policy and Docker plan for the Issue #8 pilot."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

from .policy import BRANCH, SHA

IMAGE = re.compile(r'^[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}$')
MODEL = re.compile(r'^[A-Za-z0-9][A-Za-z0-9./_-]{0,99}$')
SENSITIVE = re.compile(r'(?i)(private.key|bearer\s+|password|api[_-]?key|credential|secret|token)')
PROMPT = ('Read /fixture/facts.json and /fixture/public_fixture.txt. Return only a JSON '
          'object with exactly branch, source_sha, and fixture_sha256 from facts.json. '
          'Do not edit files, invoke shell commands, access network sites, or request permissions.')


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class RuntimePin:
    owner: str
    docker_executable: str
    image_ref: str
    cli_path: str
    cli_sha256: str
    version: str
    node_path: str = ''
    node_version: str = ''

    def validate(self):
        if self.owner not in ('codex', 'kilo') or not Path(self.docker_executable).is_absolute():
            raise ValueError('absolute Docker executable and known owner required')
        if not IMAGE.fullmatch(self.image_ref) or not re.fullmatch(r'[0-9a-f]{64}', self.cli_sha256):
            raise ValueError('pinned image and CLI digest required')
        if not self.cli_path.startswith('/opt/') or '..' in PurePosixPath(self.cli_path).parts:
            raise ValueError('CLI must use an absolute in-image /opt path')
        if not self.version or len(self.version) > 100:
            raise ValueError('CLI version required')
        if self.owner == 'kilo' and (not self.node_path.startswith('/opt/') or
                                     '..' in PurePosixPath(self.node_path).parts or
                                     not self.node_version):
            raise ValueError('Kilo requires a pinned in-image Node runtime')
        if self.owner == 'codex' and (self.node_path or self.node_version):
            raise ValueError('Codex profile cannot inherit Kilo Node')

    def fingerprint(self) -> str:
        self.validate()
        return digest(asdict(self))


@dataclass(frozen=True)
class ProviderTariff:
    owner: str
    provider: str
    model: str
    input_usd_per_million: str
    output_usd_per_million: str
    max_input_tokens: int
    max_output_tokens: int
    pricing_reference: str

    def validate(self):
        if self.owner not in ('codex', 'kilo') or not MODEL.fullmatch(self.provider) or \
           not MODEL.fullmatch(self.model) or not self.pricing_reference:
            raise ValueError('provider/model price identity missing')
        for value in (self.input_usd_per_million, self.output_usd_per_million):
            try:
                price = Decimal(value)
            except (InvalidOperation, TypeError) as exc:
                raise ValueError('invalid provider price') from exc
            if not price.is_finite() or price < 0:
                raise ValueError('invalid provider price')
        if type(self.max_input_tokens) is not int or type(self.max_output_tokens) is not int or \
           not 1 <= self.max_input_tokens <= 10000 or \
           not 1 <= self.max_output_tokens <= 10000:
            raise ValueError('provider hard token limits missing')

    def maximum_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        self.validate()
        return (Decimal(input_tokens) * Decimal(self.input_usd_per_million) +
                Decimal(output_tokens) * Decimal(self.output_usd_per_million)) / Decimal(1_000_000)


@dataclass(frozen=True)
class PilotSpec:
    issue: int
    owner: str
    worktree: str
    branch: str
    source_sha: str
    provider: str
    model: str
    max_input_tokens: int
    max_output_tokens: int
    max_tokens: int
    max_cost_usd: float
    timeout_seconds: int
    expires_at: str

    @classmethod
    def from_dict(cls, value: dict, *, require_future: bool = True) -> 'PilotSpec':
        if set(value) != set(cls.__dataclass_fields__):
            raise ValueError('pilot spec fields must match exactly')
        item = cls(**value)
        item.validate(require_future=require_future)
        return item

    def validate(self, *, require_future: bool = True):
        if type(self.issue) is not int or self.issue != 8 or \
           self.owner not in ('codex', 'kilo') or not \
           isinstance(self.branch, str) or not BRANCH.fullmatch(self.branch) or \
           not isinstance(self.source_sha, str) or not SHA.fullmatch(self.source_sha):
            raise ValueError('invalid pinned pilot issue or refs')
        if not isinstance(self.worktree, str) or not Path(self.worktree).is_absolute() or \
           not isinstance(self.provider, str) or not isinstance(self.model, str) or \
           not MODEL.fullmatch(self.provider) or not MODEL.fullmatch(self.model):
            raise ValueError('invalid pilot worktree or model')
        values = (self.max_input_tokens, self.max_output_tokens, self.max_tokens,
                  self.timeout_seconds)
        if any(type(x) is not int for x in values) or \
           not 1 <= self.max_input_tokens <= 10000 or \
           not 1 <= self.max_output_tokens <= 10000 or \
           self.max_tokens < self.max_input_tokens + self.max_output_tokens or \
           self.max_tokens > 20000 or not 10 <= self.timeout_seconds <= 300:
            raise ValueError('invalid pilot token or runtime budget')
        if type(self.max_cost_usd) not in (int, float) or not \
           Decimal(str(self.max_cost_usd)).is_finite() or not 0 < self.max_cost_usd <= 5:
            raise ValueError('invalid pilot USD cap')
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
            if expiry.tzinfo is None or (require_future and (expiry <= datetime.now(timezone.utc) or
                    expiry > datetime.now(timezone.utc) + timedelta(hours=24))):
                raise ValueError('pilot approval must expire within 24 hours')
        except (TypeError, AttributeError, ValueError) as exc:
            raise ValueError('invalid pilot expiry') from exc


@dataclass(frozen=True)
class ProbeResult:
    image_ref: str
    cli_sha256: str
    version: str
    node_version: str
    auth_ready: bool
    hard_token_limit: bool
    hard_cost_limit: bool
    evidence_kind: str


@dataclass(frozen=True)
class DockerPlan:
    argv: tuple[str, ...]
    stdin: str | None
    container_name: str
    snapshot_sha256: str
    owner: str


def verify_public_fixture(spec: PilotSpec, root: Path, git_executable: str) -> dict:
    spec.validate()
    root = root.resolve(strict=True)
    worktree = Path(spec.worktree).resolve(strict=True)
    if worktree == root or not worktree.is_relative_to(root):
        raise PermissionError('pilot worktree outside trusted root')
    marker, fixture = worktree / '.orchestrator-fixture', worktree / 'public_fixture.txt'
    if marker.is_symlink() or fixture.is_symlink() or not marker.is_file() or not fixture.is_file() or \
       marker.read_text(encoding='utf-8').strip() != 'TOY_REPO_ONLY':
        raise PermissionError('public synthetic fixture marker required')
    def git(*args):
        result = subprocess.run([git_executable, *args], cwd=worktree, text=True,
                                capture_output=True, timeout=10, check=False)
        if result.returncode:
            raise PermissionError('read-only Git verification failed')
        return result.stdout.strip()
    if Path(git('rev-parse', '--show-toplevel')).resolve(strict=True) != worktree or \
       git('branch', '--show-current') != spec.branch or \
       git('rev-parse', 'HEAD') != spec.source_sha or git('status', '--porcelain'):
        raise PermissionError('pilot source branch, SHA or cleanliness changed')
    if git('show', spec.source_sha + ':.orchestrator-fixture') != 'TOY_REPO_ONLY':
        raise PermissionError('synthetic fixture marker is not tracked at source SHA')
    source = git('show', spec.source_sha + ':public_fixture.txt')
    current = fixture.read_text(encoding='utf-8')
    if len(current.encode()) > 4096 or source != current.strip() or '\x00' in current or \
       SENSITIVE.search(current):
        raise PermissionError('fixture is not approved public/synthetic text')
    return {'branch': spec.branch, 'source_sha': spec.source_sha,
            'fixture_sha256': hashlib.sha256(current.encode()).hexdigest(),
            'fixture_text': current}


def build_docker_plan(pin: RuntimePin, spec: PilotSpec, snapshot: Path,
                      snapshot_sha256: str, container_name: str) -> DockerPlan:
    pin.validate()
    spec.validate()
    if pin.owner != spec.owner or not snapshot.is_dir() or \
       not re.fullmatch(r'orch-ro-[0-9a-f]{32}', container_name) or \
       not re.fullmatch(r'[0-9a-f]{64}', snapshot_sha256):
        raise PermissionError('invalid isolated runner identity')
    source = str(snapshot.resolve(strict=True))
    if ',' in source:
        raise PermissionError('unsupported bind source path')
    path = ':'.join(dict.fromkeys(part for part in
                                  (str(PurePosixPath(pin.cli_path).parent),
                                   str(PurePosixPath(pin.node_path).parent) if pin.node_path else '',
                                   '/usr/bin', '/bin') if part))
    common = (pin.docker_executable, 'run', '--rm', '--pull=never', '--name',
              container_name, '--label', 'acq.pilot=' + container_name,
              '--network=none', '--read-only', '--cap-drop=ALL',
              '--security-opt=no-new-privileges:true',
              '--pids-limit=32', '--memory=256m', '--cpus=1', '--user=65532:65532',
              '--mount', 'type=bind,src=' + source + ',dst=/fixture,readonly',
              '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m', '--workdir=/fixture',
              '--env', 'HOME=/tmp', '--env', 'XDG_CONFIG_HOME=/tmp/config',
              '--env', 'PATH=' + path, '--entrypoint', pin.cli_path, pin.image_ref)
    if pin.owner == 'codex':
        args = ('--ask-for-approval', 'never', 'exec', '--sandbox', 'read-only',
                '--ephemeral', '--ignore-user-config', '--json', '-C', '/fixture',
                '-m', spec.model, '-')
        stdin = PROMPT
    else:
        args = ('run', '--pure', '--model', spec.model, '--format', 'json',
                '--dir', '/fixture', PROMPT)
        stdin = None
    return DockerPlan(common + args, stdin, container_name, snapshot_sha256, pin.owner)


def snapshot_facts(root: Path, facts: dict):
    """Caller owns returned TemporaryDirectory; only two public files are staged."""
    temporary = tempfile.TemporaryDirectory(prefix='orch-ro-', dir=root)
    path = Path(temporary.name)
    public = facts['fixture_text']
    (path / 'public_fixture.txt').write_text(public, encoding='utf-8')
    attested = {key: facts[key] for key in ('branch', 'source_sha', 'fixture_sha256')}
    (path / 'facts.json').write_text(json.dumps(attested, sort_keys=True), encoding='utf-8')
    snapshot_sha = digest({'facts': attested, 'fixture': public})
    return temporary, path, snapshot_sha
