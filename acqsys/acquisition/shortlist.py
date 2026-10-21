"""Small demonstrable candidate shortlist format."""
from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timezone


def shortlist(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for c in candidates:
        item = {
            "title": c.get("title") or "",
            "source_url": c.get("source_url") or "",
            "observed_date": c.get("observed_at_utc") or c.get("posted_at") or datetime.now(timezone.utc).date().isoformat(),
            "ai_ml_requirement": c.get("ai_ml_requirement") or c.get("description") or "AI/ML related",
            "budget_if_known": c.get("budget") or c.get("budget_text") or (f"{c.get('currency')} {c.get('budget_min')}" if c.get("budget_min") else "UNKNOWN"),
            "evidence": c.get("content_evidence_ref") or c.get("access_evidence_ref") or "",
            "verification_status": c.get("verification_status") or "UNVERIFIED",
            "proposed_next_human_action": "REVIEW_MANUALLY",
        }
        out.append(item)
    return out
