"""Narrow GitHub queue, CI, draft-PR and issue interface."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import Request, urlopen

from .policy import REPOSITORY


@dataclass(frozen=True)
class CITrust:
    workflow_id: int
    workflow_blob_sha: str
    workflow_path: str = '.github/workflows/ci.yml'
    job_name: str = 'test'

    def validate(self):
        if type(self.workflow_id) is not int or self.workflow_id < 1 or not re.fullmatch(r'[0-9a-f]{40}', self.workflow_blob_sha):
            raise ValueError('trusted CI workflow identity required')
        if self.workflow_path != '.github/workflows/ci.yml' or self.job_name != 'test':
            raise ValueError('unexpected trusted CI identity')


class GitHubGateway:
    def __init__(self, token: str | None = None, ci_trust: CITrust | None = None):
        self._token = token if token is not None else os.getenv('ORCH_GITHUB_TOKEN', '')
        self._base = 'https://api.github.com/repos/' + REPOSITORY
        self.ci_trust = ci_trust

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

    def ci_evidence(self, sha: str, branch: str, source_sha: str) -> dict:
        trust = self.ci_trust
        if trust is None:
            raise PermissionError('trusted CI identity not configured')
        trust.validate()
        if not all(re.fullmatch(r'[0-9a-f]{40}', value) for value in (sha, source_sha)) or \
           not re.fullmatch(r'feat/[a-z0-9/_-]+', branch):
            raise ValueError('invalid CI refs')
        encoded = quote(trust.workflow_path, safe='/')
        content = self._request('GET', '/contents/' + encoded + '?ref=' + source_sha)
        if content.get('sha') != trust.workflow_blob_sha or content.get('path') != trust.workflow_path:
            raise PermissionError('CI workflow differs from founder-pinned blob')
        result = self._request('GET', '/actions/workflows/' + str(trust.workflow_id) +
                               '/runs?branch=' + quote(branch, safe='') + '&event=push&per_page=100')
        runs = [run for run in result.get('workflow_runs', [])
                if run.get('id') and run.get('workflow_id') == trust.workflow_id
                and run.get('path') == trust.workflow_path and run.get('head_sha') == sha
                and run.get('head_branch') == branch and run.get('event') == 'push'
                and run.get('repository', {}).get('full_name') == REPOSITORY
                and run.get('head_repository', {}).get('full_name') == REPOSITORY]
        if len(runs) != 1:
            return {'state': 'MISSING', 'url': None, 'workflow_id': trust.workflow_id,
                    'workflow_blob_sha': trust.workflow_blob_sha}
        run = runs[0]
        jobs = self._request('GET', '/actions/runs/' + str(run['id']) + '/jobs?per_page=100')
        selected = [job for job in jobs.get('jobs', []) if job.get('name') == trust.job_name
                    and job.get('run_id') == run['id']]
        if len(selected) != 1 or jobs.get('total_count') != 1:
            return {'state': 'MISSING', 'url': run.get('html_url'), 'run_id': run['id'],
                    'workflow_blob_sha': trust.workflow_blob_sha}
        job = selected[0]
        if run.get('conclusion') in ('failure', 'cancelled', 'timed_out', 'action_required') or \
           job.get('conclusion') in ('failure', 'cancelled', 'timed_out', 'action_required'):
            state = 'FAILED'
        elif run.get('status') == 'completed' and run.get('conclusion') == 'success' and \
             job.get('status') == 'completed' and job.get('conclusion') == 'success':
            state = 'SUCCESS'
        else:
            state = 'PENDING'
        return {'state': state, 'url': run.get('html_url'), 'run_id': run['id'],
                'job_id': job.get('id'), 'workflow_id': trust.workflow_id,
                'workflow_blob_sha': trust.workflow_blob_sha, 'head_sha': sha,
                'head_branch': branch}

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
