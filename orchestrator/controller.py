"""One supervised task iteration; no recursive dispatch or automatic merge."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .policy import Autonomy, Task, Settings, require_founder, validate_issue, validate_worktree
from .runners import GitReader, LiveCLIExecutor, Runner, Verifier
from .store import Store, redact


class Controller:
    def __init__(self, settings: Settings, store: Store, github, architect,
                 runners: dict[str, Runner], verifier: Verifier, git: GitReader):
        settings.validate()
        self.settings, self.store, self.github = settings, store, github
        self.architect, self.runners, self.verifier, self.git = architect, runners, verifier, git
        self.store.recover()

    def register(self, task_data: dict, founder_token: str) -> str:
        require_founder(founder_token)
        task = Task.from_dict(task_data)
        validate_worktree(task, self.settings.root, self.git)
        return self.store.add_task(task)

    def approve(self, task_id: str, founder_token: str, approved: bool, reason: str):
        require_founder(founder_token)
        task, _ = self.store.task(task_id)
        issue = self.github.issue(task.issue)
        validate_issue(task, issue, self.settings.founder_login)
        self.store.approve_task(task_id, approved, reason)

    def queue(self):
        # GitHub data is displayed, never turned into executable instructions.
        remote = {item.get('number'): item for item in self.github.queue()}
        return [{**row, 'github_open': remote.get(row['issue'], {}).get('state') == 'open'}
                for row in self.store.list_tasks()]

    def _preflight(self, task: Task):
        task.validate()
        validate_issue(task, self.github.issue(task.issue), self.settings.founder_login)
        if self.github.branch_sha(task.branch) != task.source_sha:
            raise PermissionError('remote branch SHA changed')
        validate_worktree(task, self.settings.root, self.git)

    def start(self, task_id: str, founder_token: str, mode: str = 'mock') -> str:
        require_founder(founder_token)
        if self.settings.autonomy != Autonomy.SUPERVISED:
            raise PermissionError('controller is OFF')
        task, approved = self.store.task(task_id)
        if not approved:
            raise PermissionError('task not approved')
        self._preflight(task)
        if mode != 'mock' or not self.settings.mock_only:
            raise PermissionError('live CLI execution is not activated')
        runner = self.runners.get(task.owner)
        if runner is None or isinstance(runner, LiveCLIExecutor):
            raise PermissionError('runner unavailable')
        run_id = self.store.admit(task_id, mode)
        self.store.checkpoint(run_id, 'ADMITTED', {'source_sha': task.source_sha,
                                                   'owner': task.owner})
        candidate_sha, used_tokens, used_cost, observed_ci = None, None, None, 'UNKNOWN'
        try:
            started = time.monotonic()
            result = runner.run(task, lambda: bool(self.store.run(run_id)['stop_requested']))
            candidate_sha, used_tokens, used_cost = result.head_sha, result.tokens, result.cost_usd
            if time.monotonic() - started > task.timeout_seconds:
                raise TimeoutError('run exceeded runtime budget')
            self.store.log(run_id, result.output)
            if result.exit_code or self.store.run(run_id)['stop_requested']:
                raise InterruptedError('runner exited or stop requested')
            if result.tokens is None or result.cost_usd is None or result.tokens > task.max_tokens or \
               result.cost_usd > task.max_cost_usd:
                raise PermissionError('usage missing or exceeds run budget')
            evidence = self.verifier.collect(task, result.head_sha)
            self.store.checkpoint(run_id, 'REVIEW_EVIDENCE', evidence)
            if not evidence['acceptance']['passed'] or not evidence['security_passed']:
                raise PermissionError('acceptance or security checks failed')
            ci = self.github.ci_evidence(result.head_sha, task.branch, task.source_sha)
            ci_state = ci['state']
            observed_ci = ci_state
            self.store.checkpoint(run_id, 'CI_OBSERVED', ci)
            if ci_state == 'FAILED':
                raise RuntimeError('independent CI failed')
            status = 'AWAITING_REVIEW' if ci_state == 'SUCCESS' else 'WAITING_CI'
            self.store.finish(run_id, status, result.head_sha, result.tokens,
                              result.cost_usd, ci_state)
            if self.store.run(run_id)['status'] == 'AWAITING_REVIEW':
                self._architect_review(run_id, task, evidence, ci)
        except Exception as exc:
            self.store.log(run_id, type(exc).__name__)
            if self.store.run(run_id)['status'] == 'RUNNING':
                self.store.finish(run_id, 'STOPPED' if isinstance(exc, InterruptedError) else 'FAILED',
                                  candidate_sha, used_tokens, used_cost, observed_ci)
            self.store.event('RUN_ERROR', {'error_type': type(exc).__name__}, run_id)
        return run_id

    def _architect_review(self, run_id: str, task: Task, evidence: dict, ci: dict):
        row = self.store.run(run_id)
        packet = {'issue': task.issue, 'owner': task.owner, 'source_sha': task.source_sha,
                  'head_sha': row['head_sha'], 'ci': ci, 'scope_valid': True,
                  'audit_valid': self.store.verify_events(), **evidence}
        result = self.architect.review(packet)
        self.store.decide(run_id, 'chief_architect', result['decision'], result['reason'])
        if result.get('next_task'):
            self.store.add_proposal(result['next_task'])

    def refresh_ci(self, run_id: str):
        row = self.store.run(run_id)
        if row['status'] != 'WAITING_CI':
            return row
        task, approved = self.store.task(row['task_id'])
        if not approved:
            raise PermissionError('task approval revoked')
        if datetime.fromisoformat(task.deadline_utc.replace('Z', '+00:00')) <= datetime.now(timezone.utc):
            self.store.update_ci(run_id, 'EXPIRED', 'FAILED')
            return self.store.run(run_id)
        validate_issue(task, self.github.issue(task.issue), self.settings.founder_login)
        remote_sha = self.github.branch_sha(task.branch)
        if remote_sha not in (task.source_sha, row['head_sha']):
            raise PermissionError('result branch moved')
        evidence = self.verifier.collect(task, row['head_sha'])
        if not evidence['acceptance']['passed'] or not evidence['security_passed']:
            self.store.update_ci(run_id, 'FAILED', 'FAILED')
            return self.store.run(run_id)
        ci = self.github.ci_evidence(row['head_sha'], task.branch, task.source_sha)
        ci_state = ci['state']
        self.store.checkpoint(run_id, 'CI_OBSERVED', ci)
        if ci_state == 'FAILED':
            self.store.update_ci(run_id, ci_state, 'FAILED')
        elif ci_state == 'SUCCESS':
            if remote_sha != row['head_sha']:
                raise PermissionError('successful CI is not on the remote result branch')
            self.store.update_ci(run_id, ci_state, 'AWAITING_REVIEW')
            self.store.checkpoint(run_id, 'REVIEW_EVIDENCE', evidence)
            self._architect_review(run_id, task, evidence, ci)
        return self.store.run(run_id)

    def publish(self, run_id: str, founder_token: str) -> str:
        require_founder(founder_token)
        row = self.store.run(run_id)
        if row['status'] != 'AWAITING_REVIEW' or row['ci_state'] != 'SUCCESS' or row['pr_url']:
            raise PermissionError('run is not publishable')
        decisions = self.store.decisions(run_id)
        architect_decisions = [d for d in decisions if d['actor'] == 'chief_architect']
        if not architect_decisions or architect_decisions[-1]['decision'] != 'ACCEPT' or \
           any(d['actor'] == 'founder' and d['decision'] == 'REJECT' for d in decisions):
            raise PermissionError('independent review did not accept')
        task, approved = self.store.task(row['task_id'])
        if not approved:
            raise PermissionError('task approval revoked')
        task.validate()
        validate_issue(task, self.github.issue(task.issue), self.settings.founder_login)
        if self.github.branch_sha(task.branch) != row['head_sha']:
            raise PermissionError('remote result SHA changed')
        evidence = self.verifier.collect(task, row['head_sha'])
        previous = self.store.latest_checkpoint(run_id, 'REVIEW_EVIDENCE')
        if not previous or not evidence['acceptance']['passed'] or not evidence['security_passed'] or \
           evidence['patch_sha256'] != previous['patch_sha256']:
            raise PermissionError('review evidence stale or acceptance failed')
        ci = self.github.ci_evidence(row['head_sha'], task.branch, task.source_sha)
        last_ci = self.store.latest_checkpoint(run_id, 'CI_OBSERVED')
        if ci['state'] != 'SUCCESS' or not last_ci or \
           ci.get('run_id') != last_ci.get('run_id') or \
           ci.get('workflow_blob_sha') != last_ci.get('workflow_blob_sha'):
            raise PermissionError('trusted CI evidence changed')
        self.store.checkpoint(run_id, 'PUBLICATION_REVALIDATED',
                              {'patch_sha256': evidence['patch_sha256'], 'ci': ci,
                               'acceptance': evidence['acceptance']})
        body = ('Draft engineering review only. No automatic merge.\n\n'
                'Issue: #' + str(task.issue) + '\nSource SHA: ' + task.source_sha +
                '\nResult SHA: ' + row['head_sha'] + '\nCI: SUCCESS\n' +
                'Patch SHA-256: ' + evidence['patch_sha256'] + '\n' +
                'Acceptance tests: ' + ', '.join(task.acceptance) + '\n')
        pr = self.github.create_draft_pr('Engineering result for #' + str(task.issue),
                                          task.branch, 'main', body)
        url = pr['html_url']
        self.store.decide(run_id, 'founder', 'PUBLISH', 'Founder approved draft PR')
        self.store.save_pr(run_id, url)
        self.github.comment(task.issue, {'run_id': run_id, 'sha': row['head_sha'],
                                         'ci': 'SUCCESS', 'conclusion': 'NEEDS_ARCHITECT_REVIEW',
                                         'pr_url': url})
        return url

    def reject(self, run_id: str, founder_token: str, reason: str):
        require_founder(founder_token)
        self.store.decide(run_id, 'founder', 'REJECT', reason)
        if self.store.run(run_id)['status'] == 'RUNNING':
            self.store.request_stop(run_id)

    def pause(self, run_id: str, founder_token: str):
        require_founder(founder_token)
        self.store.decide(run_id, 'founder', 'PAUSE', 'Founder paused run')
        self.store.request_stop(run_id)

    def emergency_stop(self, founder_token: str):
        require_founder(founder_token)
        self.store.request_stop('all', emergency=True)

    def clear_emergency(self, founder_token: str):
        require_founder(founder_token)
        self.store.clear_emergency()

    def publish_proposal(self, proposal_id: str, founder_token: str) -> str:
        require_founder(founder_token)
        row = self.store.proposal(proposal_id)
        if row['status'] != 'PENDING':
            raise PermissionError('proposal not pending')
        proposal = json.loads(row['body'])
        if set(proposal) != {'title', 'task'}:
            raise ValueError('invalid proposed task shape')
        payload = dict(proposal['task'])
        payload['issue'] = 1  # validate all local constraints before creating an issue
        task = Task.from_dict(payload)
        validate_worktree(task, self.settings.root, self.git)
        body = 'Supervised engineering task; founder review required before run.\n\n' + \
               json.dumps(redact({k: v for k, v in payload.items() if k != 'issue'}), indent=2)
        issue = self.github.create_issue(proposal['title'], body, task.owner)
        payload['issue'] = issue['number']
        task_id = self.store.add_task(Task.from_dict(payload))
        self.store.mark_proposal(proposal_id, 'PUBLISHED')
        return task_id

    def reject_proposal(self, proposal_id: str, founder_token: str):
        require_founder(founder_token)
        self.store.mark_proposal(proposal_id, 'REJECTED')
