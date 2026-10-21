"""Local founder dashboard and JSON API. Serve on 127.0.0.1 only unless secured."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from . import core, agents, integration

@asynccontextmanager
async def lifespan(app):
    core.init_db()
    yield
app=FastAPI(title='AI Client Acquisition Mission Control', version='0.1.0', lifespan=lifespan)

@app.middleware('http')
async def founder_auth_middleware(request:Request,call_next):
    path=request.url.path
    if path.startswith('/api/') and path!='/api/health':
        try:
            with core.founder_session(request.headers.get('x-admin-token')):
                return await call_next(request)
        except ValueError:
            if request.method not in ('GET','HEAD','OPTIONS'):
                core.record_event('policy_guard','ACTION_DENIED',{'reason_code':'FOUNDER_AUTH_REQUIRED','method':request.method},'api','request')
            return JSONResponse(status_code=403,content={'detail':'Founder authentication required'})
    return await call_next(request)


def guard(x_admin_token: Optional[str]=Header(default=None)):
    if not os.getenv('ACQ_ADMIN_TOKEN') or not x_admin_token:
        raise HTTPException(status_code=403,detail='Founder authentication required')
    return True


def execute(fn):
    try:return fn()
    except PermissionError:
        core.record_event('policy_guard','ACTION_DENIED',{'reason_code':'SOURCE_AUTH_REQUIRED'},'system','request')
        raise HTTPException(status_code=403,detail='Source authorization required')
    except ValueError as exc:
        reason=core._redact(str(exc))[:400]
        core.record_event('policy_guard','ACTION_DENIED',{'reason':reason},'system','request')
        raise HTTPException(status_code=400,detail=reason) from exc
    except Exception as exc:
        raise HTTPException(status_code=502,detail=f'Operation failed: {type(exc).__name__}. See audit events.') from exc

class LeadIn(BaseModel):
    source: str='manual'
    source_url: str
    title: str
    description: str=''
    demand_type: str='EXPLICIT_PROJECT'
    company: Optional[str]=None
    currency: Optional[str]=None
    budget_min: Optional[float]=None
    budget_max: Optional[float]=None

class FounderCandidatesIn(BaseModel):
    source_id: str
    run_id: str
    candidates: list[LeadIn]

class VerifyIn(BaseModel):
    verified: bool
    note: str

class TransitionIn(BaseModel):
    new_status: str
    note: str=''
    payment_reference: Optional[str]=None

class MemoryIn(BaseModel):
    scope: str
    kind: str
    statement: str
    source: str
    confidence: float=Field(ge=0,le=1)
    verified: bool=False

class ActivityIn(BaseModel):
    action: str
    summary_text: str
    lead_id: Optional[str]=None
    evidence: Optional[str]=None

class CustomerIn(BaseModel):
    canonical_key: str
    display_name: str
    evidence_ref: str
    independent_verified: bool=False

class CommercialEventIn(BaseModel):
    event_type: str
    evidence_ref: str
    amount: Optional[float]=None
    currency: Optional[str]=None

class SourceIn(BaseModel):
    source_id: str
    domain: str
    name: str
    category: str

class SourceTransitionIn(BaseModel):
    new_state: str
    note: str=''

class SourcePolicyIn(BaseModel):
    policy_state: str
    permissions: dict={}
    evidence: str=''

class TaskIn(BaseModel):
    title: str
    owner: str='founder'
    lead_id: Optional[str]=None
    due_at: Optional[str]=None

class BraveIn(BaseModel):
    queries: Optional[list[str]]=None
    demand_type: str='EXPLICIT_PROJECT'
    limit_per_query: int=Field(default=5,ge=1,le=20)

class RssIn(BaseModel):
    feed_url: str
    source_name: str='allowed_feed'
    approved: bool=False
    limit: int=30
    demand_type: str='EXPLICIT_PROJECT'

class FreelancerIn(BaseModel):
    query: str
    limit: int=20

@app.get('/api/health')
def health():return {'status':'ok','build':'v0.1','outbound_sending':False}

@app.get('/api/dashboard')
def dashboard():return core.summary()

@app.post('/api/leads',dependencies=[Depends(guard)])
def lead_create(body:LeadIn):return execute(lambda: core.add_lead(body.model_dump(),actor='founder'))

@app.post('/api/leads/batch',dependencies=[Depends(guard)])
def lead_batch(body:list[LeadIn]):
    if len(body)>200:raise HTTPException(400,'max 200 per batch')
    result=[]
    for lead in body:
        result.append(execute(lambda x=lead:core.add_lead(x.model_dump(),actor='founder_research_import')))
    return result

@app.post('/api/intake/founder',dependencies=[Depends(guard)])
def founder_intake(body:FounderCandidatesIn, x_admin_token:Optional[str]=Header(default=None)):
    return execute(lambda:integration.prepare_founder_candidates(
        source_id=body.source_id,
        candidates=[{**candidate.model_dump(), 'source': body.source_id}
                    for candidate in body.candidates],
        run_id=body.run_id, founder_token=x_admin_token))

@app.get('/api/leads')
def leads(status:Optional[str]=None,limit:int=100):return core.list_leads(min(max(limit,1),500),status)

@app.get('/api/leads/{lead_id}')
def lead(lead_id:str):
    r=core.get_lead(lead_id)
    if not r:raise HTTPException(404,'Not found')
    return {'lead':r,'artifacts':core.list_artifacts(lead_id),'history':core.list_events(50,lead_id)}

@app.post('/api/leads/{lead_id}/verify',dependencies=[Depends(guard)])
def verify(lead_id:str,body:VerifyIn):return execute(lambda:core.verify_lead(lead_id,body.verified,body.note))

@app.post('/api/leads/{lead_id}/transition',dependencies=[Depends(guard)])
def transition(lead_id:str,body:TransitionIn):
    return execute(lambda:core.transition_lead(lead_id,body.new_status,'founder',body.note,body.payment_reference))

@app.post('/api/customers',dependencies=[Depends(guard)])
def customer_create(body:CustomerIn):
    return {'id':execute(lambda:core.register_customer_entity(**body.model_dump()))}

@app.post('/api/leads/{lead_id}/customer/{customer_id}',dependencies=[Depends(guard)])
def customer_link(lead_id:str,customer_id:str):
    return execute(lambda:core.link_lead_customer(lead_id,customer_id))

@app.post('/api/leads/{lead_id}/commercial-events',dependencies=[Depends(guard)])
def commercial_event(lead_id:str,body:CommercialEventIn):
    return execute(lambda:core.record_commercial_event(lead_id,**body.model_dump()))

@app.post('/api/leads/{lead_id}/draft',dependencies=[Depends(guard)])
def draft(lead_id:str):return execute(lambda:agents.evidence_driven_proposal(lead_id))

@app.get('/api/leads/{lead_id}/offers',dependencies=[Depends(guard)])
def offers(lead_id:str):return execute(lambda:agents.match_offers(lead_id))

@app.post('/api/leads/{lead_id}/analyze',dependencies=[Depends(guard)])
def analyze(lead_id:str):return execute(lambda:agents.local_llm_research(lead_id))

@app.post('/api/discovery/brave',dependencies=[Depends(guard)])
def discover_brave(body:BraveIn):return execute(lambda:agents.brave_discover(body.queries,body.demand_type,body.limit_per_query))

@app.post('/api/discovery/rss',dependencies=[Depends(guard)])
def discover_rss(body:RssIn):return execute(lambda:agents.rss_discover(body.feed_url,body.source_name,body.limit,body.demand_type,body.approved))

@app.post('/api/discovery/freelancer',dependencies=[Depends(guard)])
def discover_freelancer(body:FreelancerIn):return execute(lambda:agents.freelancer_discover(body.query,body.limit))

@app.get('/api/sources')
def sources():
    from pathlib import Path
    import json
    return json.loads((Path(__file__).parent.parent/'source_registry.json').read_text(encoding='utf8'))

@app.post('/api/source-policies',dependencies=[Depends(guard)])
def source_create(body:SourceIn):
    return execute(lambda:core.register_source(**body.model_dump(),actor='founder'))

@app.post('/api/source-policies/{source_id}/transition',dependencies=[Depends(guard)])
def source_transition(source_id:str,body:SourceTransitionIn):
    return execute(lambda:core.transition_source(source_id,body.new_state,actor='founder',note=body.note))

@app.post('/api/source-policies/{source_id}/policy',dependencies=[Depends(guard)])
def source_policy(source_id:str,body:SourcePolicyIn):
    return execute(lambda:core.update_source_policy(source_id,body.policy_state,body.permissions,body.evidence,actor='founder'))

@app.get('/api/discovery/queries')
def queries():return core.search_queries()

@app.get('/api/positioning',dependencies=[Depends(guard)])
def positioning():return execute(agents.positioning_report)

@app.post('/api/memory',dependencies=[Depends(guard)])
def memory_create(body:MemoryIn):return {'id':execute(lambda:core.add_memory(**body.model_dump(),actor='founder'))}

@app.get('/api/memory')
def memories(scope:Optional[str]=None):return core.read_memory(scope)

@app.post('/api/tasks',dependencies=[Depends(guard)])
def task_create(body:TaskIn):return {'id':execute(lambda:core.create_task(**body.model_dump()))}

@app.post('/api/activity',dependencies=[Depends(guard)])
def activity(body:ActivityIn):return execute(lambda:core.manual_activity(**body.model_dump(),actor='founder'))

@app.post('/api/supervisor/cycle',dependencies=[Depends(guard)])
def supervisor():return execute(agents.supervisor_cycle)

@app.get('/api/tasks')
def tasks():return core.list_tasks()

@app.post('/api/tasks/{task_id}/done',dependencies=[Depends(guard)])
def task_done(task_id:str):return {'result':execute(lambda:core.finish_task(task_id))}

@app.get('/api/audit')
def audit(limit:int=100):return core.list_events(min(max(limit,1),500))

@app.get('/api/audit/verify')
def audit_verify():return core.verify_audit()

@app.get('/api/checkpoints/{day}',dependencies=[Depends(guard)])
def checkpoint(day:int):return execute(lambda: agents.mentor_report(day))

UI=r'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Acquisition Mission Control</title><style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b1020;color:#e9edf8}*{box-sizing:border-box}body{margin:0}main{max-width:1280px;margin:auto;padding:28px}h1{margin:0 0 6px;font-size:28px}h2{font-size:18px;margin:0 0 14px}.muted{color:#9caac6}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px;gap:12px}.tag{background:#213052;color:#b2d4ff;padding:7px 11px;border-radius:8px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.card,.panel{border:1px solid #2c3650;background:#151e32;border-radius:15px;padding:18px}.metric{font-weight:750;font-size:30px;margin-top:8px}.panel{margin-top:18px}.twocol{display:grid;grid-template-columns:1fr 1fr;gap:18px}input,textarea,select{width:100%;padding:10px;background:#0e172a;border:1px solid #34415e;color:#fff;border-radius:8px;margin:5px 0 11px;font:inherit}textarea{min-height:70px}button{background:#588efa;border:0;border-radius:8px;color:#fff;padding:10px 14px;cursor:pointer;font-weight:600}button.secondary{background:#2b3a59}button:hover{filter:brightness(1.12)}table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:11px;border-bottom:1px solid #34415e;vertical-align:top}a{color:#88b9ff;overflow-wrap:anywhere}.tablebox{overflow-x:auto}small{color:#9caac6}.actions{display:flex;gap:8px;flex-wrap:wrap}.status{color:#b7dbff}pre{white-space:pre-wrap;word-break:break-word;max-height:350px;overflow:auto;color:#c9d6ec;font-size:12px}.note{padding:10px;background:#223657;border-radius:8px}.error{color:#ff9f9f}.success{color:#95e3bd}@media(max-width:750px){.cards,.twocol{grid-template-columns:1fr}main{padding:14px}header{display:block}}
</style></head><body><main><header><div><h1>AI Acquisition Mission Control</h1><div class="muted">AI-first • Local-first • Founder-governed • Audit memory</div></div><div class="tag">Outbound automation OFF</div></header><div class="cards" id="metrics"></div>
<div class="twocol"><section class="panel"><h2>Add Opportunity / Account</h2><form id="add"><label>Founder API token (kept in this page only)</label><input id="founder-token" type="password" autocomplete="off" placeholder="Configure ACQ_ADMIN_TOKEN first"><label>Title / business need</label><input name="title" placeholder="Example: RAG integration for knowledge search" required><label>Source URL (real source only)</label><input name="source_url" type="url" placeholder="https://..." required><label>Source</label><input name="source" value="manual"><label>Demand type</label><select name="demand_type"><option value="EXPLICIT_PROJECT">Published project (unverified)</option><option value="POTENTIAL_ACCOUNT">Potential buyer (intent unverified)</option></select><label>Description / buyer requirements</label><textarea name="description"></textarea><button type="submit">Record candidate + audit</button></form></section><section class="panel"><h2>Acquisition Agent Controls</h2><p class="muted">Integrations run only when you provide their official credentials and register source permissions.</p><div class="actions"><button id="brave">Run search discovery</button><button id="freelancer" class="secondary">Freelancer API</button><button id="positioning" class="secondary">Analyze positioning</button><button id="checkpoint" class="secondary">Day-30 checkpoint</button><button id="supervisor" class="secondary">Run supervisor</button></div><p><small>Search requires BRAVE_API_KEY; Freelancer requires FREELANCER_OAUTH_TOKEN. Neither is supplied.</small></p><div class="note">No browser scraping of Upwork, Fiverr or LinkedIn. Candidates are not verified buyers. Founder authorizes external communication.</div><div id="result" style="margin-top:12px"></div></section></div>
<section class="panel"><h2>Opportunity Queue</h2><div class="tablebox"><table><thead><tr><th>Candidate</th><th>Type / score</th><th>Topics</th><th>Status</th><th>Founder's action</th></tr></thead><tbody id="leads"></tbody></table></div></section>
<section class="panel"><h2>Record a Founder Action</h2><p class="muted">Capture even offline conversations, buyer objections and commercial decisions in the same audit trail.</p><form id="activity"><div class="twocol"><div><select name="action"><option>RESEARCH_NOTE</option><option>SOURCE_CHECK</option><option>MESSAGE_SENT_MANUALLY</option><option>APPLICATION_SUBMITTED</option><option>PROPOSAL_SENT</option><option>FOLLOWUP_SENT</option><option>REPLY_RECEIVED</option><option>MEETING_HELD</option><option>BUYER_OBJECTION</option><option>PROPOSAL_REVIEWED</option><option>PRICE_DECISION</option><option>EXPERIMENT_DECISION</option></select></div><div><input name="lead_id" placeholder="Lead ID (optional)"></div></div><textarea name="summary_text" required placeholder="What happened? Decision, evidence, blocker, lesson..."></textarea><input name="evidence" placeholder="Supporting source URL or reference (optional)"><button>Record audited activity</button></form></section>
<div class="twocol"><section class="panel"><h2>Persistent Observer</h2><div class="actions"><button class="secondary" onclick="showAudit()">Latest audit events</button><button class="secondary" onclick="verifyAudit()">Verify hash chain</button></div><pre id="audit"></pre></section><section class="panel"><h2>Memory & Learning</h2><div class="muted">Only evidence-backed facts; hypotheses are stored separately.</div><form id="memory"><select name="kind"><option>LESSON</option><option>FACT</option><option>HYPOTHESIS</option><option>DECISION</option><option>RULE</option></select><input name="scope" value="business" placeholder="Memory scope"><textarea name="statement" placeholder="What did we learn?" required></textarea><input name="source" placeholder="Evidence: lead URL, event ID, or note" required><button>Save memory</button></form><pre id="memories"></pre></section></div><p class="muted">This prototype stores data locally in SQLite. For deployment, configure authentication, backups, encrypted disks, secure secrets and audit exports.</p></main>
<script>
async function api(path,method='GET',data){let token=document.querySelector('#founder-token').value;let opts={method,headers:{'Content-Type':'application/json',...(token?{'X-Admin-Token':token}:{})}};if(data!==undefined)opts.body=JSON.stringify(data);let r=await fetch('/api'+path,opts);let j=await r.json();if(!r.ok)throw Error(j.detail||JSON.stringify(j));return j;}
const esc=(s)=>String(s??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function showResult(d){document.querySelector('#result').innerHTML='<pre>'+esc(typeof d==='string'?d:JSON.stringify(d,null,2))+'</pre>'}
async function refresh(){let [s,ls,mem]=await Promise.all([api('/dashboard'),api('/leads'),api('/memory')]);document.querySelector('#metrics').innerHTML=[['Candidates',s.leads],['Paying clients',s.paying_clients+' / '+s.target_clients],['Audit events',s.events],['Open tasks',s.open_tasks]].map(([k,v])=>'<div class="card"><div class="muted">'+esc(k)+'</div><div class="metric">'+esc(v)+'</div></div>').join('');document.querySelector('#leads').innerHTML=ls.map(l=>'<tr><td><strong>'+esc(l.title)+'</strong><br><a href="'+esc(l.source_url)+'" target="_blank" rel="noopener noreferrer">Original source</a><br><small>'+esc(l.source)+'</small></td><td>'+esc(l.demand_type)+'<br><strong>'+esc(l.score)+'/100</strong></td><td>'+esc(l.categories.join(', '))+'</td><td>'+esc(l.status)+'</td><td class="actions"><button class="secondary" onclick="draft(\''+l.id+'\')">Draft</button><button class="secondary" onclick="analyze(\''+l.id+'\')">Analyze</button><button class="secondary" onclick="offers(\''+l.id+'\')">Offers</button><button class="secondary" onclick="review(\''+l.id+'\')">Review</button></td></tr>').join('')||'<tr><td colspan="5" class="muted">No candidates yet. Add a real opportunity or run an approved connector.</td></tr>';document.querySelector('#memories').textContent=mem.slice(0,5).map(x=>x.kind+': '+x.statement+' ['+x.source+']').join('\n')}
document.querySelector('#founder-token').addEventListener('change',()=>refresh().catch(e=>showResult(e.message)));
document.querySelector('#add').onsubmit=async ev=>{ev.preventDefault();let d=Object.fromEntries(new FormData(ev.target));try{showResult(await api('/leads','POST',d));await refresh()}catch(e){showResult('ERROR: '+e.message)}};
document.querySelector('#memory').onsubmit=async ev=>{ev.preventDefault();let d=Object.fromEntries(new FormData(ev.target));d.confidence=.7;try{showResult(await api('/memory','POST',d));await refresh()}catch(e){showResult('ERROR: '+e.message)}};
document.querySelector('#activity').onsubmit=async ev=>{ev.preventDefault();let d=Object.fromEntries(new FormData(ev.target));if(!d.lead_id)delete d.lead_id;try{showResult(await api('/activity','POST',d));await refresh()}catch(e){showResult('ERROR: '+e.message)}};
document.querySelector('#supervisor').onclick=()=>run('/supervisor/cycle','POST',{});
document.querySelector('#brave').onclick=()=>run('/discovery/brave','POST',{});document.querySelector('#freelancer').onclick=()=>{let q=prompt('Authorized Freelancer project-search query?','machine learning');if(q)run('/discovery/freelancer','POST',{query:q})};document.querySelector('#positioning').onclick=()=>run('/positioning');document.querySelector('#checkpoint').onclick=()=>run('/checkpoints/30');
async function run(path,method='GET',body){try{showResult(await api(path,method,body));await refresh()}catch(e){showResult('ERROR: '+e.message)}}
async function draft(id){try{let d=await api('/leads/'+id+'/draft','POST');showResult(d.result?.draft||d);await refresh()}catch(e){showResult('ERROR: '+e.message)}}
async function offers(id){try{showResult(await api('/leads/'+id+'/offers'))}catch(e){showResult('ERROR: '+e.message)}}
async function analyze(id){try{showResult(await api('/leads/'+id+'/analyze','POST'));await refresh()}catch(e){showResult('ERROR: '+e.message)}}
async function review(id){try{let d=await api('/leads/'+id);let l=d.lead;let msg='Status: '+l.status+' | Buyer verified: '+l.buyer_verified+'\nURL: '+l.source_url+'\nDescription: '+l.description+'\nRecent events: '+JSON.stringify(d.history.slice(0,3),null,2);showResult(msg)}catch(e){showResult('ERROR: '+e.message)}}
async function showAudit(){let d=await api('/audit?limit=20');document.querySelector('#audit').textContent=d.map(e=>e.seq+' '+e.at+' '+e.actor+' / '+e.action+' '+e.target_id).join('\n')}
async function verifyAudit(){document.querySelector('#audit').textContent=JSON.stringify(await api('/audit/verify'),null,2)}
refresh().catch(e=>showResult(e.message));
</script></body></html>'''

@app.get('/',response_class=HTMLResponse)
def index():return UI
