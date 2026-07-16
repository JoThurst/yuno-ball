# Yuno Ball Data Dictionary

Status: canonical inventory of tables defined by the reviewed repository
Reviewed: 2026-07-15. Table definitions come from `app/models/*_sqlalchemy.py` and Alembic migrations; production DDL should be verified against the live database before migrations.

## Conventions

* Seasons use NBA format `YYYY-YY`, such as `2024-25`.
* NBA team and player IDs should be stored without remapping. The reviewed `teams` DDL uses `SERIAL`, but ingestion expects NBA team IDs; treat NBA IDs as the canonical value.
* A game is stored from each team's perspective, so `(game_id, team_id)` identifies a team-game row.
* `Regular Season` and `Playoffs` must not overwrite each other.
* PostgreSQL is the durable system of record. Schema changes use the Alembic chain in `alembic/versions`; some legacy psycopg2 persistence remains during migration to SQLAlchemy.

## Table catalog

| Table                    | Grain / key                                                                     | Key columns                                                                                                    | Source                                                      | Intended refresh                              |
| ------------------------ | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | --------------------------------------------- |
| `players`                | one row per player; PK `player_id`                                              | `name`, `position`, `weight`, `born_date`, `age`, `exp`, `school`, `available_seasons`                         | `nba_api.stats.static.players` plus `CommonPlayerInfo`      | weekly / player discovery                     |
| `statistics`             | one player-season; unique `(player_id, season_year)`                            | `points`, `rebounds`, `assists`, `steals`, `blocks`                                                            | `PlayerCareerStats`                                         | weekly or backfill                            |
| `teams`                  | one row per team; PK `team_id`                                                  | `name`, `abbreviation`                                                                                         | team seed/static NBA identity data                          | rarely; verify each season                    |
| `roster`                 | one player-team-season; PK `(team_id, player_id, season)`                       | `player_name`, `player_number`, `position`, `how_acquired`                                                     | `CommonTeamRoster`                                          | daily during season                           |
| `game_schedule`          | one team perspective per game; PK `(game_id, team_id)`                          | season/type, opponent, date/precision, home/away, result, structured scores, source lineage                    | NBA schedule providers; reviewed external promotion         | daily; bounded historical promotion           |
| `gamelogs`               | one player-game; PK `(player_id, game_id)`                                      | `team_id`, box-score counts, `minutes_played`, `season`                                                        | `PlayerGameLogs`                                            | daily; historical backfill by player/season   |
| `team_game_stats`        | one team-game; PK `(game_id, team_id)`                                          | `opponent_team_id`, `season`, `game_date`, shooting, rebounds, assists, defense, turnovers, points, plus/minus | `TeamGameLog` joined to `game_schedule`                     | backfill by season; should update after games |
| `leaguedashplayerstats`  | one player-season; PK `(player_id, season)`                                     | team identity, totals/rates, fantasy stats, double/triple doubles, endpoint ranks                              | `LeagueDashPlayerStats`                                     | daily current season; historical backfill     |
| `league_dash_team_stats` | one team-season-season type; PK `(team_id, season, season_type)`                | prefixed metric families for 7 measures x 3 per modes, including ranks                                         | `LeagueDashTeamStats`                                       | daily current season; historical backfill     |
| `player_streaks`         | one player/stat/threshold/season; unique `(player_id, stat, season, threshold)` | `player_name`, `streak_games`, `created_at`                                                                    | last 10 from `PlayerGameLogs`                               | daily; table rebuilt each run                 |
| `player_z_scores`        | one legacy overwrite row per player; PK `player_id`                            | unversioned stat z-scores                                                                                      | deprecated historical writer                               | read-only; replaced by player heat snapshots |
| `ingestion_runs`         | one command execution; PK `run_id`                                             | run/source/season/date/cutoff, status, validation, versions, counts, bounded error, timestamps                 | Yuno Ball orchestration                                     | append per operational command                |
| `ingestion_task_runs`    | one named task in a run; unique `(run_id, task_name)`                           | source/provider, status, counts, bounded error, timestamps                                                     | fetch/calculate/validation task instrumentation             | append per task; terminal update once         |
| `external_dataset_imports` | one immutable artifact registration per source/dataset/version/hash/transformation | file identity, SHA-256, durable locator, download precision, license/use status, validation status, source run | external artifact inspection; no source-row import          | append or exact idempotent registration       |
| `stg_statsurge_availability` | one valid source row per manifest/logical row/parser; natural source grain also unique | preserved source values, parsed date/season, checkpoint precision, resolved identity candidates, version/run/method evidence, row hash and run lineage | registered Stat Surge daily checkpoint artifact | immutable staging import plus idempotent staging-only identity reconciliation |
| `external_row_rejections` | one quarantined source row per manifest/logical row/parser | row hash, reason code/detail, raw JSON values, source file and run lineage | external source parsers | append on parser validation failure |
| `stg_kaggle_games` | one source team perspective per manifest/game/team/parser | paired game/team IDs, source date/result and nullable box facts, season/type, eligibility and canonical-match states | registered `nba_games_all.csv` | immutable staging import; exact rerun is a no-op |
| `stg_kaggle_moneylines` | one source row per manifest/game/book/team/opponent/parser | two team-selection American prices, unknown timing, source-game and run lineage | registered historical moneyline CSV | atomic three-market staging |
| `stg_kaggle_spreads` | one source row per manifest/game/book/team/opponent/parser | selection-specific spread/price pairs and pair status, unknown timing | registered historical spread CSV | atomic three-market staging |
| `stg_kaggle_totals` | one source row per manifest/game/book/team/opponent/parser | separate over/under total/price pairs and pair status, unknown timing | registered historical totals CSV | atomic three-market staging |
| `external_market_anomalies` | one quarantined semantic market row per manifest/logical row/parser | market, game, reason, raw values, artifact/game/run lineage | Kaggle market parser | append on declared anomaly rule |
| `player_consecutive_streak_snapshots` | one player/stat/threshold/cutoff/version/streak kind | streak range, active state, season/type, provenance, completeness | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |
| `player_stat_window_snapshots` | one player/stat/threshold/window/cutoff/version | games played/hit, last game, season/type, provenance, completeness | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |
| `player_heat_index_snapshots` | one player/stat/window/cutoff/version | sample sizes, averages, stddev, z-score, status, provenance | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |
| `player_consistency_snapshots` | one player/stat/window/cutoff/version | sample size, mean/stddev/CV/range/median/tier, provenance | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |
| `team_game_feature_snapshots` | one scheduled game/team/window/cutoff/version | curated season/recent efficiency, deltas, SoS, rest, flags, provenance/completeness | pre-cutoff paired `team_game_stats` + `game_schedule` | append/upsert one pregame team perspective |
| `game_environment_snapshots` | one scheduled game/window/cutoff/version | paired home/away form, pace/scoring/three/chaos environment, tags, provenance/completeness | exact-cutoff team feature snapshots | append/upsert one pregame game environment |

