"""Loopback-only founder dashboard. Header token stays in page memory."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .controller import Controller
from .policy import require_founder


PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Engineering supervisor</title>
<style>body{font:16px system-ui;max-width:760px;margin:3rem auto;padding:0 1rem}
button,input,textarea{font:inherit;margin:.3rem;padding:.5rem}textarea{width:95%;height:8rem}
pre{white-space:pre-wrap;background:#f3f3f3;padding:1rem}</style>
<h1>Engineering supervisor</h1><p>SUPERVISED mock mode. Founder approval is required for each action.</p>
<label>Founder token <input id="token" type="password" autocomplete="off"></label>
<p><button onclick="call('GET','/api/queue')">Refresh queue</button>
<button onclick="call('GET','/api/runs')">Runs</button>
<button onclick="call('GET','/api/proposals')">Proposals</button>
<button onclick="call('POST','/api/emergency-stop')">Emergency stop</button>
<button onclick="call('POST','/api/emergency-clear')">Clear stop</button></p>
<p><button onclick="call('GET','/api/budgets')">Show budgets</button>
<label>Daily tokens <input id="tokens" type="number" min="1"></label>
<label>Daily USD <input id="cost" type="number" min="0.01" step="0.01"></label>
<button onclick="call('POST','/api/budgets',{daily_tokens:Number(document.getElementById('tokens').value),daily_cost_usd:Number(document.getElementById('cost').value)})">Set budgets</button></p>
<label>Task ID <input id="task"></label>
<p><button onclick="call('POST','/api/tasks/'+v('task')+'/approve',{approved:true,reason:'Founder reviewed task'})">Approve task</button>
<button onclick="call('POST','/api/tasks/'+v('task')+'/approve',{approved:false,reason:'Founder rejected task'})">Reject task</button>
<button onclick="call('POST','/api/tasks/'+v('task')+'/start',{mode:'mock'})">Start mock</button></p>
<label>Run ID <input id="run"></label>
<p><button onclick="call('POST','/api/runs/'+v('run')+'/refresh')">Check CI</button>
<button onclick="call('GET','/api/runs/'+v('run')+'/review')">Review evidence</button>
<button onclick="call('POST','/api/runs/'+v('run')+'/publish')">Approve draft PR</button>
<button onclick="call('POST','/api/runs/'+v('run')+'/pause')">Pause</button>
<button onclick="call('POST','/api/runs/'+v('run')+'/reject',{reason:'Founder rejected result'})">Reject</button></p>
<label>Proposal ID <input id="proposal"></label>
<p><button onclick="call('POST','/api/proposals/'+v('proposal')+'/publish')">Create reviewed GitHub issue</button>
<button onclick="call('POST','/api/proposals/'+v('proposal')+'/reject')">Reject proposal</button></p>
<details><summary>Register founder-authored task JSON</summary><textarea id="taskjson"></textarea>
<button onclick="register()">Register</button></details><pre id="out">No action yet.</pre>
<script>function v(id){return encodeURIComponent(document.getElementById(id).value)}
async function call(method,url,body){try{const r=await fetch(url,{method,headers:{'X-Orch-Token':document.getElementById('token').value,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.getElementById('out').textContent='Request failed'}}
function register(){try{call('POST','/api/tasks',JSON.parse(document.getElementById('taskjson').value))}catch(e){document.getElementById('out').textContent='Invalid JSON'}}</script></html>'''


def create_app(controller: Controller) -> FastAPI:
    app = FastAPI(title='Human-supervised engineering orchestrator')

    @app.middleware('http')
    async def founder_gate(request: Request, call_next):
        if request.url.path.startswith('/api/'):
            try:
                require_founder(request.headers.get('X-Orch-Token'))
            except PermissionError:
                return JSONResponse({'detail': 'founder authentication required'}, status_code=403)
        return await call_next(request)

    def response(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PermissionError:
            raise HTTPException(status_code=403, detail='action denied')
        except ValueError:
            raise HTTPException(status_code=400, detail='invalid request')

    @app.get('/', response_class=HTMLResponse)
    def home():
        return PAGE

    @app.get('/api/queue')
    def queue():
        return response(controller.queue)

    @app.get('/api/runs')
    def runs():
        return controller.store.list_runs()

    @app.get('/api/budgets')
    def budgets():
        return controller.store.budgets()

    @app.post('/api/budgets')
    def set_budgets(body: dict):
        response(controller.store.set_budgets, body.get('daily_tokens'), body.get('daily_cost_usd'))
        return controller.store.budgets()

    @app.get('/api/runs/{run_id}')
    def run(run_id: str):
        return response(controller.store.run, run_id)

    @app.get('/api/runs/{run_id}/review')
    def review(run_id: str):
        return response(controller.store.review_packet, run_id)

    @app.get('/api/proposals')
    def proposals():
        return controller.store.list_proposals()

    @app.post('/api/tasks')
    def add_task(body: dict, request: Request):
        return {'task_id': response(controller.register, body, request.headers.get('X-Orch-Token'))}

    @app.post('/api/tasks/{task_id}/approve')
    def approve(task_id: str, body: dict, request: Request):
        response(controller.approve, task_id, request.headers.get('X-Orch-Token'),
                 body.get('approved') is True, str(body.get('reason', '')))
        return {'ok': True}

    @app.post('/api/tasks/{task_id}/start')
    def start(task_id: str, body: dict, request: Request):
        return {'run_id': response(controller.start, task_id,
                                   request.headers.get('X-Orch-Token'), body.get('mode', 'mock'))}

    @app.post('/api/runs/{run_id}/refresh')
    def refresh(run_id: str):
        return response(controller.refresh_ci, run_id)

    @app.post('/api/runs/{run_id}/publish')
    def publish(run_id: str, request: Request):
        return {'pr_url': response(controller.publish, run_id, request.headers.get('X-Orch-Token'))}

    @app.post('/api/runs/{run_id}/pause')
    def pause(run_id: str, request: Request):
        response(controller.pause, run_id, request.headers.get('X-Orch-Token'))
        return {'ok': True}

    @app.post('/api/runs/{run_id}/reject')
    def reject(run_id: str, body: dict, request: Request):
        response(controller.reject, run_id, request.headers.get('X-Orch-Token'),
                 str(body.get('reason', '')))
        return {'ok': True}

    @app.post('/api/emergency-stop')
    def emergency(request: Request):
        response(controller.emergency_stop, request.headers.get('X-Orch-Token'))
        return {'ok': True}

    @app.post('/api/emergency-clear')
    def emergency_clear(request: Request):
        response(controller.clear_emergency, request.headers.get('X-Orch-Token'))
        return {'ok': True}

    @app.post('/api/proposals/{proposal_id}/publish')
    def proposal(proposal_id: str, request: Request):
        return {'task_id': response(controller.publish_proposal, proposal_id,
                                    request.headers.get('X-Orch-Token'))}

    @app.post('/api/proposals/{proposal_id}/reject')
    def reject_proposal(proposal_id: str, request: Request):
        response(controller.reject_proposal, proposal_id,
                 request.headers.get('X-Orch-Token'))
        return {'ok': True}

    return app
