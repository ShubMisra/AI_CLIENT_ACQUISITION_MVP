from acqsys.acquisition import policy, browser, workflow, worker
from pathlib import Path

def test_browser_extract_produces_candidates():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation","authenticated_extraction"}, allowed_domains={"example.com"})
    b = browser.BrowserWorker(p, fixtures_dir=Path("tests/fixtures/acquisition"))
    b.configure(allowed_domains={"example.com"})
    ext = b.extract("r1", "src", "https://example.com/projects/123")
    assert len(ext.candidates) > 0
    assert ext.candidates[0]["title"]


def test_deny_all_default_strict():
    p = policy.DenyAllPolicy()
    d = p.authorize(source_id="s", action="browser_navigation", target_url="https://x.com")
    assert not d.allowed


def test_workflow_restore_latest():
    wf = workflow.WorkflowState(storage_path=Path("data/test_acq_wf_new.json"))
    wf.checkpoint("cp1", "r1", "step1", {"a": 1})
    wf.checkpoint("cp2", "r2", "step2", {"b": 2})
    cp = wf.restore()
    assert cp is not None and cp.cp_id == "cp2"


def test_workflow_restore_specific():
    wf = workflow.WorkflowState(storage_path=Path("data/test_acq_wf2_new.json"))
    wf.checkpoint("cp1", "r1", "step1", {"a": 1})
    wf.checkpoint("cp2", "r2", "step2", {"b": 2})
    cp = wf.restore("cp1")
    assert cp is not None and cp.cp_id == "cp1"
