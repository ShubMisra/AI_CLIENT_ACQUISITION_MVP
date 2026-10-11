"""Source intelligence and policy registry (new module)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class SourceRecord:
    source_id: str
    name: str
    category: str
    url: str
    terms_url: Optional[str] = None
    policy_evidence_ref: Optional[str] = None
    access_method: str = "manual"  # manual|official_api|approved_feed|scoped_browser
    lifecycle_state: str = "MANUAL_ONLY"
    policy_state: str = "UNKNOWN"
    demand_type_primary: str = "EXPLICIT_PROJECT"
    requires_human_intervention: bool = True
    is_active: bool = False
    notes: str = ""


def load_registry() -> List[SourceRecord]:
    return []
