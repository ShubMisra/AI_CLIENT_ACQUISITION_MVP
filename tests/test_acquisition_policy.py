from acqsys.acquisition import policy

def test_deny_all_blocks():
    p = policy.DenyAllPolicy()
    d = p.authorize(source_id="s1", action="browser_navigation", target_url="https://example.com")
    assert not d.allowed


def test_allow_fixture_policy():
    p = policy.AllowFixturePolicy(allowed_sources={"src"}, allowed_actions={"browser_navigation"}, allowed_domains={"example.com"})
    d = p.authorize(source_id="src", action="browser_navigation", target_url="https://example.com/x")
    assert d.allowed
    d2 = p.authorize(source_id="bad", action="browser_navigation", target_url="https://example.com/x")
    assert not d2.allowed
