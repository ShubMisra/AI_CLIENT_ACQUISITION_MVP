# Source Access Policy Register

> The authoritative per-source record of what access is permitted, reviewed,
> and evidenced. The **register entry is the gate**: no collection from any
> source without a policy status of CONFIRMED (automated) or MANUAL_ONLY
> (founder-run). Cross-references:
> [ACQUISITION_STRATEGY.md](ACQUISITION_STRATEGY.md) §2 ·
> [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) ·
> [AS_IS_AUDIT.md](AS_IS_AUDIT.md) §2.1

## 1. Review Framework

Every source entry records:

1. **Canonical identity** — name + primary domain (single source of truth for
   the domain scope guard).
2. **Category** — explicit_marketplace_demand · rfp_and_procurement ·
   agency_partners · startup_and_direct_accounts · discovery_infrastructure ·
   offline_network.
3. **Access methods** — official API · browser (permitted reads) · manual
   (founder only) · feed (approved RSS/Atom).
4. **Visibility model** — public vs login-required vs walled-garden.
5. **ToS/robots analysis** — citations with dates; what is explicitly allowed,
   restricted, prohibited.
6. **Per-action permissions** — matrix of: public_reading · official_api ·
   browser_navigation · authenticated_extraction · messaging ·
   application_submission. Each cell: ALLOWED / FOUNDER_MANUAL / PROHIBITED.
7. **Rate limits** — official documented limits, or self-imposed conservative
   defaults (5 s delay, 100 requests/day — see
   [BROWSER_ACQUISITION_AND_HITL_SPEC.md](BROWSER_ACQUISITION_AND_HITL_SPEC.md) §1).
8. **Geographic applicability** — regions where the source is relevant.
9. **Cost** — free tier limits or paid plan thresholds.
10. **Review date** — last reviewed; quarterly re-review or on policy change.
11. **Evidence citations** — ToS/robots/API-doc URLs, snapshot references.

**Default posture:** every source starts at policy UNKNOWN = default-deny for
automation. The 25 `requires_review` entries in `source_registry.json`
([AS_IS_AUDIT.md](AS_IS_AUDIT.md) §2.1) may not be automated until reviewed
through the SM-2 flow.

## 2. Initial Register Entries

### 2.1 Upwork — `MANUAL_ONLY`
- Domain: `upwork.com` · Category: explicit_marketplace_demand · P0
- Visibility: login-required for most detail; public landing pages only
- ToS/robots: automation, scraping, and unauthorized bots prohibited; usage
  is via the founder's own logged-in human session, on-platform alerts
- Per-action: public_reading ALLOWED (founder) · official_api N/A ·
  browser_navigation PROHIBITED (automated) · authenticated_extraction
  PROHIBITED (automated) · messaging FOUNDER_MANUAL ·
  application_submission FOUNDER_MANUAL
- Cost: free (connects purchased case-by-case, founder decision)
- Evidence: Upwork Terms of Use (automation clauses), robots.txt 2026-10-10
- Note: the 10 seeded leads came from the founder's manual reading — the
  intended mode ([AS_IS_AUDIT.md](AS_IS_AUDIT.md) §2.3)

### 2.2 Freelancer.com — API `CONFIRMED` (upon OAuth setup)
- Domain: `freelancer.com` · Category: explicit_marketplace_demand · P0
- Visibility: public project listings; API access via official OAuth app
- ToS/robots: official Python SDK + documented API sanctioned for search and
  retrieval within rate limits; bulk re-publication prohibited
- Per-action: public_reading ALLOWED · official_api ALLOWED (key-limited) ·
  browser_navigation PROHIBITED while API exists
  ([EVAL_AND_TEST_MATRIX.md](EVAL_AND_TEST_MATRIX.md) scenario 3: prefer API
  over browser) · messaging/application FOUNDER_MANUAL
- Rate limits: per official API docs; self-cap 1 req/s, 5,000/day
- Cost: free tier sufficient for search
- Evidence: developers.freelancer.com docs, OAuth app registration

### 2.3 Brave Search — API `CONFIRMED` (upon key setup)
- Domain: `brave.com/search/api` (data source: whole-web index)
- Category: discovery_infrastructure · P0
- Per-action: official_api ALLOWED within plan quota · result-snippet reading
  ALLOWED · any scraping of brave.com itself PROHIBITED
