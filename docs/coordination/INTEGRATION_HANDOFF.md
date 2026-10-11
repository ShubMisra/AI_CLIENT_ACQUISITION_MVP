# P1 integration handoff — 2026-10-12

## Decision log and scope

- Issue: [#1](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/issues/1); review gates: [draft PR #3](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/3).
- Integration worktree: `C:\Users\PC\Desktop\acq-integration`; branch: `feat/codex-p1-integration`. Based on Codex P0 `e7d2fd47f93ebd8d3d93fe87e79f01b2029a5791`, then merged Kilo's published `eed60e0` into this branch. Neither source worktree or branch was edited.
- Kilo's published extractor returns an empty candidate list, so the permitted fixture-only adapter is used. It injects the real `core.CorePolicyPort` into Kilo's `AcquisitionWorker`, invokes its navigation gate, calls the port again for extraction, then reads only in-memory fixture HTML. No live browser or HTTP transport exists in this adapter.
- No source permissions, customer contact, accounts, credentials or purchases were used. The fixture source and its policy are synthetic test data, not authorization for a marketplace.

## Implemented and changed files

| File | Result |
|---|---|
| `acqsys/core.py` | Correlation context for central audit; append-only `lead_observations` schema and evidence records for new and duplicate candidates. |
| `acqsys/integration.py` | Fixture-only Kilo worker bridge, per-operation policy calls, two-field HTML extraction, canonical `core.add_lead()` intake, central task/memory/audit writes. |
| `tests/test_integration_p1.py` | Real persisted policy denial matrix, zero fixture reads, two candidates, repeat dedup, audit/evidence, manual-only founder intake, redaction. |
| `.github/workflows/ci.yml` | Python 3.11 install, compile, diff and full pytest checks without credentials or provider access. |
| `scripts/demo_p1_fixture.py` | Temporary-DB, no-network end-to-end review demo. |
| `docs/coordination/INTEGRATION_HANDOFF.md`, `CODEX_HANDOFF.md` | Integration evidence and review handoff. |

No Kilo-owned file changed. The canonical lead remains `DISCOVERED` with `buyer_verified=False`; every observation explicitly stores `UNVERIFIED` and `UNKNOWN`, source and evidence references. Both initial and repeated observations remain in SQLite and the hash-chain audit. A new candidate creates one durable founder task; run summary is stored as a `HYPOTHESIS` memory. No contact is sent.

## Verification and review evidence

- Baseline combined suite after branch merge: **48 passed**.
- `.\.venv\Scripts\python.exe -m pytest -q` from the integration worktree: **58 passed**, one upstream Starlette/httpx deprecation warning. This worktree has its own Python 3.11 virtual environment, installed from `requirements.txt` plus pytest.
- `.\.venv\Scripts\python.exe -m compileall -q acqsys tests scripts` and `git diff --check`: passed.
- `.\.venv\Scripts\python.exe -m scripts.demo_p1_fixture`: `new_leads=2`, `duplicates_on_repeat=2`, `unverified_leads=2`, `founder_tasks=2`, `paying_clients=0`, `audit_valid=true`.
- CI: pending first GitHub Actions run on this integration branch. Final run URL and SHA are reported in the completion message; update this handoff after the run if GitHub permits.

## Security and integration risk register

1. **Live acquisition is unverified.** Kilo's public `BrowserWorker.extract()` is still an empty fixture scaffold and lacks its own extraction authorization. The adapter never calls that method. A live collector needs Kilo's reviewed public operation API, guarded transport, source permission provenance, and new tests before activation.
2. **Private bridge point.** The adapter calls `AcquisitionWorker._browser.navigate` because Kilo has not published a public action method. Kilo should expose a stable operation method that accepts the same `PolicyPort` without changing the fail-closed contract.
3. **Policy and rate semantics.** Each navigation and extraction consumes one persisted source budget unit. Failed fixture reads do not refund units. Unknown/manual-only/expired/out-of-scope/unapproved/rate-exhausted requests have zero transport reads in tests.
4. **Audit and secrets.** Central events, tasks and memory are redacted and correlated in this pilot; raw fixture HTML is not persisted. Regex redaction cannot classify every possible secret. The SQLite hash chain detects row changes but cannot prevent privileged DB replacement.
5. **Commercial proof.** Existing regressions still check distinct customers and positive net receipts. Receipt and customer evidence remain founder attestations, not bank or registry verification. Production hosting and live provider access are untested.

## Review gates and next decision

The fixture pilot demonstrates central intake and authorization. It does not establish a live buyer workflow or satisfy approval to merge into `main`. Chief Architect should review the branch and CI result, then decide whether Kilo should replace the fixture extractor with a safe public collector API before any founder-authorized source pilot.
