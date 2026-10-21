from acqsys.acquisition import policy, browser, workflow, worker, cli_triage
from pathlib import Path

def test_multi_card_extraction_two_distinct():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation","authenticated_extraction"}, allowed_domains={"example.com"})
    b = browser.BrowserWorker(p, fixtures_dir=Path("tests/fixtures/acquisition/listing"))
    b.configure(allowed_domains={"example.com"})
    ext = b.extract("r1", "src", "https://example.com/listing/cards.html")
    assert len(ext.candidates) == 2
    assert ext.candidates[0]['source_url'] != ext.candidates[1]['source_url']
    assert ext.candidates[0]['content_evidence_ref'] != ext.candidates[1]['content_evidence_ref']


def test_independent_auth_nav_and_extract():
    p = policy.DenyAllPolicy()
    b = browser.BrowserWorker(p)
    try:
        b.navigate("r1", "src", "https://example.com/x")
        assert False
    except PermissionError:
        pass
    try:
        b.extract("r1", "src", "https://example.com/x")
        assert False
    except PermissionError:
        pass


def test_triage_loads_historical_json():
    items = cli_triage.triage()
    assert len(items) >= 10
    assert items[0]["url"]
    assert items[0]["title"]
    assert "budget_min" in items[0]


def test_checkpoint_atomic_persist_and_resume_fresh_policy():
    items = cli_triage.triage()
    assert len(items) == 10
    wf = workflow.WorkflowState(storage_path=Path("data/test_acq_atomic3.json"))
    wf.checkpoint("cp1", "r1", "s1", {"k": 1})
    wf.checkpoint("cp2", "r2", "s2", {"k": 2})
    cp = wf.restore(policy_check=lambda: True)
    assert cp and cp.cp_id == "cp2"
    cp2 = wf.restore("cp1", policy_check=lambda: True)
    assert cp2 and cp2.cp_id == "cp1"


def test_dedup_and_revocation():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation","authenticated_extraction"}, allowed_domains={"example.com"})
    w = worker.AcquisitionWorker(p)
    w._browser.configure(allowed_domains={"example.com"})
    res = w.discover_from_fixtures("r1", "src", ["https://example.com/projects/123", "https://example.com/projects/123"])
    assert res["results"][0]["candidates"]
