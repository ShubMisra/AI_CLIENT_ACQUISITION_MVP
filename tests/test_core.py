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
    monkeypatch.setenv('ACQ_ADMIN_TOKEN','test-founder-token')
    core.init_db()
    with core.founder_session('test-founder-token'):
        yield


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
    with pytest.raises(ValueError,match='confirmed independent customer'):
        core.transition_lead(lead,'WON')
    with pytest.raises(ValueError,match='confirmed independent customer'):
        core.transition_lead(lead,'WON',payment_reference='arbitrary-reference')
    customer=core.register_customer_entity('buyer.example','Buyer','Founder checked legal entity',True)
    core.link_lead_customer(lead,customer)
    core.record_commercial_event(lead,'SCOPE_AGREED','Signed scope document')
    core.record_commercial_event(lead,'PAYMENT_RECEIVED','Founder checked bank receipt',100,'USD')
    core.transition_lead(lead,'WON')
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
    with TestClient(app,headers={'X-Admin-Token':'test-founder-token'}) as client:
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
    with pytest.raises(ValueError,match='UNKNOWN_SOURCE'):
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
    core.manual_activity('APPLICATION_SUBMITTED','Founder submitted on platform',lid,'Platform confirmation')
    assert core.summary()['actual_contacts']==1
    assert core.summary()['proposals_sent']==1
    assert core.verify_audit()['valid']


def test_api_denials_logged():
    with TestClient(app,headers={'X-Admin-Token':'test-founder-token'}) as client:
        r=client.post('/api/leads',json=candidate())
        lid=r.json()['id']
        failed=client.post('/api/leads/'+lid+'/transition',json={'new_status':'WON'})
        assert failed.status_code==400
        assert any(e['action']=='ACTION_DENIED' for e in core.list_events())


def test_offer_matching_and_source_registry():
    lead=core.add_lead(candidate())['id']
    ranked=agents.match_offers(lead)
    assert any(x['id']=='rag_knowledge' for x in ranked)
    with TestClient(app,headers={'X-Admin-Token':'test-founder-token'}) as client:
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
    assert core.is_automated_action_allowed('open','browser_navigation') is False
    for state in ('AWAITING_FOUNDER','ONBOARDING','PILOT_READY','PILOT_RUNNING'):
        core.transition_source('open',state,'founder')
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


def test_api_founder_auth_fails_closed_and_ignores_spoofed_actor(monkeypatch):
    with TestClient(app) as client:
        body={**candidate(),'actor':'founder'}
        assert client.get('/api/leads').status_code==403
        assert client.get('/api/audit').status_code==403
        assert client.post('/api/leads',json=body).status_code==403
        assert client.post('/api/leads',json=body,headers={'X-Admin-Token':'wrong'}).status_code==403
        assert core.summary()['leads']==0
        authorized=client.post('/api/leads',json=body,headers={'X-Admin-Token':'test-founder-token'})
        assert authorized.status_code==200
        lid=authorized.json()['id']
        assert client.post(f'/api/leads/{lid}/verify',json={'verified':True,'note':'checked','actor':'founder'}).status_code==403
        assert client.post(f'/api/leads/{lid}/commercial-events',json={'event_type':'APPLICATION_SUBMITTED','evidence_ref':'platform record','actor':'founder'}).status_code==403
        ok=client.post(f'/api/leads/{lid}/commercial-events',json={'event_type':'APPLICATION_SUBMITTED','evidence_ref':'platform record'},headers={'X-Admin-Token':'test-founder-token'})
        assert ok.status_code==200
        assert any(e['action']=='APPLICATION_SUBMITTED' for e in core.list_events())
        assert core.get_lead(lid)['status']=='DISCOVERED'
        assert core.summary()['actual_contacts']==1
        assert core.summary()['proposals_sent']==1
    monkeypatch.delenv('ACQ_ADMIN_TOKEN')
    with TestClient(app) as client:
        assert client.post('/api/leads',json=candidate(),headers={'X-Admin-Token':'test-founder-token'}).status_code==403
    monkeypatch.setenv('ACQ_ADMIN_TOKEN','short')
    with TestClient(app) as client:
        assert client.post('/api/leads',json=candidate(),headers={'X-Admin-Token':'short'}).status_code==403


