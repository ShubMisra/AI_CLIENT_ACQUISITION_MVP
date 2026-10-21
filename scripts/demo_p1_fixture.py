"""Run the P1 fixture pilot in a temporary database; no network access."""
import json
import gc
import os
import tempfile
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory(prefix='acq-p1-demo-') as temporary:
        os.environ['ACQ_DB_PATH'] = str(Path(temporary) / 'demo.db')
        os.environ['ACQ_ADMIN_TOKEN'] = 'fixture-demo-token-only'
        from acqsys import core
        from acqsys.integration import (FixtureTransport, run_fixture_pilot,
                                        prepare_founder_candidates)

        core.init_db()
        with core.founder_session('fixture-demo-token-only'):
            core.register_source('fixture','fixture.example','Fixture source','MARKETPLACE',actor='founder')
            core.update_source_policy('fixture','CONFIRMED',{
                'browser_navigation':True,'authenticated_extraction':True,
                'allowed_paths':['/listing'],'rate_limit_per_hour':20,
            },'Demo fixture scope only',actor='founder')
            for state in ('EVALUATING','POLICY_REVIEW','AWAITING_FOUNDER',
                          'ONBOARDING','PILOT_READY','PILOT_RUNNING'):
                core.transition_source('fixture',state,actor='founder')
            core.register_source('manual_fixture','manual.example',
                                 'Synthetic founder record','MARKETPLACE',actor='founder')
            for state in ('EVALUATING','POLICY_REVIEW','AWAITING_FOUNDER','MANUAL_ONLY'):
                core.transition_source('manual_fixture',state,actor='founder')
        listing='https://fixture.example/listing/cards.html'
        transport=FixtureTransport({listing:
            '<div class="card"><h2>Document classifier</h2><p>Build a classifier.</p>'
            '<a href="/projects/123">View</a></div>'
            '<div class="card"><h2>Forecasting model</h2><p>Build a forecast.</p>'
            '<a href="/projects/124">View</a></div>'})
        first=run_fixture_pilot(source_id='fixture',urls=[listing],transport=transport,run_id='demo_first')
        second=run_fixture_pilot(source_id='fixture',urls=[listing],transport=transport,run_id='demo_repeat')
        founder=prepare_founder_candidates(source_id='manual_fixture',
            candidates=[{'source_url':'https://manual.example/project/1',
                         'title':'Synthetic founder supplied ML request',
                         'description':'Test-only document classification requirement; buyer unverified.',
                         'budget_min':500,'currency':'USD'}],
            run_id='demo_founder',founder_token='fixture-demo-token-only')
        founder_repeat=prepare_founder_candidates(source_id='manual_fixture',
            candidates=[{'source_url':'https://manual.example/project/1',
                         'title':'Synthetic founder supplied ML request',
                         'description':'Test-only document classification requirement; buyer unverified.',
                         'budget_min':500,'currency':'USD'}],
            run_id='demo_founder',founder_token='fixture-demo-token-only')
        print(json.dumps({
            'synthetic_test_data_only':True,
            'new_leads':sum(row.get('created') is True for row in first['results']),
            'duplicates_on_repeat':sum(row.get('created') is False for row in second['results']),
            'founder_provided_new':sum(row['created'] for row in founder['results']),
            'founder_duplicates_on_repeat':sum(not row['created'] for row in founder_repeat['results']),
            'scored_leads':sum(lead['score'] > 0 for lead in core.list_leads()),
            'unverified_leads':sum(not lead['buyer_verified'] for lead in core.list_leads()),
            'founder_tasks':len(core.list_tasks()),
            'unsent_proposal_drafts':sum(len(core.list_artifacts(lead['id'])) for lead in core.list_leads()),
            'paying_clients':core.summary()['paying_clients'],
            'audit_valid':core.verify_audit()['valid'],
            'fixture_reads':len(transport.reads),
        },sort_keys=True))
        # sqlite3 context managers commit but do not close; collect any read
        # connections before Windows removes the temporary database.
        gc.collect()


if __name__ == '__main__':
    main()
