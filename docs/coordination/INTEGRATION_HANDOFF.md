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
- GitHub Actions [Python checks run 38166034332](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/38166034332) completed **success** for code commit `51f6b1fcbd9f0198173af42ed0f1c3205475d992` (Python 3.11, requirements plus pytest, compile, diff, full suite). The final handoff-only commit's run is verified separately in the completion message.

## Security and integration risk register

1. **Live acquisition is unverified.** Kilo's public `BrowserWorker.extract()` is still an empty fixture scaffold and lacks its own extraction authorization. The adapter never calls that method. A live collector needs Kilo's reviewed public operation API, guarded transport, source permission provenance, and new tests before activation.
2. **Private bridge point.** The adapter calls `AcquisitionWorker._browser.navigate` because Kilo has not published a public action method. Kilo should expose a stable operation method that accepts the same `PolicyPort` without changing the fail-closed contract.
3. **Policy and rate semantics.** Each navigation and extraction consumes one persisted source budget unit. Failed fixture reads do not refund units. Unknown/manual-only/expired/out-of-scope/unapproved/rate-exhausted requests have zero transport reads in tests.
4. **Audit and secrets.** Central events, tasks and memory are redacted and correlated in this pilot; raw fixture HTML is not persisted. Regex redaction cannot classify every possible secret. The SQLite hash chain detects row changes but cannot prevent privileged DB replacement.
5. **Commercial proof.** Existing regressions still check distinct customers and positive net receipts. Receipt and customer evidence remain founder attestations, not bank or registry verification. Production hosting and live provider access are untested.

## Review gates and next decision

The fixture pilot demonstrates central intake and authorization. It does not establish a live buyer workflow or satisfy approval to merge into `main`. Chief Architect should review the branch and CI result, then decide whether Kilo should replace the fixture extractor with a safe public collector API before any founder-authorized source pilot.

## Public collector integration update — 2026-10-19

This section supersedes the earlier private-browser and duplicate-parser
limitations above. Work took place only in `C:\Users\PC\Desktop\acq-integration`
on `feat/codex-p1-integration`. Kilo's published
`16e9efa743e6483fdfed5aec5d3d590fd16eb49f` was merged as `cfbe827`;
Kilo's worktree and branch were not edited. Integration implementation commit:
`adc228af9dce57a229ca362503045f1b75d40aec`.

### Implemented behavior

- `acqsys/integration.py` now injects a tracing subclass of the persisted
  `core.CorePolicyPort` into Kilo's public `BrowserWorker`, then calls public
  `navigate()` and `extract()`. It no longer calls `AcquisitionWorker._browser`
  or contains `_ProjectParser`. An instrumented in-memory `fixtures_dir`
  supplies synthetic HTML only after Kilo's extraction authorization. There
  is no HTTP/browser transport, credential use or live source access.
- Kilo's public candidate DTOs are validated before intake. A single fixture
  listing page yields two href-derived URLs and two nonempty candidates.
  `core.add_lead()` stores each as a distinct `DISCOVERED` lead, unverified
  buyer and unknown availability. Page SHA-256 plus candidate URL SHA-256
  gives separate local evidence references; these do not replace Kilo's
  missing per-card locator for a future live collector.
- `acqsys/core.py` now owns the durable fixture run source/URL binding,
  cursor and status; repeat or restarted runs cannot rebind the source or
  URLs. Every resumed navigation and extraction invokes the current persisted
  core policy. A retry after partial intake deduplicates observations and
  ensures a single durable founder review task per lead. Core SQLite/hash
  chain remains authoritative; Kilo's in-memory audit/HITL and its optional
  `WorkflowState.resume()` callback are not used for integration authority.
- Founder-authenticated `import_historical_candidates()` reads the genuine
  repository-root `lead_candidates_2026-10-10.json` only. It imports all ten
  local historical records with their original source, URL, description and
  stated budgets, keeps availability `UNKNOWN`, adds unverified observations
  and founder review tasks, and fails on missing/corrupt root data. It does
  not query Upwork, Freelancer or another live source.
- `docs/coordination/INTERFACE_CONTRACT.md` records the public fixture API.
  `.github/workflows/ci.yml` compiles `scripts`, runs the full test suite and
  executes the two-card, central-audit fixture demo. The changed files in the
  implementation commit are `.github/workflows/ci.yml`, `acqsys/core.py`,
  `acqsys/integration.py`, `docs/coordination/INTERFACE_CONTRACT.md`,
  `scripts/demo_p1_fixture.py`, and `tests/test_integration_p1.py`.

### Verification

- Before synchronization: **58 passed**. Immediately after merging Kilo but
  before repairing the bridge: **73 passed, 4 integration failures**, which
  exposed the old private-browser dependency.
