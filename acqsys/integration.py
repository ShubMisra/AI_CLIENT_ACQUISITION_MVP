"""Fixture-only bridge from Kilo's public collector to central core policy/state."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

from acqsys import agents, core
from acqsys.acquisition.browser import BrowserWorker
from acqsys.acquisition.lead_qual import deduplicate

HISTORICAL_FILE = Path(__file__).resolve().parent.parent / 'lead_candidates_2026-10-10.json'


def _ensure_draft(lead_id: str) -> str:
    """Use the existing deterministic, unsent draft once per persisted lead."""
    prior = [a for a in core.list_artifacts(lead_id) if a['kind'] == 'PROPOSAL_DRAFT']
    if prior:
        return prior[0]['id']
    return agents.evidence_driven_proposal(lead_id)['result']['artifact_id']


def prepare_founder_candidates(*, source_id: str, candidates: list[dict],
                               run_id: str, founder_token: str) -> dict:
    """Founder-supplied MANUAL_ONLY records to scored leads, review tasks and drafts."""
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 50:
        raise ValueError('expected 1..50 founder candidates')
    with core.founder_session(founder_token), core.audit_correlation(run_id):
        source = core.get_source(source_id)
        if not source or source['lifecycle_state'] != 'MANUAL_ONLY' or \
           not source['human_supplied_lead_processing']:
            raise PermissionError('founder source is not approved for manual intake')
        domain = source['domain'].lower()
        if domain == 'localhost' or domain.endswith(('.local', '.internal')):
            raise PermissionError('private manual source denied')
        try:
            if not ipaddress.ip_address(domain).is_global:
                raise PermissionError('private manual source denied')
        except ValueError:
            pass
        validated = []
        for raw in candidates:
            if not isinstance(raw, dict) or raw.get('source') not in (None, source_id):
                raise ValueError('invalid candidate or source binding')
            title, description, url = raw.get('title'), raw.get('description'), raw.get('source_url')
            if not all(isinstance(v, str) and v.strip() for v in (title, description, url)):
                raise ValueError('candidate title, description and URL required')
            if len(title) > 300 or len(description) > 4000 or len(url) > 2048 or \
               raw.get('demand_type', 'EXPLICIT_PROJECT') not in core.DEMAND_TYPES:
                raise ValueError('candidate content or demand type invalid')
            normalized = core.normalize_url(url)
            parsed = urlsplit(normalized)
            if parsed.scheme != 'https' or parsed.hostname != domain or parsed.port not in (None, 443):
                raise ValueError('candidate URL outside approved HTTPS source')
            for key in ('budget_min', 'budget_max'):
                value = raw.get(key)
                if value is not None and (type(value) not in (int, float) or
                                          not math.isfinite(value) or value < 0):
                    raise ValueError('invalid stated budget')
            if raw.get('budget_min') is not None and raw.get('budget_max') is not None and \
               raw['budget_max'] < raw['budget_min']:
                raise ValueError('stated budget range invalid')
            validated.append({**raw, 'source': source_id, 'source_url': normalized,
                              'verification_status': 'UNVERIFIED',
                              'availability_status': 'UNKNOWN'})
        results = []
        for item in validated:
            lead = core.ingest_manual_lead(source_id, item, correlation_id=run_id)
            evidence = 'founder-record:sha256:' + hashlib.sha256(
                json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()
            core.record_candidate_observation(lead['lead_id'], run_id, source_id,
                                              evidence, 'founder-manual-source:' + source_id)
            task_id, _ = core.ensure_founder_review_task(
                lead['lead_id'], 'Verify candidate buyer, freshness and source evidence',
                actor='founder')
            draft_id = _ensure_draft(lead['lead_id'])
            persisted = core.get_lead(lead['lead_id'])
            results.append({'lead_id': lead['lead_id'], 'created': lead['created'],
                            'score': persisted['score'], 'review_task_id': task_id,
                            'draft_artifact_id': draft_id,
                            'verification_status': 'UNVERIFIED',
                            'availability_status': 'UNKNOWN'})
        return {'run_id': run_id, 'source_id': source_id, 'results': results,
                'drafts_sent': 0}


class _FixturePath:
    """The public BrowserWorker fixtures_dir interface, backed by known text."""

    def __init__(self, transport: 'FixtureTransport', parts: tuple[str, ...] = ()):
        self.transport, self.parts = transport, parts

    def __truediv__(self, part):
        return _FixturePath(self.transport, (*self.parts, str(part)))

    def exists(self):
        return not self.parts or '/'.join(self.parts) in self.transport._paths

    def read_text(self, *, encoding='utf-8', errors='strict'):
        key = '/'.join(self.parts)
        url, html = self.transport._paths[key]
        if len(html.encode('utf-8')) > 1_000_000:
            raise ValueError('fixture exceeds byte limit')
        self.transport.reads.append(url)
        return html


class FixtureTransport:
    """Instrumented public fixture filesystem; it cannot make HTTP requests."""

    def __init__(self, pages: dict[str, str]):
        self.pages = dict(pages)
        self.reads: list[str] = []
        self._paths: dict[str, tuple[str, str]] = {}
        for url, html in self.pages.items():
            path = urlsplit(url).path.strip('/').replace('/', '_') or 'index'
            key = path + '.html'
            if key in self._paths or not isinstance(html, str):
                raise ValueError('ambiguous or invalid fixture page')
            self._paths[key] = (url, html)
        self.fixture_root = _FixturePath(self)


class _TracedCorePort(core.CorePolicyPort):
    def __init__(self):
        self.decisions: list[tuple[str, core.AccessDecision]] = []

    def authorize(self, *, source_id: str, action: str, target_url: str):
        decision = super().authorize(source_id=source_id, action=action,
                                     target_url=target_url)
        self.decisions.append((action, decision))
        return decision

    def last_extraction(self):
        for action, decision in reversed(self.decisions):
            if action == 'authenticated_extraction':
                return decision
        raise PermissionError('extraction was not authorized')


def _candidate_from_public_result(raw: dict, *, page_url: str, html: str,
                                  source_id: str, run_id: str, decision) -> dict:
    """Validate Kilo's DTO; do not parse HTML or invent buyer verification."""
    url = core.normalize_url(str(raw.get('source_url') or ''))
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'fixture.example' or \
       not parsed.path.startswith('/projects/'):
        raise ValueError('candidate URL outside synthetic project scope')
    title = str(raw.get('title') or '').strip()
    description = str(raw.get('description') or '').strip()
    if not title or not description or raw.get('source_id') != source_id:
        raise ValueError('candidate lacks grounded title, description or source')
    # This binds the public DTO's individual URL to the exact fixture page bytes.
    # Kilo's own per-card locator remains a release blocker on PR #4.
    page_hash = hashlib.sha256(html.encode()).hexdigest()
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    evidence_ref = f'fixture:sha256:{page_hash}:url-sha256:{url_hash}'
    return core.redact({'source': source_id, 'source_id': source_id,
                        'source_url': url, 'title': title,
                        'description': description, 'demand_type': 'EXPLICIT_PROJECT',
                        'verification_status': 'UNVERIFIED',
                        'availability_status': 'UNKNOWN',
                        'content_evidence_ref': evidence_ref,
                        'access_evidence_ref': 'policy-version:' + str(decision.policy_version),
                        'run_id': run_id, 'source_page_url': page_url})


