import os
from pathlib import Path
import tempfile
import pytest
from fastapi.testclient import TestClient
from acqsys import core,agents
from acqsys.app import app

@pytest.fixture(autouse=True)
def db(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DB_PATH',tmp_path/'test.db')
    core.init_db()


def candidate(**kw):
    d={'title':'Build private RAG and agentic workflow automation with FastAPI',
       'description':'Need a detailed RAG implementation with embeddings, evaluation, deployment, authorization and monitoring. Work begins with discovery and testable outcomes.',
       'source_url':'https://example.org/project/123?utm_source=x','source':'manual', 'demand_type':'EXPLICIT_PROJECT'}
    d.update(kw)
    return d


def test_ingest_logs_and_dedup():
    a=core.add_lead(candidate())
    b=core.add_lead(candidate(source_url='https://example.org/project/123'))
    assert a['created'] and not b['created'] and a['id']==b['id']
    assert core.summary()['leads']==1
    assert [e['action'] for e in core.list_events()] == ['LEAD_DUPLICATE','LEAD_DISCOVERED']


def test_unverified_cannot_qualify():
    lead=core.add_lead(candidate())['id']
    core.transition_lead(lead,'VERIFIED')
    with pytest.raises(ValueError,match='buyer must be verified'):
        core.transition_lead(lead,'QUALIFIED')
    core.verify_lead(lead,True,'Checked source and buyer identity')
    core.transition_lead(lead,'QUALIFIED')
    assert core.get_lead(lead)['status']=='QUALIFIED'


def test_no_agent_external_communications():
    lead=core.add_lead(candidate())['id']
    core.transition_lead(lead,'VERIFIED')
    core.verify_lead(lead,True,'Verified company website')
    core.transition_lead(lead,'QUALIFIED')
    with pytest.raises(ValueError,match='founder approval'):
        core.transition_lead(lead,'CONTACTED',actor='proposal_agent')
    assert core.get_lead(lead)['status']=='QUALIFIED'


def test_win_requires_payment():
    lead=core.add_lead(candidate())['id']
    core.transition_lead(lead,'VERIFIED')
    core.verify_lead(lead,True,'Verified buyer')
    for stage in ['QUALIFIED','CONTACTED','REPLIED','DISCOVERY','PROPOSED']:
        core.transition_lead(lead,stage)
    with pytest.raises(ValueError,match='payment reference'):
        core.transition_lead(lead,'WON')
    core.transition_lead(lead,'WON',payment_reference='sandbox_test_payment_123')
    assert core.summary()['paying_clients']==1


def test_hash_chain_tampering_is_detected():
    core.add_lead(candidate())
    core.record_event('observer_agent','EXPERIMENT_NOTED',{'outcome':'failed'})
    assert core.verify_audit()['valid']
    import sqlite3
    with sqlite3.connect(core.DB_PATH) as c:
        c.execute("UPDATE events SET payload='{}' WHERE seq=1")
    assert not core.verify_audit()['valid']


def test_memory_evidence_and_no_agent_verified_memory():
    with pytest.raises(ValueError):core.add_memory('market','FACT','Has budget','','0.8')
    with pytest.raises(ValueError,match='founder'):
        core.add_memory('market','FACT','Has budget','https://example.org',.6,verified=True,actor='agent')
    core.add_memory('market','HYPOTHESIS','May need models','https://example.org',.4)
    assert core.read_memory('market')[0]['kind']=='HYPOTHESIS'


def test_search_separates_demand_types():
    q=core.search_queries()
    assert len(q['EXPLICIT_PROJECT'])>=5
    assert len(q['POTENTIAL_ACCOUNT'])>=3


def test_proposal_does_not_send_or_invent_price():
    lid=core.add_lead(candidate())['id']
    res=agents.evidence_driven_proposal(lid)
    assert 'NOT been sent' in res['result']['draft']
    assert 'No price' in res['result']['draft']
    assert len(core.list_artifacts(lid))==1
    assert any(e['action']=='AGENT_FINISHED' for e in core.list_events())


def test_malformed_source_url():
    with pytest.raises(ValueError):core.add_lead(candidate(source_url='file:///etc/passwd'))


def test_api_roundtrip():
    with TestClient(app) as client:
        assert client.get('/api/health').json()['outbound_sending'] is False
        created=client.post('/api/leads',json=candidate()).json()
        assert created['created']
        assert client.get('/api/dashboard').json()['leads']==1
        assert client.get('/api/audit/verify').json()['valid']
        assert client.get('/api/positioning').status_code==200
        assert client.get('/api/checkpoints/30').status_code==200


def test_brave_key_missing_logged():
    os.environ.pop('BRAVE_API_KEY',None)
    with pytest.raises(ValueError,match='BRAVE_API_KEY'):
        agents.brave_discover()


def test_feed_requires_founder_policy_approval():
    with pytest.raises(ValueError,match='founder'):
        agents.rss_discover('https://example.org/rss')


def test_llm_opt_in_only(monkeypatch):
    monkeypatch.delenv('OLLAMA_MODEL',raising=False)
    lid=core.add_lead(candidate())['id']
    with pytest.raises(ValueError,match='OLLAMA_MODEL'):
        agents.local_llm_research(lid)


def test_checkpoint_small_sample_warning():
    report=core.checkpoint(90)
    assert 'Too little' in report['diagnosis'][0]
    assert report['metrics']['target_clients']==3


def test_supervisor_uses_memory_and_avoids_duplicate_tasks():
    lid=core.add_lead(candidate())['id']
    core.add_memory('business','LESSON','Verify buying intent first','lead review #1',.8)
    first=agents.supervisor_cycle()['result']
    second=agents.supervisor_cycle()['result']
    assert len(first['generated_tasks'])==1
    assert len(second['generated_tasks'])==0
    assert any(x['statement']=='Verify buying intent first' for x in first['memory_context'])
    assert core.list_tasks()[0]['lead_id']==lid


def test_manual_action_audited():
    lid=core.add_lead(candidate())['id']
    event=core.manual_activity('BUYER_OBJECTION','Customer questioned data readiness',lid,'Call note 2026-10-10')
    assert event['payload']['type']=='BUYER_OBJECTION'
    assert core.verify_audit()['valid']


def test_api_denials_logged():
    with TestClient(app) as client:
        r=client.post('/api/leads',json=candidate())
        lid=r.json()['id']
        failed=client.post('/api/leads/'+lid+'/transition',json={'new_status':'WON'})
        assert failed.status_code==400
        assert any(e['action']=='ACTION_DENIED' for e in core.list_events())


def test_offer_matching_and_source_registry():
    lead=core.add_lead(candidate())['id']
    ranked=agents.match_offers(lead)
    assert any(x['id']=='rag_knowledge' for x in ranked)
    with TestClient(app) as client:
        r=client.get('/api/sources').json()
        assert len(r['source_categories']['explicit_marketplace_demand'])>=8
        assert client.get('/api/leads/'+lead+'/offers').status_code==200
        assert client.get('/').status_code==200


# --- CASE-001: manual-only source workflow and daily backup ---

def manual_only_source(sid,domain,category='MANUAL'):
    core.register_source(sid,domain,'Source '+sid,category,actor='founder')
    for state in ('EVALUATING','POLICY_REVIEW','AWAITING_FOUNDER','MANUAL_ONLY'):
        core.transition_source(sid,state,'founder')
    return core.get_source(sid)


def test_case001_manual_intake_accepted():
    manual_only_source('acme','acmejobs.example')
    res=core.ingest_manual_lead('acme',candidate(source_url='https://acmejobs.example/project/77'))
    assert res['created'] and res['score']['score']>0
    lead=core.get_lead(res['lead_id'])
    assert lead['source']=='acme' and lead['status']=='DISCOVERED'
    assert lead['categories'] and lead['score']>0
    assert core.verify_audit()['valid']


def test_case001_duplicate_rejected():
    manual_only_source('acme','acmejobs.example')
    url='https://acmejobs.example/lead/1'
    first=core.ingest_manual_lead('acme',candidate(source_url=url))
    second=core.ingest_manual_lead('acme',candidate(source_url=url))
    assert first['created'] and not second['created']
    assert first['lead_id']==second['lead_id']
    assert core.summary()['leads']==1
    assert any(e['action']=='LEAD_DUPLICATE' for e in core.list_events())


def test_case001_automated_crawl_denied():
    manual_only_source('acme','acmejobs.example')
    for action in core.AUTOMATED_ACTIONS:
        assert core.is_automated_action_allowed('acme',action) is False
    denials=[e for e in core.list_events() if e['action']=='ACTION_DENIED']
    assert len(denials)==len(core.AUTOMATED_ACTIONS)
    assert all(e['target_id']=='acme' for e in denials)
    core.update_source_policy('acme','CONFIRMED',{'browser_navigation':True},evidence='Founder re-read ToS',actor='founder')
    assert core.is_automated_action_allowed('acme','browser_navigation') is False
    core.register_source('open','openjobs.example','Open Jobs','COMMUNITY',actor='founder')
    core.transition_source('open','EVALUATING','founder')
    core.transition_source('open','POLICY_REVIEW','founder')
    core.update_source_policy('open','CONFIRMED',{'public_reading':True,'browser_navigation':True},evidence='Public listings page',actor='founder')
    assert core.is_automated_action_allowed('open','browser_navigation') is True
    assert core.is_automated_action_allowed('open','messaging') is False


def test_case001_secret_redaction():
    import json
    src=core.register_source('gated','gated.example','Gated Portal','RFP_PORTAL',actor='founder')
    assert src['evidence']==core.NOT_COLLECTED and src['reviewed_ts']==core.NOT_COLLECTED
    secret='api_key=sk-live-9f8e7d6c token: ghp_Zzzz999888 password=hunter2 Authorization=Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig'
    updated=core.update_source_policy('gated','CONFIRMED',{'public_reading':True},secret,actor='founder')
    assert core.REDACTED in updated['evidence']
    for fragment in ('sk-live-9f8e7d6c','ghp_Zzzz999888','hunter2','eyJhbGciOiJIUzI1NiJ9'):
        assert fragment not in updated['evidence']
    for e in core.list_events():
        blob=json.dumps(e['payload'])
        for fragment in ('sk-live-9f8e7d6c','ghp_Zzzz999888','hunter2'):
            assert fragment not in blob


def test_case001_audit_correlation():
    manual_only_source('linked','linked.example',category='AGENCY_DIRECTORY')
    core.ingest_manual_lead('linked',candidate(source_url='https://linked.example/work/9'))
    events=core.list_events(limit=200)
    decisions=[e for e in events if e['action']=='FOUNDER_POLICY_DECISION']
    assert len(decisions)==1 and decisions[0]['target_id']=='linked'
    assert decisions[0]['payload']['decision']=='MANUAL_ONLY'
    intake=[e for e in events if e['action']=='MANUAL_LEAD_INTAKE'][0]
    related=[e for e in events if e['correlation_id']==intake['correlation_id']]
    assert {e['action'] for e in related}=={'MANUAL_LEAD_INTAKE','LEAD_DISCOVERED'}
    by_action={e['action']:e for e in related}
    assert by_action['MANUAL_LEAD_INTAKE']['payload']['source_id']=='linked'
    assert by_action['LEAD_DISCOVERED']['payload']['lead']['source']=='linked'
    assert core.verify_audit()['valid']


def test_case001_policy_rereview():
    manual_only_source('rr','recheck.example')
    core.transition_source('rr','POLICY_REVIEW','founder','Annual policy re-review')
    assert core.get_source('rr')['lifecycle_state']=='POLICY_REVIEW'
    core.update_source_policy('rr','CONFIRMED',{'manual_browser_access':True,'human_supplied_lead_processing':True},evidence='Founder re-read terms on 2026-10-10',actor='founder')
    core.transition_source('rr','AWAITING_FOUNDER','founder')
    core.transition_source('rr','MANUAL_ONLY','founder','Remain manual-only')
    src=core.get_source('rr')
    assert src['lifecycle_state']=='MANUAL_ONLY' and src['policy_state']=='CONFIRMED'
    assert src['reviewed_ts'] not in ('',core.NOT_COLLECTED)
    assert src['review_expires_ts'] not in ('',core.NOT_COLLECTED)
    assert core.ingest_manual_lead('rr',candidate(source_url='https://recheck.example/lead/5'))['created']


def test_case001_invalid_transition_denied():
    core.register_source('bad','nope.example','Nope Source','DISCOVERY_INFRA',actor='founder')
    with pytest.raises(ValueError,match='invalid source transition'):
        core.transition_source('bad','ACTIVE','founder')
    assert core.get_source('bad')['lifecycle_state']=='DISCOVERED'
    denials=[e for e in core.list_events() if e['action']=='ACTION_DENIED' and e['target_id']=='bad']
    assert len(denials)==1 and denials[0]['payload']['attempted_state']=='ACTIVE'
    core.transition_source('bad','EVALUATING','founder')
    core.transition_source('bad','POLICY_REVIEW','founder')
    core.transition_source('bad','AWAITING_FOUNDER','founder')
    with pytest.raises(ValueError,match='founder'):
        core.transition_source('bad','ONBOARDING','agent')
    assert core.get_source('bad')['lifecycle_state']=='AWAITING_FOUNDER'
    assert len([e for e in core.list_events() if e['action']=='ACTION_DENIED' and e['target_id']=='bad'])==2


def test_backup_db_snapshot():
    core.add_lead(candidate())
    path=core.backup_db()
    p=Path(path)
    assert p.exists() and p.parent.name=='backups'
    assert p.name.startswith('acquisition_backup_') and p.name.endswith('.db')
    import sqlite3
    with sqlite3.connect(str(p)) as c:
        assert c.execute('SELECT COUNT(*) FROM leads').fetchone()[0]==1
    alt=Path(core.backup_db(dest_dir=str(p.parent/'alt')))
    assert alt.exists() and alt.parent.name=='alt'
    assert core.verify_audit()['valid']
