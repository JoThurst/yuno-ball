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
| `game_schedule`          | one team perspective per game; PK `(game_id, team_id)`                          | `season`, `opponent_team_id`, `game_date`, `home_or_away`, `result`, `score`                                   | `LeagueGameFinder`; future games from NBA CDN schedule JSON | daily; historical backfill by season          |
| `gamelogs`               | one player-game; PK `(player_id, game_id)`                                      | `team_id`, box-score counts, `minutes_played`, `season`                                                        | `PlayerGameLogs`                                            | daily; historical backfill by player/season   |
| `team_game_stats`        | one team-game; PK `(game_id, team_id)`                                          | `opponent_team_id`, `season`, `game_date`, shooting, rebounds, assists, defense, turnovers, points, plus/minus | `TeamGameLog` joined to `game_schedule`                     | backfill by season; should update after games |
| `leaguedashplayerstats`  | one player-season; PK `(player_id, season)`                                     | team identity, totals/rates, fantasy stats, double/triple doubles, endpoint ranks                              | `LeagueDashPlayerStats`                                     | daily current season; historical backfill     |
| `league_dash_team_stats` | one team-season-season type; PK `(team_id, season, season_type)`                | prefixed metric families for 7 measures x 3 per modes, including ranks                                         | `LeagueDashTeamStats`                                       | daily current season; historical backfill     |
| `player_streaks`         | one player/stat/threshold/season; unique `(player_id, stat, season, threshold)` | `player_name`, `streak_games`, `created_at`                                                                    | last 10 from `PlayerGameLogs`                               | daily; table rebuilt each run                 |
| `ingestion_runs`         | one command execution; PK `run_id`                                             | run/source/season/date/cutoff, status, validation, versions, counts, bounded error, timestamps                 | Yuno Ball orchestration                                     | append per operational command                |
| `ingestion_task_runs`    | one named task in a run; unique `(run_id, task_name)`                           | source/provider, status, counts, bounded error, timestamps                                                     | fetch/calculate/validation task instrumentation             | append per task; terminal update once         |
| `player_consecutive_streak_snapshots` | one player/stat/threshold/cutoff/version/streak kind | streak range, active state, season/type, provenance, completeness | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |
| `player_stat_window_snapshots` | one player/stat/threshold/window/cutoff/version | games played/hit, last game, season/type, provenance, completeness | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |
| `player_heat_index_snapshots` | one player/stat/window/cutoff/version | sample sizes, averages, stddev, z-score, status, provenance | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |
| `player_consistency_snapshots` | one player/stat/window/cutoff/version | sample size, mean/stddev/CV/range/median/tier, provenance | pre-cutoff `gamelogs` + `game_schedule` | append/upsert one logical slate snapshot |

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

Notes: current roster refresh deletes all rows for a team, not only the current season. This can erase historical roster membership and should be corrected before roster history is treated as training data.

### `game_schedule`

`game_id VARCHAR`; `season VARCHAR`; `team_id BIGINT FK teams`; `opponent_team_id BIGINT FK teams`; `game_date TIMESTAMP`; `home_or_away CHAR(1)` in `H/A`; nullable `result CHAR(1)` in `W/L`; nullable `score VARCHAR`; PK `(game_id, team_id)`.

Notes: there are two rows per game. `score` is unstructured and has produced parsing inconsistencies. Add numeric `team_score` and `opponent_score` columns or derive them from a canonical game table.

For bounded historical repair, null `result` pairs may be reconciled from
`team_game_stats.wl` and `team_game_stats.pts` only when both sources contain
the same reciprocal team pair and date, one W and one L, and non-tied scores.
`scripts/reconcile_schedule_results.py` never overwrites a non-null result and
blocks the full transaction on an ambiguous or conflicting game.

### `gamelogs`

`player_id BIGINT`; `game_id VARCHAR`; `team_id BIGINT`; `points`, `assists`, `rebounds`, `steals`, `blocks`, `turnovers INT`; `minutes_played VARCHAR`; `season VARCHAR`; PK `(player_id, game_id)`.

Notes: insert currently uses `DO NOTHING`, so corrected box scores are not refreshed. Store minutes numerically and update mutable statistics on conflict.

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

`team_schedule_factors` references the matching team-perspective schedule row through composite FK `(game_id, team_id) -> game_schedule(game_id, team_id)` with cascade delete. A single-column FK on `game_id` is invalid because `game_schedule` stores two rows per game.

## Planned analytical tables (not implemented)

These are contracts from the modeling plan, not current tables:

* `team_game_features`: one pregame team-perspective snapshot per `(game_id, team_id, feature_version)`.
* `game_model_labels`: one completed game with home/away scores, margin, total, and winner.
* `model_predictions`: immutable prediction records with model version, as-of timestamp, and probabilities/estimates.

See `MODEL_FEATURE_PLAN.md`; do not silently add them to current-state diagrams until migrations exist.
