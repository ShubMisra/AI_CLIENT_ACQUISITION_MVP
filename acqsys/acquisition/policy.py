"""Permission gate for acquisition actions (dependency-injected).

Implements the Codex PolicyPort contract (default-deny).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


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
        return AccessDecision(allowed=False, reason_code="DENY_ALL_DEFAULT", policy_version=None, expires_at=None, permitted_scope=())


class AllowFixturePolicy:
    def __init__(self, allowed_sources: set[str] | None = None, allowed_actions: set[str] | None = None, allowed_domains: set[str] | None = None, policy_version: str | None = "v1"):
        self.allowed_sources = set(allowed_sources) if allowed_sources is not None else None
        self.allowed_actions = set(allowed_actions) if allowed_actions is not None else None
        self.allowed_domains = set(allowed_domains) if allowed_domains is not None else None
        self.policy_version = policy_version

    def authorize(self, *, source_id: str, action: str, target_url: str) -> AccessDecision:
        try:
            parsed = urlparse(target_url)
            hostname = parsed.hostname or ""
        except Exception:
            return AccessDecision(allowed=False, reason_code="INVALID_TARGET_URL", policy_version=self.policy_version)

        if self.allowed_sources is not None and source_id not in self.allowed_sources:
            return AccessDecision(allowed=False, reason_code="SOURCE_NOT_ALLOWED", policy_version=self.policy_version)
        if self.allowed_actions is not None and action not in self.allowed_actions:
            return AccessDecision(allowed=False, reason_code="ACTION_NOT_ALLOWED", policy_version=self.policy_version)
        if self.allowed_domains is not None:
            if not self.allowed_domains:
                return AccessDecision(allowed=False, reason_code="DOMAIN_NOT_ALLOWED", policy_version=self.policy_version)
            if hostname not in self.allowed_domains:
                ok = False
                for d in self.allowed_domains:
                    if hostname == d or hostname.endswith(f".{d}"):
                        ok = True
                        break
                if not ok:
                    return AccessDecision(allowed=False, reason_code="DOMAIN_NOT_ALLOWED", policy_version=self.policy_version)
        return AccessDecision(allowed=True, reason_code="ALLOWED", policy_version=self.policy_version)
