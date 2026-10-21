"""Bounded action-oriented browser abstraction with fixtures."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List
from urllib.parse import urljoin, urlparse
import ipaddress
import socket


@dataclass
class ExtractionResult:
    candidates: List[Dict[str, Any]]
    evidence_refs: List[str]
    notes: List[str]


class BrowserWorker:
    def __init__(self, policy, fixtures_dir: Path | None = None, clock: Callable[[], str] | None = None):
        self._policy = policy
        self._fixtures_dir = fixtures_dir or Path(__file__).parent.parent.parent / "tests" / "fixtures" / "acquisition"
        self._clock = clock or (lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"))
        self._allowed_domains: set[str] | None = None

    def configure(self, *, allowed_domains: set[str] | None = None, **kwargs):
        if allowed_domains is not None:
            self._allowed_domains = set(allowed_domains)
        return self

    def _validate_target(self, target_url: str) -> tuple:
        try:
            parsed = urlparse(target_url)
            if parsed.scheme not in ("http", "https"):
                raise PermissionError("INVALID_SCHEME")
            hostname = parsed.hostname or ""
            if not hostname:
                raise PermissionError("INVALID_TARGET_URL")
            if hostname in ("localhost",) or hostname.endswith((".local", ".internal")):
                raise PermissionError("PRIVATE_HOST_FORBIDDEN")
            try:
                infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
                for entry in infos:
                    addr = ipaddress.ip_address(entry[4][0])
                    if not addr.is_global:
                        raise PermissionError("PRIVATE_HOST_FORBIDDEN")
            except PermissionError:
                raise
            except Exception:
                pass
        except PermissionError:
            raise
        except Exception:
            raise PermissionError("INVALID_TARGET_URL")
        return parsed, hostname

    def _check(self, source_id: str, action: str, target_url: str):
        parsed, hostname = self._validate_target(target_url)
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
        return {"url": url, "policy_version": getattr(dec, "policy_version", None), "ts": self._clock()}

    def extract(self, run_id: str, source_id: str, url: str, html: str | None = None) -> ExtractionResult:
        dec = self._check(source_id, "authenticated_extraction", url)
        if html is None and self._fixtures_dir.exists():
            parsed = urlparse(url)
            for fixture in [
                self._fixtures_dir / f"{(parsed.path.strip('/').replace('/', '_') or 'index')}.html",
                self._fixtures_dir / Path(parsed.path).name,
                self._fixtures_dir / "listing" / Path(parsed.path).name,
            ]:
                if fixture.exists():
                    html = fixture.read_text(encoding="utf-8", errors="replace")
                    break
        if html is None:
            html = ""

        candidates: List[Dict[str, Any]] = []
        parsed = urlparse(url)
        evidence_refs: List[str] = [f"fixture:{parsed.path or parsed.netloc}", f"url:{url}"]

        card_blocks = re.findall(r"<div[^>]*class=['\"][^'\"]*card[^'\"]*['\"][^>]*>(.*?)</div>", html, re.IGNORECASE | re.DOTALL)
        if len(card_blocks) < 2:
            card_blocks = re.findall(r"<div[^>]*>(.*?)</div>", html, re.IGNORECASE | re.DOTALL)

        if len(card_blocks) >= 2:
            for i in range(min(2, len(card_blocks))):
                block = card_blocks[i]
                m = re.search(r"<h[12][^>]*>(.*?)</h[12]>", block, re.IGNORECASE | re.DOTALL)
                title = re.sub(r"<[^>]+>", " ", m.group(1)).strip() if m else f"card-{i+1}"
                title = re.sub(r"\s+", " ", title)
                mp = re.search(r"<p[^>]*>(.*?)</p>", block, re.IGNORECASE | re.DOTALL)
                desc = None
                if mp:
                    desc = re.sub(r"<[^>]+>", " ", mp.group(1)).strip()
                    desc = re.sub(r"\s+", " ", desc)[:400]
                ma = re.search(r"<a[^>]*href=['\"]([^'\"]+)['\"]", block, re.IGNORECASE)
                card_url = ma.group(1) if ma else url
                card_url = urljoin(url, card_url)
                parsed_card = urlparse(card_url)
                if parsed_card.scheme not in ("http", "https"):
                    card_url = url
                cand = {
                    "source_id": source_id,
                    "source_url": card_url,
                    "title": title,
                    "description": desc,
                    "demand_type": "EXPLICIT_PROJECT",
                    "verification_status": "UNVERIFIED",
                    "availability_status": "UNKNOWN",
                    "content_evidence_ref": f"fixture:{parsed.path or parsed.netloc}:card{i}",
                    "access_evidence_ref": "policy-evidence-reference",
                    "observed_at_utc": self._clock(),
                }
                candidates.append(cand)
        else:
            m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = re.sub(r"\s+", " ", m.group(1)).strip() if m else "fixture-item"
            mp = re.search(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
            desc = re.sub(r"<[^>]+>", " ", mp.group(1)).strip()[:400] if mp else None
            cand = {
                "source_id": source_id,
                "source_url": url,
                "title": title,
                "description": desc,
                "demand_type": "EXPLICIT_PROJECT",
                "verification_status": "UNVERIFIED",
                "availability_status": "UNKNOWN",
                "content_evidence_ref": f"fixture:{parsed.path or parsed.netloc}:card0",
                "access_evidence_ref": "policy-evidence-reference",
                "observed_at_utc": self._clock(),
            }
            candidates.append(cand)
        return ExtractionResult(candidates=candidates, evidence_refs=evidence_refs, notes=["fixture-based-extraction"])
