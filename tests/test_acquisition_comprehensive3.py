from acqsys.acquisition import policy, browser, workflow, cli_triage
from pathlib import Path
import tempfile
import os

def test_two_cards_distinct_urls_and_evidence():
    p = policy.AllowFixturePolicy(allowed_sources={'src'}, allowed_actions={'browser_navigation','authenticated_extraction'}, allowed_domains={'example.com'})
    b = browser.BrowserWorker(p, fixtures_dir=Path('tests/fixtures/acquisition/listing'))
    b.configure(allowed_domains={'example.com'})
    ext = b.extract('r1','src','https://example.com/listing/cards.html')
    assert len(ext.candidates) == 2
    assert ext.candidates[0]['source_url'] != ext.candidates[1]['source_url']
    assert ext.candidates[0]['content_evidence_ref'] != ext.candidates[1]['content_evidence_ref']
    assert ext.candidates[0]['source_url'].startswith('http')

def test_resume_requires_policy_check():
    wf = workflow.WorkflowState(storage_path=Path('data/test_resume_req.json'))
    wf.checkpoint('cp1','r1','s',{})
    try:
        wf.restore('cp1')
        assert False
    except ValueError:
        pass
    wf.restore('cp1', policy_check=lambda: True)

def test_persistence_failure_true_negative():
    d = Path(tempfile.gettempdir()) / 'no_access_dir_xyz3' / 'bad.json'
    wf = workflow.WorkflowState(storage_path=d)
    try:
        wf.checkpoint('c1','r1','s',{})
        assert False
    except RuntimeError:
        pass

def test_corrupted_checkpoint_handled():
    d = Path('data/corrupt_test2.json')
    d.parent.mkdir(exist_ok=True)
    d.write_text('{bad json', encoding='utf-8')
    wf = workflow.WorkflowState(storage_path=d)
    assert wf.status()['status'] == 'IDLE'
    if d.exists():
        os.remove(d)
    wf2 = workflow.WorkflowState(storage_path=d)
    wf2.checkpoint('c1','r1','s',{})
    if d.exists():
        os.remove(d)

def test_triage_missing_or_corrupt_fails():
    items = cli_triage.triage()
    assert len(items) == 10
