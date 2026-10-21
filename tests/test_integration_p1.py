"""Issue #1 contract tests: the pilot is fixture-only and writes central state."""
import json
import sqlite3
from pathlib import Path

import pytest

from acqsys import core
from acqsys.integration import (FixtureTransport, run_fixture_pilot,
                                resume_fixture_pilot, import_historical_candidates,
                                prepare_founder_candidates)
from acqsys import integration
from acqsys.app import app
from fastapi.testclient import TestClient


TOKEN = 'fixture-founder-token'
URL_A = 'https://fixture.example/projects/123'
URL_B = 'https://fixture.example/projects/124'
PAGES = {
    URL_A: '<h1>Document classifier</h1><p>Build a classifier for a document queue.</p>',
    URL_B: '<h1>Forecasting model</h1><p>Build a demand forecasting model.</p>',
}
LISTING_URL = 'https://fixture.example/listing/cards.html'
CARDS = '''<html><body>
<div class="card"><h2>Document classifier</h2><p>Build a classifier for a document queue.</p><a href="/projects/123">View</a></div>
<div class="card"><h2>Forecasting model</h2><p>Build a demand forecasting model.</p><a href="/projects/124">View</a></div>
</body></html>'''


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


def test_public_single_page_extraction_two_distinct_url_leads_and_durable_review():
    source(paths=['/listing', '/projects'])
    transport = FixtureTransport({LISTING_URL: CARDS})
    first = run_fixture_pilot(source_id='fixture', urls=[LISTING_URL],
                              transport=transport, run_id='cards_first')
    assert first['status'] == 'COMPLETED'
    assert transport.reads == [LISTING_URL]
    assert len(first['results']) == 2
    assert all(row['created'] for row in first['results'])
    assert {row['candidate']['source_url'] for row in first['results']} == {URL_A, URL_B}
    assert len({row['candidate']['content_evidence_ref'] for row in first['results']}) == 2
    assert len(core.list_leads()) == 2
    assert len(core.list_tasks()) == 2
    assert all(row['score'] > 0 and row['review_task_id'] and row['draft_artifact_id']
               for row in first['results'])
    assert all(len(core.list_artifacts(lead['id'])) == 1 and
               'NOT been sent' in core.list_artifacts(lead['id'])[0]['content']
               for lead in core.list_leads())
    assert all(not lead['buyer_verified'] and lead['status'] == 'DISCOVERED'
               for lead in core.list_leads())
    assert all(obs['verification_status'] == 'UNVERIFIED' and
               obs['availability_status'] == 'UNKNOWN'
               for lead in core.list_leads()
               for obs in core.list_lead_observations(lead['id']))
    second = run_fixture_pilot(source_id='fixture', urls=[LISTING_URL],
                               transport=transport, run_id='cards_repeat')
    assert len(second['results']) == 2
    assert all(row['created'] is False for row in second['results'])
    assert len(core.list_leads()) == 2 and len(core.list_tasks()) == 2
    assert all(len(core.list_artifacts(lead['id'])) == 1 for lead in core.list_leads())
    assert core.verify_audit()['valid']


def test_founder_provided_synthetic_api_intake_scores_tasks_and_drafts():
    with core.founder_session(TOKEN):
        core.register_source('manual_fixture', 'manual.example',
                             'Synthetic founder source', 'MARKETPLACE', actor='founder')
        for state in ('EVALUATING', 'POLICY_REVIEW', 'AWAITING_FOUNDER', 'MANUAL_ONLY'):
            core.transition_source('manual_fixture', state, actor='founder')
    candidate = {'source_url': 'https://manual.example/project/1',
                 'title': 'Synthetic document classification request',
                 'description': 'Test-only AI/ML classification scope supplied by the founder.',
                 'budget_min': 500, 'currency': 'USD'}
    payload = {'source_id': 'manual_fixture', 'run_id': 'synthetic_founder_1',
               'candidates': [candidate]}
    with TestClient(app) as client:
        assert client.post('/api/intake/founder', json=payload).status_code == 403
        response = client.post('/api/intake/founder', json=payload,
                               headers={'X-Admin-Token': TOKEN})
        assert response.status_code == 200, response.text
        first = response.json()['results'][0]
        repeat = client.post('/api/intake/founder', json=payload,
                             headers={'X-Admin-Token': TOKEN}).json()['results'][0]
    assert first['created'] and not repeat['created']
    assert first['lead_id'] == repeat['lead_id']
    assert first['review_task_id'] == repeat['review_task_id']
    assert first['draft_artifact_id'] == repeat['draft_artifact_id']
    lead = core.get_lead(first['lead_id'])
    assert lead['score'] == first['score'] > 0 and not lead['buyer_verified']
    assert lead['status'] == 'DISCOVERED'
    assert len(core.list_tasks()) == len(core.list_artifacts(lead['id'])) == 1
    assert 'NOT been sent' in core.list_artifacts(lead['id'])[0]['content']
    assert core.summary()['paying_clients'] == 0 and core.verify_audit()['valid']


