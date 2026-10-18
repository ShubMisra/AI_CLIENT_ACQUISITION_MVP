"""AI Client Acquisition: local-first lead intelligence, durable audit, memory and decisions.

No outbound contact automation. All published claims and outbound actions require founder approval.
SQLite audit uses a hash chain: tamper-evident against accidental modification, NOT tamper-proof
against privileged database replacement. Back up off-host for meaningful tamper resistance.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

DB_PATH = Path(os.getenv('ACQ_DB_PATH', str(Path(__file__).parent.parent / 'data' / 'acquisition.db')))
WRITE_LOCK = threading.RLock()
GENESIS = 'GENESIS'
STAGES = ('DISCOVERED','VERIFIED','QUALIFIED','PROPOSAL_DRAFTED','CONTACTED','REPLIED','DISCOVERY','PROPOSED','NEGOTIATING','WON','LOST','REJECTED')
LIFECYCLE = {
    'DISCOVERED': {'VERIFIED','REJECTED'},
    'VERIFIED': {'QUALIFIED','REJECTED'},
    'QUALIFIED': {'PROPOSAL_DRAFTED','CONTACTED','REJECTED'},
    'PROPOSAL_DRAFTED': {'CONTACTED','REJECTED'},
    'CONTACTED': {'REPLIED','REJECTED','LOST'},
    'REPLIED': {'DISCOVERY','LOST','REJECTED'},
    'DISCOVERY': {'PROPOSED','LOST','REJECTED'},
    'PROPOSED': {'NEGOTIATING','WON','LOST'},
    'NEGOTIATING': {'WON','LOST'},
    'WON': set(), 'LOST': set(), 'REJECTED': set(),
}
# Step before source evidence is captured; we cannot infer that a search result is an active job.
LABELS = ['ML','NLP','COMPUTER_VISION','GENAI_RAG','AGENTIC_AI','LLM_ENGINEERING','DATA_MLOPS','ANALYTICS','OTHER']
KEYWORDS = {
 'ML': ['machine learning','prediction','classification','fraud','forecasting','anomaly detection','xgboost','scikit-learn'],
 'NLP': ['nlp','text classification','entity extraction','sentiment','spacy'],
 'COMPUTER_VISION': ['computer vision','object detection','yolo','image classification','ocr','defect detection'],
 'GENAI_RAG': ['rag','retrieval augmented','vector database','embeddings','semantic search','knowledge base','chatbot'],
 'AGENTIC_AI': ['agentic','ai agent','workflow automation','langgraph','multi-agent','tool calling'],
 'LLM_ENGINEERING': ['fine-tuning','finetuning','llm inference','vllm','quantization','lora','model serving'],
 'DATA_MLOPS': ['mlops','data pipeline','airflow','spark','dbt','feature store','mlflow','databricks'],
 'ANALYTICS': ['business intelligence','dashboard','shap','analytics','ab test','data science'],
}
# Two distinct kinds of intelligence: actual posted demands vs companies for further research.
DEMAND_TYPES = ('EXPLICIT_PROJECT','POTENTIAL_ACCOUNT')

# CASE-001: source lifecycle governance. Automated source access requires a founder-confirmed policy;
# MANUAL_ONLY sources accept founder-supplied leads only.
SOURCE_CATEGORIES=('MARKETPLACE','AGENCY_DIRECTORY','RFP_PORTAL','COMMUNITY','DISCOVERY_INFRA','MANUAL')
SOURCE_LIFECYCLE_STATES=('DISCOVERED','EVALUATING','POLICY_REVIEW','AWAITING_FOUNDER','ONBOARDING','PILOT_READY','PILOT_RUNNING','ACTIVE','MANUAL_ONLY','REJECTED','BLOCKED','SUSPENDED','RETIRED')
SOURCE_LIFECYCLE_TRANSITIONS={
    'DISCOVERED':{'EVALUATING','REJECTED'},
    'EVALUATING':{'POLICY_REVIEW','REJECTED'},
    'POLICY_REVIEW':{'AWAITING_FOUNDER','REJECTED'},
    'AWAITING_FOUNDER':{'ONBOARDING','MANUAL_ONLY','REJECTED'},
    'ONBOARDING':{'PILOT_READY','BLOCKED','REJECTED'},
    'PILOT_READY':{'PILOT_RUNNING','BLOCKED','SUSPENDED'},
    'PILOT_RUNNING':{'ACTIVE','BLOCKED','SUSPENDED'},
    'ACTIVE':{'SUSPENDED','RETIRED'},
    'MANUAL_ONLY':{'POLICY_REVIEW','RETIRED'},  # manual-only sources can be re-reviewed
    'BLOCKED':{'POLICY_REVIEW','RETIRED'},
    'SUSPENDED':{'POLICY_REVIEW','RETIRED'},
    'RETIRED':set(),
}
ACCESS_POLICY_STATES=('UNKNOWN','RESEARCHING','AWAITING_REVIEW','CONFIRMED','UNCLEAR','PROHIBITED','EXPIRED','REVOKED')
PERMISSION_KEYS=('public_reading','official_api','feed_read','browser_navigation','authenticated_extraction','messaging','application_submission','manual_browser_access','human_supplied_lead_processing')
AUTOMATED_ACTIONS=('official_api','feed_read','browser_navigation','authenticated_extraction','messaging','application_submission')
REDACTED='[REDACTED]'
NOT_COLLECTED='[NOT_COLLECTED]'
_SECRET_RE=re.compile(r"(?i)(?:\b|_)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|authorization|auth|credential[s]?|key)\s*([:=])\s*(\"[^\"]*\"|'[^']*'|[^\s,;&]+)")
_BEARER_RE=re.compile(r'(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]{8,}')
_URL_USERINFO_RE=re.compile(r'(?i)(https?://)[^\s/@]+@')
_SENSITIVE_URL_KEYS=('token','secret','password','passwd','pwd','key','credential','auth','signature','sig','session','cookie','code')
_FOUNDER_AUTH=ContextVar('founder_authenticated',default=False)
_AUDIT_CORRELATION=ContextVar('audit_correlation',default=None)


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason_code: str
    policy_version: str | None = None
    expires_at: str | None = None
    permitted_scope: tuple[str, ...] = ()


class PolicyPort(Protocol):
    def authorize(self, *, source_id: str, action: str, target_url: str) -> AccessDecision: ...


class CorePolicyPort:
    def authorize(self, *, source_id: str, action: str, target_url: str) -> AccessDecision:
        return policy_check(source_id,action,target_url)


@contextmanager
def audit_correlation(correlation_id):
    """Bind one safe run identifier to all core and policy events in this context."""
    value=str(correlation_id)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value):
        raise ValueError('invalid audit correlation id')
    mark=_AUDIT_CORRELATION.set(value)
    try:yield
    finally:_AUDIT_CORRELATION.reset(mark)


@contextmanager
def founder_session(token):
    configured=os.getenv('ACQ_ADMIN_TOKEN')
    if not configured or len(configured)<16 or not token or not hmac.compare_digest(str(token),configured):
        raise ValueError('founder authentication required')
    mark=_FOUNDER_AUTH.set(True)
    try:yield
    finally:_FOUNDER_AUTH.reset(mark)


def require_founder():
    if not _FOUNDER_AUTH.get():raise ValueError('founder authentication required')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False, default=str)


def normalize_url(url):
    s = urlsplit(url.strip())
    if s.scheme not in {'https','http'} or not s.netloc or s.username or s.password or not s.hostname:
        raise ValueError('Source URL must be an HTTP(S) URL')
    path = s.path.rstrip('/') or '/'
    keep = [(k,v) for k,v in parse_qsl(s.query, keep_blank_values=True)
            if not k.lower().startswith(('utm_','fbclid','gclid')) and not _sensitive_url_key(k)]
    return urlunsplit((s.scheme.lower(),s.netloc.lower(),path,urlencode(sorted(keep)),''))


def _sensitive_url_key(key):
    return any(word in key.lower() for word in _SENSITIVE_URL_KEYS)


def _redact(text):
    """Redact common credential shapes; avoid putting arbitrary private text in audit payloads."""
    t=str(text or '')
    t=_URL_USERINFO_RE.sub(lambda m:m.group(1)+REDACTED+'@',t)
    t=_BEARER_RE.sub(lambda m:m.group(1)+' '+REDACTED,t)
    return _SECRET_RE.sub(lambda m:m.group(1)+m.group(2)+REDACTED,t)


def redact(value):
    if isinstance(value,str):return _redact(value)
    if isinstance(value,dict):
        return {str(k):(REDACTED if _sensitive_field_key(k) else redact(v)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [redact(v) for v in value]
    return value


def _sensitive_field_key(key):
    key=str(key).lower().replace('-','_')
    return key in {'password','passwd','pwd','secret','token','api_key','access_key','secret_key',
                   'authorization','auth','credential','credentials','cookie','cookies','session_cookie',
                   'mfa_code','otp','client_secret'} or key.endswith(('_token','_password','_secret'))


def classify(text):
    t=text.lower()
    scores={k:sum(1 for term in words if term in t) for k,words in KEYWORDS.items()}
    labels=[k for k,v in scores.items() if v>0]
    return labels or ['OTHER']


def score_lead(lead):
    """Evidence-driven ranking; missing evidence cannot create a high rank."""
    text=((lead.get('title') or '')+' '+(lead.get('description') or '')).lower()
    categories=classify(text)
    budget=lead.get('budget_min')
    dtype=lead.get('demand_type')
    evidence=bool(lead.get('source_url'))
    desc_len=len((lead.get('description') or '').strip())
    # Manual input is a candidate only; source URL is necessary but not a verified buyer.
    score=0
    reasons=[]
    if evidence: score+=10;reasons.append('source URL provided, not independently verified')
    if dtype=='EXPLICIT_PROJECT': score+=20;reasons.append('explicit-project claim; requires verification')
    else: score+=5;reasons.append('potential account; no confirmed intent to purchase')
    if any(x in categories for x in ('ML','NLP','COMPUTER_VISION','GENAI_RAG','AGENTIC_AI','LLM_ENGINEERING','DATA_MLOPS')):
        score+=20; reasons.append('relevant engineering terms')
    if desc_len>=120:score+=10;reasons.append('substantive description')
    if budget is not None:
        score += 10 if budget >= 300 else 3
        reasons.append('stated budget; not independently confirmed')
    if lead.get('buyer_verified'):
        score+=20; reasons.append('buyer manually verified')
    if lead.get('status') in ('QUALIFIED','PROPOSAL_DRAFTED','CONTACTED','REPLIED','DISCOVERY','PROPOSED','NEGOTIATING','WON'):
        score+=10;reasons.append('qualified in workflow')
    warnings=[]
    if budget is not None and budget<=100:
        score-=12
        warnings.append('Very low stated budget; validate time and scope before applying')
    if budget is not None and 100 < budget <= 1000 and len(categories)>=3:
        score-=8
        warnings.append('Multiple technical domains at a modest fixed budget; investigate under-scoping')
    if budget is not None and budget>=15000:
        warnings.append('Potentially substantial scope; check founder capacity and consider paid discovery or partners')
    if dtype=='POTENTIAL_ACCOUNT':
        warnings.append('Company research signal only; no verified outsourcing intent')
    confidence='low' if not lead.get('buyer_verified') else ('medium' if dtype=='POTENTIAL_ACCOUNT' else 'higher')
    return {'score':max(0,min(score,100)),'categories':categories,'confidence':confidence,'reasons':reasons,'risk_flags':warnings,
            'gate':'VERIFY_BEFORE_OUTREACH' if not lead.get('buyer_verified') else 'FOUNDER_APPROVAL_REQUIRED'}


def _con():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(str(DB_PATH),timeout=20,check_same_thread=False)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=20000')
    return c


def init_db():
    with WRITE_LOCK, _con() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY, source TEXT NOT NULL,source_url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL, description TEXT NOT NULL, demand_type TEXT NOT NULL,
            company TEXT, currency TEXT, budget_min REAL, budget_max REAL,
            buyer_verified INTEGER NOT NULL DEFAULT 0, verification_note TEXT,
            status TEXT NOT NULL DEFAULT 'DISCOVERED',score INTEGER NOT NULL DEFAULT 0,
            categories TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            first_paid_at TEXT,founder_note TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,
            at TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,
            target_type TEXT,target_id TEXT,correlation_id TEXT,payload TEXT NOT NULL,
            prev_hash TEXT NOT NULL,hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memory (
            id TEXT PRIMARY KEY, scope TEXT NOT NULL,kind TEXT NOT NULL,
            statement TEXT NOT NULL,source TEXT NOT NULL,confidence REAL NOT NULL,
            verified INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,lead_id TEXT,title TEXT NOT NULL,owner TEXT NOT NULL,
            status TEXT NOT NULL,due_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,lead_id TEXT NOT NULL,kind TEXT NOT NULL,
            content TEXT NOT NULL,created_at TEXT NOT NULL,
            FOREIGN KEY(lead_id) REFERENCES leads(id)
        );
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, method TEXT NOT NULL,
            enabled INTEGER NOT NULL,access_status TEXT NOT NULL,notes TEXT
        );
        CREATE TABLE IF NOT EXISTS sources_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT UNIQUE NOT NULL,
            domain TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            lifecycle_state TEXT NOT NULL DEFAULT 'DISCOVERED',
            created_ts TEXT NOT NULL,
            updated_ts TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_access_policy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL REFERENCES sources_lifecycle(source_id),
            policy_state TEXT NOT NULL DEFAULT 'UNKNOWN',
            public_reading INTEGER DEFAULT 0,
            official_api INTEGER DEFAULT 0,
            browser_navigation INTEGER DEFAULT 0,
            authenticated_extraction INTEGER DEFAULT 0,
            messaging INTEGER DEFAULT 0,
            application_submission INTEGER DEFAULT 0,
            manual_browser_access INTEGER DEFAULT 1,
            human_supplied_lead_processing INTEGER DEFAULT 1,
            rate_limit_notes TEXT DEFAULT '',
            evidence TEXT DEFAULT '',
            reviewed_ts TEXT DEFAULT '',
            review_expires_ts TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_rate_usage (
            source_id TEXT NOT NULL, hour_start TEXT NOT NULL, used INTEGER NOT NULL,
            PRIMARY KEY(source_id,hour_start)
        );
        CREATE TABLE IF NOT EXISTS customer_entities (
            id TEXT PRIMARY KEY, canonical_key TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
            independent_verified INTEGER NOT NULL DEFAULT 0, evidence_ref TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS commercial_events (
            id TEXT PRIMARY KEY, lead_id TEXT NOT NULL REFERENCES leads(id),
            customer_id TEXT REFERENCES customer_entities(id), event_type TEXT NOT NULL,
            evidence_ref TEXT NOT NULL, amount REAL, currency TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lead_observations (
            id TEXT PRIMARY KEY, lead_id TEXT NOT NULL REFERENCES leads(id),
            run_id TEXT NOT NULL, source_id TEXT NOT NULL,
            content_evidence_ref TEXT NOT NULL, access_evidence_ref TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
            availability_status TEXT NOT NULL DEFAULT 'UNKNOWN', observed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fixture_collection_runs (
            run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, urls TEXT NOT NULL,
            cursor INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'READY',
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_observations_lead ON lead_observations(lead_id);
        CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_events_target ON events(target_type,target_id);
        CREATE INDEX IF NOT EXISTS idx_sources_lifecycle_state ON sources_lifecycle(lifecycle_state);
        CREATE INDEX IF NOT EXISTS idx_commercial_lead ON commercial_events(lead_id,event_type);
        ''')
        columns={r['name'] for r in c.execute('PRAGMA table_info(source_access_policy)')}
        for name,ddl in {
            'feed_read':'INTEGER DEFAULT 0',
            'policy_version':'INTEGER NOT NULL DEFAULT 0',
            'allowed_paths':"TEXT NOT NULL DEFAULT '[\"/\"]'",
            'account_state':"TEXT NOT NULL DEFAULT 'UNRESTRICTED'",
            'rate_limit_per_hour':'INTEGER NOT NULL DEFAULT 60',
        }.items():
            if name not in columns:c.execute(f'ALTER TABLE source_access_policy ADD COLUMN {name} {ddl}')
        lead_columns={r['name'] for r in c.execute('PRAGMA table_info(leads)')}
        if 'customer_id' not in lead_columns:c.execute('ALTER TABLE leads ADD COLUMN customer_id TEXT REFERENCES customer_entities(id)')
    return str(DB_PATH)


@contextmanager
def atomic():
    init_db()
    with WRITE_LOCK:
        c=_con()
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()


def _event(c, actor, action, target_type='', target_id='', payload=None, correlation_id=None):
    payload = redact(payload or {})
    tail=c.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
    prev=tail['hash'] if tail else GENESIS
    data={'event_id':str(uuid.uuid4()),'at':now(),'actor':_redact(actor),'action':_redact(action),
          'target_type':_redact(target_type),'target_id':_redact(target_id),'correlation_id':_redact(correlation_id or _AUDIT_CORRELATION.get() or str(uuid.uuid4())),
          'payload':payload}
    digest=hashlib.sha256((prev+'|'+dumps(data)).encode('utf-8')).hexdigest()
    c.execute('INSERT INTO events(event_id,at,actor,action,target_type,target_id,correlation_id,payload,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?,?,?)',
              (data['event_id'],data['at'],data['actor'],data['action'],data['target_type'],data['target_id'],data['correlation_id'],dumps(payload),prev,digest))
    return {'prev_hash':prev,'hash':digest,**data}


def record_event(actor,action,payload=None,target_type='',target_id='',correlation_id=None):
    with atomic() as c:
        return _event(c,actor,action,target_type,target_id,payload,correlation_id)


def verify_audit():
    init_db()
    with _con() as c:
        rows=c.execute('SELECT * FROM events ORDER BY seq').fetchall()
    prev=GENESIS
    for row in rows:
        x=dict(row)
        data={k:x[k] for k in ('event_id','at','actor','action','target_type','target_id','correlation_id')}
        data['payload']=json.loads(x['payload'])
        expected=hashlib.sha256((prev+'|'+dumps(data)).encode()).hexdigest()
        if prev!=x['prev_hash'] or expected!=x['hash']:
            return {'valid':False,'events_checked':x['seq'],'error':'audit chain mismatch'}
        prev=x['hash']
    return {'valid':True,'events_checked':len(rows),'last_hash':prev,'warning':'Hash chain is tamper-evident but cannot prevent privileged database replacement.'}


def _row_dict(row):
    d=dict(row)
    d['categories']=json.loads(d['categories'])
    d['buyer_verified']=bool(d['buyer_verified'])
    return d


def add_lead(item,actor='discovery_agent', correlation_id=None):
    """Every ingestion attempt, including duplicates, is auditable."""
    url=normalize_url(item['source_url'])
    title=_redact((item.get('title') or '').strip())
    if not title:raise ValueError('title required')
    demand=item.get('demand_type','EXPLICIT_PROJECT')
    if demand not in DEMAND_TYPES:raise ValueError('invalid demand_type')
    lead_id=str(uuid.uuid4())
    ts=now()
    inp=redact({k:item.get(k) for k in ['source','title','description','demand_type','company','currency','budget_min','budget_max']})
    inp['title']=title
    inp['source_url']=url
    inp['demand_type']=demand
    inp['source']=inp['source'] or 'manual'
    inp['description']=inp['description'] or ''
    with atomic() as c:
        existing=c.execute('SELECT id FROM leads WHERE source_url=?',(url,)).fetchone()
        if existing:
            _event(c,actor,'LEAD_DUPLICATE','lead',existing['id'],{'source_url':url},correlation_id)
            return {'id':existing['id'],'created':False}
        rating=score_lead({**inp,'buyer_verified':False,'status':'DISCOVERED'})
        c.execute('''INSERT INTO leads(id,source,source_url,title,description,demand_type,company,currency,budget_min,budget_max,status,score,categories,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (lead_id,inp['source'],url,title,inp['description'],demand,inp['company'],inp['currency'],inp['budget_min'],inp['budget_max'],'DISCOVERED',rating['score'],dumps(rating['categories']),ts,ts))
        audit_lead={k:v for k,v in inp.items() if k!='description'}
        audit_lead['description_sha256']=hashlib.sha256(inp['description'].encode('utf-8')).hexdigest()
        _event(c,actor,'LEAD_DISCOVERED','lead',lead_id,{'lead':audit_lead,'score':rating},correlation_id)
    return {'id':lead_id,'created':True,'score':rating}


def record_candidate_observation(lead_id, run_id, source_id,
                                 content_evidence_ref, access_evidence_ref):
    """Preserve unverified extraction evidence, including repeat observations."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(run_id)):
        raise ValueError('invalid run id')
    if not content_evidence_ref or not access_evidence_ref:
        raise ValueError('candidate evidence references required')
    observation_id=str(uuid.uuid4())
    with atomic() as c:
        lead=c.execute('SELECT source FROM leads WHERE id=?',(lead_id,)).fetchone()
        if not lead or lead['source']!=source_id:
            raise ValueError('lead/source mismatch')
        content_ref=_redact(str(content_evidence_ref))
        access_ref=_redact(str(access_evidence_ref))
        existing=c.execute('SELECT id FROM lead_observations WHERE lead_id=? AND run_id=? AND content_evidence_ref=?',
                           (lead_id,run_id,content_ref)).fetchone()
        if existing:return existing['id']
        c.execute('INSERT INTO lead_observations VALUES(?,?,?,?,?,?,?,?,?)',
                  (observation_id,lead_id,run_id,source_id,content_ref,access_ref,
                   'UNVERIFIED','UNKNOWN',now()))
        _event(c,'acquisition_agent','CANDIDATE_OBSERVED','lead',lead_id,
               {'observation_id':observation_id,'content_evidence_ref':content_ref,
                'access_evidence_ref':access_ref,'verification_status':'UNVERIFIED',
                'availability_status':'UNKNOWN'},run_id)
    return observation_id


