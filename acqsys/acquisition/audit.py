"""Redacted audit events for acquisition runs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

_SECRET_KEYS = re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|authorization|auth|credential[s]?|key)")
_BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]{8,}")

REDACTED = "[REDACTED]"


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: REDACTED if _SECRET_KEYS.search(str(k)) else redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        s = _BEARER_RE.sub(REDACTED, obj)
        return s
    return obj


@dataclass
class AuditEvent:
    event_id: str
    run_id: str
    source_id: str
    kind: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "run_id": self.run_id, "source_id": self.source_id, "kind": self.kind, "payload": redact(self.payload)}


class AuditLog:
    def __init__(self):
        self._events: List[AuditEvent] = []

    def record(self, event_id: str, run_id: str, source_id: str, kind: str, payload: Dict[str, Any]) -> AuditEvent:
        ev = AuditEvent(event_id=event_id, run_id=run_id, source_id=source_id, kind=kind, payload=payload)
        self._events.append(ev)
        return ev

    def events(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events]