## Column details

### `players`

`player_id INT PK`; `name VARCHAR(255)`; `position VARCHAR(50)`; `weight INT`; `born_date VARCHAR(25)`; `age INT`; `exp INT`; `school VARCHAR(255)`; `available_seasons TEXT`.

Notes: `age` is time-dependent and currently calculated from year only. `available_seasons` is comma-delimited text; normalize if it becomes a frequent query dimension.

### `statistics`

`stat_id SERIAL PK`; `player_id INT FK players`; `season_year VARCHAR(7)`; `points`, `rebounds`, `assists`, `steals`, `blocks INT`; unique `(player_id, season_year)`.

Notes: NBA career endpoint values are season aggregates, despite generic names. Prefer `leaguedashplayerstats` for richer league-comparable aggregates.

### `teams` and `roster`

`teams`: `team_id SERIAL PK`, `name VARCHAR(255)`, `abbreviation VARCHAR(10)`.

`roster`: `team_id FK teams`, `player_id FK players`, `player_name`, `player_number`, `position`, `how_acquired`, `season`; PK `(team_id, player_id, season)`.

Notes: roster seasons are canonical `YYYY-YY`. Refresh normalizes the provider
payload, resolves every player first, then atomically upserts and removes absent
members only within the requested team-season. Empty or partially unresolved
payloads fail closed and previous seasons are never deleted.

### `game_schedule`

`game_id VARCHAR`; `season VARCHAR`; explicit `season_type` in `Pre Season`,
`Regular Season`, `All-Star`, `Playoffs`, `Play-In`, `NBA Cup`, or `Unknown`;
`team_id BIGINT FK teams`; `opponent_team_id BIGINT FK teams`; `game_date
TIMESTAMP`; `game_date_precision` in `exact/date_only`; `home_or_away CHAR(1)`
in `H/A`; nullable `result CHAR(1)` in `W/L`; legacy nullable `score VARCHAR`;
nullable paired numeric `team_score` and `opponent_score`; `source_name`; and
optional row-level `source_import_id`, `source_run_id`, `source_row_number`,
`source_row_sha256`, and `source_parser_version`. PK `(game_id, team_id)`.