def fixture_run(run_id):
    """Read the central checkpoint for a fixture-only acquisition run."""
    init_db()
    with _con() as c:
        row=c.execute('SELECT * FROM fixture_collection_runs WHERE run_id=?',(run_id,)).fetchone()
    if not row:return None
    result=dict(row)
    result['urls']=json.loads(result['urls'])
    return result


def create_fixture_run(run_id,source_id,urls):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(run_id)) or not source_id or \
       not isinstance(urls,list) or not 1<=len(urls)<=20:
        raise ValueError('invalid fixture run identity')
    if any(not isinstance(url,str) or not url or len(url)>2048 for url in urls):
        raise ValueError('invalid fixture run URLs')
    with atomic() as c:
        existing=c.execute('SELECT * FROM fixture_collection_runs WHERE run_id=?',(run_id,)).fetchone()
        if existing:
            if existing['source_id']!=source_id or json.loads(existing['urls'])!=urls:
                raise ValueError('fixture run identity cannot be rebound')
            return dict(existing)
        c.execute('INSERT INTO fixture_collection_runs(run_id,source_id,urls,cursor,status,updated_at) '
                  'VALUES(?,?,?,?,?,?)',(run_id,source_id,dumps(urls),0,'READY',now()))
        _event(c,'acquisition_agent','FIXTURE_RUN_CREATED','source',source_id,
               {'run_id':run_id,'url_count':len(urls)},run_id)
    return fixture_run(run_id)


