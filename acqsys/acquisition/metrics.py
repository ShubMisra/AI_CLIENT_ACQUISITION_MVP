"""Source performance measurements."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class SourceMetrics:
    source_id: str
    candidates_found: int = 0
    denials: int = 0
    interventions: int = 0
    founder_minutes_est: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "candidates_found": self.candidates_found,
            "denials": self.denials,
            "interventions": self.interventions,
            "founder_minutes_est": round(self.founder_minutes_est, 2),
        }


class MetricsCollector:
    def __init__(self):
        self._m: Dict[str, SourceMetrics] = {}

    def inc_candidates(self, source_id: str, n: int = 1) -> None:
        self._m.setdefault(source_id, SourceMetrics(source_id=source_id)).candidates_found += n

    def inc_denials(self, source_id: str, n: int = 1) -> None:
        self._m.setdefault(source_id, SourceMetrics(source_id=source_id)).denials += n

    def inc_interventions(self, source_id: str, n: int = 1) -> None:
        self._m.setdefault(source_id, SourceMetrics(source_id=source_id)).interventions += n

    def add_founder_minutes(self, source_id: str, m: float) -> None:
        self._m.setdefault(source_id, SourceMetrics(source_id=source_id)).founder_minutes_est += m

    def get(self, source_id: str) -> Dict[str, Any]:
        return self._m.get(source_id, SourceMetrics(source_id=source_id)).to_dict()

    def all(self) -> List[Dict[str, Any]]:
        return sorted((v.to_dict() for v in self._m.values()), key=lambda x: x["source_id"])
