# Yuno Ball project status

Status: descriptive Daily/history release candidate prepared locally; public launch is NO-GO
Reviewed: 2026-10-16
Repository Alembic head: `i5j6k7l8m9n0`

This is the short operational status of the launch slice and analytics
roadmap. The repository, live database profile, and the contract documents
linked below remain authoritative for implementation detail. Dated research
notes are evidence records, not competing status boards.

The local-only status snapshot at `/design/status` is not launch evidence.

## Release candidate checkpoint — 2026-10-16

This candidate was consolidated from base commit
`f852525c739a040d6c45a5c2817ba056805593d4`. The runtime candidate SHA is
recorded in a documentation-only release record immediately after the runtime
commit, avoiding a misleading self-referential SHA. The candidate adds
production season validation, bounded storage readiness, configured Redis
handling, safer public error responses, and production route limits for the
descriptive Daily/history beta. Research/design and experimental betting
surfaces are excluded in production. It has not passed service-backed staging;
the main checkout remains a separate dirty worktree.

Final local verification on 2026-10-16 used the repository Python 3.10.6
environment. `compileall` passed and the focused release set passed 34 tests.
The complete suite with an inert SQLite sentinel returned 457 passed, 15
skipped, and 3 failed; all three failures were PostgreSQL-dependent tests that
received PostgreSQL-only `keepalives` arguments through SQLite. The exact three
tests then passed against the configured local PostgreSQL database. `alembic
current` reported `i5j6k7l8m9n0 (head)` and `alembic check` found no new
upgrade operations. These are local development results, not staging results.

`npm ci`, the CSS build, and the JavaScript build passed. Swiper was upgraded
from 11.2.5 to 12.1.2 to remove its critical advisory. A non-breaking `npm
audit fix` reduced the remaining audit result to seven build-tool-chain
findings (five high, two moderate, zero critical); eliminating them requires a
breaking Tailwind 4 migration and is deferred from this narrow candidate. The
ignored, reproducibly built CSS and Swiper asset SHA-256 values were
`FE9045DC39127BF00BC4B4F09BA6876645BDB7D9C6FA5D6D1946070795FE7361` and
`59E71068CBB5A3DEBEA99A2A8802E0EA1728B04DDE6736D94D44EE873B6ED5F5`.

Local preview update — 2026-10-16: the configured local PostgreSQL connection
served source-backed historical slates. March 3, 2025 showed nine games and
March 4 showed eight; the archive and a date-specific matchup page loaded.
Redis was unavailable. A final production-configured Flask test-client check
reported HTTP 200 `degraded_ready` with PostgreSQL available and Redis
unavailable, matching the corrected contract. It also returned nine and eight
games for the two dates, an empty July 1 slate, HTTP 200 for archive and the
permanent `CLE-CHI` matchup, correct date redirects, and HTTP 404 for the
dashboard, design-status, and betting surfaces. This used localhost process
configuration and the personal-PC database; it was not a deployed server or a
staging environment. The sampled pages correctly displayed freshness as
`UNKNOWN` because the durable history contains no qualifying full validated
daily ingest marker. That safe state remains a launch blocker until staging
produces and monitors a qualifying marker.

The read-only reconciliation tool passed a source-to-itself regression check:
both sampled dates matched at nine and eight games, duplicate groups and pair
failures were zero, and both sides reported Alembic head. This validates the
tool and date semantics only. It is not source-to-managed-target migration
evidence.

Current launch gate: no service-backed staging check has run. `/health/ready` checks
only bounded PostgreSQL/Redis connectivity and has per-worker in-process plus
global Redis-backed rate limits in production;
it does not certify migrations, data freshness, ingestion, or page behavior.
Do not describe this candidate as launch-approved until a candidate-commit
staging deployment has passed route, page, freshness, rollback, and dependency
checks. Predictions, Rotation Shock, SoS production use, and public odds remain
out of this beta's scope.

The intended V1 public journey is the Daily games slate followed by permanent,
date-specific matchup pages, with archive navigation. The owner confirmed this
as the desired beta shape on 2026-10-16. Presentation polish remains a V1
release task; broader player-focused experiences follow this launch slice.
Before public traffic, move the production database off the personal PC to a
private managed PostgreSQL service, reconcile a controlled copy of the data,
enable backups with a tested restore, establish scheduled single-owner ingest
and freshness monitoring, and pass staging on the exact release candidate.
See [PRODUCT_STRATEGY.md](PRODUCT_STRATEGY.md) and
[DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md).

## Launch decision — NO-GO as of 2026-10-16

The descriptive product boundary is coherent, but the release is **NO-GO** for
public traffic. This is not a judgment on the localhost preview; it records
missing release evidence. Every item below must be attached to one immutable
candidate commit and one named staging environment before the decision can
change:

