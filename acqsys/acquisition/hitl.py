"""Human-in-the-loop (founder) intervention modeling."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InterventionRequest:
    req_id: str
    reason: str
    source_id: str
    target_url: str | None = None
    required_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


class InterventionQueue:
    def __init__(self):
        self._items: List[InterventionRequest] = []

    def request(self, req_id: str, reason: str, source_id: str, target_url: str | None = None, required_actions: List[str] | None = None) -> InterventionRequest:
        ir = InterventionRequest(req_id=req_id, reason=reason, source_id=source_id, target_url=target_url, required_actions=required_actions or [])
        self._items.append(ir)
        return ir

    def pending(self) -> List[InterventionRequest]:
        return [i for i in self._items if not i.resolved]

    def resolve(self, req_id: str) -> None:
        for i in self._items:
            if i.req_id == req_id:
                i.resolved = True
                return
