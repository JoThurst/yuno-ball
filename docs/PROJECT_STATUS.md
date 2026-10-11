# Yuno Ball project status

Status: canonical cross-program handoff
Reviewed: 2026-10-10
Repository Alembic head: `i5j6k7l8m9n0`

This is the short operational status of the launch slice and analytics
roadmap. The repository, live database profile, and the contract documents
linked below remain authoritative for implementation detail. Dated research
notes are evidence records, not competing status boards.

For a visual read, open the read-only control room at `/design/status`.

## Executive position

Yuno Ball has a shippable descriptive Daily Intelligence V1 historical slice:
the public slate, date, archive, and matchup destinations are implemented with
freshness, completeness, provenance, and explicit empty states. The product is
not yet a prediction or betting-edge product.

The current product-surface review confirms that Daily and date-scoped Matchup
are the public spine. Players and Teams remain supporting context, `/games` is
the archive/lookup destination, and `/dashboard/` is now an internal
research/data-quality console. The old home, streak, chart, games, and matchup
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
| Daily Intelligence V1 | Public descriptive product slice complete; historical postgame context added | `/daily/`, `/daily/archive`, `/daily/YYYY-MM-DD`, `/matchup/YYYY-MM-DD/AWAY-HOME`; completed matchups add durable final score/result and bounded canonical player lines beside cutoff-aware evidence |
| Public route diet | Active implementation slice | `/daily/` owns the public story; `/games` owns lookup; `/dashboard/` is internal; retired aliases redirect |
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
files on `codex/program-e-sos-rotation-gate`. These changes are a coherent but
uncommitted package covering route consolidation, Daily historical outcomes,
status/docs updates, and focused regression coverage. The last committed
checkpoint remains `c57b8fd` from September 13.

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
