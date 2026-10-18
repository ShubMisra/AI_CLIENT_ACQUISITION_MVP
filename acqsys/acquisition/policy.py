"""Permission gate for acquisition actions (dependency-injected)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
import ipaddress


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason_code: str
    policy_version: str | None = None
    expires_at: str | None = None
    permitted_scope: tuple[str, ...] = ()


class PolicyPort(Protocol):
    def authorize(self, *, source_id: str, action: str, target_url: str) -> AccessDecision: ...


class DenyAllPolicy:
    def authorize(self, *, source_id: str, action: str, target_url: str) -> AccessDecision:
        return AccessDecision(allowed=False, reason_code="DENY_ALL_DEFAULT")


class AllowFixturePolicy:
    def __init__(self, allowed_sources: set[str] | None = None, allowed_actions: set[str] | None = None, allowed_domains: set[str] | None = None, policy_version: str | None = "v1"):
        self.allowed_sources = allowed_sources
        self.allowed_actions = allowed_actions
        self.allowed_domains = allowed_domains
        self.policy_version = policy_version

    def authorize(self, *, source_id: str, action: str, target_url: str) -> AccessDecision:
        try:
            parsed = urlparse(target_url)
            if parsed.scheme not in ("http", "https"):
                return AccessDecision(allowed=False, reason_code="INVALID_TARGET_URL")
            hostname = parsed.hostname or ""
            if not hostname:
                return AccessDecision(allowed=False, reason_code="INVALID_TARGET_URL")
            if hostname in ("localhost",) or hostname.endswith((".local", ".internal")):
                return AccessDecision(allowed=False, reason_code="PRIVATE_HOST_FORBIDDEN")
            try:
                import socket
                infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
                for entry in infos:
                    addr = ipaddress.ip_address(entry[4][0])
                    if not addr.is_global:
                        return AccessDecision(allowed=False, reason_code="PRIVATE_HOST_FORBIDDEN")
            except Exception:
                pass
        except Exception:
            return AccessDecision(allowed=False, reason_code="INVALID_TARGET_URL")

        if self.allowed_sources is None or source_id not in self.allowed_sources:
            return AccessDecision(allowed=False, reason_code="SOURCE_NOT_ALLOWED")
        if self.allowed_actions is None or action not in self.allowed_actions:
            return AccessDecision(allowed=False, reason_code="ACTION_NOT_ALLOWED")
        if self.allowed_domains is None or not self.allowed_domains:
            return AccessDecision(allowed=False, reason_code="DOMAIN_NOT_ALLOWED")
        if hostname not in self.allowed_domains:
            ok = False
            for d in self.allowed_domains:
                if hostname == d or hostname.endswith(f".{d}"):
                    ok = True
                    break
            if not ok:
                return AccessDecision(allowed=False, reason_code="DOMAIN_NOT_ALLOWED")
        return AccessDecision(allowed=True, reason_code="ALLOWED", policy_version=self.policy_version)