- Final local `.\.venv\Scripts\python.exe -m pytest -q`: **88 passed,
  1 upstream Starlette/httpx deprecation warning**. `compileall -q acqsys
  tests scripts` and `git diff --check` passed.
- Local and CI `python -m scripts.demo_p1_fixture`:
  `new_leads=2`, `duplicates_on_repeat=2`, `unverified_leads=2`,
  `founder_tasks=2`, `fixture_reads=2`, `paying_clients=0`,
  `audit_valid=true`.
- [Push CI run 39165244450](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39165244450)
  and [PR CI run 39165247598](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/actions/runs/39165247598)
  both concluded **success** at exact implementation SHA
  `adc228af9dce57a229ca362503045f1b75d40aec`. The PR job
  `117786713695` log reports **88 passed, 1 warning** on Python 3.11.17
  and the demo counts above. Draft [PR #5](https://github.com/ShubMisra/AI_CLIENT_ACQUISITION_MVP/pull/5)
  remains unmerged.

### Open issues and integration dependencies

Kilo PR #4 remains DRAFT with Issue #2 open at its currently published
`16e9efa` head. Its `AllowFixturePolicy` and `BrowserWorker._check` still
accept HTTP and insufficiently reject userinfo/private targets; this
integration uses the stricter `CorePolicyPort` and never activates live
network access. Kilo's own per-card evidence refs remain identical, so the
integration binds a local URL/page hash while awaiting Kilo's card locator.
Kilo's `WorkflowState.resume`/`restore` still permit an omitted policy
callback, and its CLI triage still has a fixture-copy fallback. Integration
uses central run recovery and explicit root historical import, but those
Kilo APIs must be corrected and independently retested before live use.
The fixture-only result does not verify current buyer availability, source
terms, payment evidence, or real browser/DNS containment. No source was
activated, no buyer was contacted, and no merge into `main` was made.

## Business intake follow-up — 2026-10-21

This section supersedes the earlier Kilo-head and fixture-only pipeline status
above. Integration branch `feat/codex-p1-integration` merged Kilo PR #4's
published `902b9fd1a7bfe8e3cec7d23ef6483258fb4e344b` as `03e3676`,
then synchronized PR #4's newer `51f1ca7a39e20f201d52a188ab7a22195e055d71`.
The latter differs only in `KILO_HANDOFF.md`; acquisition source files are
identical. Kilo's branch and worktree were not edited. The latest delta includes distinct
card evidence, a qualification alias, a shortlist formatter, and additional
negative tests. Central `CorePolicyPort`, SQLite, audit and run state remain
authoritative; Kilo's fixture policy, workflow checkpoint and shortlist are
not production access or buyer verification authorities.

The smallest business-path change adds founder-authenticated
`POST /api/intake/founder` for one registered `MANUAL_ONLY` source and up to
50 founder-provided records. The request validates the whole batch before
writing, binds each HTTPS URL to the approved public source domain, and rejects
private hosts, missing descriptions, invalid budget ranges and demand types. Existing
`core.ingest_manual_lead` scores, deduplicates and persists each candidate.
Central observations and one founder review task record what remains to be
verified. Existing `agents.evidence_driven_proposal` stores one deterministic
draft per lead, marked unsent and requiring founder approval. The permitted
synthetic fixture path uses the same draft step; repeat intake reuses drafts.
No model endpoint or customer communication is involved.

The Kilo `BrowserWorker` used by the fixture bridge now checks HTTPS,
userinfo, port and private IP literals without DNS resolution before calling
the central policy port. The bridge still rejects invalid card targets before
lead intake. Kilo's standalone `AllowFixturePolicy` and `WorkflowState` remain
outside this integration's trust boundary and require independent correction
before any real source work.

The synthetic end-to-end demo uses only reserved `fixture.example` and
`manual.example` records in a temporary database. Observed local output:
`new_leads=2`, `duplicates_on_repeat=2`, `founder_provided_new=1`,
`founder_duplicates_on_repeat=1`, `scored_leads=3`, `founder_tasks=3`,
`unsent_proposal_drafts=3`, `unverified_leads=3`, `paying_clients=0`,
`audit_valid=true`. The combined local full suite passes **99 tests** with
one upstream Starlette/httpx warning. Exact final SHA and Actions runs are
recorded in draft PR #5 after publication.

Follow-up files: `acqsys/core.py`, `acqsys/integration.py`,
`acqsys/acquisition/browser.py`, `acqsys/app.py`,
`tests/test_integration_p1.py`, `scripts/demo_p1_fixture.py`, and this handoff.
The merge also carries Kilo's reviewed fixture modules and tests. The source
policy register does not authorize a live crawl, and no current buyer,
availability, payment or conversion claim follows from the test data.
