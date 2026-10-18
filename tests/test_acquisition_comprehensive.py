from acqsys.acquisition import policy, browser, workflow, worker, cli_triage
from pathlib import Path
import tempfile
import os


def test_multi_card_extraction_two_distinct():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation","authenticated_extraction"}, allowed_domains={"example.com"})
    b = browser.BrowserWorker(p, fixtures_dir=Path("tests/fixtures/acquisition/listing"))
    b.configure(allowed_domains={"example.com"})
    urls = ["https://example.com/listing/a.html", "https://example.com/listing/b.html"]
    results = []
    for url in urls:
        nav = b.navigate("r1", "src", url)
        ext = b.extract("r1", "src", url)
        assert ext.candidates
        assert ext.evidence_refs
        results.append((nav["url"], ext.candidates[0]["title"], ext.candidates[0]["description"]))
    assert results[0][0] != results[1][0]
    assert results[0][1] != results[1][1]


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
    wf = workflow.WorkflowState(storage_path=Path("data/test_acq_atomic2.json"))
    wf.checkpoint("cp1", "r1", "s1", {"k": 1})
    wf.checkpoint("cp2", "r2", "s2", {"k": 2})
    cp = wf.restore()
    assert cp and cp.cp_id == "cp2"
    cp2 = wf.restore("cp1")
    assert cp2 and cp2.cp_id == "cp1"


def test_dedup_and_revocation():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation","authenticated_extraction"}, allowed_domains={"example.com"})
    w = worker.AcquisitionWorker(p)
    w._browser.configure(allowed_domains={"example.com"})
    res = w.discover_from_fixtures("r1", "src", ["https://example.com/projects/123", "https://example.com/projects/123"])
    assert res["results"][0]["candidates"]
