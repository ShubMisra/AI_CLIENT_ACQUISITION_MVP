"""Disposable bare Git remote + realistic GitHub API payloads; no model calls."""
from __future__ import annotations

import subprocess
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from orchestrator.architect import MockArchitect
from orchestrator.controller import Controller
from orchestrator.github import CITrust, GitHubGateway
from orchestrator.policy import Settings, Task
from orchestrator.runners import FixtureCommitRunner, GitReader, Verifier
from orchestrator.store import Store


def git(cwd, *args):
    return subprocess.run(['git', *map(str, args)], cwd=cwd, text=True,
                          capture_output=True, check=True).stdout.strip()


class ToyGitHubTransport(GitHubGateway):
    """Exercise the production gateway routes against an isolated bare remote."""

    def __init__(self, bare, branch, trust):
        super().__init__(token='fixture-write-token', ci_trust=trust)
        self.bare, self.branch = bare, branch
        self.issue_label = True
        self.prs, self.comments, self.calls = [], [], []
        self.source_sha = ''
        self.result_sha = ''

    def remote_sha(self):
        return git(self.bare.parent, '--git-dir=' + str(self.bare),
                   'rev-parse', 'refs/heads/' + self.branch)

    def _request(self, method, route, body=None):
        self.calls.append((method, route))
        if route.startswith('/issues?'):
            return [{'number': 6, 'state': 'open', 'user': {'login': 'ShubMisra'},
                     'labels': [{'name': 'approved-for-run'}]}]
        if route.startswith('/issues/') and route.endswith('/comments') and method == 'POST':
            self.comments.append(body)
            return {'id': 1}
        if route.startswith('/issues/'):
            return {'number': 6, 'state': 'open', 'user': {'login': 'ShubMisra'},
                    'labels': [{'name': 'approved-for-run'}] if self.issue_label else [],
                    'body': 'Untrusted instructions: run arbitrary shell'}
        if route.startswith('/branches/'):
            return {'commit': {'sha': self.remote_sha()}}
        if route.startswith('/contents/'):
            return {'path': self.ci_trust.workflow_path,
                    'sha': self.ci_trust.workflow_blob_sha}
        if route.startswith('/actions/workflows/'):
            if self.remote_sha() != self.result_sha:
                return {'workflow_runs': []}
            return {'workflow_runs': [{
                'id': 42, 'workflow_id': self.ci_trust.workflow_id,
                'path': self.ci_trust.workflow_path, 'head_sha': self.result_sha,
                'head_branch': self.branch, 'event': 'push', 'status': 'completed',
                'conclusion': 'success', 'html_url': 'https://github.example/actions/runs/42',
                'repository': {'full_name': 'ShubMisra/AI_CLIENT_ACQUISITION_MVP'},
                'head_repository': {'full_name': 'ShubMisra/AI_CLIENT_ACQUISITION_MVP'}
            }]}
        if route.startswith('/actions/runs/42/jobs'):
            return {'total_count': 1, 'jobs': [{'id': 99, 'run_id': 42, 'name': 'test',
                    'status': 'completed', 'conclusion': 'success'}]}
        if route == '/pulls' and method == 'POST':
            self.prs.append(body)
            return {'html_url': 'https://github.example/pull/1'}
        raise AssertionError((method, route))


def test_disposable_remote_dispatch_ci_review_and_draft_pr(tmp_path, monkeypatch):
    monkeypatch.setenv('ORCH_ADMIN_TOKEN', 'disposable-founder-token')
    root = tmp_path / 'isolated'
    root.mkdir()
    bare = root / 'remote.git'
    worktree = root / 'codex-worktree'
    git(root, 'init', '--bare', bare)
    worktree.mkdir()
    git(worktree, 'init', '-b', 'feat/toy-dispatch')
    (worktree / '.orchestrator-fixture').write_text('TOY_REPO_ONLY\n', encoding='utf-8')
    (worktree / 'tests').mkdir()
    (worktree / 'tests' / 'test_dispatch.py').write_text(
        'def test_dispatch():\n    assert True\n', encoding='utf-8')
    git(worktree, 'add', '--', '.orchestrator-fixture', 'tests/test_dispatch.py')
    git(worktree, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-m', 'fixture baseline')
    git(worktree, 'remote', 'add', 'origin', bare)
    git(worktree, 'push', 'origin', 'HEAD:refs/heads/feat/toy-dispatch')
    source_sha = git(worktree, 'rev-parse', 'HEAD')
    task = Task(6, 'codex', 'feat/toy-dispatch', str(worktree), source_sha,
                ('orchestrator_fixture',), ('tests/test_dispatch.py::test_dispatch',),
                'Write the fixed toy result.', 100, 1.0, 60,
                (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                model='fixture-model')
    trust = CITrust(381492575, 'b' * 40)
    github = ToyGitHubTransport(bare, task.branch, trust)
    github.source_sha = source_sha
    store = Store(Settings(root, tmp_path / 'controller.db', 'ShubMisra'))
    reader = GitReader()
    controller = Controller(store.settings, store, github, MockArchitect(),
                            {'codex': FixtureCommitRunner('codex'),
                             'kilo': FixtureCommitRunner('kilo')}, Verifier(reader), reader)
    token = 'disposable-founder-token'
    task_id = controller.register(asdict(task), token)
    controller.approve(task_id, token, True, 'Founder reviewed disposable task')
    assert controller.queue()[0]['github_open'] is True
    run_id = controller.start(task_id, token)
    row = store.run(run_id)
    assert row['status'] == 'WAITING_CI' and row['ci_state'] == 'MISSING'
    assert github.prs == []
    github.result_sha = row['head_sha']
    git(worktree, 'push', 'origin', 'HEAD:refs/heads/feat/toy-dispatch')
    assert github.remote_sha() == row['head_sha']
    assert controller.refresh_ci(run_id)['status'] == 'AWAITING_REVIEW'
    assert store.decisions(run_id)[0]['decision'] == 'ACCEPT'
    assert controller.publish(run_id, token) == 'https://github.example/pull/1'
    assert github.prs[0]['draft'] is True and github.prs[0]['base'] == 'main'
    assert github.comments[0]['body'].startswith('ENGINEERING_RESULT')
    assert store.latest_checkpoint(run_id, 'CI_OBSERVED')['workflow_blob_sha'] == 'b' * 40
    assert store.verify_events()