def run_fixture_pilot(*, source_id: str, urls: list[str], transport: FixtureTransport,
                      run_id: str) -> dict:
    """Reauthorize every public navigation/extraction, then write central state."""
    with core.audit_correlation(run_id):
        core.create_fixture_run(run_id, source_id, urls)
        state = core.fixture_run(run_id)
        if state['status'] == 'COMPLETED':
            return {'run_id': run_id, 'results': [], 'status': 'COMPLETED'}
        port = _TracedCorePort()
        browser = BrowserWorker(port, fixtures_dir=transport.fixture_root)
        browser.configure(allowed_domains={'fixture.example'})
        results: list[dict] = []
        for index in range(state['cursor'], len(urls)):
            url = urls[index]
            try:
                browser.navigate(run_id, source_id, url)
                if source_id != 'fixture' or urlsplit(url).hostname != 'fixture.example':
                    raise PermissionError('synthetic fixture source required')
                core.update_fixture_run(run_id, index, 'RUNNING')
                before = len(transport.reads)
                extraction = browser.extract(run_id, source_id, url)
                decision = port.last_extraction()
                if not decision.allowed or len(transport.reads) == before or \
                   transport.reads[-1] != url or not extraction.candidates:
                    raise ValueError('empty or unread fixture extraction')
                candidates = deduplicate(extraction.candidates)
                mapped = [_candidate_from_public_result(
                    raw, page_url=url, html=transport.pages[url], source_id=source_id,
                    run_id=run_id, decision=decision) for raw in candidates]
                page_results = []
                for candidate in mapped:
                    lead = core.add_lead(candidate, actor='acquisition_agent',
                                         correlation_id=run_id)
                    core.record_candidate_observation(
                        lead['id'], run_id, source_id,
                        candidate['content_evidence_ref'],
                        candidate['access_evidence_ref'])
                    core.record_event('acquisition_agent',
                                      'CANDIDATE_EXTRACTED' if lead['created'] else
                                      'CANDIDATE_DEDUPLICATED',
                                      {'source_id': source_id,
                                       'content_evidence_ref': candidate['content_evidence_ref'],
                                       'verification_status': 'UNVERIFIED',
                                       'availability_status': 'UNKNOWN'},
                                      'lead', lead['id'])
                    task_id, task_created = core.ensure_founder_review_task(
                        lead['id'], 'Verify candidate buyer and source evidence',
                        actor='acquisition_agent')
                    if task_created:
                        core.record_event('acquisition_agent', 'HUMAN_TASK_CREATED',
                                          {'task_id': task_id}, 'lead', lead['id'])
                    draft_id = _ensure_draft(lead['id'])
                    page_results.append({'candidate': candidate, 'lead_id': lead['id'],
                                         'created': lead['created'],
                                         'score': core.get_lead(lead['id'])['score'],
                                         'review_task_id': task_id,
                                         'draft_artifact_id': draft_id})
                if not page_results:
                    raise ValueError('no grounded candidates')
                results.extend(page_results)
                core.update_fixture_run(run_id, index + 1,
                                        'COMPLETED' if index + 1 == len(urls) else 'RUNNING')
            except PermissionError:
                core.update_fixture_run(run_id, index, 'BLOCKED')
                results.append({'url': core.redact(url), 'denied': 'POLICY_DENIED'})
                break
            except Exception as exc:
                core.update_fixture_run(run_id, index, 'BLOCKED')
                core.record_event('acquisition_agent', 'COLLECTOR_ITEM_FAILED',
                                  {'error_type': type(exc).__name__}, 'source', source_id)
                results.append({'url': core.redact(url), 'error': type(exc).__name__})
                break
        core.add_memory('acquisition-run:' + run_id, 'HYPOTHESIS',
                        f'{sum(r.get("created") is True for r in results)} fixture candidates need founder verification',
                        'fixture-run:' + run_id, 0.5, actor='acquisition_agent')
        core.record_event('acquisition_agent', 'COLLECTOR_FINISHED',
                          {'created': sum(r.get('created') is True for r in results),
                           'duplicates': sum(r.get('created') is False for r in results),
                           'denied': sum('denied' in r for r in results)},
                          'source', source_id)
    return {'run_id': run_id, 'results': results,
            'status': core.fixture_run(run_id)['status']}