Notes: there are two reciprocal team-perspective rows per game. Numeric scores
are authoritative when populated; the older `score` string remains for
backward compatibility and is not repaired by the schema migration. Existing
rows are labeled `legacy_nba_pipeline`, while new NBA schedule writes infer
event type from the NBA game-ID prefix and record `nba-cdn-schedule`. Rows from
`kaggle-uploaded-pack` require complete manifest/run/row/parser lineage and
paired numeric scores at the database boundary.

For bounded historical repair, null `result` pairs may be reconciled from
`team_game_stats.wl` and `team_game_stats.pts` only when both sources contain
the same reciprocal team pair and date, one W and one L, and non-tied scores.
`scripts/reconcile_schedule_results.py` never overwrites a non-null result and
blocks the full transaction on an ambiguous or conflicting game.

### `gamelogs`

`player_id BIGINT`; `game_id VARCHAR`; `team_id BIGINT`; `points`, `assists`, `rebounds`, `steals`, `blocks`, `turnovers INT`; `minutes_played VARCHAR`; `season VARCHAR`; PK `(player_id, game_id)`.

Notes: player-game writes use an atomic `ON CONFLICT (player_id, game_id) DO
UPDATE` for mutable box-score fields. Missing provider values remain `NULL`
rather than being converted to basketball zeroes. New writes normalize game IDs
to ten digits and seasons to `YYYY-YY`; composite schedule and player foreign
keys protect the observation grain. Minutes remain provider-formatted text and
should be migrated numerically in a future bounded schema change.

### `team_game_stats`

Identity: `game_id`, `team_id`, `opponent_team_id`, `season`, `game_date`.
Shooting: `fg`, `fga`, `fg_pct`, `fg3`, `fg3a`, `fg3_pct`, `ft`, `fta`, `ft_pct`.
Other: `reb`, `ast`, `stl`, `blk`, `tov`, `pts`, `plus_minus`.
PK `(game_id, team_id)`; FK `(game_id, team_id)` to `game_schedule` with cascade delete.

Notes: reviewed ingestion forces `plus_minus = 0`; do not use that column as a model feature until corrected. A retrieval method's positional mapping predates `game_date` and is currently offset; prefer named-column results.

The single-column `oreb`, `dreb`, and `wl` indexes were removed after PostgreSQL recorded zero scans while the table's season, team, and primary-key indexes were actively used. The column comments remain part of the ORM metadata.

### `leaguedashplayerstats`

Identity: `player_id`, `player_name`, `season`, `team_id`, `team_abbreviation`, `age`.
Base values: `gp`, `w`, `l`, `w_pct`, `min`, `fgm`, `fga`, `fg_pct`, `fg3m`, `fg3a`, `fg3_pct`, `ftm`, `fta`, `ft_pct`, `oreb`, `dreb`, `reb`, `ast`, `tov`, `stl`, `blk`, `blka`, `pf`, `pfd`, `pts`, `plus_minus`, `nba_fantasy_pts`, `dd2`, `td3`, `wnba_fantasy_pts`.
Ranks: matching `*_rank` columns for endpoint-ranked metrics.
PK `(player_id, season)`.

Notes: the current key cannot represent a player traded between teams as separate stints and endpoint aggregate simultaneously. Decide whether the desired grain is player-season overall or player-team-season.

### `league_dash_team_stats`

Identity: `team_id`, `team_name`, `season`, `season_type`; PK `(team_id, season, season_type)`.

Metric columns follow:

`{measure}_{per_mode}_{stat}`

* Measures: `base`, `advanced`, `misc`, `fourfactors`, `scoring`, `opponent`, `defense`.
* Per modes: `totals`, `per48`, `per100possessions`.
* Stats vary by measure and include NBA-returned values and rank columns.

Examples: `base_totals_pts`, `base_per100possessions_fg_pct_rank`, `advanced_totals_off_rating`, `advanced_per100possessions_def_rating`, `fourfactors_per48_efg_pct`, and opponent/defense-prefixed fields.

Notes: the wide schema is endpoint-shaped and currently hundreds of columns. Validate every generated key against allowed columns before dynamic SQL. For modeling, prefer stable curated feature views over selecting directly from this table.

### `player_streaks`

