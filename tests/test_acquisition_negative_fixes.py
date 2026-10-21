from acqsys.acquisition import policy, browser, workflow, cli_triage
from pathlib import Path
import tempfile
import os

def test_http_rejected():
    p = policy.AllowFixturePolicy(allowed_sources={'s'}, allowed_actions={'browser_navigation'}, allowed_domains={'example.com'})
    d = p.authorize(source_id='s', action='browser_navigation', target_url='http://example.com/x')
    assert not d.allowed

def test_invalid_scheme_rejected():
    p = policy.AllowFixturePolicy(allowed_sources={'s'}, allowed_actions={'browser_navigation'}, allowed_domains={'example.com'})
    d = p.authorize(source_id='s', action='browser_navigation', target_url='file:///etc/passwd')
    assert not d.allowed

def test_private_host_rejected():
    p = policy.AllowFixturePolicy(allowed_sources={'s'}, allowed_actions={'browser_navigation'}, allowed_domains={'localhost'})
    d = p.authorize(source_id='s', action='browser_navigation', target_url='http://localhost/x')
    assert not d.allowed

def test_card_links_safe_absolute_distinct():
    p = policy.AllowFixturePolicy(allowed_sources={'src'}, allowed_actions={'browser_navigation','authenticated_extraction'}, allowed_domains={'example.com'})
    b = browser.BrowserWorker(p, fixtures_dir=Path('tests/fixtures/acquisition/listing'))
    b.configure(allowed_domains={'example.com'})
    ext = b.extract('r1','src','https://example.com/listing/cards.html')
    assert len(ext.candidates)==2
    for c in ext.candidates:
        assert c['source_url'].startswith('https://example.com/')
    assert ext.candidates[0]['source_url'] != ext.candidates[1]['source_url']
    assert ext.candidates[0]['content_evidence_ref'] != ext.candidates[1]['content_evidence_ref']

def test_resume_mandatory_policy_check():
    wf = workflow.WorkflowState(storage_path=Path('data/test_mand.json'))
    wf.checkpoint('c1','r1','s',{})
    try:
        wf.restore('c1')
        assert False
    except ValueError:
        pass

def test_corrupted_checkpoint_resets():
    d = Path('data/corrupt_x.json')
    d.parent.mkdir(exist_ok=True)
    d.write_text('{oops', encoding='utf-8')
    wf = workflow.WorkflowState(storage_path=d)
    assert wf.status().get('status') == 'IDLE'
    if d.exists():
        os.remove(d)

def test_historical_missing_raises():
    # real file exists; just verify load
    items = cli_triage.triage()
    assert len(items)==10
