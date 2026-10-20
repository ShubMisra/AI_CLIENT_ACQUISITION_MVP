"""One-shot, founder-gated, offline READ-ONLY pilot. Real CLI launch is disabled."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from .policy import require_founder
from .cancellation import TerminationUnverified
from .readonly_policy import (DockerPlan, PilotSpec, ProbeResult, ProviderTariff,
                              RuntimePin, build_docker_plan, digest, snapshot_facts,
                              verify_public_fixture)
from .store import Store


class MockPilotBackend:
    """Offline test double: neither Docker nor either model provider is contacted."""

    def probe(self, pin: RuntimePin, tariff: ProviderTariff) -> ProbeResult:
        return ProbeResult(pin.image_ref, pin.cli_sha256, pin.version,
                           pin.node_version, True, True, True, 'mock')

    def run(self, plan: DockerPlan, facts: dict, stop_requested, timeout_seconds: int) -> dict:
        if stop_requested():
            raise InterruptedError('pilot stopped')
        return {'report': {key: facts[key] for key in
                           ('branch', 'source_sha', 'fixture_sha256')},
                'input_tokens': 0, 'output_tokens': 0, 'charged_cost_usd': 0.0}

    def terminate(self, container_name: str) -> None:
        # No host process exists in mock mode. A real backend is not installed.
        if not re.fullmatch(r'orch-ro-[0-9a-f]{32}', container_name):
            raise ValueError('invalid pilot process identity')


class ReadOnlyPilot:
    def __init__(self, store: Store, root: Path, git_executable: str,
                 profiles: dict[str, RuntimePin], tariffs: dict[tuple[str, str, str], ProviderTariff],
                 backend=None):
        self.store = store
        self.root = root.resolve(strict=True)
        self.git_executable = git_executable
        self.profiles = dict(profiles)
        self.tariffs = dict(tariffs)
        self.backend = backend if backend is not None else MockPilotBackend()
        if type(self.backend) is not MockPilotBackend:
            # Integration test doubles may subclass this type. No production backend is enabled.
            if not isinstance(self.backend, MockPilotBackend):
                raise PermissionError('real CLI backend is disabled')
        for owner, pin in self.profiles.items():
            pin.validate()
            if owner != pin.owner:
                raise ValueError('profile owner mismatch')
        for key, tariff in self.tariffs.items():
            tariff.validate()
            if key != (tariff.owner, tariff.provider, tariff.model):
                raise ValueError('tariff identity mismatch')

    def _preflight(self, spec: PilotSpec, *, expected_pin: str | None = None,
                   expected_tariff: str | None = None) -> tuple[RuntimePin, ProviderTariff, dict]:
        spec.validate()
        pin = self.profiles.get(spec.owner)
        tariff = self.tariffs.get((spec.owner, spec.provider, spec.model))
        if not pin or not tariff:
            raise PermissionError('separate owner profile and provider tariff required')
        if expected_pin is not None and pin.fingerprint() != expected_pin:
            raise PermissionError('CLI profile changed after approval')
        if expected_tariff is not None and digest(asdict(tariff)) != expected_tariff:
            raise PermissionError('provider price changed after approval')
        if spec.max_input_tokens > tariff.max_input_tokens or \
           spec.max_output_tokens > tariff.max_output_tokens or \
           tariff.maximum_cost(spec.max_input_tokens, spec.max_output_tokens) > \
                Decimal(str(spec.max_cost_usd)):
            raise PermissionError('provider hard cap cannot cover pilot budget')
        probe = self.backend.probe(pin, tariff)
        if probe != ProbeResult(pin.image_ref, pin.cli_sha256, pin.version,
                                pin.node_version, True, True, True, 'mock'):
            raise PermissionError('mock profile mismatch; live attestation is unavailable')
        facts = verify_public_fixture(spec, self.root, self.git_executable)
        return pin, tariff, facts

    def approve(self, raw_spec: dict, founder_token: str | None) -> str:
        require_founder(founder_token)
        spec = PilotSpec.from_dict(raw_spec)
        pin, tariff, _ = self._preflight(spec)
        stored = {**asdict(spec), 'profile_fingerprint': pin.fingerprint(),
                  'tariff_fingerprint': digest(asdict(tariff))}
        return self.store.pilot_approve(stored)

    def run_mock(self, approval_id: str, founder_token: str | None) -> str:
        require_founder(founder_token)
        approval = self.store.pilot_approval(approval_id)
        raw = approval['spec']
        spec = PilotSpec.from_dict({key: raw[key] for key in PilotSpec.__dataclass_fields__})
        pin, tariff, facts = self._preflight(spec,
                                            expected_pin=raw['profile_fingerprint'],
                                            expected_tariff=raw['tariff_fingerprint'])
        run_id = self.store.pilot_admit(approval_id)
        try:
            temporary, snapshot_path, snapshot_hash = snapshot_facts(self.root, facts)
            with temporary:
                row = self.store.pilot_run(run_id)
                plan = build_docker_plan(pin, spec, snapshot_path, snapshot_hash,
                                         row['container_name'])
                result = self.backend.run(plan, facts,
                                          lambda: bool(self.store.pilot_run(run_id)['stop_requested']),
                                          spec.timeout_seconds)
                report, in_tokens, out_tokens, charged = self._validate_result(result, facts,
                                                                                 spec, tariff)
                # A model response cannot authorize publication; recheck the exact source and fixture.
                if verify_public_fixture(spec, self.root, self.git_executable) != facts:
                    raise PermissionError('pilot source changed during execution')
                if self.store.pilot_run(run_id)['stop_requested']:
                    raise InterruptedError('pilot stopped')
                self.store.pilot_finish(run_id, 'MOCK_VERIFIED_READ_ONLY', spec.source_sha,
                                        in_tokens, out_tokens, charged, report,
                                        digest(report), None)
        except Exception as exc:
            # Never persist the exception string or raw model output: either may contain secrets.
            code = type(exc).__name__
            if isinstance(exc, TerminationUnverified):
                self.store.request_stop(run_id, emergency=True)
            try:
                self.backend.terminate(self.store.pilot_run(run_id)['container_name'])
            except Exception:
                self.store.request_stop(run_id, emergency=True)
                raise PermissionError('pilot termination unverified; emergency stop active') from None
            self.store.pilot_finish(run_id, 'STOPPED' if isinstance(exc, InterruptedError)
                                    else 'FAILED', None, None, None, None, None, None, code)
        return run_id

    @staticmethod
    def _validate_result(result: dict, facts: dict, spec: PilotSpec,
                         tariff: ProviderTariff) -> tuple[dict, int, int, float]:
        if type(result) is not dict or set(result) != {'report', 'input_tokens',
                                                       'output_tokens', 'charged_cost_usd'}:
            raise ValueError('missing measured usage or report')
        report = result['report']
        expected = {key: facts[key] for key in ('branch', 'source_sha', 'fixture_sha256')}
        if type(report) is not dict or report != expected:
            raise ValueError('pilot report is not exact deterministic facts')
        used_in, used_out, charge = (result['input_tokens'], result['output_tokens'],
                                    result['charged_cost_usd'])
        if type(used_in) is not int or type(used_out) is not int or \
           type(charge) not in (int, float) or used_in < 0 or used_out < 0 or \
           used_in > spec.max_input_tokens or used_out > spec.max_output_tokens or \
           used_in + used_out > spec.max_tokens or \
           not Decimal(str(charge)).is_finite() or not 0 <= charge <= spec.max_cost_usd or \
           Decimal(str(charge)) > tariff.maximum_cost(used_in, used_out):
            raise ValueError('measured provider usage exceeds hard cap')
        return expected, used_in, used_out, float(charge)

    def stop(self, run_id: str, founder_token: str | None) -> None:
        require_founder(founder_token)
        row = self.store.pilot_run(run_id)
        self.store.pilot_stop(run_id)
        if row['status'] == 'RUNNING':
            try:
                self.backend.terminate(row['container_name'])
            except Exception:
                self.store.request_stop(run_id, emergency=True)
                raise PermissionError('pilot termination unverified; emergency stop active') from None

    def revoke(self, approval_id: str, founder_token: str | None) -> None:
        require_founder(founder_token)
        run_id = self.store.pilot_revoke(approval_id)
        if run_id:
            row = self.store.pilot_run(run_id)
            if row['status'] == 'RUNNING':
                try:
                    self.backend.terminate(row['container_name'])
                except Exception:
                    self.store.request_stop(run_id, emergency=True)
                    raise PermissionError('pilot termination unverified; emergency stop active') from None

    def emergency_stop(self, founder_token: str | None) -> None:
        require_founder(founder_token)
        self.store.request_stop('', emergency=True)
        for row in self.store.pilot_orphans():
            self.backend.terminate(row['container_name'])

    def recover(self) -> list[str]:
        # Invoked on service startup before admitting new work. Failure holds the stop gate.
        recovered = []
        for row in self.store.pilot_orphans():
            try:
                self.backend.terminate(row['container_name'])
            except Exception:
                self.store.request_stop('', emergency=True)
                raise PermissionError('orphan termination unverified') from None
            if self.store.pilot_mark_recovered(row['id']):
                recovered.append(row['id'])
        return recovered

    @staticmethod
    def execute_live(*_args, **_kwargs):
        raise PermissionError('real Codex and Kilo CLI execution is disabled')