def update_fixture_run(run_id,cursor,status):
    if status not in ('RUNNING','BLOCKED','COMPLETED','PAUSED') or type(cursor) is not int:
        raise ValueError('invalid fixture run transition')
    with atomic() as c:
        row=c.execute('SELECT * FROM fixture_collection_runs WHERE run_id=?',(run_id,)).fetchone()
        if not row or cursor<row['cursor'] or cursor>len(json.loads(row['urls'])):
            raise ValueError('invalid fixture run cursor')
        if row['status']=='COMPLETED' and status!='COMPLETED':
            raise ValueError('completed fixture run cannot restart')
        c.execute('UPDATE fixture_collection_runs SET cursor=?,status=?,updated_at=? WHERE run_id=?',
                  (cursor,status,now(),run_id))
        _event(c,'acquisition_agent','FIXTURE_RUN_'+status,'source',row['source_id'],
               {'run_id':run_id,'cursor':cursor},run_id)
    return fixture_run(run_id)


def list_lead_observations(lead_id):
    init_db()
    with _con() as c:
        return [dict(row) for row in c.execute(
            'SELECT * FROM lead_observations WHERE lead_id=? ORDER BY observed_at,id',
            (lead_id,)).fetchall()]


def get_lead(lead_id):
    init_db()
    with _con() as c:
        r=c.execute('SELECT * FROM leads WHERE id=?',(lead_id,)).fetchone()
    return _row_dict(r) if r else None