`id SERIAL PK`; `player_id`; `player_name`; `stat`; `threshold`; `streak_games`; `season`; `created_at`; unique `(player_id, stat, season, threshold)`.

Implemented thresholds: PTS `10/15/20/25`, REB `4/6/8/10`, AST `2/4/6/8/10`, FG3M `1/2/3/4`; rows require at least 7 qualifying games among the fetched last 10.

Notes: this is a count in the last ten, not a necessarily consecutive streak. Rename the metric or calculate consecutive games if the UI claims consecutive streaks.

### `ingestion_runs` and `ingestion_task_runs`

`ingestion_runs.run_id UUID-shaped VARCHAR(36) PK`; optional self-referencing `parent_run_id`; `run_type`; `source`; canonical `season`; optional `season_type`, `target_date`, and `feature_cutoff`; `status` in `running/success/partial/failed`; `validation_status` in `not_run/passed/failed/skipped`; start/finish timestamps; optional row counts, provider, code/calculation versions, bounded error metadata, and JSON details.

`ingestion_task_runs.task_run_id UUID-shaped VARCHAR(36) PK`; `run_id FK ingestion_runs ON DELETE CASCADE`; unique `(run_id, task_name)`; `source`; `status` in `running/success/skipped/failed`; start/finish timestamps; optional row counts, provider, bounded error metadata, and JSON details.

The tables are operational history, not analytical snapshots. `daily_ingest.py`, standalone `daily_fetch.py`, and standalone `daily_calculate.py` acquire one PostgreSQL advisory lock name before creating a root run. Child commands attach tasks to the parent run through `YUNOBALL_INGESTION_RUN_ID` and do not compete for a second lock.

### `external_dataset_imports`

`import_id UUID-shaped VARCHAR(36) PK`; source and dataset names/version;
source URL; local file name, byte size, SHA-256, and media type; optional
`downloaded_at` with an explicit precision of `exact`, `file_mtime`, or
`unknown`; durable `storage_locator`; license identifier, review status, and
commercial-use status; immutable `transformation_version`;
`source_run_id FK ingestion_runs`; optional inspected row count;
`validation_status` in `registered/profiled/failed/rejected`; JSON manifest
details; and created/updated timestamps.

The natural key is `(source_name, dataset_name, dataset_version, sha256,
transformation_version)`. Re-registering byte-identical metadata is a no-op;
changing immutable metadata under the same key fails instead of rewriting
provenance. A `registered` row proves that the artifact was inspected and
recorded, not that its contents, license, or commercial use have been approved.
This table contains manifests only: source rows are not staged or promoted.
`dataSource/archive` is temporary and must not be recorded as the durable
storage locator.

### `stg_statsurge_availability` and `external_row_rejections`

`stg_statsurge_availability` preserves the original `PLAYER`, `STATUS`,
`REASON`, `TEAM`, `GAME`, and `DATE` values as named columns and JSON, plus a
logical source row number, row SHA-256, parsed `report_date`, derived canonical
season, source artifact/run IDs, and parser version. Its source natural grain
is `(source_dataset_version, report_date, matchup_text, reported_team_name,
reported_player_name)` within one manifest/parser version.

The archive is one daily checkpoint per source row, not report-revision
history. Every staged row therefore stores `source_checkpoint =
daily_2pm_report`, `source_published_at = NULL`, `source_time_precision =
report_checkpoint`, and `source_time_confidence = methodology_level`. Initial
rows are explicitly `identity_unresolved` and `not_evaluated` for pregame
cutoff safety. The versioned reconciliation then resolves only exact team names
(plus one reviewed Clippers alias), unique normalized player names, and strict
matchup/date game pairs. It stores `identity_resolution_version`, the resolving
ingestion run, and JSON method/candidate evidence without changing raw values.

The validated `statsurge-identity-v1` run resolves all three identities for
35,234 of 35,522 rows; 288 remain partial, including 257 player-unresolved rows
across 14 names and 31 rows for two missing/cancelled games. There are zero
identity conflicts. Every row remains `validation_status = staged` and
`cutoff_status = unknown` because methodology-level 2 p.m. semantics plus a
date-only schedule cannot prove strict pregame availability.

`external_row_rejections` retains a rejected row's raw values, row hash,
logical source row number, reason, manifest, parser, and ingestion run. The
import transaction requires every source row to exist in exactly one staged or
rejected partition. Neither table is an application-serving or model-feature
contract.

### Kaggle game and historical market staging