def test_direct_founder_actor_string_is_not_authority():
    mark=core._FOUNDER_AUTH.set(False)
    try:
        lead=core.add_lead(candidate())['id']
        with pytest.raises(ValueError,match='founder authentication'):
            core.verify_lead(lead,True,'checked',actor='founder')
        with pytest.raises(ValueError,match='founder authentication'):
            core.transition_lead(lead,'VERIFIED',actor='founder')
        with pytest.raises(ValueError,match='founder authentication'):
            core.record_commercial_event(lead,'APPLICATION_SUBMITTED','platform record')
        with pytest.raises(ValueError,match='founder authorization'):
            core.update_source_policy('missing','CONFIRMED',evidence='terms',actor='founder')
    finally:core._FOUNDER_AUTH.reset(mark)


def active_source(source_id='feed',domain='feed.example',action='feed_read',paths=None,rate=60):
    core.register_source(source_id,domain,'Test source','DISCOVERY_INFRA',actor='founder')
    core.transition_source(source_id,'EVALUATING','founder')
    core.transition_source(source_id,'POLICY_REVIEW','founder')
    core.update_source_policy(source_id,'CONFIRMED',
        {action:True,'allowed_paths':paths or ['/'],'rate_limit_per_hour':rate},'Founder reviewed feed terms',actor='founder')
    for state in ('AWAITING_FOUNDER','ONBOARDING','PILOT_READY','PILOT_RUNNING','ACTIVE'):
        core.transition_source(source_id,state,'founder')
    return source_id


def test_policy_port_denies_unapproved_scope_expiry_account_and_rate():
    port=core.CorePolicyPort()
    missing=port.authorize(source_id='missing',action='feed_read',target_url='https://feed.example/rss')
    assert not missing.allowed and missing.reason_code=='UNKNOWN_SOURCE'
    sid=active_source(paths=['/rss'],rate=1)
    denied=port.authorize(source_id=sid,action='feed_read',target_url='https://feed.example/private')
    assert denied.reason_code=='TARGET_OUT_OF_SCOPE'
    assert port.authorize(source_id=sid,action='feed_read',target_url='https://feed.example/rss/%2e%2e/private').reason_code=='TARGET_OUT_OF_SCOPE'
    assert port.authorize(source_id=sid,action='feed_read',target_url='https://feed.example/rss/%252e%252e/private').reason_code=='TARGET_OUT_OF_SCOPE'
    assert port.authorize(source_id=sid,action='application_submission',target_url='https://feed.example/rss').reason_code=='OUTBOUND_PROHIBITED'
    allowed=port.authorize(source_id=sid,action='feed_read',target_url='https://feed.example/rss')
    assert allowed.allowed and allowed.policy_version and allowed.permitted_scope==('https://feed.example/rss',)
    assert port.authorize(source_id=sid,action='feed_read',target_url='https://feed.example/rss').reason_code=='RATE_LIMITED'
    with core.atomic() as c:
        c.execute('UPDATE source_access_policy SET review_expires_ts=? WHERE source_id=?',('2000-01-01T00:00:00+00:00',sid))
    assert port.authorize(source_id=sid,action='feed_read',target_url='https://feed.example/rss').reason_code=='POLICY_EXPIRED'
    core.update_source_policy(sid,'CONFIRMED',{'account_state':'RESTRICTED'},'Founder rechecked terms',actor='founder')
    assert core.get_source(sid)['allowed_paths']==['/rss']
    assert port.authorize(source_id=sid,action='feed_read',target_url='https://feed.example/rss').reason_code=='ACCOUNT_RESTRICTED'
    assert core.verify_audit()['valid']


def test_manual_review_and_suspended_sources_denied():
    manual_only_source('manual','manual.example')
    assert core.policy_check('manual','browser_navigation','https://manual.example/').reason_code=='INACTIVE_SOURCE'
    core.register_source('review','review.example','Review','COMMUNITY',actor='founder')
    core.transition_source('review','EVALUATING','founder')
    core.transition_source('review','POLICY_REVIEW','founder')
    core.update_source_policy('review','CONFIRMED',{'browser_navigation':True},'Founder read terms',actor='founder')
    assert core.policy_check('review','browser_navigation','https://review.example/').reason_code=='INACTIVE_SOURCE'
    sid=active_source('paused','paused.example')
    core.transition_source(sid,'SUSPENDED','founder')
    assert core.policy_check(sid,'feed_read','https://paused.example/').reason_code=='INACTIVE_SOURCE'


