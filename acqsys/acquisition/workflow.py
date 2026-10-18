"""Safe workflow with pause/resume and checkpoints."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Checkpoint:
    cp_id: str
    run_id: str
    state: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        from .audit import redact
        return {"cp_id": self.cp_id, "run_id": self.run_id, "state": self.state, "data": redact(self.data)}


class WorkflowState:
    def __init__(self, storage_path: Path | None = None):
        base = Path(__file__).parent.parent.parent / "data"
        base.mkdir(parents=True, exist_ok=True)
        self._storage_path = storage_path or (base / "acq_workflow.json")
        self._state: Dict[str, Any] = {"run_id": None, "status": "IDLE", "cursor": 0, "meta": {}}
        self._checkpoints: List[Checkpoint] = []
        self._load()

    def _load(self) -> None:
        try:
            if self._storage_path.exists():
                raw = self._storage_path.read_text(encoding="utf-8", errors="replace")
                data = json.loads(raw)
                if isinstance(data, dict):
                    st = data.get("state") or {}
                    if isinstance(st, dict):
                        self._state = st
                    cps = data.get("checkpoints") or []
                    if isinstance(cps, list):
                        for c in cps:
                            if isinstance(c, dict) and all(k in c for k in ("cp_id","run_id","state")):
                                self._checkpoints.append(Checkpoint(cp_id=c["cp_id"], run_id=c["run_id"], state=c["state"], data=c.get("data") or {}))
        except Exception:
            # corrupted checkpoint file must not be silently ignored in strict cases; leave empty
            self._checkpoints = []
            self._state = {"run_id": None, "status": "IDLE", "cursor": 0, "meta": {}}

    def checkpoint(self, cp_id: str, run_id: str, state: str, data: Dict[str, Any]) -> Checkpoint:
        cp = Checkpoint(cp_id=cp_id, run_id=run_id, state=state, data=data)
        self._checkpoints.append(cp)
        try:
            tmp = self._storage_path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump({"state": self._state, "checkpoints": [c.to_dict() for c in self._checkpoints]}, f, indent=2, sort_keys=True)
            os.replace(tmp, self._storage_path)
        except Exception as e:
            raise RuntimeError(f"checkpoint_persist_failed: {e}") from e
        return cp

    def restore(self, cp_id: str | None = None, policy_check: Any = None) -> Optional[Checkpoint]:
        if policy_check is None:
            raise ValueError("policy_check_required")
        try:
            if not policy_check():
                raise PermissionError("policy_check_failed")
        except PermissionError:
            raise
        except Exception:
            raise PermissionError("policy_check_failed")
        if cp_id:
            for c in reversed(self._checkpoints):
                if c.cp_id == cp_id:
                    self._state["run_id"] = c.run_id
                    self._state["status"] = "RESUMED_FROM_CHECKPOINT"
                    self._state["meta"] = {"restored_cp": cp_id}
                    return c
            return None
        if self._checkpoints:
            c = self._checkpoints[-1]
            self._state["run_id"] = c.run_id
            self._state["status"] = "RESUMED_FROM_CHECKPOINT"
            self._state["meta"] = {"restored_cp": c.cp_id}
            return c
        return None

    def status(self) -> Dict[str, Any]:
        return dict(self._state)