def list_leads(limit=100,status=None):
    init_db()
    with _con() as c:
        if status:
            rows=c.execute('SELECT * FROM leads WHERE status=? ORDER BY score DESC,created_at DESC LIMIT ?', (status,limit)).fetchall()
        else:
            rows=c.execute('SELECT * FROM leads ORDER BY score DESC,created_at DESC LIMIT ?',(limit,)).fetchall()
    return [_row_dict(x) for x in rows]


def verify_lead(lead_id, verified, note, actor='founder'):
    if actor!='founder':raise ValueError('founder authorization required to verify buyer')
    require_founder()
    if not note.strip():raise ValueError('verification note and basis required')
    note=_redact(note)
    with atomic() as c:
        r=c.execute('SELECT * FROM leads WHERE id=?',(lead_id,)).fetchone()
        if not r:raise ValueError('lead not found')
        buyer=1 if verified else 0
        rating=score_lead({**_row_dict(r),'buyer_verified':bool(buyer)})
        c.execute('UPDATE leads SET buyer_verified=?,verification_note=?,score=?,updated_at=? WHERE id=?',
                  (buyer,note,rating['score'],now(),lead_id))
        _event(c,actor,'BUYER_VERIFIED' if verified else 'BUYER_UNVERIFIED','lead',lead_id,{'note':note,'rating':rating})
    return get_lead(lead_id)


def transition_lead(lead_id,new_status,actor='founder',note='',payment_reference=None):
    new_status=new_status.upper()
    if new_status not in STAGES:raise ValueError('invalid status')
    if actor!='founder':raise ValueError('founder approval required for lead transitions')
    require_founder()
    with atomic() as c:
        r=c.execute('SELECT * FROM leads WHERE id=?',(lead_id,)).fetchone()
        if not r:raise ValueError('lead not found')
        before=r['status']
        if new_status not in LIFECYCLE[before]:
            raise ValueError(f'invalid transition {before} -> {new_status}')
        if new_status in {'QUALIFIED','CONTACTED','PROPOSED','NEGOTIATING','WON'} and not r['buyer_verified']:
            raise ValueError('buyer must be verified before this stage')
        if new_status=='WON' and not _lead_has_confirmed_payment(c,lead_id):
            raise ValueError('confirmed independent customer, agreed scope and received payment required')
        paid_at=now() if new_status=='WON' else r['first_paid_at']
        c.execute('UPDATE leads SET status=?, first_paid_at=?,updated_at=? WHERE id=?', (new_status,paid_at,now(),lead_id))
        _event(c,actor,'LEAD_TRANSITION','lead',lead_id,{'from':before,'to':new_status,'note':_redact(note),'legacy_payment_reference':bool(payment_reference)})
    return get_lead(lead_id)


def add_memory(scope,kind,statement,source,confidence,verified=False,actor='agent'):
    if not source or not statement:raise ValueError('memory requires statement and evidence source')
    if not 0<=confidence<=1:raise ValueError('confidence out of range')
    if kind not in ('FACT','HYPOTHESIS','LESSON','RULE','DECISION'):
        raise ValueError('invalid memory kind')
    if verified and actor!='founder':raise ValueError('only founder can verify a memory')
    if actor=='founder' or verified:require_founder()
    scope,statement,source=(_redact(x) for x in (scope,statement,source))
    m_id=str(uuid.uuid4())
    with atomic() as c:
        c.execute('INSERT INTO memory VALUES(?,?,?,?,?,?,?,?)',(m_id,scope,kind,statement,source,confidence,int(verified),now()))
        _event(c,actor,'MEMORY_WRITTEN','memory',m_id,{'scope':scope,'kind':kind,
            'statement_sha256':hashlib.sha256(statement.encode('utf-8')).hexdigest(),
            'source':source,'confidence':confidence,'verified':verified})
    return m_id


def read_memory(scope=None,limit=100):
    init_db()
    with _con() as c:
        if scope:
            rows=c.execute('SELECT * FROM memory WHERE scope=? ORDER BY created_at DESC LIMIT ?',(scope,limit)).fetchall()
        else:
            rows=c.execute('SELECT * FROM memory ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall()
    return [dict(x) for x in rows]


def create_task(title,owner='founder',lead_id=None,due_at=None,actor='agent'):
    title,owner,due_at=_redact(title),_redact(owner),_redact(due_at) if due_at else None
    task_id=str(uuid.uuid4());ts=now()
    with atomic() as c:
        c.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',(task_id,lead_id,title,owner,'TODO',due_at,ts,ts))
        _event(c,actor,'TASK_CREATED','task',task_id,{'title':title,'owner':owner,'lead_id':lead_id,'due_at':due_at})
    return task_id


def ensure_founder_review_task(lead_id,title,actor='acquisition_agent'):
    """Create one durable review task per lead and title, including after retry."""
    title=_redact(title)
    with atomic() as c:
        if not c.execute('SELECT 1 FROM leads WHERE id=?',(lead_id,)).fetchone():
            raise ValueError('lead not found')
        existing=c.execute('SELECT id FROM tasks WHERE lead_id=? AND title=? ORDER BY created_at LIMIT 1',
                           (lead_id,title)).fetchone()
        if existing:return existing['id'],False
        task_id=str(uuid.uuid4());ts=now()
        c.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?)',
                  (task_id,lead_id,title,'founder','TODO',None,ts,ts))
        _event(c,actor,'TASK_CREATED','task',task_id,
               {'title':title,'owner':'founder','lead_id':lead_id,'due_at':None})
    return task_id,True


