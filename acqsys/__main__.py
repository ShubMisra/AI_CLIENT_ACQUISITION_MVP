import argparse
import json
from . import core, agents

parser=argparse.ArgumentParser(description='AI client acquisition local-first command line')
sub=parser.add_subparsers(dest='cmd',required=True)
sub.add_parser('init');sub.add_parser('stats');sub.add_parser('sources');sub.add_parser('audit-verify');sub.add_parser('positioning');sub.add_parser('supervisor')
p=sub.add_parser('serve');p.add_argument('--port',type=int,default=8765)
p=sub.add_parser('import-json');p.add_argument('file')
p=sub.add_parser('add');p.add_argument('--title',required=True);p.add_argument('--url',required=True);p.add_argument('--description',default='');p.add_argument('--type',default='EXPLICIT_PROJECT')
p=sub.add_parser('brave');p.add_argument('--type',default='EXPLICIT_PROJECT')
p=sub.add_parser('freelancer');p.add_argument('query')
p=sub.add_parser('rss');p.add_argument('url');p.add_argument('--approved',action='store_true');p.add_argument('--type',default='EXPLICIT_PROJECT')
p=sub.add_parser('checkpoint');p.add_argument('day',type=int,choices=[30,60,90])
p=sub.add_parser('leads');p.add_argument('--limit',type=int,default=20)
p=sub.add_parser('draft');p.add_argument('lead_id')
p=sub.add_parser('verify');p.add_argument('lead_id');p.add_argument('--note',required=True)
p=sub.add_parser('transition');p.add_argument('lead_id');p.add_argument('status');p.add_argument('--note',default='');p.add_argument('--payment-reference')
args=parser.parse_args()
if args.cmd=='serve':
 import uvicorn
 print('Local dashboard: http://127.0.0.1:'+str(args.port))
 uvicorn.run('acqsys.app:app',host='127.0.0.1',port=args.port,reload=False)
else:
 core.init_db()
 if args.cmd=='init':result={'db':str(core.DB_PATH)}
 elif args.cmd=='stats':result=core.summary()
 elif args.cmd=='audit-verify':result=core.verify_audit()
 elif args.cmd=='sources':result=core.search_queries()
 elif args.cmd=='positioning':result=agents.positioning_report()
 elif args.cmd=='supervisor':result=agents.supervisor_cycle()
 elif args.cmd=='leads':result=core.list_leads(args.limit)
 elif args.cmd=='import-json':
  from pathlib import Path
  data=json.loads(Path(args.file).read_text(encoding='utf8'))
  if not isinstance(data,list) or len(data)>200:raise SystemExit('JSON must be a list of at most 200 candidates')
  result=[core.add_lead(v,actor='founder_research_import') for v in data]
 elif args.cmd=='add':result=core.add_lead({'source_url':args.url,'title':args.title,'description':args.description,'demand_type':args.type},'founder')
 elif args.cmd=='brave':result=agents.brave_discover(demand_type=args.type)
 elif args.cmd=='rss':result=agents.rss_discover(args.url,demand_type=args.type,approved=args.approved)
 elif args.cmd=='freelancer':result=agents.freelancer_discover(args.query)
 elif args.cmd=='checkpoint':result=agents.mentor_report(args.day)
 elif args.cmd=='draft':result=agents.evidence_driven_proposal(args.lead_id)
 elif args.cmd=='verify':result=core.verify_lead(args.lead_id,True,args.note)
 elif args.cmd=='transition':result=core.transition_lead(args.lead_id,args.status,note=args.note,payment_reference=args.payment_reference)
 print(json.dumps(result,indent=2,default=str))
