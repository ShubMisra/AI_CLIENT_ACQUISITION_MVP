"""Fixed offline role outputs. This file is staged alone with a public fixture."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] != 'role' or sys.argv[2] not in (
            'codex-blocked', 'kilo-diagnostic', 'codex-resume') or sys.argv[3] != '/fixture':
        return 2
    role = sys.argv[2]
    root = Path('/fixture')
    task = json.loads((root / 'task.json').read_text(encoding='utf-8'))
    fixture_bytes = (root / 'hosted_public.json').read_bytes()
    if hashlib.sha256(fixture_bytes).hexdigest() != task['fixture_sha256']:
        return 3
    fixture = json.loads(fixture_bytes)
    if fixture != {'fixture_id': 'hosted-public-v1', 'company': 'Synthetic Example Co',
                   'note': 'Public toy task only'}:
        return 4
    if task['role'] != role or task['mode'] != 'MOCK_ONLY' or task['owner'] != (
            'kilo' if role == 'kilo-diagnostic' else 'codex'):
        return 5
    if task['diagnostic_finding'] != ('CHECK_FIXTURE_ID' if role == 'codex-resume' else None):
        return 7
    if os.environ.get('GITHUB_TOKEN') or os.environ.get('HOST_SECRET_MARKER'):
        return 6
    outcomes = {
        'codex-blocked': {'status': 'BLOCKED', 'reason': 'SYNTHETIC_ASSERTION',
                          'failed_attempts': 2,
                          'attempt_codes': ['SYNTHETIC_ASSERTION_A',
                                            'SYNTHETIC_ASSERTION_B']},
        'kilo-diagnostic': {'status': 'FINDING', 'finding': 'CHECK_FIXTURE_ID',
                            'suggested_path': 'tests/fixtures/hosted_public.json'},
        'codex-resume': {'status': 'VERIFIED', 'check': 'FIXTURE_ID_MATCH',
                         'fixture_id': fixture['fixture_id']},
    }
    result = {'mode': 'MOCK_ONLY', 'role': role, 'owner': task['owner'],
              'source_sha': task['source_sha'], 'task_digest': task['task_digest'],
              'outcome': outcomes[role],
              'usage': {'provider_calls': 0, 'tokens': 0, 'charged_cost_usd': 0}}
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