def test_redaction_covers_leads_urls_nested_audit_memory_and_errors():
    raw='api_key=sk-live-secret password=hunter2 Bearer abcdefghijk12345'
    lead=core.add_lead(candidate(source_url='https://example.org/project/123?token=URLSECRET&utm_source=x',description=raw))['id']
    assert 'URLSECRET' not in core.get_lead(lead)['source_url']
    assert 'sk-live-secret' not in core.get_lead(lead)['description']
    core.add_memory('business','FACT',raw,'token=MEMSECRET',.5,actor='founder')
    core.manual_activity('RESEARCH_NOTE',raw,lead,'https://example.org/?api_key=EVENTSECRET')
    core.record_event('agent','ERROR',{'nested':[{'password':'PLAINSECRET','text':'token=DEEPSECRET'}]})
    try:
        agents.audited_agent('test','FAIL',lambda _: (_ for _ in ()).throw(ValueError('token=ERRORSECRET')))
    except ValueError:pass
    blob=str(core.list_events(1000))+str(core.read_memory())+str(core.get_lead(lead))
    for secret in ('URLSECRET','sk-live-secret','hunter2','MEMSECRET','EVENTSECRET','PLAINSECRET','DEEPSECRET','ERRORSECRET'):
        assert secret not in blob
    with pytest.raises(ValueError):core.add_lead(candidate(source_url='https://user:pass@example.org/project/1'))
    assert core.verify_audit()['valid']


def test_two_paid_leads_same_customer_count_once_and_refund_excludes():
    customer=core.register_customer_entity('one-buyer.example','One Buyer','Candidate identity',False)
    assert core.summary()['paying_clients']==0
    assert customer==core.register_customer_entity('one-buyer.example','One Buyer','Legal entity checked',True)
    assert customer==core.register_customer_entity('one-buyer.example','One Buyer','Same entity',True)
    leads=[]
    for n in (1,2):
        lead=core.add_lead(candidate(source_url=f'https://example.org/project/{n}'))['id']
        core.link_lead_customer(lead,customer)
        core.record_commercial_event(lead,'SCOPE_AGREED',f'Agreement {n}')
        assert core.summary()['paying_clients']==(1 if n==2 else 0)
        core.record_commercial_event(lead,'PAYMENT_RECEIVED',f'Bank receipt {n}',100,'USD')
        leads.append(lead)
    assert core.summary()['paying_clients']==1
    core.record_commercial_event(leads[0],'PAYMENT_REFUNDED','Partial refund checked',50,'USD')
    assert core.summary()['paying_clients']==1
    with pytest.raises(ValueError,match='exceeds received'):
        core.record_commercial_event(leads[0],'PAYMENT_REFUNDED','Impossible refund',1000,'USD')
    core.record_commercial_event(leads[1],'PAYMENT_REFUNDED','Refund checked',100,'USD')
    assert core.summary()['paying_clients']==1
    core.record_commercial_event(leads[0],'PAYMENT_REFUNDED','Final refund checked',50,'USD')
    assert core.summary()['paying_clients']==0


def test_live_connector_checks_policy_before_network(monkeypatch):
    monkeypatch.setenv('BRAVE_API_KEY','fixture-only-not-a-real-key')
    monkeypatch.setenv('FREELANCER_OAUTH_TOKEN','fixture-only-not-a-real-token')
    calls=[]
    def fake_get(url,**kwargs):
        calls.append(url)
        if 'freelancer.com' in url:
            return b'{"result":{"projects":[{"id":987,"title":"NLP contract","description":"Need text classifier","budget":{"minimum":500}}]}}'
        return b'{"web":{"results":[{"url":"https://example.org/new-job","title":"ML project","description":"Short scope"}]}}'
    monkeypatch.setattr(agents,'_guarded_https_get',fake_get)
    with pytest.raises(ValueError,match='UNKNOWN_SOURCE'):
        agents.brave_discover(queries=['ML project'])
    with pytest.raises(ValueError,match='UNKNOWN_SOURCE'):
        agents.freelancer_discover('ML project')
    assert calls==[]
    active_source('brave_search_api','api.search.brave.com','official_api',['/res/v1/web/search'])
    result=agents.brave_discover(queries=['ML project'])['result']
    assert len(result)==1 and result[0]['created']
    active_source('freelancer_official_api','www.freelancer.com','official_api',['/api/projects/0.1/projects/active'])
    freelancer=agents.freelancer_discover('NLP contract')['result']
    assert len(freelancer)==1 and freelancer[0]['created']
    assert len(calls)==2 and calls[0].startswith('https://api.search.brave.com/res/v1/web/search?q=')
    assert calls[1].startswith('https://www.freelancer.com/api/projects/0.1/projects/active/?query=')
    assert core.verify_audit()['valid']


