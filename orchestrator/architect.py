"""Stateless Chief Architect Responses API boundary; no ChatGPT chat access."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from .store import compact, redact


class OpenAIArchitect:
    def __init__(self, instructions_path: Path, model: str, enabled: bool = False,
                 budget_guard=None):
        self.instructions_path = instructions_path
        self.model = model
        self.enabled = enabled
        self.budget_guard = budget_guard

    def review(self, evidence: dict) -> dict:
        if not self.enabled:
            raise PermissionError('Chief Architect API expenditure disabled')
        key = os.getenv('OPENAI_API_KEY', '')
        if not key:
            raise PermissionError('OpenAI API key unavailable')
        instructions = self.instructions_path.read_text(encoding='utf-8')
        if len(instructions) > 12000:
            raise ValueError('instructions too large')
        review_input = compact(redact(evidence))
        if len(review_input.encode('utf-8')) > 24000:
            raise PermissionError('complete review evidence exceeds API budget')
        if self.budget_guard is None or not self.budget_guard(26000):
            raise PermissionError('Chief Architect API budget not approved')
        payload = {'model': self.model, 'instructions': instructions,
                   'input': review_input,
                   'max_output_tokens': 1200, 'store': False, 'tools': []}
        req = Request('https://api.openai.com/v1/responses',
                      data=json.dumps(payload).encode(), method='POST',
                      headers={'Authorization': 'Bearer ' + key,
                               'Content-Type': 'application/json'})
        with urlopen(req, timeout=45) as response:
            data = json.loads(response.read(250_000))
        text = ''.join(part.get('text', '') for item in data.get('output', [])
                       for part in item.get('content', []) if part.get('type') == 'output_text')
        result = json.loads(text)
        if set(result) != {'decision', 'reason', 'next_task'} or result['decision'] not in ('ACCEPT', 'REJECT'):
            raise ValueError('invalid architect response')
        if not isinstance(result['reason'], str) or len(result['reason']) > 1000:
            raise ValueError('invalid architect reason')
        if result['next_task'] is not None and not isinstance(result['next_task'], dict):
            raise ValueError('invalid next-task proposal')
        return {'decision': result['decision'], 'reason': redact(result['reason']),
                'next_task': redact(result['next_task']), 'usage': data.get('usage')}


class MockArchitect:
    def review(self, evidence: dict) -> dict:
        decision = 'ACCEPT' if evidence.get('ci', {}).get('state') == 'SUCCESS' and \
                   evidence.get('scope_valid') and evidence.get('patch') and \
                   evidence.get('acceptance', {}).get('passed') and \
                   evidence.get('audit_valid') and evidence.get('security_passed') and not any(
                       item.get('severity') in ('HIGH', 'REVIEW') for item in evidence.get('security_findings', [])) \
                   else 'REJECT'
        return {'decision': decision, 'reason': 'Fixture review from independent evidence',
                'next_task': None, 'usage': {'total_tokens': 0}}
