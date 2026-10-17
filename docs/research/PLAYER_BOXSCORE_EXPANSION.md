# Yuno Ball Player Box-Score Expansion

Status: proposed implementation specification  
Prepared: 2026-07-15  
Prerequisite: foundation phases complete and current-season source reconciliation passed.

## Problem

The current player gamelog contract is too thin for serious role, matchup, availability-impact, or player-prop analysis. It primarily stores:

- points;
- rebounds;
- assists;
- steals;
- blocks;
- turnovers;
- minutes as text.

It lacks the shooting, participation, role, efficiency, and possession context needed for differentiated analysis.

## Goals

1. Add complete traditional player game facts.
2. Add a separate advanced player-game table.
3. Preserve corrected box-score updates.
4. Support arbitrary seasons without manual code changes.
5. Retain source and ingestion provenance.
6. Avoid a single unstable table containing every endpoint field.
7. Provide stable curated contracts to downstream calculations.

## Source research

Evaluate current V3 NBA box-score endpoints through the repository's centralized provider layer.

Candidate endpoint families:

- traditional box score;
- advanced box score;
- usage;
- scoring;
- four factors;
- matchup;
- summary.

Do not assume dataset order. Access named datasets and add response-schema contract tests.

For each endpoint, test:

- successful retrieval;
- dataset names;
- required parameters;
- historical coverage;
- regular season and playoffs;
- overtime;
- DNP/inactive players;
- traded players;
- missing fields;
- schema drift;
- latency;
- corrected-game behavior.

Retain sanitized raw fixtures for tests.

## Proposed stable tables

### `player_game_boxscores`

Grain: `(game_id, player_id)`.

Suggested fields:

- `game_id`
- `player_id`
- `team_id`
- `season`
- `season_type`
- `game_date`
- `started`
- `position`
- `participation_status`
- `participation_comment`
- `minutes`
- `fgm`
- `fga`
- `fg_pct`
- `fg3m`
- `fg3a`
- `fg3_pct`
- `ftm`
- `fta`
- `ft_pct`
- `oreb`
- `dreb`
- `reb`
- `ast`
- `stl`
- `blk`
- `tov`
- `pf`
- `pts`
- `plus_minus`
- `source`
- `source_updated_at`
- `source_run_id`
- `created_at`
- `updated_at`

Use numeric minutes.

Do not infer `started` from minutes. Store null when the source does not provide a truthful value.

### `player_game_advanced`

Grain: `(game_id, player_id, calculation/source version)` if endpoint revisions must coexist; otherwise `(game_id, player_id)` with correction-aware source upserts.

Candidate fields:

- offensive rating;
- defensive rating;
- net rating;
- assist percentage;
- assist-to-turnover;
- offensive/defensive/total rebound percentages;
- effective field-goal percentage;
- true-shooting percentage;
- usage percentage;
- pace;
- possessions;
- PIE;
- source metadata.

Only keep fields that pass source and semantic validation.

### Raw endpoint observations

Do not place every provider field directly into the curated tables.

Retain raw payload references with:

- endpoint;
- parameters;
- request/retrieval time;
- source game ID;
- response hash;
- endpoint schema version;
- parse status;
- source run ID.

## Relationship to current `gamelogs`

Use an expand/migrate/contract approach.

1. Add the new tables.
2. Populate a bounded sample.
3. Validate against current gamelogs.
4. Update calculations to prefer new fields.
5. Retain compatibility queries temporarily.
6. Backfill eligible seasons.
7. Deprecate thin gamelog reads only after all consumers migrate.

Do not drop the existing table in the first release.

## Corrected box scores

Source game facts may be corrected.

Required behavior:

- upsert mutable box-score fields at the natural grain;
- update `source_updated_at`;
- retain ingestion-run history;
- record which derived snapshots require recalculation;
- do not silently rewrite previously published predictions;
- allow new derived calculation versions after a source correction.

## Backfill policy

Before backfill, report:

- games by season;
- expected player rows;
- source success rate;
- unmatched players/teams;
- null rate by field;
- current gamelog overlap;
- corrected-value differences;
- estimated calls and runtime.

Commands should support:

- `--season`
- `--season-type`
- `--date-from`
- `--date-to`
- `--game-id`
- `--team-id`
- `--dry-run`
- `--resume`
- bounded concurrency.

## Initial derived uses

The first uses should be descriptive:

- minutes trend;
- starting frequency;
- shot-volume trend;
- scoring efficiency;
- free-throw pressure;
- offensive-rebounding role;
- foul risk;
- turnover load;
- usage and true-shooting context;
- teammate-availability role changes.

Do not start player-prop claims immediately.

## Role Stability research

Candidate features:

- median minutes;
- interquartile range of minutes;
- starting percentage;
- usage mean and volatility;
- field-goal-attempt share;
- free-throw-attempt share;
- games since role change;
- teammate availability;
- replacement-level minutes;
- sample size.

Every historical value must use games before the target cutoff.

## Validation

- row uniqueness;
- player/team/game foreign-key integrity;
- numeric minutes;
- team/player totals reconcile with official team totals within known semantics;
- source final score matches schedule;
- DNP rows distinguished from zero-stat participation;
- corrected records update;
- regular season and playoffs do not overwrite;
- no hard-coded season;
- rerun idempotency;
- raw endpoint contract tests;
- useful partial state when an advanced endpoint fails.

## Acceptance criteria

- complete traditional player box scores exist at a stable grain;
- advanced metrics are separate and curated;
- downstream services do not depend on positional response tuples;
- all values carry source/run provenance;
- corrected boxes update safely;
- historical backfill is bounded and resumable;
- player-role analytics can be calculated without using future games;
- current pages expose freshness and missing states;
- no production model assumes availability or role fields that are absent.
