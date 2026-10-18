"""Triage CLI helpers for historical lead candidates."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import json


def _load_from_json() -> List[Dict[str, Any]]:
    base = Path(__file__).parent.parent.parent
    candidates: List[Dict[str, Any]] = []
    seen = set()
    for loc in [
        base / "lead_candidates_2026-10-10.json",
        base / "data" / "lead_candidates_2026-10-10.json",
        base / "tests" / "fixtures" / "acquisition" / "lead_candidates_2026-10-10.json",
        base / "fixtures" / "lead_candidates_2026-10-10.json",
    ]:
        if loc.exists():
            try:
                raw = loc.read_text(encoding="utf-8", errors="replace")
                data = json.loads(raw)
            except Exception as e:
                raise FileNotFoundError(f"failed_to_load_historical: {loc} ({e})") from e
            items = data if isinstance(data, list) else (data.get("candidates") or [])
            for item in items:
                url = item.get("source_url") or item.get("url")
                if url and url not in seen:
                    seen.add(url)
                    candidates.append(item)
    if not candidates:
        raise FileNotFoundError("lead_candidates_2026-10-10.json not found")
    return candidates


def triage() -> List[Dict[str, Any]]:
    items = _load_from_json()
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(items):
        out.append(
            {
                "id": item.get("id") or f"hist-{i+1:03d}",
                "url": item.get("source_url") or item.get("url") or "",
                "title": item.get("title") or "",
                "category_hint": item.get("category_hint") or item.get("category") or "OTHER",
                "technical_fit": "HYPOTHESIS",
                "current_opening": "UNKNOWN",
                "verification_tasks": [
                    "Verify post freshness and scope",
                    "Confirm buyer identity/contact policy",
                    "Check budget/currency grounding",
                ],
                "proposed_founder_action": "REVIEW_MANUALLY",
                "verification_status": "UNVERIFIED",
                "availability_status": "UNKNOWN",
                "source": item.get("source"),
                "demand_type": item.get("demand_type"),
                "currency": item.get("currency"),
                "budget_min": item.get("budget_min"),
                "budget_max": item.get("budget_max"),
                "description": item.get("description"),
            }
        )
    return out