def finish_task(task_id,actor='founder'):
    with atomic() as c:
        row=c.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
        if not row:raise ValueError('task not found')
        c.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=?',('DONE',now(),task_id))
        _event(c,actor,'TASK_FINISHED','task',task_id,{'from':row['status'],'to':'DONE'})


def list_tasks(limit=100):
    init_db()
    with _con() as c:
        return [dict(x) for x in c.execute('SELECT * FROM tasks ORDER BY status DESC,created_at DESC LIMIT ?', (limit,)).fetchall()]


def store_artifact(lead_id,kind,content,actor='proposal_agent'):
    if not get_lead(lead_id):raise ValueError('lead not found')
    content=_redact(content)
    aid=str(uuid.uuid4())
    with atomic() as c:
        c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(aid,lead_id,kind,content,now()))
        _event(c,actor,'ARTIFACT_CREATED','lead',lead_id,{'artifact_id':aid,'kind':kind,'length':len(content)})
    return aid


def list_artifacts(lead_id):
    init_db()
    with _con() as c:
        return [dict(x) for x in c.execute('SELECT * FROM artifacts WHERE lead_id=? ORDER BY created_at DESC',(lead_id,)).fetchall()]


def list_events(limit=100,target_id=None):
    init_db()
    with _con() as c:
        if target_id:
            rows=c.execute('SELECT * FROM events WHERE target_id=? ORDER BY seq DESC LIMIT ?',(target_id,limit)).fetchall()
        else:
            rows=c.execute('SELECT * FROM events ORDER BY seq DESC LIMIT ?',(limit,)).fetchall()
    result=[]
    for r in rows:
        d=dict(r);d['payload']=json.loads(d['payload']);result.append(d)
    return result


COMMERCIAL_EVENT_TYPES=('APPLICATION_SUBMITTED','PROPOSAL_SENT','CONTACT_SENT','FOLLOWUP_SENT','REPLY_RECEIVED',
                        'DISCOVERY_HELD','SCOPE_AGREED','PAYMENT_RECEIVED','PAYMENT_REFUNDED')


def register_customer_entity(canonical_key,display_name,evidence_ref,independent_verified=False):
    """Founder-attested organization identity. One canonical key represents one customer."""
    require_founder()
    key=_redact(canonical_key.strip().lower())
    if not key or len(key)<3 or not display_name.strip() or not evidence_ref.strip():
        raise ValueError('customer key, name and identity evidence required')
    with atomic() as c:
        existing=c.execute('SELECT id,independent_verified FROM customer_entities WHERE canonical_key=?',(key,)).fetchone()
        if existing:
            if independent_verified and not existing['independent_verified']:
                c.execute('UPDATE customer_entities SET independent_verified=1,evidence_ref=? WHERE id=?',
                          (_redact(evidence_ref),existing['id']))
                _event(c,'founder','CUSTOMER_VERIFIED','customer',existing['id'],{'evidence_ref':evidence_ref})
            return existing['id']
        cid=str(uuid.uuid4())
        c.execute('INSERT INTO customer_entities VALUES(?,?,?,?,?,?)',
                  (cid,key,_redact(display_name),int(independent_verified),_redact(evidence_ref),now()))
        _event(c,'founder','CUSTOMER_REGISTERED','customer',cid,
               {'canonical_key':key,'independent_verified':bool(independent_verified),'evidence_ref':evidence_ref})
    return cid


def link_lead_customer(lead_id,customer_id):
    require_founder()
    with atomic() as c:
        if not c.execute('SELECT 1 FROM customer_entities WHERE id=?',(customer_id,)).fetchone():
            raise ValueError('customer not found')
        row=c.execute('SELECT customer_id FROM leads WHERE id=?',(lead_id,)).fetchone()
        if not row:raise ValueError('lead not found')
        if row['customer_id'] and row['customer_id']!=customer_id:
            raise ValueError('lead customer already linked; investigate identity before changing')
        c.execute('UPDATE leads SET customer_id=?,updated_at=? WHERE id=?',(customer_id,now(),lead_id))
        _event(c,'founder','LEAD_CUSTOMER_LINKED','lead',lead_id,{'customer_id':customer_id})
    return get_lead(lead_id)


def _lead_has_confirmed_payment(c,lead_id):
    return bool(c.execute('''SELECT 1 FROM leads l JOIN customer_entities ce ON ce.id=l.customer_id
        WHERE l.id=? AND ce.independent_verified=1
        AND EXISTS (SELECT 1 FROM commercial_events e WHERE e.lead_id=l.id AND e.event_type='SCOPE_AGREED')
        AND COALESCE((SELECT SUM(CASE WHEN e.event_type='PAYMENT_RECEIVED' THEN e.amount
                                      WHEN e.event_type='PAYMENT_REFUNDED' THEN -e.amount ELSE 0 END)
                      FROM commercial_events e WHERE e.lead_id=l.id),0)>0''',(lead_id,)).fetchone())


def record_commercial_event(lead_id,event_type,evidence_ref,amount=None,currency=None):
    """Record an action the founder already took; this function never contacts a buyer."""
    require_founder()
    event_type=str(event_type).upper()
    if event_type not in COMMERCIAL_EVENT_TYPES:raise ValueError('unsupported commercial event')
    if not evidence_ref or not evidence_ref.strip():raise ValueError('founder evidence reference required')
    if event_type in ('PAYMENT_RECEIVED','PAYMENT_REFUNDED') and (amount is None or amount<=0 or not currency or not re.fullmatch(r'[A-Z]{3}',currency)):
        raise ValueError('positive amount and ISO currency required')
    with atomic() as c:
        lead=c.execute('SELECT customer_id FROM leads WHERE id=?',(lead_id,)).fetchone()
        if not lead:raise ValueError('lead not found')
        customer_id=lead['customer_id']
        if event_type in ('SCOPE_AGREED','PAYMENT_RECEIVED','PAYMENT_REFUNDED'):
            if not customer_id:raise ValueError('linked customer required for scope and payment')
            customer=c.execute('SELECT independent_verified FROM customer_entities WHERE id=?',(customer_id,)).fetchone()
            if not customer or not customer['independent_verified']:
                raise ValueError('independent customer verification required')
        if event_type=='PAYMENT_RECEIVED' and not c.execute(
            "SELECT 1 FROM commercial_events WHERE lead_id=? AND event_type='SCOPE_AGREED'",(lead_id,)).fetchone():
            raise ValueError('agreed scope required before receipt')
        if event_type in ('PAYMENT_RECEIVED','PAYMENT_REFUNDED'):
            currencies={r['currency'] for r in c.execute("SELECT currency FROM commercial_events WHERE lead_id=? AND event_type IN ('PAYMENT_RECEIVED','PAYMENT_REFUNDED')",(lead_id,))}
            if currencies and currency not in currencies:raise ValueError('payment currency must match existing deal receipts')
        if event_type=='PAYMENT_REFUNDED':
            net=c.execute("SELECT COALESCE(SUM(CASE WHEN event_type='PAYMENT_RECEIVED' THEN amount WHEN event_type='PAYMENT_REFUNDED' THEN -amount ELSE 0 END),0) FROM commercial_events WHERE lead_id=?",(lead_id,)).fetchone()[0]
            if amount>net:raise ValueError('refund exceeds received net funds')
        event_id=str(uuid.uuid4())
        c.execute('INSERT INTO commercial_events VALUES(?,?,?,?,?,?,?,?)',
                  (event_id,lead_id,customer_id,event_type,_redact(evidence_ref),amount,_redact(currency) if currency else None,now()))
        _event(c,'founder',event_type,'lead',lead_id,{'commercial_event_id':event_id,'customer_id':customer_id,
            'evidence_ref':evidence_ref,'amount':amount,'currency':currency})
    return {'id':event_id,'lead_id':lead_id,'event_type':event_type,'customer_id':customer_id}


