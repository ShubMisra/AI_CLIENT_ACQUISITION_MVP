# Identity and Secrets Specification

> Where credentials live, who can touch them, and how they never leak into
> prompts, logs, audit events, or git. Cross-references:
> [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §6 ·
> [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §5 ·
> [AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §7

## 1. Current State (verified)

No credential vault exists: `requirements.txt` contains only
fastapi/uvicorn/httpx/pydantic, and the only secret-adjacent mechanism is the
optional `ACQ_ADMIN_TOKEN` in `.env` (no `.env` present — see
[AS_IS_AUDIT.md](AS_IS_AUDIT.md) §3). This spec defines the target design;
implementation is backlog E7.

## 2. Vault Design

**Primary: Python `keyring`** (OS credential manager — Windows Credential
Manager on this host, Keychain on macOS, Secret Service on Linux):

- Cross-platform, no external service, no new infrastructure
- Namespace convention: `acqsys/<source_id>/<key_name>`
  (e.g., `acqsys/freelancer/oauth_token`, `acqsys/brave/api_key`)

**Fallback:** encrypted JSON vault at `data/vault.enc` (AES-GCM via
`cryptography`), file permissioned to the owner account, master key held in
keyring. Used only where no OS backend exists. Both paths expose the same
interface:

```python
vault_put(key_id, value)          # write, audit-logged by key_id only
vault_get(key_id) -> value        # read, audit-logged by key_id only
vault_delete(key_id)              # removal, audit-logged
vault_list() -> [key_ids]         # ids only, never values
```

**What is stored:** API keys (Brave), OAuth tokens (Freelancer), session
tokens/cookies for permitted authenticated reads, and the admin token.
**What is never stored:** employer/other-party credentials, payment
instruments, third parties' personal data.

## 3. Access by Reference — the Core Invariant

Application code and agents handle **key IDs only**:

- `vault_get` is called at the last possible moment (the boundary function
  that talks to the external API), and the secret object is never assigned
  into any dict/list that flows onward.
- Secrets never enter: LLM prompts or context · agent memory · audit event
  payloads · log lines · artifacts · task payloads · git-tracked files.
- Tests assert the negative: constructing any audit event whose serialized
  detail contains a stored secret value fails the suite (extension of
  `test_hash_chain_tampering_is_detected` discipline; new test in
  [EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) §regression).

## 4. Rotation and Expiry

| Rule | Detail |
|---|---|
| Expiry tracking | Vault records store `key_id, created_at, expires_at, source_id, rotated_at` metadata (metadata in DB, value in keyring) |
| Rotation | Manual, founder-approved. The agent raises a `ROTATION_DUE` task 7 days before expiry; founder generates the new credential through the provider's legitimate interface and replaces it via vault tooling |
| Old value | Zeroized on rotation (overwritten); rotation event hash-chained |
| Breach response | Immediate `vault_delete` + provider-side revocation (founder) + incident event — see §8 |

## 5. Vault Audit

Every vault operation writes an audit event containing **key ID, operation,
actor, outcome — never the value**:

```json
{"action":"VAULT_READ","detail":{"key_id":"acqsys/brave/api_key",
 "operation":"get","outcome":"ok"},"prev_hash":"…","hash":"…"}
```

`vault_list` output (ids) is safe to display; any UI or draft that receives a
value in error must treat it as a leak incident (§8). Redaction rules align
with [AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §7.

## 6. Session Isolation

- One browser profile per source
  ([BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §5);
  a session cookie belongs to exactly one source scope and is stored as
  `acqsys/<source_id>/session`, never exchanged across sources.
- Scoped credentials: each integration uses the narrowest token scope the
  provider offers (e.g., Freelancer OAuth read-only scope if available).
- The dashboard never displays values; it displays `key_id + last-four-of-
  fingerprint` (SHA-256 prefix) so the founder can confirm which credential
  is configured without exposing it.

## 7. MFA / CAPTCHA Challenge Interface

When a login or session encounters an MFA prompt or CAPTCHA:

1. **Pause** — the agent stops the run (SM-4 → WAITING_FOR_HUMAN) and raises
   a HITL task with evidence
   ([BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §3).
2. **Alert** — task appears in `/api/tasks` and the founder notification path.
3. **Founder completes the challenge** through the legitimate interface (the
   provider's own page in the source's headed browser profile). Agents never
   see, store, or replay MFA codes or CAPTCHA solutions.
4. **Capture redacted status** — only the outcome is recorded:
   `{"challenge":"MFA","resolved_by":"founder","status":"SESSION_ACTIVE"}`.
5. **Revalidate + resume** — the run re-checks session validity before
   continuing; unresolved challenges past the HITL timeout abort the job.

## 8. Threat Model and Limits

**Protects against:** casual exposure — secrets appearing in git, prompts,
logs, screenshots, memory dumps of agent context, or audit exports.

**Does NOT protect against:** a local administrator or malware on the
founder's machine reading OS credential storage directly. Threat model
assumption: the founder's workstation is trusted at the OS level; the vault
raises the bar against *accidental and agent-mediated* leakage, not
determined local attackers. Documented in
[DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md) risk R5.

## 9. Revocation

- **Immediate invalidation capability:** `vault_delete(key_id)` removes local
  access instantly; founder then revokes server-side (provider consoles) —
  both halves are required, and both are audit events.
- Every source entry in
  [SOURCE_ACCESS_POLICY_REGISTER.md](SOURCE_ACCESS_POLICY_REGISTER.md) lists
  where its credentials are revoked server-side.
- On ACCOUNT_CLOSED (SM-3), the associated profile and all its key IDs are
  deleted with hash-chained destruction events.

## 10. Backup

- The encrypted fallback vault file is included in the daily backup only in
  its **encrypted** form; keyring-backed secrets are NOT exportable by the
  backup job (OS-managed).
- A one-page recovery note (kept offline by the founder) records: which key
  IDs exist, where each is revoked server-side, and re-entry order after a
  machine loss. The note contains no secret values.

## 11. Implementation Checklist (E7)

- [ ] `keyring` dependency added; interface module with the four operations
- [ ] Audit events on all operations (key IDs only)
- [ ] Expiry metadata + `ROTATION_DUE` task generation
- [ ] Redaction guard test (no secret value in any event/memory/prompt)
- [ ] `.gitignore` covers `data/vault.enc`, `profiles/`, `.env`
- [ ] Dashboard shows key IDs + fingerprints only
- [ ] MFA/CAPTCHA pause flow wired to HITL tasks
