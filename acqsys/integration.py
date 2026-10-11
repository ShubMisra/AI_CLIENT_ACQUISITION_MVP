"""Fixture-only bridge from Kilo's policy-injected worker into core state.

This module has no HTTP or browser transport. A live collector must be reviewed
separately; fixture authorization does not grant live source access.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from typing import Mapping
from urllib.parse import urlsplit

from acqsys import core
from acqsys.acquisition.worker import AcquisitionWorker


class FixtureTransport:
    """Instrumentable, in-memory fixture source; missing URLs fail closed."""

    def __init__(self, pages: Mapping[str, str]):
        self._pages = dict(pages)
        self.reads: list[str] = []

    def read(self, url: str) -> str:
        if url not in self._pages:
            raise ValueError('fixture unavailable')
        if len(self._pages[url].encode('utf-8')) > 1_000_000:
            raise ValueError('fixture exceeds byte limit')
        self.reads.append(url)
        return self._pages[url]


class _ProjectParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._active: str | None = None
        self.title: list[str] = []
        self.description: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ('h1', 'p'):
            self._active = tag

    def handle_endtag(self, tag):
        if tag == self._active:
            self._active = None

    def handle_data(self, data):
        if self._active == 'h1':
            self.title.append(data)
        elif self._active == 'p':
            self.description.append(data)


def run_fixture_pilot(*, source_id: str, urls: list[str], transport: FixtureTransport,
                      run_id: str) -> dict:
    """Authorize each fixture navigation and extraction, then persist candidates.

    The Kilo worker performs navigation authorization. This adapter supplies its
    missing extraction gate and candidate persistence without changing Kilo files.
    """
    port = core.CorePolicyPort()
    worker = AcquisitionWorker(port)
    results = []
    with core.audit_correlation(run_id):
        core.record_event('acquisition_agent','COLLECTOR_STARTED',
                          {'source_id': source_id, 'fixture_only': True},'source',source_id)
        for url in urls:
            try:
                # No transport read occurs until both policy decisions permit it.
                worker._browser.navigate(run_id, source_id, url)
                decision = port.authorize(source_id=source_id,
                                          action='authenticated_extraction', target_url=url)
                if not decision.allowed:
                    results.append({'url': core.normalize_url(url), 'denied': decision.reason_code})
                    continue
                if source_id != 'fixture' or urlsplit(url).hostname != 'fixture.example':
                    raise ValueError('fixture pilot requires the fixture source')
                html = transport.read(url)
                parser = _ProjectParser()
                parser.feed(html)
                title = ' '.join(''.join(parser.title).split())
                description = ' '.join(''.join(parser.description).split())
                if not title or not description:
                    core.record_event('acquisition_agent','CANDIDATE_REJECTED',
                                      {'reason_code':'EMPTY_EXTRACTION'},'source',source_id)
                    results.append({'url': core.normalize_url(url), 'error':'EMPTY_EXTRACTION'})
                    continue
                evidence_ref = 'fixture:sha256:' + hashlib.sha256(html.encode()).hexdigest()
                candidate = {'source':source_id, 'source_id':source_id,
                             'source_url':core.normalize_url(url), 'title':title,
                             'description':description, 'demand_type':'EXPLICIT_PROJECT',
                             'verification_status':'UNVERIFIED', 'availability_status':'UNKNOWN',
                             'content_evidence_ref':evidence_ref,
                             'access_evidence_ref':'policy-version:' + str(decision.policy_version),
                             'run_id':run_id}
                candidate = core.redact(candidate)
                lead = core.add_lead(candidate, actor='acquisition_agent', correlation_id=run_id)
                core.record_candidate_observation(
                    lead['id'],run_id,source_id,evidence_ref,candidate['access_evidence_ref'])
                action = 'CANDIDATE_EXTRACTED' if lead['created'] else 'CANDIDATE_DEDUPLICATED'
                core.record_event('acquisition_agent',action,
                                  {'source_id':source_id, 'content_evidence_ref':evidence_ref,
                                   'access_evidence_ref':candidate['access_evidence_ref'],
                                   'verification_status':'UNVERIFIED',
                                   'availability_status':'UNKNOWN'},
                                  'lead',lead['id'])
                if lead['created']:
                    task_id=core.create_task('Verify candidate buyer and source evidence',
                                             lead_id=lead['id'],actor='acquisition_agent')
                    core.record_event('acquisition_agent','HUMAN_TASK_CREATED',
                                      {'task_id':task_id},'lead',lead['id'])
                results.append({'candidate':candidate, 'lead_id':lead['id'],
                                'created':lead['created']})
            except PermissionError:
                # CorePolicyPort already records a redacted ACTION_DENIED.
                results.append({'denied':'POLICY_DENIED'})
            except Exception as exc:
                core.record_event('acquisition_agent','COLLECTOR_ITEM_FAILED',
                                  {'error_type':type(exc).__name__},'source',source_id)
                results.append({'error':type(exc).__name__})
        core.add_memory('acquisition-run:'+run_id,'HYPOTHESIS',
                        f'{sum(bool(r.get("created")) for r in results)} fixture candidates need founder verification',
                        'fixture-run:'+run_id,0.5,actor='acquisition_agent')
        core.record_event('acquisition_agent','COLLECTOR_FINISHED',
                          {'created':sum(bool(r.get('created')) for r in results),
                           'duplicates':sum(r.get('created') is False for r in results),
                           'denied':sum('denied' in r for r in results)},'source',source_id)
    return {'run_id':run_id,'results':results}