def summary():
    init_db()
    with _con() as c:
        statuses={r['status']:r['n'] for r in c.execute('SELECT status,COUNT(*) n FROM leads GROUP BY status')}
        n=c.execute('SELECT COUNT(*) n FROM events').fetchone()['n']
        mem=c.execute('SELECT COUNT(*) n FROM memory').fetchone()['n']
        tasks=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='TODO'").fetchone()['n']
        num=c.execute('''SELECT COUNT(DISTINCT l.customer_id) n FROM leads l
          JOIN customer_entities ce ON ce.id=l.customer_id WHERE ce.independent_verified=1
          AND EXISTS (SELECT 1 FROM commercial_events e WHERE e.lead_id=l.id AND e.event_type='SCOPE_AGREED')
          AND COALESCE((SELECT SUM(CASE WHEN e.event_type='PAYMENT_RECEIVED' THEN e.amount
                                        WHEN e.event_type='PAYMENT_REFUNDED' THEN -e.amount ELSE 0 END)
                        FROM commercial_events e WHERE e.lead_id=l.id),0)>0''').fetchone()['n']
        signed=c.execute("SELECT COUNT(DISTINCT e.customer_id) n FROM commercial_events e JOIN customer_entities ce ON ce.id=e.customer_id WHERE e.event_type='SCOPE_AGREED' AND ce.independent_verified=1").fetchone()['n']
        commercial={r['event_type']:r['n'] for r in c.execute('SELECT event_type,COUNT(DISTINCT lead_id) n FROM commercial_events GROUP BY event_type')}
        actual_contacts=c.execute("SELECT COUNT(DISTINCT lead_id) n FROM commercial_events WHERE event_type IN ('APPLICATION_SUBMITTED','PROPOSAL_SENT','CONTACT_SENT','FOLLOWUP_SENT')").fetchone()['n']
        proposals_sent=c.execute("SELECT COUNT(DISTINCT lead_id) n FROM commercial_events WHERE event_type IN ('APPLICATION_SUBMITTED','PROPOSAL_SENT')").fetchone()['n']
        cats={}
        for r in c.execute('SELECT categories FROM leads'):
            for category in json.loads(r['categories']):cats[category]=cats.get(category,0)+1
    return {'leads':sum(statuses.values()),'paying_clients':num,'signed_clients':signed,'target_clients':3,'stages':statuses,
            'actual_contacts':actual_contacts,'proposals_sent':proposals_sent,'commercial_events_by_type':commercial,
            'category_signals':cats,'events':n,'memory_items':mem,'open_tasks':tasks}


def checkpoint(day):
    if day not in (30,60,90):raise ValueError('supported checkpoints: 30,60,90')
    s=summary(); total=s['leads'];contacted=s['actual_contacts']
    proposed=s['proposals_sent']
    won=s['paying_clients']
    problems=[]
    if total<10:problems.append('Too little discovery data. Source access and discovery may be the bottleneck.')
    if total>=10 and contacted<3:problems.append('Discovery exists but outreach is low; examine verification, prioritization and founder approval queue.')
    if contacted>=10 and proposed==0:problems.append('Approaches exist but no proposals; inspect response quality and discovery outcomes.')
    if proposed>=4 and won==0:problems.append('Proposal-to-payment conversion low; investigate fit, price, credibility, scope and time constraints.')
    if not problems:problems.append('No decisive bottleneck detected with current stage counts; inspect qualitative evidence and event history.')
    return {'day':day,'metrics':s,'diagnosis':problems,
        'decision':'REVISE_EXPERIMENT' if problems and problems[0].startswith('Too little') else 'FOUNDER_REVIEW',
        'limitations':'Based on recorded stages only; do not infer causation or market-wide conversion rates from a small sample.'}


def search_queries():
    """Two parallel source-discovery tracks; search is NOT evidence of buyer intent."""
    explicit=['"machine learning" "freelance" project','"computer vision" "contract" developer',
       '"RAG" "contractor" implementation','"LLM fine tuning" "freelancer"',
       '"AI agent" "project" hire','"NLP" "consultant" project',
       '"predictive analytics" "RFP"','"MLOps" "contract" project']
    accounts=['software development agency AI integration partner','data engineering consultancy AI services subcontractor',
      'startup hiring computer vision engineers','operations company invoice processing automation case study']
    return {'EXPLICIT_PROJECT':explicit,'POTENTIAL_ACCOUNT':accounts}

ACTIVITY_TYPES = ('RESEARCH_NOTE','SOURCE_CHECK','PROFILE_UPDATED','OUTREACH_DRAFT_REVIEWED',
                  'MESSAGE_SENT_MANUALLY','APPLICATION_SUBMITTED','PROPOSAL_SENT','FOLLOWUP_SENT',
                  'REPLY_RECEIVED','MEETING_HELD','BUYER_OBJECTION','PROPOSAL_REVIEWED',
                  'PRICE_DECISION','MILESTONE_UPDATE','PAYMENT_NOTE','EXPERIMENT_DECISION')

def manual_activity(action,summary_text,lead_id=None,evidence=None,actor='founder'):
    if action not in ACTIVITY_TYPES:raise ValueError('unsupported activity action')
    if actor!='founder':raise ValueError('manual business activity must be reported by founder')
    require_founder()
    mapped={'MESSAGE_SENT_MANUALLY':'CONTACT_SENT','APPLICATION_SUBMITTED':'APPLICATION_SUBMITTED',
            'PROPOSAL_SENT':'PROPOSAL_SENT','FOLLOWUP_SENT':'FOLLOWUP_SENT',
            'REPLY_RECEIVED':'REPLY_RECEIVED','MEETING_HELD':'DISCOVERY_HELD'}
    if action in mapped and not lead_id:raise ValueError('lead_id required for commercial activity')
    if lead_id and not get_lead(lead_id):raise ValueError('lead not found')
    if not summary_text.strip():raise ValueError('activity requires description')
    event=record_event(actor,'BUSINESS_ACTIVITY',{'type':action,'summary':_redact(summary_text[:2000]),
                'evidence':_redact(evidence)},'lead' if lead_id else 'business',lead_id or 'global')
    if lead_id and action in mapped:
        record_commercial_event(lead_id,mapped[action],evidence or summary_text)
    return event


def _flag(value):
    return 1 if (value in (1,True) or str(value).strip().lower() in ('1','true','yes')) else 0