| Gate | Current evidence | Required evidence for GO |
| --- | --- | --- |
| Candidate artifact | Candidate tree verified locally; exact runtime SHA is recorded by the follow-up release record | Exact commit, dependency set, built asset hashes, and Alembic head staged together |
| Staging | Not provided | Private staging host and URL running production configuration; localhost does not qualify |
| Durable database | Personal-PC PostgreSQL was read locally | Private managed PostgreSQL destination, verified source backup, source/target schema and exact-row reconciliation |
| Recovery | Not performed for this candidate | Automated backup/PITR policy plus a timed restore into an isolated database and application read smoke |
| Redis/readiness | Pre-correction local probe returned 503; candidate degraded contract is code/test evidence only | Private Redis configured; staging proves healthy 200, Redis-loss 200/degraded, and PostgreSQL-loss 503 |
| Ingestion | No staged schedule/monitor was verified | Single-owner scheduled job, successful validated run, no-op/rerun proof, and alerting on failed/partial/stale state |
| Product route matrix | Local source-backed spot checks only | Two distinct real dates, archive, permanent scheduled/final matchups, empty/stale states, redirects, and production-only 404 restrictions |
| Rollback | Not rehearsed | Previous commit recorded; application rollback, cache handling, and database restore/recovery drill recorded |

Required external inputs are: a private managed PostgreSQL destination and
operator access; a private Redis endpoint; a staging host/domain with protected
environment configuration; the intended ingestion network/proxy policy; backup
retention and recovery objectives; an alert destination and on-call owner; and
the previous known-good application commit. Secrets must be supplied through
the protected environment and must not be pasted into documentation or logs.

