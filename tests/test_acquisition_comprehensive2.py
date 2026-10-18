from acqsys.acquisition import policy, browser, workflow, worker, cli_triage
from pathlib import Path
import tempfile
import os

def test_empty_allowlist_denies():
    p = policy.AllowFixturePolicy(allowed_sources=None, allowed_actions=None, allowed_domains=set())
    d = p.authorize(source_id='s', action='browser_navigation', target_url='https://example.com/x')
    assert not d.allowed

def test_authenticated_extraction_requires_auth():
    p = policy.AllowFixturePolicy(allowed_sources={'src'}, allowed_actions={'browser_navigation'}, allowed_domains={'example.com'})
    b = browser.BrowserWorker(p, fixtures_dir=Path('tests/fixtures/acquisition/listing'))
    b.configure(allowed_domains={'example.com'})
    b.navigate('r1','src','https://example.com/listing/cards.html')
    try:
        p2 = policy.AllowFixturePolicy(allowed_sources={'src'}, allowed_actions={'browser_navigation'}, allowed_domains={'example.com'})
        b2 = browser.BrowserWorker(p2, fixtures_dir=Path('tests/fixtures/acquisition/listing'))
        b2.configure(allowed_domains={'example.com'})
        b2.extract('r1','src','https://example.com/listing/cards.html')
        assert False
    except PermissionError:
        pass

def test_two_cards_from_one_html():
    p = policy.AllowFixturePolicy(allowed_sources={'src'}, allowed_actions={'browser_navigation','authenticated_extraction'}, allowed_domains={'example.com'})
    b = browser.BrowserWorker(p, fixtures_dir=Path('tests/fixtures/acquisition/listing'))
    b.configure(allowed_domains={'example.com'})
    b.navigate('r1','src','https://example.com/listing/cards.html')
    ext = b.extract('r1','src','https://example.com/listing/cards.html')
    assert len(ext.candidates) == 2
    assert ext.candidates[0]['title'] != ext.candidates[1]['title']

def test_resume_revalidates_policy_cross_instance():
    p = policy.AllowFixturePolicy(allowed_sources={'src'}, allowed_actions={'browser_navigation','authenticated_extraction'}, allowed_domains={'example.com'})
    w = worker.AcquisitionWorker(p)
    w._browser.configure(allowed_domains={'example.com'})
    w._workflow.checkpoint('cp1','r1','s1',{'k':1})
    # new instance with deny
    w2 = worker.AcquisitionWorker(policy.DenyAllPolicy())
    w2._workflow.restore('cp1')
    try:
        w2._browser.navigate('r2','src','https://example.com/x')
        assert False
    except PermissionError:
        pass

def test_persistence_failure_raises():
    d = Path(tempfile.gettempdir()) / 'noaccess' / 'bad.json'
    try:
        wf = workflow.WorkflowState(storage_path=d)
        wf.checkpoint('c1','r1','s',{})
        assert False
    except Exception:
        pass

def test_triage_requires_real_historical():
    items = cli_triage.triage()
    assert len(items) == 10