def register_source(source_id,domain,name,category,actor='system'):
    """Register a source with default lifecycle and access-policy records."""
    source_id=str(source_id).strip();domain=str(domain).strip().lower();name=str(name).strip();category=str(category).strip().upper()
    if not source_id:raise ValueError('source_id required')
    if not name:raise ValueError('name required')
    if not re.fullmatch(r'[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+',domain):raise ValueError('domain must be a bare hostname like example.com')
    if category not in SOURCE_CATEGORIES:raise ValueError('invalid source category')
    if actor=='founder':require_founder()
    ts=now()
    with atomic() as c:
        if c.execute('SELECT 1 FROM sources_lifecycle WHERE source_id=?',(source_id,)).fetchone():raise ValueError('source already registered')
        c.execute('INSERT INTO sources_lifecycle(source_id,domain,name,category,lifecycle_state,created_ts,updated_ts,notes) VALUES(?,?,?,?,?,?,?,?)',(source_id,domain,name,category,'DISCOVERED',ts,ts,''))
        c.execute('INSERT INTO source_access_policy(source_id) VALUES(?)',(source_id,))
        _event(c,actor,'SOURCE_REGISTERED','source',source_id,{'domain':domain,'name':name,'category':category,'lifecycle_state':'DISCOVERED','policy_state':'UNKNOWN'})
    return get_source(source_id)


def transition_source(source_id,new_state,actor='system',note=''):
    """Validate against SOURCE_LIFECYCLE_TRANSITIONS; founder decisions from AWAITING_FOUNDER are audited twice (state + decision)."""
    new_state=str(new_state).strip().upper()
    if new_state not in SOURCE_LIFECYCLE_STATES:raise ValueError('invalid source lifecycle state')
    error=None
    with atomic() as c:
        r=c.execute('SELECT * FROM sources_lifecycle WHERE source_id=?',(source_id,)).fetchone()
        if not r:raise ValueError('source not found')
        before=r['lifecycle_state']
        if new_state==before:error=f'source already in state {new_state}'
        elif new_state not in SOURCE_LIFECYCLE_TRANSITIONS.get(before,set()):error=f'invalid source transition {before} -> {new_state}'
        elif (before=='AWAITING_FOUNDER' or new_state in {'ONBOARDING','PILOT_READY','PILOT_RUNNING','ACTIVE','MANUAL_ONLY'}) and actor!='founder':
            error='founder authorization required for source onboarding decision'
        else:
            if actor=='founder':require_founder()
            c.execute('UPDATE sources_lifecycle SET lifecycle_state=?,updated_ts=? WHERE source_id=?',(new_state,now(),source_id))
            _event(c,actor,'SOURCE_TRANSITION','source',source_id,{'from':before,'to':new_state,'note':note})
            if before=='AWAITING_FOUNDER':
                _event(c,actor,'FOUNDER_POLICY_DECISION','source',source_id,{'decision':new_state,'note':note})
    if error:
        record_event(actor,'ACTION_DENIED',{'reason':error,'attempted_state':new_state},'source',source_id)
        raise ValueError(error)
    return get_source(source_id)


def update_source_policy(source_id,policy_state,permissions_dict=None,evidence='',actor='system'):
    """Only an authenticated founder can alter policy or permissions."""
    if actor!='founder' or not _FOUNDER_AUTH.get():
        record_event('policy_guard','ACTION_DENIED',{'reason_code':'FOUNDER_AUTH_REQUIRED','attempted_policy_state':policy_state},'source',source_id)
        raise ValueError('founder authorization required to update source policy')
    policy_state=str(policy_state).strip().upper()
    if policy_state not in ACCESS_POLICY_STATES:raise ValueError('invalid policy state')
    perms=dict(permissions_dict or {})
    unknown=set(perms)-set(PERMISSION_KEYS)-{'rate_limit_notes','allowed_paths','account_state','rate_limit_per_hour'}
    if unknown:raise ValueError('unknown permission keys: '+','.join(sorted(unknown)))
    evidence=_redact(evidence);rate=_redact(perms.get('rate_limit_notes',''))
    paths=perms.get('allowed_paths')
    if paths is not None and (not isinstance(paths,(list,tuple)) or not paths or any(not isinstance(p,str) or not p.startswith('/') or p.startswith('//') or _redact(p)!=p for p in paths)):
        raise ValueError('allowed_paths must be nonempty URL path prefixes')
    account_state=str(perms['account_state']).upper() if 'account_state' in perms else None
    if account_state is not None and account_state not in ('UNRESTRICTED','RESTRICTED','SUSPENDED'):
        raise ValueError('invalid account_state')
    hourly=int(perms['rate_limit_per_hour']) if 'rate_limit_per_hour' in perms else None
    if hourly is not None and not 1<=hourly<=3600:raise ValueError('rate_limit_per_hour must be 1..3600')
    if policy_state=='CONFIRMED' and not evidence.strip():raise ValueError('policy evidence required')
    with atomic() as c:
        if not c.execute('SELECT 1 FROM sources_lifecycle WHERE source_id=?',(source_id,)).fetchone():raise ValueError('source not found')
        cur=c.execute('SELECT * FROM source_access_policy WHERE source_id=?',(source_id,)).fetchone()
        if not cur:raise ValueError('source policy not found')
        paths=paths if paths is not None else json.loads(cur['allowed_paths'])
        account_state=account_state or cur['account_state']
        hourly=hourly or cur['rate_limit_per_hour']
        flags={k:_flag(perms.get(k,cur[k])) for k in PERMISSION_KEYS}
        ts=now()
        reviewed=ts if policy_state=='CONFIRMED' else (cur['reviewed_ts'] or '')
        expires=(datetime.now(timezone.utc)+timedelta(days=90)).isoformat(timespec='seconds') if policy_state=='CONFIRMED' else (cur['review_expires_ts'] or '')
        version=cur['policy_version']+1
        c.execute('UPDATE source_access_policy SET policy_state=?,public_reading=?,official_api=?,feed_read=?,browser_navigation=?,authenticated_extraction=?,messaging=?,application_submission=?,manual_browser_access=?,human_supplied_lead_processing=?,rate_limit_notes=?,evidence=?,reviewed_ts=?,review_expires_ts=?,policy_version=?,allowed_paths=?,account_state=?,rate_limit_per_hour=? WHERE source_id=?',
                  (policy_state,)+tuple(flags[k] for k in PERMISSION_KEYS)+(rate,evidence,reviewed,expires,version,dumps(paths),account_state,hourly,source_id))
        c.execute('UPDATE sources_lifecycle SET updated_ts=? WHERE source_id=?',(ts,source_id))
        _event(c,actor,'SOURCE_POLICY_UPDATED','source',source_id,{'policy_state':policy_state,'policy_version':version,'permissions':{k:bool(flags[k]) for k in PERMISSION_KEYS},'allowed_paths':paths,'account_state':account_state,'rate_limit_per_hour':hourly,'evidence':evidence,'reviewed_ts':reviewed,'review_expires_ts':expires})
    return get_source(source_id)