def test_rss_uses_registered_policy_not_caller_approved_boolean(monkeypatch):
    url='https://feed.example/rss'
    called=[]
    monkeypatch.setattr(agents,'_guarded_https_get',lambda target:(called.append(target) or b'<rss><channel><item><title>ML contract</title><link>https://example.org/lead/rss</link><description>Need a model</description></item></channel></rss>'))
    with pytest.raises(ValueError,match='UNKNOWN_SOURCE'):
        agents.rss_discover(url,source_name='feed',approved=True)
    assert called==[]
    active_source('feed','feed.example','feed_read',['/rss'])
    result=agents.rss_discover(url,source_name='feed',approved=False)['result']
    assert len(result)==1 and result[0]['created']
    assert called==[url]


def test_rss_pins_checked_ip_and_keeps_original_tls_hostname(monkeypatch):
    original='https://feed.example/rss'
    checked=[]
    monkeypatch.setattr(agents.socket,'getaddrinfo',lambda host,*a,**kw:(checked.append(host) or [(None,None,None,None,('93.184.216.34',443))]))
    class Sock:pass
    connected=[]
    monkeypatch.setattr(agents.socket,'create_connection',lambda addr,timeout:(connected.append(addr) or Sock()))
    class Context:
        def wrap_socket(self,sock,server_hostname):
            assert server_hostname=='feed.example'
            return sock
    monkeypatch.setattr(agents.ssl,'create_default_context',lambda:Context())
    class FakeHTTPS:
        def __init__(self,host,port,timeout,context):
            self.host,self.port,self.timeout,self._context=host,port,timeout,context
        def request(self,method,target,headers):
            self.connect()
            assert (method,target)==('GET','/rss')
        def getresponse(self):
            class Response:
                status=200
                def read(self,n):return b'<rss/>'
            return Response()
        def close(self):pass
    monkeypatch.setattr(agents.http.client,'HTTPSConnection',FakeHTTPS)
    assert agents._guarded_https_get(original)==b'<rss/>'
    assert checked==['feed.example']
    assert connected==[('93.184.216.34',443)]


