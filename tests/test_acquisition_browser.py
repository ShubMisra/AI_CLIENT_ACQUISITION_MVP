from pathlib import Path
from acqsys.acquisition import browser, policy

def test_browser_fixture_extract_minimal():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation"}, allowed_domains={"example.com"})
    b = browser.BrowserWorker(p, fixtures_dir=Path("tests/fixtures/acquisition"))
    b.configure(allowed_domains={"example.com"})
    nav = b.navigate("r1", "src", "https://example.com/projects/123")
    assert nav["url"].startswith("https://example.com")
    ext = b.extract("r1", "src", "https://example.com/projects/123")
    assert isinstance(ext.candidates, list)
    assert ext.evidence_refs


def test_browser_blocks_unauthorized():
    p = policy.DenyAllPolicy()
    b = browser.BrowserWorker(p)
    try:
        b.navigate("r1", "src", "https://example.com/x")
        assert False
    except PermissionError:
        pass
