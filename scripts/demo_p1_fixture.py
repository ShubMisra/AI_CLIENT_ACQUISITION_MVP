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
        from acqsys.integration import FixtureTransport, run_fixture_pilot

        core.init_db()
        with core.founder_session('fixture-demo-token-only'):
            core.register_source('fixture','fixture.example','Fixture source','MARKETPLACE',actor='founder')
            core.update_source_policy('fixture','CONFIRMED',{
                'browser_navigation':True,'authenticated_extraction':True,
                'allowed_paths':['/projects'],'rate_limit_per_hour':20,
            },'Demo fixture scope only',actor='founder')
            for state in ('EVALUATING','POLICY_REVIEW','AWAITING_FOUNDER',
                          'ONBOARDING','PILOT_READY','PILOT_RUNNING'):
                core.transition_source('fixture',state,actor='founder')
        urls=['https://fixture.example/projects/123','https://fixture.example/projects/124']
        transport=FixtureTransport({
            urls[0]:'<h1>Document classifier</h1><p>Build a classifier.</p>',
            urls[1]:'<h1>Forecasting model</h1><p>Build a forecast.</p>',
        })
        first=run_fixture_pilot(source_id='fixture',urls=urls,transport=transport,run_id='demo_first')
        second=run_fixture_pilot(source_id='fixture',urls=urls,transport=transport,run_id='demo_repeat')
        print(json.dumps({
            'fixture_only':True,
            'new_leads':sum(row.get('created') is True for row in first['results']),
            'duplicates_on_repeat':sum(row.get('created') is False for row in second['results']),
            'unverified_leads':sum(not lead['buyer_verified'] for lead in core.list_leads()),
            'founder_tasks':len(core.list_tasks()),
            'paying_clients':core.summary()['paying_clients'],
            'audit_valid':core.verify_audit()['valid'],
        },sort_keys=True))
        # sqlite3 context managers commit but do not close; collect any read
        # connections before Windows removes the temporary database.
        gc.collect()


if __name__ == '__main__':
    main()
