"""Narrow GitHub queue, CI, draft-PR and issue interface."""
from __future__ import annotations

import json
import os
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

from .policy import REPOSITORY


class GitHubGateway:
    def __init__(self, token: str | None = None):
        self._token = token if token is not None else os.getenv('ORCH_GITHUB_TOKEN', '')
        self._base = 'https://api.github.com/repos/' + REPOSITORY

    def _request(self, method: str, route: str, body: dict | None = None):
        if not route.startswith('/') or '://' in route or '..' in route:
            raise ValueError('invalid GitHub route')
        if method != 'GET' and not self._token:
            raise PermissionError('GitHub write token not configured')
        data = json.dumps(body).encode() if body is not None else None
        headers = {'Accept': 'application/vnd.github+json',
                   'User-Agent': 'acq-supervised-orchestrator',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if self._token:
            headers['Authorization'] = 'Bearer ' + self._token
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(self._base + route, data=data, headers=headers, method=method)
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read(1_000_000))

    def issue(self, number: int) -> dict:
        return self._request('GET', '/issues/' + str(int(number)))

    def queue(self) -> list[dict]:
        return self._request('GET', '/issues?state=open&labels=approved-for-run&per_page=100')

    def branch_sha(self, branch: str) -> str:
        result = self._request('GET', '/branches/' + quote(branch, safe=''))
        return result['commit']['sha']

    def ci_evidence(self, sha: str) -> dict:
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError('invalid SHA')
        checks = self._request('GET', '/commits/' + sha + '/check-runs?per_page=100')
        runs = [run for run in checks.get('check_runs', [])
                if run.get('name') == 'test' and run.get('app', {}).get('slug') == 'github-actions'
                and run.get('head_sha') == sha]
        if not runs:
            return {'state': 'MISSING', 'url': None, 'checks': 0}
        url = runs[0].get('html_url')
        if any(run.get('conclusion') in ('failure', 'cancelled', 'timed_out', 'action_required') for run in runs):
            return {'state': 'FAILED', 'url': url, 'checks': len(runs)}
        if all(run.get('status') == 'completed' and run.get('conclusion') == 'success' for run in runs):
            return {'state': 'SUCCESS', 'url': url, 'checks': len(runs)}
        return {'state': 'PENDING', 'url': url, 'checks': len(runs)}

    def create_issue(self, title: str, body: str, owner: str) -> dict:
        return self._request('POST', '/issues', {'title': title[:160], 'body': body[:10000],
                                                 'labels': ['needs-founder-review', 'owner:' + owner]})

    def create_draft_pr(self, title: str, head: str, base: str, body: str) -> dict:
        if base != 'main' or not head.startswith('feat/'):
            raise ValueError('invalid PR refs')
        return self._request('POST', '/pulls', {'title': title[:160], 'head': head,
                                                'base': base, 'body': body[:10000],
                                                'draft': True})

    def comment(self, issue: int, payload: dict) -> dict:
        return self._request('POST', '/issues/' + str(int(issue)) + '/comments',
                             {'body': 'ENGINEERING_RESULT\n```json\n' +
                              json.dumps(payload, sort_keys=True) + '\n```'})
