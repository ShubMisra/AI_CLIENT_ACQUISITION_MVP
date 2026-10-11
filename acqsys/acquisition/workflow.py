"""Safe workflow with pause/resume and checkpoints."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Checkpoint:
    cp_id: str
    run_id: str
    state: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"cp_id": self.cp_id, "run_id": self.run_id, "state": self.state, "data": data_redact(self.data)}


def data_redact(obj: Any) -> Any:
    from .audit import redact

    return redact(obj)


class WorkflowState:
    def __init__(self, storage_path: Path | None = None):
        self._storage_path = storage_path or (Path(__file__).parent.parent.parent / "data" / "acq_workflow.json")
        self._state: Dict[str, Any] = {"run_id": None, "status": "IDLE", "cursor": 0, "meta": {}}
        self._checkpoints: List[Checkpoint] = []
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

    def pause(self, reason: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self._state["status"] = "PAUSED"
        self._state["meta"] = data_redact({"reason": reason, "meta": meta or {}})
        return dict(self._state)

    def resume(self, run_id: str | None = None) -> Dict[str, Any]:
        if run_id:
            self._state["run_id"] = run_id
        self._state["status"] = "RUNNING"
        return dict(self._state)

    def checkpoint(self, cp_id: str, run_id: str, state: str, data: Dict[str, Any]) -> Checkpoint:
        cp = Checkpoint(cp_id=cp_id, run_id=run_id, state=state, data=data)
        self._checkpoints.append(cp)
        try:
            with self._storage_path.open("w", encoding="utf-8") as f:
                json.dump({"state": self._state, "checkpoints": [c.to_dict() for c in self._checkpoints]}, f, indent=2, sort_keys=True)
        except Exception:
            pass
        return cp

    def status(self) -> Dict[str, Any]:
        return dict(self._state)
