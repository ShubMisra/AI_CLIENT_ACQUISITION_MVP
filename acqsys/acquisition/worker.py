"""Permission-aware acquisition worker orchestrator."""
from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import audit, browser, hitl, lead_qual, metrics, policy, source_intel, workflow


class AcquisitionWorker:
    def __init__(self, policy_port: policy.PolicyPort | None = None):
        self._policy = policy_port or policy.DenyAllPolicy()
        self._browser = browser.BrowserWorker(self._policy)
        self._audit = audit.AuditLog()
        self._metrics = metrics.MetricsCollector()
        self._hitl = hitl.InterventionQueue()
        self._workflow = workflow.WorkflowState()
        self._sources: List[source_intel.SourceRecord] = source_intel.load_registry()

    def record_event(self, run_id: str, source_id: str, kind: str, payload: Dict[str, Any]) -> None:
        ev_id = str(uuid.uuid4())
        self._audit.record(ev_id, run_id, source_id, kind, payload)

    def triage_unverified(self) -> List[Dict[str, Any]]:
        from . import cli_triage

        return cli_triage.triage()

    def discover_from_fixtures(self, run_id: str, source_id: str, urls: List[str]) -> Dict[str, Any]:
        results = []
        for url in urls:
            try:
                nav = self._browser.navigate(run_id, source_id, url)
                ext = self._browser.extract(run_id, source_id, url)
                cands = [lead_qual.qual(c) for c in ext.candidates]
                cands = lead_qual.deduplicate(cands)
                self._metrics.inc_candidates(source_id, len(cands))
                results.append({"url": url, "candidates": cands, "nav": nav})
            except PermissionError as e:
                self._metrics.inc_denials(source_id, 1)
                self.record_event(run_id, source_id, "DENIAL", {"url": url, "reason": str(e)})
            except Exception as e:
                self.record_event(run_id, source_id, "ERROR", {"url": url, "error_type": type(e).__name__})
        return {"run_id": run_id, "results": results}
