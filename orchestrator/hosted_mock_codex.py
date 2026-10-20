"""The only executable agent in the hosted pilot. Public fixture, no provider SDK."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
from pathlib import Path

VERSION = 'mock-codex/1'


def main() -> int:
    if sys.argv[1:] != ['exec', '--sandbox', 'read-only', '--fixture', '/fixture']:
        return 2
    root = Path('/fixture')
    facts = json.loads((root / 'facts.json').read_text(encoding='utf-8'))
    fixture = (root / 'hosted_public.json').read_bytes()
    if hashlib.sha256(fixture).hexdigest() != facts['fixture_sha256']:
        return 3
    public = json.loads(fixture)
    if set(public) != {'fixture_id', 'company', 'note'}:
        return 4
    forbidden_read = any(p.exists() for p in (
        Path('/root/.ssh/id_rsa'), Path('/fixture/data/acquisition.db'),
        Path('/fixture/.git'), Path('/fixture/.env')))
    secret_visible = bool(os.environ.get('HOST_SECRET_MARKER') or os.environ.get('GITHUB_TOKEN'))
    try:
        (root / 'write-attempt').write_text('forbidden', encoding='utf-8')
        write_denied = False
    except OSError:
        write_denied = True
    try:
        with socket.create_connection(('192.0.2.1', 443), timeout=0.3):
            network_denied = False
    except OSError:
        network_denied = True
    report = {
        'mode': 'MOCK', 'status': 'MOCK_VERIFIED_READ_ONLY',
        'source_sha': facts['source_sha'], 'fixture_sha256': facts['fixture_sha256'],
        'fixture': public, 'cli_version': VERSION,
        'checks': {'private_paths_absent': not forbidden_read,
                   'secret_env_absent': not secret_visible,
                   'write_denied': write_denied, 'network_denied': network_denied},
        'usage': {'input_tokens': 0, 'output_tokens': 0,
                  'charged_cost_usd': 0, 'provider_calls': 0,
                  'evidence': 'OFFLINE_NO_PROVIDER'},
    }
    print(json.dumps(report, sort_keys=True, separators=(',', ':')))
    return 0 if all(report['checks'].values()) else 5


if __name__ == '__main__':
    raise SystemExit(main())
