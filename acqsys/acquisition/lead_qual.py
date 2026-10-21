"""Lead qualification and deduplication (new module)."""
from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlparse


def canonicalize_url(u: str) -> str:
    try:
        p = urlparse(u)
        return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path}".rstrip("/") or u
    except Exception:
        return u


def deduplicate(cands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for c in cands:
        key = canonicalize_url(c.get("source_url", ""))
        if key and key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def qualify(cand: Dict[str, Any]) -> Dict[str, Any]:
    q = dict(cand)
    q.setdefault("verification_status", "UNVERIFIED")
    q.setdefault("availability_status", "UNKNOWN")
    q.setdefault("demand_type", cand.get("demand_type", "EXPLICIT_PROJECT"))
    q.setdefault("content_evidence_ref", cand.get("content_evidence_ref"))
    q.setdefault("access_evidence_ref", cand.get("access_evidence_ref"))
    q.setdefault("observed_at_utc", cand.get("observed_at_utc"))
    return q


# backward compatibility
qual = qualify