def resume_fixture_pilot(*, run_id: str, transport: FixtureTransport) -> dict:
    """Restore centrally bound source/URLs; every operation rechecks policy."""
    state = core.fixture_run(run_id)
    if not state:
        raise ValueError('fixture run not found')
    return run_fixture_pilot(source_id=state['source_id'], urls=state['urls'],
                             transport=transport, run_id=run_id)


def import_historical_candidates(*, run_id: str, founder_token: str) -> dict:
    """Founder-approved local intake of the genuine root historical file."""
    with core.founder_session(founder_token), core.audit_correlation(run_id):
        raw = HISTORICAL_FILE.read_bytes()  # Missing/corrupt root fails; no fixture fallback.
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            raise ValueError('historical candidates must be a nonempty list')
        for item in data:
            if not isinstance(item, dict) or not item.get('source') or not item.get('source_url') or \
               not item.get('title') or not item.get('description'):
                raise ValueError('historical candidate lacks provenance or content')
            core.normalize_url(item['source_url'])
        file_hash = hashlib.sha256(raw).hexdigest()
        results = []
        for index, item in enumerate(data):
            source_id = str(item['source'])
            candidate = {**item, 'verification_status': 'UNVERIFIED',
                         'availability_status': 'UNKNOWN'}
            lead = core.add_lead(candidate, actor='founder', correlation_id=run_id)
            evidence_ref = f'historical-file:sha256:{file_hash}:row:{index + 1}'
            core.record_candidate_observation(lead['id'], run_id, source_id,
                                              evidence_ref, 'founder-local-file-import')
            core.ensure_founder_review_task(
                lead['id'], 'Verify historical candidate freshness, buyer and source evidence',
                actor='founder')
            results.append({'lead_id': lead['id'], 'created': lead['created'],
                            'source_url': core.normalize_url(item['source_url']),
                            'verification_status': 'UNVERIFIED',
                            'availability_status': 'UNKNOWN'})
        core.record_event('founder', 'HISTORICAL_CANDIDATES_IMPORTED',
                          {'count': len(results), 'created': sum(r['created'] for r in results),
                           'file_sha256': file_hash}, 'source', 'historical-local-file')
    return {'run_id': run_id, 'results': results}
