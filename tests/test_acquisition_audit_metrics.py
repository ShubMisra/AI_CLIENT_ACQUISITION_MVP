from acqsys.acquisition import audit, metrics, hitl

def test_audit_redacts():
    a = audit.AuditLog()
    a.record("e1", "r1", "src", "TEST", {"token": "abc123", "auth": "Bearer XYZ"})
    ev = a.events()[0]
    payload = ev["payload"]
    assert payload["token"] == audit.REDACTED
    assert audit.REDACTED in payload["auth"]


def test_metrics_counters():
    m = metrics.MetricsCollector()
    m.inc_candidates("src", 2)
    m.inc_denials("src", 1)
    m.inc_interventions("src", 1)
    m.add_founder_minutes("src", 5.5)
    d = m.get("src")
    assert d["candidates_found"] == 2
    assert d["denials"] == 1
    assert d["founder_minutes_est"] == 5.5


def test_hitl_queue():
    q = hitl.InterventionQueue()
    q.request("req1", "LOGIN_MFA", "src", target_url="https://example.com")
    assert q.pending()
    q.resolve("req1")
    assert not q.pending()