def test_founder_batch_denies_unapproved_or_invalid_candidate_before_writes():
    with core.founder_session(TOKEN):
        core.register_source('manual_fixture', 'manual.example',
                             'Synthetic founder source', 'MARKETPLACE', actor='founder')
        for state in ('EVALUATING', 'POLICY_REVIEW', 'AWAITING_FOUNDER', 'MANUAL_ONLY'):
            core.transition_source('manual_fixture', state, actor='founder')
    good = {'source_url': 'https://manual.example/project/1', 'title': 'Test only',
            'description': 'Synthetic ML work request'}
    bad = {**good, 'source_url': 'https://other.example/project/2'}
    with pytest.raises(ValueError, match='outside approved'):
        prepare_founder_candidates(source_id='manual_fixture', candidates=[good, bad],
                                   run_id='invalid_batch', founder_token=TOKEN)
    with pytest.raises(PermissionError):
        prepare_founder_candidates(source_id='unknown', candidates=[good],
                                   run_id='unknown_source', founder_token=TOKEN)
    assert core.list_leads() == [] and core.list_tasks() == []
    assert core.verify_audit()['valid']


def test_integrated_fixture_policy_denial_never_queries_dns(monkeypatch):
    import socket
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *_a, **_k:
                        (_ for _ in ()).throw(AssertionError('DNS called')))
    source(paths=['/listing'])
    transport = FixtureTransport({LISTING_URL: CARDS})
    result = run_fixture_pilot(source_id='fixture', urls=[LISTING_URL],
                               transport=transport, run_id='no_dns_fixture')
    assert result['status'] == 'COMPLETED' and len(result['results']) == 2
    assert core.verify_audit()['valid']


def test_extraction_denied_after_allowed_navigation_has_zero_fixture_reads():
    source(paths=['/listing'], extraction=False)
    transport = FixtureTransport({LISTING_URL: CARDS})
    result = run_fixture_pilot(source_id='fixture', urls=[LISTING_URL],
                               transport=transport, run_id='extract_denied')
    assert result['status'] == 'BLOCKED' and transport.reads == []
    events = [e for e in core.list_events(200) if e['correlation_id'] == 'extract_denied']
    assert any(e['action'] == 'POLICY_CHECKED' and
               e['payload'].get('action') == 'browser_navigation' for e in events)
    assert any(e['action'] == 'ACTION_DENIED' and
               e['payload'].get('action') == 'authenticated_extraction' for e in events)
    assert not core.list_leads()


def test_public_extractor_fallback_without_fixture_is_rejected():
    source()
    transport = FixtureTransport({})
    result = run_fixture_pilot(source_id='fixture', urls=[URL_A],
                               transport=transport, run_id='missing_page')
    assert result['status'] == 'BLOCKED' and transport.reads == []
    assert result['results'][0]['error'] == 'ValueError'
    assert not core.list_leads() and not core.list_tasks()


def test_bad_card_target_rejects_whole_page_before_intake():
    source(paths=['/listing'])
    html = CARDS.replace('href="/projects/124"', 'href="http://127.0.0.1/private"')
    transport = FixtureTransport({LISTING_URL: html})
    result = run_fixture_pilot(source_id='fixture', urls=[LISTING_URL],
                               transport=transport, run_id='bad_card')
    assert result['status'] == 'BLOCKED' and transport.reads == [LISTING_URL]
    assert not core.list_leads() and not core.list_tasks()


def test_central_resume_revalidates_and_can_complete_after_founder_authorization():
    source(paths=['/listing'], extraction=False)
    transport = FixtureTransport({LISTING_URL: CARDS})
    first = run_fixture_pilot(source_id='fixture', urls=[LISTING_URL],
                              transport=transport, run_id='resume_authorized')
    assert first['status'] == 'BLOCKED' and transport.reads == []
    with core.founder_session(TOKEN):
        core.update_source_policy('fixture', 'CONFIRMED', {
            'browser_navigation': True, 'authenticated_extraction': True,
            'allowed_paths': ['/listing'], 'rate_limit_per_hour': 20,
        }, 'Founder reviewed resumed fixture scope', actor='founder')
    resumed = resume_fixture_pilot(run_id='resume_authorized', transport=transport)
    assert resumed['status'] == 'COMPLETED'
    assert len(resumed['results']) == 2 and transport.reads == [LISTING_URL]
    assert core.fixture_run('resume_authorized')['cursor'] == 1
    assert core.verify_audit()['valid']
    with pytest.raises(ValueError, match='rebound'):
        run_fixture_pilot(source_id='fixture', urls=[URL_A], transport=transport,
                          run_id='resume_authorized')


