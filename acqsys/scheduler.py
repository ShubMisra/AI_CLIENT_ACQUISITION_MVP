"""Optional local periodic supervisor. Keeps running only while this process stays alive.
Run: python -m acqsys.scheduler --every-hours 24
Does not call paid APIs, send messages, scrape sites, or purchase anything.
"""
import argparse
import time
from . import agents,core
p=argparse.ArgumentParser();p.add_argument('--every-hours',type=int,default=24);p.add_argument('--once',action='store_true')
a=p.parse_args()
if not 1<=a.every_hours<=168:raise SystemExit('Hours must be 1..168')
while True:
    try:
        result=agents.supervisor_cycle()
        print('Supervisor cycle done: tasks created',len(result['result']['generated_tasks']),flush=True)
    except Exception as exc:
        core.record_event('scheduler','CYCLE_FAILED',{'error':str(exc)[:200]})
        print('Supervisor cycle failed:',exc,flush=True)
    if a.once:break
    time.sleep(a.every_hours*3600)