def test_legacy_database_migrates_without_changing_audit(tmp_path,monkeypatch):
    import sqlite3,hashlib
    legacy=tmp_path/'legacy.db'
    monkeypatch.setattr(core,'DB_PATH',legacy)
    with sqlite3.connect(legacy) as c:
        c.execute('''CREATE TABLE leads (id TEXT PRIMARY KEY,source TEXT NOT NULL,source_url TEXT NOT NULL UNIQUE,title TEXT NOT NULL,
          description TEXT NOT NULL,demand_type TEXT NOT NULL,company TEXT,currency TEXT,budget_min REAL,budget_max REAL,
          buyer_verified INTEGER NOT NULL DEFAULT 0,verification_note TEXT,status TEXT NOT NULL DEFAULT 'DISCOVERED',
          score INTEGER NOT NULL DEFAULT 0,categories TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
          first_paid_at TEXT,founder_note TEXT)''')
        c.execute('''CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,at TEXT NOT NULL,
          actor TEXT NOT NULL,action TEXT NOT NULL,target_type TEXT,target_id TEXT,correlation_id TEXT,payload TEXT NOT NULL,
          prev_hash TEXT NOT NULL,hash TEXT NOT NULL)''')
        c.execute('''CREATE TABLE sources_lifecycle (id INTEGER PRIMARY KEY AUTOINCREMENT,source_id TEXT UNIQUE NOT NULL,
          domain TEXT NOT NULL,name TEXT NOT NULL,category TEXT NOT NULL,lifecycle_state TEXT NOT NULL DEFAULT 'DISCOVERED',
          created_ts TEXT NOT NULL,updated_ts TEXT NOT NULL,notes TEXT DEFAULT '')''')
        c.execute('''CREATE TABLE source_access_policy (id INTEGER PRIMARY KEY AUTOINCREMENT,source_id TEXT NOT NULL,
          policy_state TEXT NOT NULL DEFAULT 'UNKNOWN',public_reading INTEGER DEFAULT 0,official_api INTEGER DEFAULT 0,
          browser_navigation INTEGER DEFAULT 0,authenticated_extraction INTEGER DEFAULT 0,messaging INTEGER DEFAULT 0,
          application_submission INTEGER DEFAULT 0,manual_browser_access INTEGER DEFAULT 1,human_supplied_lead_processing INTEGER DEFAULT 1,
          rate_limit_notes TEXT DEFAULT '',evidence TEXT DEFAULT '',reviewed_ts TEXT DEFAULT '',review_expires_ts TEXT DEFAULT '')''')
        c.execute("INSERT INTO leads(id,source,source_url,title,description,demand_type,created_at,updated_at) VALUES('old','manual','https://example.org/old','Old lead','Historical','EXPLICIT_PROJECT','2026-10-01','2026-10-01')")
        event={'event_id':'old-event','at':'2026-10-01','actor':'founder','action':'LEAD_DISCOVERED','target_type':'lead',
               'target_id':'old','correlation_id':'old-run','payload':{}}
        digest=hashlib.sha256(('GENESIS|'+core.dumps(event)).encode()).hexdigest()
        c.execute('INSERT INTO events(event_id,at,actor,action,target_type,target_id,correlation_id,payload,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  ('old-event','2026-10-01','founder','LEAD_DISCOVERED','lead','old','old-run','{}','GENESIS',digest))
    core.init_db()
    with sqlite3.connect(legacy) as c:
        policy_columns={r[1] for r in c.execute('PRAGMA table_info(source_access_policy)')}
    assert {'feed_read','policy_version','allowed_paths','account_state','rate_limit_per_hour'}<=policy_columns
    assert core.get_lead('old')['title']=='Old lead'
    assert core.verify_audit()['valid'] and core.verify_audit()['events_checked']==1
    assert core.summary()['paying_clients']==0


def test_source_policy_api_requires_auth_and_can_activate():
    body={'source_id':'api-source','domain':'api.example','name':'API source','category':'DISCOVERY_INFRA'}
    with TestClient(app) as client:
        assert client.post('/api/source-policies',json=body).status_code==403
        headers={'X-Admin-Token':'test-founder-token'}
        assert client.post('/api/source-policies',json=body,headers=headers).status_code==200
        assert client.post('/api/source-policies/api-source/policy',json={'policy_state':'CONFIRMED','permissions':{'official_api':True},'evidence':'Founder reviewed terms'},headers=headers).status_code==200
        for state in ('EVALUATING','POLICY_REVIEW','AWAITING_FOUNDER','ONBOARDING','PILOT_READY','PILOT_RUNNING','ACTIVE'):
            assert client.post('/api/source-policies/api-source/transition',json={'new_state':state},headers=headers).status_code==200
    assert core.policy_check('api-source','official_api','https://api.example/').allowed


def test_authenticated_commercial_api_records_scope_and_received_funds():
    headers={'X-Admin-Token':'test-founder-token'}
    with TestClient(app,headers=headers) as client:
        lead=client.post('/api/leads',json=candidate()).json()['id']
        customer=client.post('/api/customers',json={'canonical_key':'commercial.example','display_name':'Commercial Buyer',
            'evidence_ref':'Founder checked customer registry','independent_verified':True}).json()['id']
        assert client.post(f'/api/leads/{lead}/customer/{customer}').status_code==200
        assert client.post(f'/api/leads/{lead}/commercial-events',json={'event_type':'PAYMENT_RECEIVED',
            'evidence_ref':'Bank receipt','amount':200,'currency':'USD'}).status_code==400
        assert client.post(f'/api/leads/{lead}/commercial-events',json={'event_type':'SCOPE_AGREED',
            'evidence_ref':'Signed scope'}).status_code==200
        assert client.post(f'/api/leads/{lead}/commercial-events',json={'event_type':'PAYMENT_RECEIVED',
            'evidence_ref':'Founder checked bank receipt','amount':200,'currency':'USD'}).status_code==200
        assert client.get('/api/dashboard').json()['paying_clients']==1
        assert client.get('/api/audit/verify').json()['valid']