- Rate limits: per plan (free tier ~1 qps, monthly quota)
- Cost: free tier; founder approves any paid upgrade
- Evidence: API terms + plan documentation

### 2.4 RSS/Atom feeds — `PER_FEED_APPROVAL`
- Domains: per feed · Category: discovery_infrastructure · P1
- Each feed URL requires its own founder approval with evidence that the
  publisher offers the feed publicly (feed is an implicit invitation);
  `test_feed_requires_founder_policy_approval` enforces the gate
- Per-action: feed_reading ALLOWED (approved feeds) · everything else N/A
- Rate limits: poll ≤ hourly per feed; respect caching headers

### 2.5 Contra — `UNKNOWN` (needs review)
- Domain: `contra.com` · Category: explicit_marketplace_demand · P1
- No public API documented; ToS review pending → default-deny for automation;
  founder may use manually meanwhile

### 2.6 PeoplePerHour — `UNKNOWN` (needs review)
- Domain: `peopleperhour.com` · P1 · same posture as Contra; review at
  second-wave onboarding

### 2.7 Guru — `UNKNOWN` (needs review)
- Domain: `guru.com` · P1 · same posture; ToS automation clauses to be read
  before any navigation beyond public landing pages

### 2.8 Clutch — `UNKNOWN` (public directory)
- Domain: `clutch.co` · Category: agency_partners · P0 (for pipeline P-B)
- Public company directory. Permitted use: founder + search-index reading of
  public pages for prospect list building, with attribution norms respected.
  Bulk automated harvesting PROHIBITED pending explicit review; extraction
  volume capped manually (~20 profiles/week, human-paced)

### 2.9 LinkedIn — `MANUAL_ONLY` — automation `PROHIBITED`
- Domain: `linkedin.com` · Category: startup_and_direct_accounts · P0
- ToS/robots: scraping and automated activity explicitly prohibited; user
  agreement enforced aggressively
- Per-action: every automated cell PROHIBITED · messaging, connection
  requests, profile research FOUNDER_MANUAL only
- Evidence: LinkedIn User Agreement (hiQ litigation history reinforces
  caution); robots.txt disallows essentially all crawling
- Note: registered in `source_registry.json` as
  `human_or_approved_integration_only` — the strictest entry

## 3. Template for New Source Reviews

```markdown
### <Source name> — <status>
- Domain / Category / Priority:
- Visibility: public | login-required | walled-garden
- ToS/robots analysis: <what is allowed/restricted/prohibited, with dates>
- Per-action matrix:
  | public_reading | official_api | browser_navigation | authenticated_extraction | messaging | application_submission |
  |---|---|---|---|---|---|
  | <A/FM/P> | ... | ... | ... | ... | ... |
- Rate limits (official or self-imposed):
- Geographic applicability:
- Cost:
- Review date / reviewer:
- Evidence citations:
- Decision (founder): ACTIVATE | MANUAL_ONLY | REJECT — <rationale>
```

`A` = allowed (automated, within limits) · `FM` = founder-manual · `P` =
prohibited.

## 4. Re-Review Schedule

| Trigger | Action |
|---|---|
| Quarterly calendar tick | Re-read ToS/robots for every ACTIVE or CONFIRMED source; refresh citations |
| Policy change detected (page diff, incident) | Source → SUSPENDED immediately; re-review before reactivation |
| Access violation or block event | Incident review; status → BLOCKED; founder decides repair vs RETIRED |
| New source proposed | Full review through the template; AWAITING_FOUNDER gate before any automated access |

All reviews and status changes are audit events; the observer reports
stale reviews (>90 days) as `STALE_POLICY_REVIEW`
([AUDIT_MEMORY_OBSERVER_SPEC.md](AUDIT_MEMORY_OBSERVER_SPEC.md) §5).

## 5. Registry Migration Note

This register currently lives in this document plus `source_registry.json`
(32 entries, 25 `requires_review`). Backlog E5 migrates statuses into the
`sources` table so transitions (SM-1/SM-2) become auditable state changes;
the JSON file remains the reviewed seed
([AS_IS_AUDIT.md](AS_IS_AUDIT.md) §5, reuse decision table).