def get_source(source_id):
    """Lifecycle + policy view; empty review/evidence fields are reported as [NOT_COLLECTED]."""
    init_db()
    with _con() as c:
        s=c.execute('SELECT * FROM sources_lifecycle WHERE source_id=?',(source_id,)).fetchone()
        p=c.execute('SELECT * FROM source_access_policy WHERE source_id=?',(source_id,)).fetchone()
    if not s:return None
    out=dict(s)
    if p:
        for k in PERMISSION_KEYS:out[k]=bool(p[k])
        out['policy_state']=p['policy_state']
        out['rate_limit_notes']=p['rate_limit_notes'] or NOT_COLLECTED
        out['evidence']=p['evidence'] or NOT_COLLECTED
        out['reviewed_ts']=p['reviewed_ts'] or NOT_COLLECTED
        out['review_expires_ts']=p['review_expires_ts'] or NOT_COLLECTED
        out['policy_version']=p['policy_version']
        out['allowed_paths']=json.loads(p['allowed_paths'])
        out['account_state']=p['account_state']
        out['rate_limit_per_hour']=p['rate_limit_per_hour']
    else:
        out['policy_state']='UNKNOWN'
    return out


def list_sources(lifecycle_state=None):
    init_db()
    with _con() as c:
        if lifecycle_state:
            rows=c.execute('SELECT s.*,p.policy_state FROM sources_lifecycle s LEFT JOIN source_access_policy p ON p.source_id=s.source_id WHERE s.lifecycle_state=? ORDER BY s.created_ts,s.source_id',(lifecycle_state,)).fetchall()
        else:
            rows=c.execute('SELECT s.*,p.policy_state FROM sources_lifecycle s LEFT JOIN source_access_policy p ON p.source_id=s.source_id ORDER BY s.created_ts,s.source_id').fetchall()
    return [dict(x) for x in rows]


def policy_check(source_id,action,target_url):
    """Default-deny, audited authorization for one impending network operation."""
    try:parsed=urlsplit(str(target_url))
    except ValueError:parsed=urlsplit('')
    safe_url=_redact(urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'','')))
    reason=None
    with atomic() as c:
        source=c.execute('SELECT * FROM sources_lifecycle WHERE source_id=?',(source_id,)).fetchone()
        policy=c.execute('SELECT * FROM source_access_policy WHERE source_id=?',(source_id,)).fetchone()
        if action not in AUTOMATED_ACTIONS:reason='UNKNOWN_ACTION'
        elif action in ('messaging','application_submission'):reason='OUTBOUND_PROHIBITED'
        elif not source or not policy:reason='UNKNOWN_SOURCE'
        elif source['lifecycle_state'] not in ('ACTIVE','PILOT_RUNNING'):reason='INACTIVE_SOURCE'
        elif policy['policy_state']!='CONFIRMED' or not policy['evidence'] or policy['policy_version']<1:reason='POLICY_UNCONFIRMED'
        elif not policy['review_expires_ts']:reason='POLICY_EXPIRED'
        else:
            try:expired=datetime.fromisoformat(policy['review_expires_ts'])<=datetime.now(timezone.utc)
            except (ValueError,TypeError):expired=True
            if expired:reason='POLICY_EXPIRED'
        if not reason and policy['account_state']!='UNRESTRICTED':reason='ACCOUNT_RESTRICTED'
        if not reason and not policy[action]:reason='ACTION_NOT_ALLOWED'
        if not reason:
            try:
                paths=json.loads(policy['allowed_paths'])
                path=unquote(parsed.path or '/')
                valid_path=path==unquote(path) and not ('\\' in path or '//' in path or any(seg in ('.','..') for seg in path.split('/')))
                valid_path=valid_path and any(prefix=='/' or path==prefix.rstrip('/') or path.startswith(prefix.rstrip('/')+'/') for prefix in paths)
                valid_host=parsed.scheme=='https' and parsed.hostname==source['domain'] and not parsed.username and not parsed.password and parsed.port in (None,443)
                valid_query=not any(_sensitive_url_key(k) for k,_ in parse_qsl(parsed.query,keep_blank_values=True))
                if not (valid_path and valid_host and valid_query):reason='TARGET_OUT_OF_SCOPE'
            except (ValueError,TypeError,KeyError):reason='TARGET_OUT_OF_SCOPE'
        if not reason:
            hour=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:00:00Z')
            used=c.execute('SELECT used FROM source_rate_usage WHERE source_id=? AND hour_start=?',(source_id,hour)).fetchone()
            if used and used['used']>=policy['rate_limit_per_hour']:reason='RATE_LIMITED'
            else:
                c.execute('INSERT INTO source_rate_usage(source_id,hour_start,used) VALUES(?,?,1) ON CONFLICT(source_id,hour_start) DO UPDATE SET used=used+1',(source_id,hour))
        allowed=reason is None
        version=str(policy['policy_version']) if policy else None
        expiry=policy['review_expires_ts'] if policy else None
        scope=tuple('https://'+source['domain']+p for p in json.loads(policy['allowed_paths'])) if allowed else ()
        decision=AccessDecision(allowed,reason or 'ALLOWED',version,expiry,scope)
        _event(c,'policy_guard','POLICY_CHECKED' if allowed else 'ACTION_DENIED','source',source_id,
               {'action':action,'target_url':safe_url,'reason_code':decision.reason_code,'policy_version':version})
    return decision


def is_automated_action_allowed(source_id,action,actor='system',target_url=None):
    """Compatibility wrapper; new integrations use CorePolicyPort.authorize."""
    source=get_source(source_id)
    target=target_url or ('https://'+source['domain']+'/' if source else 'https://invalid.example/')
    return policy_check(source_id,action,target).allowed


def ingest_manual_lead(source_id,lead_data,actor='founder'):
    """Founder-supplied lead for a MANUAL_ONLY source; routed through add_lead for dedup, classification, scoring and audit."""
    if actor!='founder':
        record_event(actor,'ACTION_DENIED',{'reason':'manual lead intake requires founder','source_id':source_id},'source',source_id)
        raise ValueError('manual lead intake requires founder')
    require_founder()
    src=get_source(source_id)
    if not src:raise ValueError('source not found')
    if src['lifecycle_state']!='MANUAL_ONLY':
        reason=f"manual intake requires MANUAL_ONLY source, found {src['lifecycle_state']}"
        record_event(actor,'ACTION_DENIED',{'reason':reason},'source',source_id)
        raise ValueError(reason)
    if not src['human_supplied_lead_processing']:
        reason='human_supplied_lead_processing is not enabled in source policy'
        record_event(actor,'ACTION_DENIED',{'reason':reason},'source',source_id)
        raise ValueError(reason)
    item=dict(lead_data or {})
    item['source']=source_id
    correlation_id=str(uuid.uuid4())
    result=add_lead(item,actor=actor,correlation_id=correlation_id)
    record_event(actor,'MANUAL_LEAD_INTAKE',{'source_id':source_id,'lead_id':result['id'],'created':result['created'],'title':str(item.get('title') or '')[:200],'source_url':item.get('source_url')},'source',source_id,correlation_id=correlation_id)
    return {'source_id':source_id,'lead_id':result['id'],'created':result['created'],'score':result.get('score'),'correlation_id':correlation_id}


def backup_db(dest_dir=None):
    """Consistent snapshot via the SQLite backup API; one file per UTC day, returns the backup path."""
    init_db()
    dest=Path(dest_dir) if dest_dir else DB_PATH.parent/'backups'
    dest.mkdir(parents=True,exist_ok=True)
    day=datetime.now(timezone.utc).date().isoformat()
    dest_path=dest/f'acquisition_backup_{day}.db'
    src=_con()
    try:
        out=sqlite3.connect(str(dest_path))
        try:src.backup(out)
        finally:out.close()
    finally:
        src.close()
    record_event('system','DB_BACKUP_CREATED',{'path':str(dest_path),'source_db':str(DB_PATH),'date':day},'system',str(dest_path))
    return str(dest_path)
