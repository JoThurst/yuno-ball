# Yuno Ball project status

Status: canonical cross-program handoff
Reviewed: 2026-09-13
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

The historical player/team foundation is strong enough for continued research.
Program G has completed its current research gates but has not approved a public
prediction model. Program H1 now has durable role-history and pregame-baseline
projections, but historical source timing prevents production use of the
baseline. The 2026-27 bridge is wired and safe on quiet days; its real smoke
proof waits for the first completed game.

## Status matrix

| Area | Status now | Evidence / next gate |
| --- | --- | --- |
| Daily Intelligence V1 | Public descriptive product slice complete | `/daily/`, `/daily/archive`, `/daily/YYYY-MM-DD`, `/matchup/YYYY-MM-DD/AWAY-HOME`; navbar is DB-only and the page loader has a failsafe |
| Historical launch slice | Complete | 2024-25 archive/date/matchup routes are source-derived and read-only |
| C7 player facts | Historical foundation complete for 2020-21 through 2025-26 | Keep `gamelogs` fallback; run the 2026-27 completed-game bridge smoke when evidence exists |
| Program D snapshots | Foundation complete for approved 2024-25 and 2025-26 seasons | Preserve cutoff/completeness gates; no automatic expansion into unsupported seasons |
| Program E SoS | Research wording/examples approved only | No production field, route, cache, or default Daily insight |
| Program G | Research gates complete; prediction publication blocked | Continue monitoring/ablation; next model gate is pre-registered walk-forward and calibration review |
| Program H0 | Evidence audit complete | Availability and starter coverage remain incomplete |
| Program H1 | Foundation and bounded apply/replay complete | [Pre-registered calibration protocol](research/PROGRAM_H_H1_ROLE_BAND_CALIBRATION_PROTOCOL_2026-09-13.md), then forward timing evidence before any consumer |
| 2026-27 bridge | Wired; quiet-day proof passed | First completed game required for Traditional → Advanced → C5 → replay smoke |
| Odds observation pilot | One-request SportsGameOdds probe passed; source approval remains open | Canonical identity mapping, pair/timestamp review, licensing/coverage; no edge claims |

## What is blocked versus what is not

### Blocked by external or evidence state

- The real 2026-27 bridge smoke cannot run before a completed game exists.
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

- Keep the 2026-27 bridge and role-history projection ready for the first game.
- Run the read-only source-timing audit and record forward evidence.
- Execute the now pre-registered H1 walk-forward calibration once an approved
  timing population exists; the complete historical date-proxy rehearsal is
  recorded but remains audit-only.
- Continue G monitoring and frozen feature-family comparisons.
- Improve Daily presentation, accessibility, freshness language, and historical
  route QA without changing the semantic contract.
- Prepare odds-provider evaluation and deployment/runbook changes without
  publishing market conclusions.

## Latest forward-timing baseline — 2026-09-13

The read-only H1 timing audit was rerun across the two approved historical
seasons and the current-season bridge. Historical facts all have a
`data_available_at`, but those values are 2026 backfill timestamps rather than
original source-publication times, so none of the exact target-team rows has
strictly eligible historical role history under the production cutoff. The
current season has exact schedule precision but no completed-game facts yet.

| Season | Facts | Exact target-team rows | Rows with strict prior history | Interpretation |
| --- | ---: | ---: | ---: | --- |
| 2024-25 | 32,515 | 10 | 0 | Backfill timing is not production-safe |
| 2025-26 | 32,179 | 1,994 | 0 | Backfill timing is not production-safe |
| 2026-27 | 0 | 2,400 | 0 | Awaiting the first completed game |

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

## Definition of the next launch gates

1. First 2026-27 completed-game bridge run: exact schedule identity, Traditional
   facts, Advanced facts, C5 reconciliation, role-history write, and exact
   replay/no-op proof.
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
