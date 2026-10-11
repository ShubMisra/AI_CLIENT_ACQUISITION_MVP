from acqsys.acquisition import policy, worker

def test_worker_triage_unverified():
    w = worker.AcquisitionWorker(policy.DenyAllPolicy())
    items = w.triage_unverified()
    assert len(items) == 10
    for i in items:
        assert i["verification_status"] == "UNVERIFIED"
        assert i["availability_status"] == "UNKNOWN"
        assert "current_opening" in i


def test_worker_discovery_blocks_by_default():
    w = worker.AcquisitionWorker(policy.DenyAllPolicy())
    res = w.discover_from_fixtures("r1", "src", ["https://example.com/projects/123"])
    assert res["run_id"] == "r1"
    assert res["results"] == []  # blocked by deny


def test_worker_discovery_allows_with_policy():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation"}, allowed_domains={"example.com"})
    w = worker.AcquisitionWorker(p)
    w._browser.configure(allowed_domains={"example.com"})  # type: ignore
    res = w.discover_from_fixtures("r1", "src", ["https://example.com/projects/123"])
    assert res["results"]
