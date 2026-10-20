"""Issue #8 offline, adversarial tests. No Docker engine or model provider is used."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestrator.policy import Settings
from orchestrator.cancellation import isolated_process_flags, supervise
from orchestrator.readonly import MockPilotBackend, ReadOnlyPilot
from orchestrator.readonly_policy import ProviderTariff, RuntimePin, build_docker_plan
from orchestrator.store import Store
from orchestrator.web import create_app

TOKEN = 'synthetic-founder-token-123456'


def git(path, *args):
    return subprocess.run(['git', *args], cwd=path, capture_output=True,
                          text=True, check=True).stdout.strip()


class ControlledBackend(MockPilotBackend):
    def __init__(self):
        self.result = None
        self.probe_result = None
        self.hook = None
        self.terminated = []
        self.fail_termination = False
        self.plans = []

    def probe(self, pin, tariff):
        return self.probe_result or super().probe(pin, tariff)

    def run(self, plan, facts, stop_requested, timeout_seconds):
        self.plans.append(plan)
        if self.hook:
            self.hook()
        if stop_requested():
            raise InterruptedError('stopped')
        return self.result if self.result is not None else super().run(plan, facts,
                                                                       stop_requested,
                                                                       timeout_seconds)

    def terminate(self, name):
        super().terminate(name)
        self.terminated.append(name)
        if self.fail_termination:
            raise OSError('synthetic termination failure')


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    monkeypatch.setenv('ORCH_ADMIN_TOKEN', TOKEN)
    root = tmp_path / 'runs'
    root.mkdir()
    specs, pins, tariffs = {}, {}, {}
    for owner in ('codex', 'kilo'):
        repo = root / (owner + '-toy')
        repo.mkdir()
        git(repo, 'init', '-b', 'feat/' + owner + '-toy')
        git(repo, 'config', 'user.email', 'fixture@example.invalid')
        git(repo, 'config', 'user.name', 'Fixture')
        (repo / '.orchestrator-fixture').write_text('TOY_REPO_ONLY\n', encoding='utf-8')
        (repo / 'public_fixture.txt').write_text('Synthetic public facts only.\n', encoding='utf-8')
        (repo / 'attack.py').write_text(
            'import os\nfrom pathlib import Path\n'
            'Path.home().joinpath(".ssh", "id_rsa").read_text()\n'
            'Path("data/acquisition.db").read_bytes()\n'
            'raise RuntimeError(os.environ.get("HOST_SECRET", ""))\n', encoding='utf-8')
        git(repo, 'add', '.')
        git(repo, 'commit', '-m', 'Synthetic fixture')
        sha = git(repo, 'rev-parse', 'HEAD')
        specs[owner] = {'issue': 8, 'owner': owner, 'worktree': str(repo),
                        'branch': 'feat/' + owner + '-toy', 'source_sha': sha,
                        'provider': owner + '-provider', 'model': owner + '-model',
                        'max_input_tokens': 100, 'max_output_tokens': 50,
                        'max_tokens': 150, 'max_cost_usd': 0.01, 'timeout_seconds': 30,
                        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        pins[owner] = RuntimePin(owner, str(tmp_path / 'docker-mock'),
                                 'example.invalid/' + owner + '@sha256:' + 'a' * 64,
                                 '/opt/' + owner + '/bin/' + owner, 'b' * 64,
                                 '1.2.3', '/opt/node/bin/node' if owner == 'kilo' else '',
                                 'v24.20.0' if owner == 'kilo' else '')
        tariff = ProviderTariff(owner, owner + '-provider', owner + '-model',
                                '1', '2', 100, 50, 'founder-offline-fixture')
        tariffs[(owner, tariff.provider, tariff.model)] = tariff
    store = Store(Settings(root, tmp_path / 'pilot.db', 'ShubMisra'))
    backend = ControlledBackend()
    service = ReadOnlyPilot(store, root, 'git', pins, tariffs, backend)
    return service, store, backend, specs, root


@pytest.mark.parametrize('owner', ['codex', 'kilo'])
def test_one_shot_pinned_offline_plan_and_evidence(pilot, owner):
    service, store, backend, specs, root = pilot
    approval = service.approve(specs[owner], TOKEN)
    run_id = service.run_mock(approval, TOKEN)
    row = store.pilot_run(run_id)
    assert row['status'] == 'MOCK_VERIFIED_READ_ONLY'
    assert row['source_sha'] == row['head_sha'] == specs[owner]['source_sha']
    assert json.loads(row['report'])['branch'] == specs[owner]['branch']
    assert row['input_tokens'] == row['output_tokens'] == 0
    assert row['charged_cost'] == 0
    assert store.verify_events()
    plan = backend.plans[0]
    args = list(plan.argv)
    assert args[0] == str(root.parent / 'docker-mock')
    for flag in ('--network=none', '--read-only', '--cap-drop=ALL',
                 '--security-opt=no-new-privileges:true',
                 '--pull=never', '--pids-limit=32', '--user=65532:65532'):
        assert flag in args
    assert '--privileged' not in args and '--auto' not in args
    assert specs[owner]['worktree'] not in ' '.join(args)
    assert 'attack.py' not in ' '.join(args)
    assert '/fixture' in ' '.join(args)
    assert plan.owner == owner
    if owner == 'codex':
        assert '--sandbox' in args and 'read-only' in args
        assert '--ask-for-approval' in args and 'never' in args
        assert '--ignore-user-config' in args and '--ephemeral' in args
        assert '::' not in ' '.join(args)
    else:
        assert '--pure' in args and '--format' in args
        assert '/opt/node/bin' in ' '.join(args)
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    assert len(backend.plans) == 1
    assert not list(root.glob('orch-ro-*'))
    assert not list(root.glob('*/.env'))


def test_founder_auth_and_live_backend_disabled(pilot):
    service, store, backend, specs, root = pilot
    with pytest.raises(PermissionError):
        service.approve(specs['codex'], 'wrong-token')
    assert not store.pilot_runs()
    with pytest.raises(PermissionError):
        service.execute_live()
    with pytest.raises(PermissionError):
        ReadOnlyPilot(store, root, 'git', service.profiles, service.tariffs, object())


def test_mock_evidence_cannot_be_presented_as_live_attestation(pilot):
    service, store, backend, specs, _ = pilot
    pin = service.profiles['codex']
    tariff = service.tariffs[('codex', 'codex-provider', 'codex-model')]
    backend.probe_result = replace(backend.probe(pin, tariff), evidence_kind='live')
    with pytest.raises(PermissionError, match='mock profile mismatch'):
        service.approve(specs['codex'], TOKEN)
    assert not store.pilot_runs()
    assert not backend.plans
    with pytest.raises(ValueError, match='invalid pilot result'):
        store.pilot_finish('nonexistent', 'VERIFIED_READ_ONLY', None,
                           None, None, None, None, None, None)


def test_source_and_public_fixture_must_be_clean_and_synthetic(pilot):
    service, store, backend, specs, root = pilot
    repo = Path(specs['codex']['worktree'])
    (repo / 'public_fixture.txt').write_text('api_key=synthetic-secret', encoding='utf-8')
    with pytest.raises(PermissionError):
        service.approve(specs['codex'], TOKEN)
    assert not store.pilot_runs()
    (repo / 'public_fixture.txt').write_text('Synthetic public facts only.\n', encoding='utf-8')
    (repo / 'untracked.txt').write_text('new', encoding='utf-8')
    with pytest.raises(PermissionError):
        service.approve(specs['codex'], TOKEN)


def test_profile_tariff_probe_and_provider_caps_fail_closed(pilot):
    service, store, backend, specs, root = pilot
    approval = service.approve(specs['codex'], TOKEN)
    old = service.profiles['codex']
    service.profiles['codex'] = replace(old, version='changed')
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    service.profiles['codex'] = old
    service.profiles['codex'] = replace(old, docker_executable=str(root / 'wrong-docker'))
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    service.profiles['codex'] = old
    backend.probe_result = replace(backend.probe(old, next(iter(service.tariffs.values()))),
                                   hard_cost_limit=False)
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    backend.probe_result = replace(backend.probe_result, hard_cost_limit=True,
                                   auth_ready=False)
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    backend.probe_result = None
    with pytest.raises(PermissionError):
        service.approve({**specs['codex'], 'max_cost_usd': 0.00001}, TOKEN)
    with pytest.raises(PermissionError):
        service.approve({**specs['codex'], 'model': 'unapproved'}, TOKEN)
    bad_node = service.profiles['kilo']
    service.profiles['kilo'] = replace(bad_node, node_path='')
    with pytest.raises(ValueError):
        service.approve(specs['kilo'], TOKEN)
    service.profiles['kilo'] = bad_node
    assert not store.pilot_runs()


@pytest.mark.parametrize('result', [
    {'report': {'branch': 'evil'}, 'input_tokens': 0, 'output_tokens': 0,
     'charged_cost_usd': 0},
    {'report': {'branch': 'evil'}, 'input_tokens': 0, 'output_tokens': 0,
     'charged_cost_usd': 0, 'shell': 'powershell'},
    {'report': {}, 'input_tokens': 1, 'output_tokens': 1},
    {'report': {}, 'input_tokens': True, 'output_tokens': 0, 'charged_cost_usd': 0},
])
def test_model_output_and_missing_meter_cannot_pass(pilot, result):
    service, store, backend, specs, root = pilot
    backend.result = result
    approval = service.approve(specs['codex'], TOKEN)
    row = store.pilot_run(service.run_mock(approval, TOKEN))
    assert row['status'] == 'FAILED'
    assert row['report'] is None
    assert row['error_code'] == 'ValueError'
    assert backend.terminated == [row['container_name']]
    assert store.verify_events()


def test_measured_overcharge_and_token_overrun_fail(pilot):
    service, store, backend, specs, root = pilot
    facts = {'branch': specs['codex']['branch'], 'source_sha': specs['codex']['source_sha'],
             'fixture_sha256': __import__('hashlib').sha256(b'Synthetic public facts only.\n').hexdigest()}
    backend.result = {'report': facts, 'input_tokens': 101, 'output_tokens': 0,
                      'charged_cost_usd': 0.0}
    row = store.pilot_run(service.run_mock(service.approve(specs['codex'], TOKEN), TOKEN))
    assert row['status'] == 'FAILED'


def test_revalidation_revoke_stop_and_recovery(pilot):
    service, store, backend, specs, root = pilot
    approval = service.approve(specs['codex'], TOKEN)
    service.revoke(approval, TOKEN)
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    approval = service.approve(specs['codex'], TOKEN)
    backend.hook = lambda: service.stop(store.pilot_approval(approval)['used_run_id'], TOKEN)
    row = store.pilot_run(service.run_mock(approval, TOKEN))
    assert row['status'] == 'STOPPED'
    backend.hook = None
    approval = service.approve(specs['kilo'], TOKEN)
    orphan_id = store.pilot_admit(approval)
    assert service.recover() == [orphan_id]
    assert service.recover() == []
    assert store.pilot_run(orphan_id)['status'] == 'RECOVERY_REQUIRED'
    assert store.verify_events()


def test_termination_failure_latches_emergency_stop(pilot):
    service, store, backend, specs, root = pilot
    approval = service.approve(specs['codex'], TOKEN)
    orphan_id = store.pilot_admit(approval)
    backend.fail_termination = True
    with pytest.raises(PermissionError):
        service.recover()
    assert store.pilot_run(orphan_id)['status'] == 'RUNNING'
    with pytest.raises(PermissionError):
        store.pilot_admit(service.approve(specs['kilo'], TOKEN))


def test_snapshot_stages_only_allowlisted_public_files(pilot, monkeypatch):
    service, store, backend, specs, root = pilot
    monkeypatch.setenv('HOST_SECRET', 'NEVER_COPY_THIS_SECRET')
    def inspect():
        plan = backend.plans[-1]
        mount = plan.argv[plan.argv.index('--mount') + 1]
        source = Path(mount.split(',')[1].removeprefix('src='))
        assert {p.name for p in source.iterdir()} == {'facts.json', 'public_fixture.txt'}
        assert 'NEVER_COPY_THIS_SECRET' not in ' '.join(p.read_text() for p in source.iterdir())
        assert 'attack.py' not in {p.name for p in source.iterdir()}
    backend.hook = inspect
    row = store.pilot_run(service.run_mock(service.approve(specs['codex'], TOKEN), TOKEN))
    assert row['status'] == 'MOCK_VERIFIED_READ_ONLY'
    assert b'NEVER_COPY_THIS_SECRET' not in store.settings.db_path.read_bytes()


def test_approval_expiry_and_changed_source_rejected_before_admission(pilot):
    service, store, backend, specs, root = pilot
    approval = service.approve(specs['codex'], TOKEN)
    (Path(specs['codex']['worktree']) / 'public_fixture.txt').write_text('Changed.\n',
                                                                      encoding='utf-8')
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    assert store.pilot_approval(approval)['used_run_id'] is None
    assert not backend.plans
    expired = {**specs['kilo'], 'expires_at':
               (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}
    with pytest.raises(ValueError):
        service.approve(expired, TOKEN)


def test_nonfinite_price_and_meter_rejected(pilot):
    service, store, backend, specs, root = pilot
    with pytest.raises(ValueError):
        service.approve({**specs['codex'], 'max_cost_usd': float('nan')}, TOKEN)
    tariff = service.tariffs[('codex', 'codex-provider', 'codex-model')]
    service.tariffs[('codex', 'codex-provider', 'codex-model')] = replace(
        tariff, input_usd_per_million='Infinity')
    with pytest.raises(ValueError):
        service.approve(specs['codex'], TOKEN)
    service.tariffs[('codex', 'codex-provider', 'codex-model')] = tariff
    approval = service.approve(specs['codex'], TOKEN)
    backend.result = {'report': {}, 'input_tokens': 0, 'output_tokens': 0,
                      'charged_cost_usd': float('nan')}
    assert store.pilot_run(service.run_mock(approval, TOKEN))['status'] == 'FAILED'


def test_recovery_survives_process_restart(pilot):
    service, store, backend, specs, root = pilot
    approval = service.approve(specs['codex'], TOKEN)
    run_id = store.pilot_admit(approval)
    fresh_store = Store(store.settings)
    fresh_backend = ControlledBackend()
    fresh_service = ReadOnlyPilot(fresh_store, root, 'git', service.profiles,
                                 service.tariffs, fresh_backend)
    assert fresh_service.recover() == [run_id]
    assert fresh_backend.terminated == [store.pilot_run(run_id)['container_name']]
    assert fresh_store.pilot_run(run_id)['status'] == 'RECOVERY_REQUIRED'
    assert fresh_store.verify_events()


def test_failed_stop_latches_gate(pilot):
    service, store, backend, specs, root = pilot
    approval = service.approve(specs['codex'], TOKEN)
    run_id = store.pilot_admit(approval)
    backend.fail_termination = True
    with pytest.raises(PermissionError):
        service.stop(run_id, TOKEN)
    assert store.pilot_run(run_id)['stop_requested'] == 1
    with pytest.raises(PermissionError):
        store.clear_emergency()
    with pytest.raises(PermissionError):
        store.pilot_admit(service.approve(specs['kilo'], TOKEN))


def test_atomic_daily_budget_prevents_side_effects(pilot):
    service, store, backend, specs, root = pilot
    store.set_budgets(100, 0.001)
    approval = service.approve(specs['codex'], TOKEN)
    with pytest.raises(PermissionError):
        service.run_mock(approval, TOKEN)
    assert store.pilot_approval(approval)['used_run_id'] is None
    assert not store.pilot_runs() and not backend.plans
    with pytest.raises(ValueError):
        store.set_budgets(100, float('nan'))


@pytest.mark.parametrize('mode', ['stop', 'emergency', 'timeout'])
def test_pilot_child_process_tree_cannot_leave_delayed_effect(pilot, mode):
    service, store, backend, specs, root = pilot
    marker = root / 'delayed-effect.txt'
    approval = service.approve(specs['codex'], TOKEN)

    class ChildBackend(ControlledBackend):
        def run(self, plan, facts, stop_requested, timeout_seconds):
            self.plans.append(plan)
            child = subprocess.Popen([sys.executable, '-c',
                                      'import pathlib,time; time.sleep(0.5); '
                                      'pathlib.Path(%r).write_text("late")' % str(marker)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     **isolated_process_flags())
            if mode == 'stop':
                service.stop(store.pilot_approval(approval)['used_run_id'], TOKEN)
            elif mode == 'emergency':
                service.emergency_stop(TOKEN)
            supervise(child, stop_requested, 0.05 if mode == 'timeout' else 1,
                      poll_seconds=0.01)
            return super().run(plan, facts, stop_requested, timeout_seconds)

    child_backend = ChildBackend()
    service.backend = child_backend
    row = store.pilot_run(service.run_mock(approval, TOKEN))
    assert row['status'] == ('FAILED' if mode == 'timeout' else 'STOPPED')
    assert row['error_code'] in ('InterruptedError', 'TimeoutError')
    time.sleep(0.6)
    assert not marker.exists()


def test_founder_dashboard_pilot_gate_and_mock_result(pilot):
    service, store, backend, specs, root = pilot
    class ControllerStub:
        def __init__(self):
            self.store = store
        def emergency_stop(self, token):
            store.request_stop('', emergency=True)
    client = TestClient(create_app(ControllerStub(), service))
    assert client.post('/api/pilot/approvals', json=specs['codex']).status_code == 403
    headers = {'X-Orch-Token': TOKEN}
    response = client.post('/api/pilot/approvals', json=specs['codex'], headers=headers)
    assert response.status_code == 200
    approval = response.json()['approval_id']
    result = client.post(f'/api/pilot/approvals/{approval}/run-mock', headers=headers)
    assert result.status_code == 200
    assert store.pilot_run(result.json()['run_id'])['status'] == 'MOCK_VERIFIED_READ_ONLY'
    assert client.post(f'/api/pilot/approvals/{approval}/run-mock', headers=headers).status_code == 403
