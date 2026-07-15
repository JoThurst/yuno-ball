# ADR 0001: Versioned Historical Analytical Snapshots

- Status: Accepted for incremental implementation
- Date: 2026-07-15
- Decision owners: Yuno Ball engineering

## Context

Yuno Ball currently mixes durable source facts, current operational state, and analytical snapshots. Several derived player tables are cleared and rebuilt for a season. Team rows carry a calculation date but consume current endpoint aggregates and unbounded game histories. Historical slate queries then select the latest season row rather than the latest row known at the requested cutoff.

This makes reruns destructive, historical pages unstable, and model backfills vulnerable to target-game or future-game leakage.

## Decision

Yuno Ball will use three explicit persistence classes:

1. Durable source facts, such as one team box score or player game log at its natural grain. Corrections update the current canonical fact; raw source observations may be added when correction history has product or audit value.
2. Latest operational state, such as the current schedule row, latest player status, latest bookmaker line, or current league endpoint aggregate. These tables optimize serving and are not historical training inputs.
3. Historical analytical snapshots, published append-only at a meaningful feature cutoff and calculation version.

Every new historical analytical snapshot will include:

- canonical `season` and `season_type`;
- `feature_as_of`, representing the latest instant data was allowed into the calculation;
- `data_available_at` or an explicitly documented source-availability rule;
- immutable `calculation_version`;
- `source_run_id`;
- `created_at`;
- completeness state and machine-readable missing-input flags.

Snapshot natural keys include their entity dimensions, cutoff, and calculation version. Re-running the same key is an idempotent upsert. A corrected algorithm or changed source-availability interpretation publishes a new calculation version rather than rewriting an already published version.

## Cutoff and selection contract

- Pregame features use only games with an actual event time strictly earlier than the target tipoff.
- Rolling and expanding features are computed after ordering by actual game time and applying an explicit one-game shift where the target row is present in the calculation frame.
- Current endpoint aggregates are prohibited for historical pregame reconstruction unless an observation captured before the target tipoff exists.
- Missing inputs remain missing. Zero is stored only when the source explicitly reports basketball zero.
- Readers select the latest complete snapshot satisfying `feature_as_of <= requested_cutoff` for the requested calculation version.
- Readers do not fall forward to a newer snapshot. A missing eligible snapshot yields an honest missing/stale state.

## Publication and failure contract

Calculations stage or buffer a complete grain, validate it, and merge it in one transaction. Publication records are marked complete only after the merge and validation commit. A failed run retains the last complete published snapshot and does not warm related caches.

One advisory job lock prevents overlapping runs for the same operational pipeline. Durable run and task records capture requested season/date/cutoff, status, timestamps, provider, code and calculation versions, row counts, validation result, parent run, and bounded error summaries.

## Season contract

Season values use `YYYY-YY` everywhere. The domain layer provides validation, formatting, parsing, previous/next transitions, and date-based season membership. Operational selection distinguishes:

- `season_for_date`: pure calendar membership;
- `latest_known_season`: newest canonical season represented in durable data;
- `active_ingestion_season`: explicit override, otherwise schedule-aware operational selection;
- `default_display_season`: UI policy, allowed to differ from ingestion policy.

Season type is a separate dimension. Playoffs do not start a new season.

## Migration strategy

Use expand, migrate, contract:

1. Add v2 snapshot tables, indexes, run records, and shared readers.
2. Dual-read or explicitly switch consumers after validating parity and cutoff behavior.
3. Backfill only bounded, eligible source coverage under a new calculation version.
4. Retire old tables in a later approved migration after rollback and retention requirements are satisfied.

No initial migration drops legacy tables or historical rows.

## Phase 2 player snapshot decision

Phase 2 uses four metric-specific append-only tables rather than one polymorphic
JSON table: `player_consecutive_streak_snapshots`,
`player_stat_window_snapshots`, `player_heat_index_snapshots`, and
`player_consistency_snapshots`. This retains typed metric columns and lets each
natural key express its real dimensions.

The canonical player snapshot is one league-slate-date publication at 10:00
America/New_York for `player-v2.1`. Inputs are ordered by the canonical
`game_schedule.game_date` UTC event timestamp and must belong to a local NBA calendar date strictly before
the target slate date. This is the smallest grain that supports Daily serving
and reusable pregame modeling without duplicating every player row per game. A
future intraday or per-game product must use a separate finer grain.
Days without a scheduled game for the requested season type publish no snapshot.

Because source facts do not yet store an observed-at timestamp, Phase 2 uses the
documented rule `scheduled_tipoff + 6 hours` for `data_available_at`. A snapshot
is rejected when that proxy is later than `feature_as_of`; `created_at` records
publication time. Changing this rule requires a new calculation version.

Daily uses `player_stat_window_snapshots` as the publication anchor, then reads
all four metric families at exactly the same cutoff and version. Before the
first v2 anchor exists, legacy latest-state tables remain the current-date
rollback/read compatibility path. Historical requests never use that fallback.
Once an anchor exists, an empty metric family remains
honestly empty rather than falling back to a future legacy row.

## Phase 3 team/game snapshot decision

Phase 3 uses two typed additive tables. `team_game_feature_snapshots` stores one
scheduled team perspective per game, window, cutoff, and calculation version.
`game_environment_snapshots` stores the paired home/away environment at that
same cutoff/version. The current calculation version is `team-v2.1`.

Historical team season and recent metrics are rebuilt exclusively from paired
`team_game_stats` joined to canonical schedule event times. The target slate
date and all later games are excluded in both the database query and pure
builder. Missing team/opponent box-score values exclude that game from the
calculation and are recorded with played/used counts; they are never replaced
with zero. Early-season windows remain partial.

`league_dash_team_stats` remains latest provider state and a current validation
reference. It is not copied into the v2 history because its hundreds of
endpoint-shaped columns lack point-in-time observations and are vulnerable to
schema drift. The chosen stable boundary is a curated set of game-fact-derived
efficiency, four-factor, opponent-strength, rest, flag, and environment fields.
Raw wide endpoint observation history may be added later only with truthful
observation timestamps and a separate retention contract.

Daily publication writes team and environment rows in one transaction after
schedule factors. Historical publication is bounded to scheduled slate dates,
supports dry run, resume, team filter, and explicit calculation versions, and
does not replace legacy current UI projections in this phase. Historical
readers use latest-complete `feature_as_of <= requested_cutoff`; legacy tables
are never a historical fallback.

## Consequences

Storage and query keys become wider, and backfills require more operational discipline. In return, historical pages and model features become reproducible, reruns become safe, source corrections are explicit, and freshness/completeness can be shown honestly to users.

## Rejected alternatives

- Adding only `stat_date` to current replacement tables: it does not enforce an input cutoff or algorithm version.
- Copying all 772 league team endpoint columns into every daily snapshot: it is expensive and still fails without point-in-time source observations.
- Reconstructing historical endpoint aggregates from today's endpoint response: it leaks future knowledge.
- Replacing missing metrics with zero: it changes basketball meaning and hides source failures.
- Dropping old tables while creating v2: it removes the rollback path.