Use the evidence worksheet in
[DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md#release-evidence-worksheet) for
the exact commands and result record. Offline tests and localhost responses may
be recorded as development evidence only and cannot fill a staging row.

## Prior integration checkpoint evidence — 2026-10-11

The public Daily surface now presents freshness, provenance, and postgame
details at more readable sizes. Final matchup pages can show all available
canonical traditional player-game rows with source and selection time; the
payload retains the V1 compact `actual.box_score.leaders` field. Game-level
coverage is explicitly partial or missing because canonical facts do not
certify a complete official roster.

Deployment entrypoints now match their servers: Gunicorn imports the Flask
WSGI app from `wsgi:app`, and Uvicorn imports the ASGI adapter from `asgi:app`.
Importing the WSGI module no longer overrides operator proxy settings.

Research gates remain closed. The H1 timing audit excludes facts without an
exact own-game schedule from strict eligible history and fails readiness when
source order cannot be checked; timestamps still do not prove original source
publication time. Program G monitoring now compares candidates with the
strength-plus-form control only on full same-size held-out populations and
always reports production prediction approval as false. SoS examples have a
research-only evidence contract. Odds fixture review now requires finite
spread/total lines and reciprocal spread signs; zero lines remain valid.

Verification on 2026-10-11: `python -m compileall -q app` and the changed
scripts passed. Focused tests across Daily/matchup, server entrypoints, H1,
odds, and G monitoring passed (46 passed, including the service-level box-score
test). The full offline suite returned 431 passed, 15 skipped, and 4
deselected. The deselected checks require either PostgreSQL
(`TestDashboardServiceUnit.test_get_calendar_days`, `test_orm_read_access`,
and `TestPlayerRoutes.test_player_list_route`) or a running app at
`127.0.0.1:8000` (`test_request_tracing`). No production database writes or
live provider calls were made. The full database-backed gate remains
unverified in this environment.

## Prior product assessment — 2026-10-11

Yuno Ball had an implemented descriptive Daily Intelligence V1 historical slice:
the public slate, date, archive, and matchup destinations are implemented with
freshness, completeness, provenance, and explicit empty states. The product is
not yet a prediction or betting-edge product.

The current product-surface review confirms that Daily and date-scoped Matchup
are the public spine. Players and Teams remain supporting context, `/games` is
the archive/lookup destination, and `/dashboard/`, `/design/*`, and
`/daily/betting` return 404 in production for this beta. The old home, streak, chart, games, and matchup
aliases no longer compete with the public spine. Daily and Matchup translate
official availability into plain-language listed statuses while preserving
cutoff, source, completeness, and unresolved identity metadata. See the
[product surface evaluation](research/PRODUCT_SURFACE_EVALUATION_2026-09-13.md).

The historical player/team foundation is strong enough for continued research.
Program G has completed its current research gates but has not approved a public
prediction model. Program H1 now has durable role-history and pregame-baseline
projections, but historical source timing prevents production use of the
baseline. The 2026-27 schedule is now onboarded, and preseason is externally
underway, but the current C7 bridge is intentionally Regular Season-only. The
real bridge smoke therefore waits for the first completed eligible Regular
Season game, not merely the start of preseason.

## Status matrix

| Area | Status now | Evidence / next gate |
| --- | --- | --- |
| Daily Intelligence V1 | Implemented; release candidate verification pending | `/daily/`, `/daily/archive`, `/daily/YYYY-MM-DD`, `/matchup/YYYY-MM-DD/AWAY-HOME`; completed matchups add bounded canonical player lines with explicit partial/missing coverage |
| Public route diet | Implemented; staging verification pending | `/daily/` owns the public story; `/games` owns lookup; research/design/betting pages return 404 in production; retired aliases redirect |
| Historical launch slice | Complete | 2024-25 archive/date/matchup routes are source-derived and read-only |
| C7 player facts | Historical foundation complete for 2020-21 through 2025-26 | Keep `gamelogs` fallback; run the 2026-27 completed-game bridge smoke when evidence exists |
| Program D snapshots | Foundation complete for approved 2024-25 and 2025-26 seasons | Preserve cutoff/completeness gates; no automatic expansion into unsupported seasons |
| Program E SoS | Research wording/examples approved only | No production field, route, cache, or default Daily insight |
| Program G | Frozen feature-family comparison complete; prediction publication blocked | All four candidate variants passed two-season coverage; continue monitoring and keep the matchup family research-only |
| Program H0 | Evidence audit complete | Availability and starter coverage remain incomplete |
| Program H1 | Foundation and bounded apply/replay complete | [Pre-registered calibration protocol](research/PROGRAM_H_H1_ROLE_BAND_CALIBRATION_PROTOCOL_2026-09-13.md), then forward timing evidence before any consumer |
| 2026-27 bridge | Wired; quiet-day proof passed; season-state re-audited | Database has 1,200 scheduled Regular Season games / 2,400 team rows, 0 Pre Season rows, and 0 player facts; run Traditional → Advanced → C5 → replay on the first completed Regular Season game |
| Odds observation pilot | One-request SportsGameOdds probe and fixture pair review complete; source approval remains open | Canonical identity mapping, broader pair/timestamp review, licensing/coverage; no edge claims |

## What is blocked versus what is not

### Blocked by external or evidence state

- Preseason has started externally, but this repository has no stored `Pre Season`
  rows and the C7 player-fact contract is Regular Season-only. The real
  2026-27 bridge smoke still cannot run until an eligible Regular Season game
  is completed and onboarded.
- Historical H1 strict baselines cannot use backfill retrieval timestamps as
  original pregame publication times.
- Rotation Shock cannot claim expected minutes, replacement quality, or exact
  rotation impact without reliable availability timing, starter evidence, and
  role history.
- Public predictions remain blocked until the G research, calibration,
  immutable-storage, and consumer gates pass.
- The original NBA live odds transport remains blocked. The alternate
  SportsGameOdds transport probe passed, but the adapter must still fail closed
  until identity, pair completeness, timestamp precision, and licensing/
  coverage review pass.

### Work that can continue now

- Keep the 2026-27 bridge and role-history projection ready for the first
  eligible Regular Season game.
- If preseason analytics are desired, define a separate event-type contract
  first; do not silently mix preseason schedule, roster, availability, or
  player-fact rows into Regular Season features.
- Run the read-only source-timing audit and record forward evidence.
- Execute the now pre-registered H1 walk-forward calibration once an approved
  timing population exists; the complete historical date-proxy rehearsal is
  recorded but remains audit-only.
- Continue G monitoring and frozen feature-family comparisons.
- Improve Daily presentation, accessibility, freshness language, and historical
  route QA without changing the semantic contract.
- Prepare odds-provider evaluation and deployment/runbook changes without
  publishing market conclusions.

## Latest season-state and forward-timing audit — 2026-10-10

The read-only H1 timing audit was rerun across the two approved historical
seasons and the current-season bridge. Historical facts all have a
`data_available_at`, but those values are 2026 backfill timestamps rather than
original source-publication times, so none of the exact target-team rows has
strictly eligible historical role history under the production cutoff. The
current season has exact Regular Season schedule precision but no completed-
game facts yet. Preseason is not represented in the current database snapshot,
so it cannot advance a Regular Season-only C7 smoke gate.

| Season | Facts | Exact target-team rows | Rows with strict prior history | Interpretation |
| --- | ---: | ---: | ---: | --- |
| 2024-25 | 32,515 | 10 | 0 | Backfill timing is not production-safe |
| 2025-26 | 32,179 | 1,994 | 0 | Backfill timing is not production-safe |
| 2026-27 | 0 | 2,400 | 0 | Regular Season schedule onboarded; awaiting first completed eligible game |

This audit performed no writes. The forward gate will become meaningful when
the 2026-27 bridge records collection-time timestamps for completed-game
facts before later target tipoffs.

## Latest G monitoring rerun — 2026-09-13

Both chronological held-out directions completed again across 1,075 games per
season with `writes_performed=false`. The interval-aware reports remain useful
research evidence, but calibration is direction-dependent and therefore does
not clear the public-prediction gate. The G monitoring state is current; the
next work is broader evidence and frozen feature-family comparison, not route
publication.

## Latest checklist evidence — 2026-09-13

The frozen feature-family comparison completed across 1,075 eligible games in
each of the 2024-25 and 2025-26 Regular Seasons. All candidates had full
coverage; `strength_form_schedule` and `strength_form_schedule_matchup`
passed the subgroup gate in both seasons. The matchup variant's log-loss range
was `0.0109` across the two seasons. This remains model-research evidence only.

The H1 role-band rehearsal evaluated 25,617 historical player-games and
returned a 3.83-minute median absolute error with 35% band coverage. Its
`historical_game_date_proxy` timing policy remains audit-only and
`production_ready=false`. The forward timing audit found zero strictly
eligible historical prior rows for the 2024-25 sample (10 exact target-team
rows), confirming that collection-time evidence is still the required gate.

The normalized SportsGameOdds fixture review recognizes moneyline and spread
pairs, reports incomplete totals and duplicate selections, preserves provider
team IDs as unresolved, and performs no writes. A provider identity map and a
broader bounded sample remain unapproved; another live request requires
explicit quota authorization.

The full repository suite is green at 439 passed and 2 skipped, with warnings
only. Compileall passed. `alembic check` reports no new upgrade operations
after the intentionally retained but unmodeled legacy `users` table was
excluded from autogenerate comparison.

The October 10 worktree audit found 28 modified tracked files and 5 untracked
files on `codex/program-e-sos-rotation-gate`. That coherent package covered
route consolidation, Daily historical outcomes, status/docs updates, and
focused regression coverage. It is now committed as `14042c9` and the working
tree is clean.

## Definition of the next launch gates

1. First eligible 2026-27 Regular Season completed-game bridge run: exact
   schedule identity, Traditional facts, Advanced facts, C5 reconciliation,
   role-history write, and exact replay/no-op proof.
2. Forward timing audit: confirm `data_available_at` is collection-time
   evidence that precedes future target tipoffs; retain source run lineage.
3. H1 calibration review: pre-register band thresholds, run chronological
   evaluation, report coverage and error by history depth, and approve a new
   version only if evidence supports it.
4. Availability join review: require report timestamp precision, identity
   coverage, and explicit incomplete/unknown behavior.
5. Product decision gate: only after the above, decide whether H1 feeds Daily
   context or Rotation Shock research.
6. Odds pilot gate: after the successful explicit probe, require canonical team
   identity, complete game-market pairs, timestamp precision, and licensing
   review before any durable apply or Daily market context.
7. Optional preseason product gate: only if preseason analytics are a product
   requirement, define separate event-type semantics and provenance before
   collecting or exposing preseason player facts.

## Canonical documents

- [Master analytics roadmap](roadmaps/MASTER_ANALYTICS_ROADMAP.md) — program
  order and evidence gates.
- [Ingestion runbook](INGESTION_RUNBOOK.md) — operational commands, replay, and
  recovery.
- [Daily Intelligence V1 package](research/DAILY_INTELLIGENCE_V1_PACKAGE_2026-09-05.md)
  — public descriptive payload contract.
- [H1 role-baseline report](research/PROGRAM_H_H1_ROLE_BASELINE_FOUNDATION_2026-09-13.md)
  — role-history, timing, calibration, and database evidence.
- [H1 calibration protocol](research/PROGRAM_H_H1_ROLE_BAND_CALIBRATION_PROTOCOL_2026-09-13.md)
  — locked evaluation design and pass/fail thresholds.
- [Database profile](DATABASE_PROFILE.md) — sanitized live schema and coverage
  snapshot.
- [Source catalog](SOURCE_CATALOG.md) and [metric catalog](METRIC_CATALOG.md) —
  source and metric semantics.

## Operator commands

```text
python scripts/audit_program_h_source_timing.py --season 2025-26 --season-type "Regular Season"
python scripts/audit_program_h_role_baseline.py --season 2024-25 --season-type "Regular Season"
python scripts/build_program_h_role_baselines.py --season 2024-25 --season-type "Regular Season" --max-target-games 25 --dry-run
python scripts/probe_sportsgameodds.py --env-file C:\Code\sports_analytics\.env
```

These H1 commands are read-only unless the materializer is explicitly run
without `--dry-run`; historical proxy audits never publish durable rows.
