"""Issue #1 contract tests: the pilot is fixture-only and writes central state."""
import json
import sqlite3
from pathlib import Path

import pytest

from acqsys import core
from acqsys.integration import FixtureTransport, run_fixture_pilot


TOKEN = 'fixture-founder-token'
URL_A = 'https://fixture.example/projects/123'
URL_B = 'https://fixture.example/projects/124'
PAGES = {
    URL_A: '<h1>Document classifier</h1><p>Build a classifier for a document queue.</p>',
    URL_B: '<h1>Forecasting model</h1><p>Build a demand forecasting model.</p>',
}


@pytest.fixture(autouse=True)
def isolated_core(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'integration.db')
    monkeypatch.setenv('ACQ_ADMIN_TOKEN', TOKEN)
    core.init_db()


def source(*, manual=False, extraction=True, paths=None, rate=20):
    with core.founder_session(TOKEN):
        core.register_source('fixture', 'fixture.example', 'Fixture source', 'MARKETPLACE', actor='founder')
        for state in ('EVALUATING', 'POLICY_REVIEW', 'AWAITING_FOUNDER'):
            core.transition_source('fixture', state, actor='founder')
        if manual:
            core.transition_source('fixture', 'MANUAL_ONLY', actor='founder')
        else:
            core.update_source_policy('fixture', 'CONFIRMED', {
                'browser_navigation': True,
                'authenticated_extraction': extraction,
                'allowed_paths': paths or ['/projects'],
                'rate_limit_per_hour': rate,
            }, 'Founder reviewed fixture-only scope', actor='founder')
            for state in ('ONBOARDING', 'PILOT_READY', 'PILOT_RUNNING'):
                core.transition_source('fixture', state, actor='founder')


@pytest.mark.parametrize('case', [
    'unknown', 'manual', 'expired', 'wrong_host', 'wrong_path',
    'unapproved_action', 'rate_exhausted',
])
def test_denial_has_zero_transport_reads(case):
    if case != 'unknown':
        source(manual=case == 'manual', extraction=case != 'unapproved_action',
               rate=1 if case == 'rate_exhausted' else 20)
    if case == 'expired':
        with sqlite3.connect(core.DB_PATH) as db:
            db.execute("UPDATE source_access_policy SET review_expires_ts='2020-01-01T00:00:00+00:00'")
    url = {'wrong_host': 'https://other.example/projects/123',
           'wrong_path': 'https://fixture.example/private/123'}.get(case, URL_A)
    transport = FixtureTransport({url: PAGES[URL_A]})
    result = run_fixture_pilot(source_id='fixture', urls=[url], transport=transport,
                               run_id='case_'+case)
    assert transport.reads == []
    assert not any(row.get('created') for row in result['results'])
    events = [e for e in core.list_events(200) if e['correlation_id'] == 'case_'+case]
    assert any(e['action'] == 'ACTION_DENIED' for e in events)
    assert core.verify_audit()['valid']


def test_two_fixture_projects_persist_unverified_dedup_and_correlated_audit():
    source()
    transport = FixtureTransport(PAGES)
    first = run_fixture_pilot(source_id='fixture', urls=[URL_A, URL_B],
                              transport=transport, run_id='pilot_one')
    assert len(first['results']) == 2
    assert all(row['created'] for row in first['results'])
    assert len({row['lead_id'] for row in first['results']}) == 2
    assert all(row['candidate']['title'] and row['candidate']['description']
               for row in first['results'])
    assert all(row['candidate']['verification_status'] == 'UNVERIFIED'
               for row in first['results'])
    second = run_fixture_pilot(source_id='fixture', urls=[URL_A, URL_B],
                               transport=transport, run_id='pilot_two')
    assert all(not row['created'] for row in second['results'])
    assert {row['lead_id'] for row in first['results']} == {
        row['lead_id'] for row in second['results']}
    leads = core.list_leads()
    assert len(leads) == 2
    assert {lead['source_url'] for lead in leads} == {URL_A, URL_B}
    assert all(lead['status'] == 'DISCOVERED' and not lead['buyer_verified']
               and lead['demand_type'] == 'EXPLICIT_PROJECT' for lead in leads)
    assert len(core.list_tasks()) == 2
    assert all(len(core.list_lead_observations(lead['id'])) == 2 for lead in leads)
    assert all(obs['verification_status'] == 'UNVERIFIED'
               and obs['availability_status'] == 'UNKNOWN'
               and obs['content_evidence_ref'].startswith('fixture:sha256:')
               for lead in leads for obs in core.list_lead_observations(lead['id']))
    assert core.read_memory('acquisition-run:pilot_one')[0]['kind'] == 'HYPOTHESIS'
    events = [e for e in core.list_events(200) if e['correlation_id'] == 'pilot_one']
    assert sum(e['action'] == 'POLICY_CHECKED' for e in events) == 4
    assert sum(e['action'] == 'CANDIDATE_EXTRACTED' for e in events) == 2
    assert sum(e['action'] == 'LEAD_DISCOVERED' for e in events) == 2
    assert sum(e['action'] == 'CANDIDATE_DEDUPLICATED' for e in core.list_events(200)) == 2
    assert core.verify_audit()['valid']
    assert core.summary()['paying_clients'] == 0


def test_secret_redaction_and_founder_only_manual_intake():
    source(manual=True)
    assert run_fixture_pilot(source_id='fixture', urls=[URL_A],
                             transport=FixtureTransport(PAGES), run_id='manual_denied')['results']
    with pytest.raises(ValueError, match='founder'):
        core.ingest_manual_lead('fixture', {'source_url':URL_A,'title':'Manual lead'},actor='agent')
    with core.founder_session(TOKEN):
        added=core.ingest_manual_lead('fixture', {'source_url':URL_A,'title':'Manual lead',
             'description':'password=fictional-example-value'},actor='founder')
    assert added['created']
    assert core.get_lead(added['lead_id'])['status'] == 'DISCOVERED'
    assert core.get_lead(added['lead_id'])['buyer_verified'] is False
    assert 'fictional-example-value' not in json.dumps(core.list_events(200))
    assert 'fictional-example-value' not in core.get_lead(added['lead_id'])['description']
    assert core.verify_audit()['valid']


def test_fixture_content_secret_is_redacted_from_result_and_db():
    source()
    transport=FixtureTransport({URL_A:'<h1>Document classifier</h1><p>password=fictional-example-value</p>'})
    result=run_fixture_pilot(source_id='fixture', urls=[URL_A], transport=transport,
                             run_id='secret_pilot')
    assert result['results'][0]['created']
    assert 'fictional-example-value' not in json.dumps(result)
    assert 'fictional-example-value' not in json.dumps(core.list_events(200))
    assert 'fictional-example-value' not in core.list_leads()[0]['description']
    assert core.verify_audit()['valid']
