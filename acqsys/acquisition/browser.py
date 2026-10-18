"""Bounded action-oriented browser abstraction with fixtures."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List
from urllib.parse import urlparse

from .policy import AccessDecision, PolicyPort


@dataclass
class BrowserAction:
    type: str
    target: str | None = None
    data: Dict[str, Any] | None = None


@dataclass
class ExtractionResult:
    candidates: List[Dict[str, Any]]
    evidence_refs: List[str]
    notes: List[str]


@dataclass
class BrowserRun:
    run_id: str
    source_id: str
    actions_taken: List[BrowserAction]
    extractions: List[ExtractionResult]
    policy_decisions: List[Dict[str, Any]]
    denials: List[Dict[str, Any]]
    interventions: List[Dict[str, Any]]
    checkpoints: List[Dict[str, Any]]


class BrowserWorker:
    def __init__(self, policy: PolicyPort, fixtures_dir: Path | None = None, clock: Callable[[], str] | None = None):
        self._policy = policy
        self._fixtures_dir = fixtures_dir or Path(__file__).parent.parent.parent / "tests" / "fixtures" / "acquisition"
        self._clock = clock or (lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"))
        self._allowed_domains: set[str] = set()
        self._max_steps = 10
        self._max_bytes = 1_000_000
        self._rate_limit_per_run = 100

    def configure(self, *, allowed_domains: set[str] | None = None, max_steps: int | None = None, max_bytes: int | None = None):
        if allowed_domains is not None:
            self._allowed_domains = set(allowed_domains)
        if max_steps is not None:
            self._max_steps = max_steps
        if max_bytes is not None:
            self._max_bytes = max_bytes
        return self

    def _check(self, source_id: str, action: str, target_url: str) -> AccessDecision:
        try:
            parsed = urlparse(target_url)
            if parsed.scheme not in ("http", "https"):
                raise PermissionError("INVALID_SCHEME")
            hostname = parsed.hostname or ""
        except Exception:
            raise PermissionError("INVALID_TARGET_URL")
        dec = self._policy.authorize(source_id=source_id, action=action, target_url=target_url)
        if not dec.allowed:
            raise PermissionError(f"{dec.reason_code}: {source_id} {action} {target_url}")
        if self._allowed_domains is not None:
            if not self._allowed_domains:
                raise PermissionError(f"DOMAIN_NOT_ALLOWED: {hostname}")
            if hostname not in self._allowed_domains:
                ok = False
                for d in self._allowed_domains:
                    if hostname == d or hostname.endswith(f".{d}"):
                        ok = True
                        break
                if not ok:
                    raise PermissionError(f"DOMAIN_NOT_ALLOWED: {hostname}")
        return dec

    def navigate(self, run_id: str, source_id: str, url: str) -> Dict[str, Any]:
        dec = self._check(source_id, "browser_navigation", url)
        return {"url": url, "policy_version": dec.policy_version, "ts": self._clock()}

    def extract(self, run_id: str, source_id: str, url: str, html: str | None = None) -> ExtractionResult:
        dec = self._check(source_id, "authenticated_extraction", url)
        if html is None and self._fixtures_dir.exists():
            parsed = urlparse(url)
            slug = parsed.path.strip("/").replace("/", "_") or "index"
            candidates_paths = []
            candidates_paths.append(self._fixtures_dir / f"{slug}.html")
            candidates_paths.append(self._fixtures_dir / Path(parsed.path).name)
            listing = self._fixtures_dir / "listing" / Path(parsed.path).name
            if listing.exists():
                candidates_paths.append(listing)
            for fixture in candidates_paths:
                if fixture.exists():
                    html = fixture.read_text(encoding="utf-8", errors="replace")
                    break
        if html is None:
            html = ""

        candidates: List[Dict[str, Any]] = []
        parsed = urlparse(url)
        evidence_refs: List[str] = [f"fixture:{parsed.path or parsed.netloc}", f"url:{url}"]

        card_titles = re.findall(r"<h[12][^>]*>(.*?)</h[12]>", html, re.IGNORECASE | re.DOTALL)
        card_paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)

        if len(card_titles) >= 2:
            for i in range(min(2, len(card_titles))):
                title = re.sub(r"<[^>]+>", " ", card_titles[i]).strip()
                title = re.sub(r"\s+", " ", title)
                desc = None
                if i < len(card_paras):
                    desc = re.sub(r"<[^>]+>", " ", card_paras[i]).strip()
                    desc = re.sub(r"\s+", " ", desc)
                    if len(desc) > 400:
                        desc = desc[:400]
                cand = {
                    "source_id": source_id,
                    "source_url": url,
                    "title": title or f"card-{i+1}",
                    "description": desc,
                    "demand_type": "EXPLICIT_PROJECT",
                    "verification_status": "UNVERIFIED",
                    "availability_status": "UNKNOWN",
                    "content_evidence_ref": f"fixture:{parsed.path or parsed.netloc}",
                    "access_evidence_ref": "policy-evidence-reference",
                    "observed_at_utc": self._clock(),
                }
                candidates.append(cand)
        else:
            m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = m.group(1).strip() if m else None
            if not title:
                m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
                title = re.sub(r"<[^>]+>", " ", m.group(1)).strip() if m else (Path(parsed.path).name or "fixture-item")
            title = re.sub(r"\s+", " ", title)
            cand = {
                "source_id": source_id,
                "source_url": url,
                "title": title,
                "description": None,
                "demand_type": "EXPLICIT_PROJECT",
                "verification_status": "UNVERIFIED",
                "availability_status": "UNKNOWN",
                "content_evidence_ref": f"fixture:{parsed.path or parsed.netloc}",
                "access_evidence_ref": "policy-evidence-reference",
                "observed_at_utc": self._clock(),
            }
            mp = re.search(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
            if mp:
                desc = re.sub(r"<[^>]+>", " ", mp.group(1)).strip()
                desc = re.sub(r"\s+", " ", desc)
                if desc:
                    cand["description"] = desc[:400]
            candidates.append(cand)
        return ExtractionResult(candidates=candidates, evidence_refs=evidence_refs, notes=["fixture-based-extraction"])
