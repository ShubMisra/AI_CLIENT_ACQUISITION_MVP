# Acquisition authorization interface — v1

This is the committed contract for the Codex core and Kilo's injected acquisition modules. Import `AccessDecision` and `CorePolicyPort` from `acqsys.core`; inject a `PolicyPort` compatible object into collectors. No collector may infer permission from a login, a search result, a caller boolean, or a source name.

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason_code: str
    policy_version: str | None = None
    expires_at: str | None = None
    permitted_scope: tuple[str, ...] = ()

class PolicyPort(Protocol):
    def authorize(self, *, source_id: str, action: str, target_url: str) -> AccessDecision: ...

# Production adapter: core.CorePolicyPort().authorize(...)
# Functional form: core.policy_check(source_id, action, target_url)
```

Call before **each** network operation, including a new page navigation or API request. The call records `POLICY_CHECKED` on allowance and `ACTION_DENIED` on denial in the audit chain. It consumes one unit of the source's persisted rate budget on allowance. Callers must stop on `allowed=False`; they must not retry under another source ID. Source IDs identify the service actually contacted: a Brave API query is `brave_search_api`, a Freelancer API query is `freelancer_official_api`, and an RSS feed uses its separately registered source ID. Returned third-party URLs are candidates, never authorization for a fetch.

Supported automated actions: `official_api`, `feed_read`, `browser_navigation`, `authenticated_extraction`. `messaging` and `application_submission` always deny in this port. A source requires lifecycle `ACTIVE` or `PILOT_RUNNING`, policy `CONFIRMED`, unexpired review, explicit action permission, a target within the registered host and allowed path prefixes, an unrestricted account, and remaining rate budget. Unknown source/action, missing evidence, manual-only, review/pause states, expiry, target mismatch, and rate exhaustion deny by default. Reason codes are stable uppercase strings such as `UNKNOWN_SOURCE`, `UNKNOWN_ACTION`, `INACTIVE_SOURCE`, `POLICY_UNCONFIRMED`, `POLICY_EXPIRED`, `ACTION_NOT_ALLOWED`, `TARGET_OUT_OF_SCOPE`, `ACCOUNT_RESTRICTED`, `RATE_LIMITED`, and `OUTBOUND_PROHIBITED`.

`source_access_policy` stores `policy_version`, `allowed_paths` (JSON path prefixes), `account_state`, `rate_limit_per_hour`, and `feed_read`. The founder must register and activate a source, confirm policy evidence, and configure these fields through trusted local core calls. The JSON catalog is research data, not live authorization. `allowed_paths` defaults to `/` for the registered host; use a narrower prefix when the reviewed permission is narrower. Caller code must still use a guarded HTTP client: this policy check is an authorization decision, not a complete DNS-rebinding defense.

Founder writes in the API require `X-Admin-Token` matching configured `ACQ_ADMIN_TOKEN`. If unset, API writes fail closed. Core founder-only decisions require the `founder_session(token)` context; an `actor='founder'` string alone grants nothing. CLI founder commands should use the same configured token. Do not put the token in audit payloads, URLs, or exception text.

Candidate storage remains `core.add_lead()` with `EXPLICIT_PROJECT` or `POTENTIAL_ACCOUNT`; an extracted candidate stays unverified. Kilo may map its `POTENTIAL_DEMAND` DTO to `POTENTIAL_ACCOUNT` in an adapter. Never mark buyer verification, availability, contact, or payment from extraction alone.
