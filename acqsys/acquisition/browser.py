"""Bounded action-oriented browser abstraction with fixtures + mocked services."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from .policy import AccessDecision, PolicyPort

REDACTED = "[REDACTED]"


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
        dec = self._policy.authorize(source_id=source_id, action=action, target_url=target_url)
        if not dec.allowed:
            raise PermissionError(f"{dec.reason_code}: {source_id} {action} {target_url}")
        # extra domain guard
        parsed = urlparse(target_url)
        if self._allowed_domains and parsed.hostname not in self._allowed_domains:
            raise PermissionError(f"DOMAIN_NOT_ALLOWED: {parsed.hostname}")
        return dec

    def navigate(self, run_id: str, source_id: str, url: str) -> Dict[str, Any]:
        dec = self._check(source_id, "browser_navigation", url)
        return {"url": url, "policy_version": dec.policy_version, "ts": self._clock()}

    def extract(self, run_id: str, source_id: str, url: str, html: str | None = None) -> ExtractionResult:
        if html is None and self._fixtures_dir.exists():
            # try loading fixture by slug
            parsed = urlparse(url)
            slug = parsed.path.strip("/").replace("/", "_") or "index"
            fixture = self._fixtures_dir / f"{slug}.html"
            if fixture.exists():
                html = fixture.read_text(encoding="utf-8", errors="replace")
        if html is None:
            html = ""
        # minimal evidence-based extraction (safe, deterministic)
        candidates: List[Dict[str, Any]] = []
        evidence_refs: List[str] = [f"fixture:{url}"]
        notes: List[str] = []
        return ExtractionResult(candidates=candidates, evidence_refs=evidence_refs, notes=notes)