`stg_kaggle_games` preserves all 125,624 team-perspective source rows at unique
`(source_import_id, game_id, team_id, parser_version)` grain. Every valid source
game has exactly two reciprocal team perspectives. Blank historical fields stay
`NULL`; cancelled/non-final rows may have null W/L, and 6,248 source rows retain
missing dates. `promotion_eligibility` separates the 2006-07 through 2017-18
regular-season/playoff range from pre-2006 history, preseason/All-Star events,
and the incomplete 2018-19 fragment. `canonical_match_status` records exact-ID
reconciliation. The playoff-only promotion on 2026-07-16 inserted 838 missing
games (1,676 reciprocal rows), marked those source rows `promoted`, and marked
all 999 eligible playoff games `matched`. The 12,059 missing eligible
regular-season games remain staged for a separate bounded phase; 363 require
the audited unanimous player-game date repair before promotion.

The three market tables preserve source-row grain
`(source_import_id, game_id, book_id, team_id, opponent_team_id,
parser_version)` and have a composite foreign key to the staged source
game/team perspective. They store a single `historical_static` snapshot with
`timing_precision = unknown`; no row may be called opening, closing, or
prediction-time odds. Non-inverse spread lines and differing over/under totals
are retained as `selection_specific`, not normalized away.

`external_market_anomalies` currently quarantines both-positive moneylines,
spread prices with absolute value above 750, and totals outside the initial
150-260 range. All source rows must reconcile exactly into staged, anomaly, or
parser-rejection partitions. These tables have no route, cache, canonical
observation, or modeling consumer.

### Versioned player analytical snapshots

All four Phase 2 tables include canonical `season`, separate `season_type`,
`feature_as_of`, `data_available_at`, immutable `calculation_version`,
`source_run_id FK ingestion_runs`, `completeness_status`, JSON
`missing_input_flags`, and `created_at`. The current version is `player-v2.1`.
Natural keys include the metric dimensions, cutoff, and calculation version;
rerunning that exact key is an idempotent upsert, while a new version preserves
the prior rows.

Snapshots are published at 10:00 ET for a target league slate date and exclude
every game whose Eastern calendar date is the target date or later. The current
source-availability rule is scheduled tipoff plus six hours. Only complete rows
are selected by serving readers. Missing source stats are not converted to zero;
the affected player/stat result is omitted from the complete publication.
Non-slate dates do not create snapshot rows.

### Versioned team/game analytical snapshots

Phase 3 adds `team_game_feature_snapshots` and
`game_environment_snapshots` under calculation version `team-v2.1`. Team
features are unique on `(game_id, team_id, window_size, feature_as_of,
calculation_version)` and retain the composite schedule foreign key. Game
environments are unique on `(game_id, window_size, feature_as_of,
calculation_version)` and retain separate composite home/away schedule foreign
keys.

The team row stores curated season-to-date and recent-window offensive rating,
defensive rating, net rating, pace, eFG%, turnover percentage, offensive rebound
percentage, free-throw rate, three-point scoring share, deltas, opponent-strength
summaries, schedule density/rest, versioned flags, source coverage counts, and
missing-input details. `season_games_used` and `window_games_used` expose games
excluded for incomplete paired box scores; missing values are never coerced to
basketball zero. Early-season rows remain `partial` until the requested window
is available.

Both tables use the 10:00 ET slate cutoff and `scheduled_tipoff + 6 hours`
source-availability proxy. Inputs must have an Eastern game date strictly before
the slate date. Readers select the latest complete version with
`feature_as_of <= requested_cutoff` and never fall forward. Legacy
`team_daily_metrics`, `team_daily_flags`, and `game_environment_daily` remain
latest-state UI compatibility projections and are prohibited historical model
inputs.

`league_dash_team_stats` remains the latest endpoint-shaped provider table. It
is not copied into historical snapshots and is not a point-in-time source. The
curated v2 tables are the stable analytical boundary; raw observation history
for the wide provider payload remains intentionally deferred.

`team_schedule_factors` references the matching team-perspective schedule row through composite FK `(game_id, team_id) -> game_schedule(game_id, team_id)` with cascade delete. A single-column FK on `game_id` is invalid because `game_schedule` stores two rows per game.

## Planned analytical tables (not implemented)

These are contracts from the modeling plan, not current tables:

* `game_model_labels`: one completed game with home/away scores, margin, total, and winner.
* `model_predictions`: immutable prediction records with model version, as-of timestamp, and probabilities/estimates.

See `MODEL_FEATURE_PLAN.md`; do not silently add them to current-state diagrams until migrations exist.