def test_replayed_checkpoint_keeps_two_unique_leads_observations_and_tasks():
    source(paths=['/listing'])
    transport = FixtureTransport({LISTING_URL: CARDS})
    run_fixture_pilot(source_id='fixture', urls=[LISTING_URL],
                      transport=transport, run_id='crash_replay')
    # Simulate a crash after intake but before the final cursor write.
    with sqlite3.connect(core.DB_PATH) as db:
        db.execute("UPDATE fixture_collection_runs SET cursor=0,status='BLOCKED' WHERE run_id='crash_replay'")
    resumed = resume_fixture_pilot(run_id='crash_replay', transport=transport)
    assert resumed['status'] == 'COMPLETED'
    assert len(resumed['results']) == 2 and not any(r['created'] for r in resumed['results'])
    assert len(core.list_leads()) == 2 and len(core.list_tasks()) == 2
    assert all(len(core.list_lead_observations(lead['id'])) == 1 for lead in core.list_leads())
    assert core.verify_audit()['valid']


@pytest.mark.parametrize('mode', ['revoked', 'manual', 'expired'])
def test_resume_after_policy_loss_has_zero_reads(mode):
    source(manual=mode == 'manual', paths=['/listing'])
    core.create_fixture_run('restart_denied', 'fixture', [LISTING_URL])
    core.update_fixture_run('restart_denied', 0, 'PAUSED')
    if mode == 'revoked':
        with core.founder_session(TOKEN):
            core.update_source_policy('fixture', 'REVOKED', {},
                                      'Founder revoked fixture access', actor='founder')
    elif mode == 'expired':
        with sqlite3.connect(core.DB_PATH) as db:
            db.execute("UPDATE source_access_policy SET review_expires_ts='2020-01-01T00:00:00+00:00'")
    fresh_transport = FixtureTransport({LISTING_URL: CARDS})
    result = resume_fixture_pilot(run_id='restart_denied', transport=fresh_transport)
    assert result['status'] == 'BLOCKED' and fresh_transport.reads == []
    assert not core.list_leads()
    assert core.verify_audit()['valid']


def test_genuine_historical_intake_preserves_ten_sources_and_unknown_status():
    assert integration.HISTORICAL_FILE.is_file()
    with pytest.raises(ValueError, match='founder'):
        import_historical_candidates(run_id='history_denied', founder_token='wrong')
    first = import_historical_candidates(run_id='history_first', founder_token=TOKEN)
    assert len(first['results']) == 10 and all(row['created'] for row in first['results'])
    leads = core.list_leads()
    assert len(leads) == 10 and len(core.list_tasks()) == 10
    assert all(lead['source'] == 'web_research_2026-10-10_unverified' and
               lead['status'] == 'DISCOVERED' and not lead['buyer_verified']
               for lead in leads)
    assert any(lead['budget_min'] == 25000 for lead in leads)
    assert all(obs['availability_status'] == 'UNKNOWN' and
               obs['verification_status'] == 'UNVERIFIED' and
               obs['content_evidence_ref'].startswith('historical-file:sha256:')
               for lead in leads for obs in core.list_lead_observations(lead['id']))
    repeat = import_historical_candidates(run_id='history_repeat', founder_token=TOKEN)
    assert len(repeat['results']) == 10 and not any(r['created'] for r in repeat['results'])
    assert len(core.list_leads()) == 10 and len(core.list_tasks()) == 10
    assert core.verify_audit()['valid']


def test_missing_or_corrupt_genuine_historical_file_fails_loudly(tmp_path, monkeypatch):
    missing = tmp_path / 'lead_candidates_2026-10-10.json'
    monkeypatch.setattr(integration, 'HISTORICAL_FILE', missing)
    with pytest.raises(FileNotFoundError):
        import_historical_candidates(run_id='missing_history', founder_token=TOKEN)
    missing.write_text('{broken json', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        import_historical_candidates(run_id='corrupt_history', founder_token=TOKEN)
    assert not core.list_leads()
