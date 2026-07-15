# Yuno Ball Database Profile

Status: generated sanitized snapshot for analytics evaluation
Generated (UTC): 2026-07-15T23:38:06+00:00
Connection: `postgresql://***@12ca17b49a…/yunoball_local (host redacted)`

This file is produced by `scripts/generate_database_profile.py` using **read-only** PostgreSQL transactions. It intentionally omits credentials, hostnames, dumps, and PII beyond public NBA identifiers.

## Alembic

- Current revision (DB `alembic_version`): `m3n4o5p6q7r8`
- Head revision(s) (migration files): `m3n4o5p6q7r8`
- In sync with single head: `True`
- Migration files parsed: 19

## Tables overview

| Table | Rows | Columns |
| --- | ---: | ---: |
| `alembic_version` | 1 | 1 |
| `game_environment_daily` | 74 | 27 |
| `game_environment_snapshots` | 9 | 29 |
| `game_odds` | 156 | 25 |
| `game_schedule` | 26966 | 8 |
| `gamelogs` | 154313 | 11 |
| `ingestion_runs` | 21 | 22 |
| `ingestion_task_runs` | 6 | 15 |
| `league_dash_team_stats` | 138 | 772 |
| `leaguedashplayerstats` | 5463 | 66 |
| `player_consecutive_streak_snapshots` | 1511870 | 21 |
| `player_consecutive_streaks` | 11458 | 14 |
| `player_consistency` | 7756 | 15 |
| `player_consistency_snapshots` | 997248 | 22 |
| `player_game_status` | 3027 | 13 |
| `player_heat_index` | 6870 | 12 |
| `player_heat_index_snapshots` | 909429 | 21 |
| `player_stat_window_snapshots` | 4591776 | 19 |
| `player_stat_windows` | 33096 | 12 |
| `player_streaks` | 1291 | 8 |
| `player_z_scores` | 533 | 12 |
| `players` | 1583 | 9 |
| `roster` | 530 | 7 |
| `statistics` | 5359 | 8 |
| `team_daily_flags` | 249 | 9 |
| `team_daily_metrics` | 300 | 74 |
| `team_game_feature_snapshots` | 18 | 61 |
| `team_game_stats` | 5161 | 28 |
| `team_schedule_factors` | 2592 | 17 |
| `teams` | 30 | 3 |
| `users` | 1 | 8 |

## Schema detail

### `alembic_version`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `version_num` | character varying(32) | NO |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_16979_1_not_null` | CHECK |  |  |
| `alembic_version_pkc` | PRIMARY KEY | version_num |  |

#### Indexes

- `alembic_version_pkc`: `CREATE UNIQUE INDEX alembic_version_pkc ON public.alembic_version USING btree (version_num)`

### `game_environment_daily`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('game_environment_daily_id_seq'::regclass) |
| 2 | `game_id` | bigint | NO |  |
| 3 | `game_date` | date | NO |  |
| 4 | `season` | text | NO |  |
| 5 | `home_team_id` | integer | NO |  |
| 6 | `away_team_id` | integer | NO |  |
| 7 | `home_off_rtg_lastn` | double precision | YES |  |
| 8 | `home_def_rtg_lastn` | double precision | YES |  |
| 9 | `home_pace_lastn` | double precision | YES |  |
| 10 | `away_off_rtg_lastn` | double precision | YES |  |
| 11 | `away_def_rtg_lastn` | double precision | YES |  |
| 12 | `away_pace_lastn` | double precision | YES |  |
| 13 | `pace_projection` | double precision | YES |  |
| 14 | `scoring_env_index` | double precision | YES |  |
| 15 | `three_env_index` | double precision | YES |  |
| 16 | `reb_env_index` | double precision | YES |  |
| 17 | `ft_env_index` | double precision | YES |  |
| 18 | `chaos_index` | double precision | YES |  |
| 19 | `pace_up_for_home` | boolean | YES | false |
| 20 | `pace_up_for_away` | boolean | YES | false |
| 21 | `three_point_fest` | boolean | YES | false |
| 22 | `paint_battle` | boolean | YES | false |
| 23 | `glass_war` | boolean | YES | false |
| 24 | `whistle_heavy` | boolean | YES | false |
| 25 | `tags` | ARRAY | YES |  |
| 26 | `details_json` | jsonb | YES |  |
| 27 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_16982_1_not_null` | CHECK |  |  |
| `2200_16982_27_not_null` | CHECK |  |  |
| `2200_16982_2_not_null` | CHECK |  |  |
| `2200_16982_3_not_null` | CHECK |  |  |
| `2200_16982_4_not_null` | CHECK |  |  |
| `2200_16982_5_not_null` | CHECK |  |  |
| `2200_16982_6_not_null` | CHECK |  |  |
| `game_environment_daily_away_team_id_fkey` | FOREIGN KEY | away_team_id | `teams` (team_id) |
| `game_environment_daily_home_team_id_fkey` | FOREIGN KEY | home_team_id | `teams` (team_id) |
| `game_environment_daily_pkey` | PRIMARY KEY | id |  |
| `game_environment_daily_unique` | UNIQUE | game_id, game_id, game_date, game_date |  |

#### Indexes

- `game_environment_daily_pkey`: `CREATE UNIQUE INDEX game_environment_daily_pkey ON public.game_environment_daily USING btree (id)`
- `game_environment_daily_unique`: `CREATE UNIQUE INDEX game_environment_daily_unique ON public.game_environment_daily USING btree (game_id, game_date)`
- `idx_game_environment_away_team`: `CREATE INDEX idx_game_environment_away_team ON public.game_environment_daily USING btree (away_team_id)`
- `idx_game_environment_game_date`: `CREATE INDEX idx_game_environment_game_date ON public.game_environment_daily USING btree (game_date)`
- `idx_game_environment_game_id`: `CREATE INDEX idx_game_environment_game_id ON public.game_environment_daily USING btree (game_id)`
- `idx_game_environment_home_team`: `CREATE INDEX idx_game_environment_home_team ON public.game_environment_daily USING btree (home_team_id)`
- `idx_game_environment_season`: `CREATE INDEX idx_game_environment_season ON public.game_environment_daily USING btree (season)`

### `game_environment_snapshots`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | bigint | NO | nextval('game_environment_snapshots_id_seq'::regclass) |
| 2 | `game_id` | character varying(20) | NO |  |
| 3 | `game_date` | date | NO |  |
| 4 | `scheduled_tipoff` | timestamp with time zone | NO |  |
| 5 | `home_team_id` | integer | NO |  |
| 6 | `away_team_id` | integer | NO |  |
| 7 | `window_size` | integer | NO |  |
| 8 | `home_off_rtg_lastn` | double precision | YES |  |
| 9 | `home_def_rtg_lastn` | double precision | YES |  |
| 10 | `home_pace_lastn` | double precision | YES |  |
| 11 | `away_off_rtg_lastn` | double precision | YES |  |
| 12 | `away_def_rtg_lastn` | double precision | YES |  |
| 13 | `away_pace_lastn` | double precision | YES |  |
| 14 | `pace_projection` | double precision | YES |  |
| 15 | `scoring_env_index` | double precision | YES |  |
| 16 | `three_env_index` | double precision | YES |  |
| 17 | `chaos_index` | double precision | YES |  |
| 18 | `pace_up_for_home` | boolean | NO | false |
| 19 | `pace_up_for_away` | boolean | NO | false |
| 20 | `tags` | jsonb | NO | '[]'::jsonb |
| 21 | `season` | character varying(7) | NO |  |
| 22 | `season_type` | character varying(32) | NO |  |
| 23 | `feature_as_of` | timestamp with time zone | NO |  |
| 24 | `data_available_at` | timestamp with time zone | YES |  |
| 25 | `calculation_version` | character varying(64) | NO |  |
| 26 | `source_run_id` | character varying(36) | NO |  |
| 27 | `completeness_status` | character varying(16) | NO |  |
| 28 | `missing_input_flags` | jsonb | NO | '{}'::jsonb |
| 29 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17868_18_not_null` | CHECK |  |  |
| `2200_17868_19_not_null` | CHECK |  |  |
| `2200_17868_1_not_null` | CHECK |  |  |
| `2200_17868_20_not_null` | CHECK |  |  |
| `2200_17868_21_not_null` | CHECK |  |  |
| `2200_17868_22_not_null` | CHECK |  |  |
| `2200_17868_23_not_null` | CHECK |  |  |
| `2200_17868_25_not_null` | CHECK |  |  |
| `2200_17868_26_not_null` | CHECK |  |  |
| `2200_17868_27_not_null` | CHECK |  |  |
| `2200_17868_28_not_null` | CHECK |  |  |
| `2200_17868_29_not_null` | CHECK |  |  |
| `2200_17868_2_not_null` | CHECK |  |  |
| `2200_17868_3_not_null` | CHECK |  |  |
| `2200_17868_4_not_null` | CHECK |  |  |
| `2200_17868_5_not_null` | CHECK |  |  |
| `2200_17868_6_not_null` | CHECK |  |  |
| `2200_17868_7_not_null` | CHECK |  |  |
| `ck_game_environment_snapshot_completeness` | CHECK |  |  |
| `fk_game_environment_snapshot_away_schedule` | FOREIGN KEY | game_id, game_id, away_team_id, away_team_id | `game_schedule` (game_id, team_id) |
| `fk_game_environment_snapshot_home_schedule` | FOREIGN KEY | game_id, game_id, home_team_id, home_team_id | `game_schedule` (game_id, team_id) |
| `game_environment_snapshots_away_team_id_fkey` | FOREIGN KEY | away_team_id | `teams` (team_id) |
| `game_environment_snapshots_home_team_id_fkey` | FOREIGN KEY | home_team_id | `teams` (team_id) |
| `game_environment_snapshots_source_run_id_fkey` | FOREIGN KEY | source_run_id | `ingestion_runs` (run_id) |
| `game_environment_snapshots_pkey` | PRIMARY KEY | id |  |
| `uq_game_environment_snapshot_natural_key` | UNIQUE | game_id, game_id, game_id, game_id, window_size, window_size, window_size, window_size, feature_as_of, feature_as_of, feature_as_of, feature_as_of, calculation_version, calculation_version, calculation_version, calculation_version |  |

#### Indexes

- `game_environment_snapshots_pkey`: `CREATE UNIQUE INDEX game_environment_snapshots_pkey ON public.game_environment_snapshots USING btree (id)`
- `idx_game_environment_snapshot_date`: `CREATE INDEX idx_game_environment_snapshot_date ON public.game_environment_snapshots USING btree (game_date, feature_as_of)`
- `idx_game_environment_snapshot_latest`: `CREATE INDEX idx_game_environment_snapshot_latest ON public.game_environment_snapshots USING btree (season, season_type, calculation_version, completeness_status, feature_as_of)`
- `uq_game_environment_snapshot_natural_key`: `CREATE UNIQUE INDEX uq_game_environment_snapshot_natural_key ON public.game_environment_snapshots USING btree (game_id, window_size, feature_as_of, calculation_version)`

### `game_odds`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('game_odds_id_seq'::regclass) |
| 2 | `game_id` | character varying(20) | NO |  |
| 3 | `game_date` | date | NO |  |
| 4 | `season` | text | NO |  |
| 5 | `home_team_id` | integer | NO |  |
| 6 | `away_team_id` | integer | NO |  |
| 7 | `sportsbook_id` | character varying(50) | NO |  |
| 8 | `sportsbook_name` | text | YES |  |
| 9 | `country_code` | character varying(10) | YES |  |
| 10 | `sportsbook_url` | text | YES |  |
| 11 | `home_ml_odds` | double precision | YES |  |
| 12 | `away_ml_odds` | double precision | YES |  |
| 13 | `home_ml_opening` | double precision | YES |  |
| 14 | `away_ml_opening` | double precision | YES |  |
| 15 | `home_ml_trend` | character varying(10) | YES |  |
| 16 | `away_ml_trend` | character varying(10) | YES |  |
| 17 | `home_spread` | double precision | YES |  |
| 18 | `away_spread` | double precision | YES |  |
| 19 | `home_spread_opening` | double precision | YES |  |
| 20 | `away_spread_opening` | double precision | YES |  |
| 21 | `spread_home_odds` | double precision | YES |  |
| 22 | `spread_away_odds` | double precision | YES |  |
| 23 | `raw_data` | jsonb | YES |  |
| 24 | `recorded_at` | timestamp with time zone | NO | now() |
| 25 | `updated_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_16995_1_not_null` | CHECK |  |  |
| `2200_16995_24_not_null` | CHECK |  |  |
| `2200_16995_25_not_null` | CHECK |  |  |
| `2200_16995_2_not_null` | CHECK |  |  |
| `2200_16995_3_not_null` | CHECK |  |  |
| `2200_16995_4_not_null` | CHECK |  |  |
| `2200_16995_5_not_null` | CHECK |  |  |
| `2200_16995_6_not_null` | CHECK |  |  |
| `2200_16995_7_not_null` | CHECK |  |  |
| `game_odds_away_team_id_fkey` | FOREIGN KEY | away_team_id | `teams` (team_id) |
| `game_odds_home_team_id_fkey` | FOREIGN KEY | home_team_id | `teams` (team_id) |
| `game_odds_pkey` | PRIMARY KEY | id |  |
| `game_odds_unique` | UNIQUE | game_id, game_id, sportsbook_id, sportsbook_id |  |

#### Indexes

- `game_odds_pkey`: `CREATE UNIQUE INDEX game_odds_pkey ON public.game_odds USING btree (id)`
- `game_odds_unique`: `CREATE UNIQUE INDEX game_odds_unique ON public.game_odds USING btree (game_id, sportsbook_id)`
- `idx_game_odds_game_date`: `CREATE INDEX idx_game_odds_game_date ON public.game_odds USING btree (game_date)`
- `idx_game_odds_game_id`: `CREATE INDEX idx_game_odds_game_id ON public.game_odds USING btree (game_id)`
- `idx_game_odds_season`: `CREATE INDEX idx_game_odds_season ON public.game_odds USING btree (season)`
- `idx_game_odds_sportsbook`: `CREATE INDEX idx_game_odds_sportsbook ON public.game_odds USING btree (sportsbook_id)`

### `game_schedule`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `game_id` | character varying | NO |  |
| 2 | `season` | character varying | NO |  |
| 3 | `team_id` | integer | NO |  |
| 4 | `opponent_team_id` | integer | NO |  |
| 5 | `game_date` | timestamp without time zone | NO |  |
| 6 | `home_or_away` | character varying(1) | NO |  |
| 7 | `result` | character varying(1) | YES |  |
| 8 | `score` | character varying | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17003_1_not_null` | CHECK |  |  |
| `2200_17003_2_not_null` | CHECK |  |  |
| `2200_17003_3_not_null` | CHECK |  |  |
| `2200_17003_4_not_null` | CHECK |  |  |
| `2200_17003_5_not_null` | CHECK |  |  |
| `2200_17003_6_not_null` | CHECK |  |  |
| `game_schedule_home_or_away_check` | CHECK |  |  |
| `game_schedule_result_check` | CHECK |  |  |
| `game_schedule_opponent_team_id_fkey` | FOREIGN KEY | opponent_team_id | `teams` (team_id) |
| `game_schedule_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `game_schedule_pkey` | PRIMARY KEY | game_id, game_id, team_id, team_id |  |

#### Indexes

- `game_schedule_pkey`: `CREATE UNIQUE INDEX game_schedule_pkey ON public.game_schedule USING btree (game_id, team_id)`
- `idx_game_schedule_game_date`: `CREATE INDEX idx_game_schedule_game_date ON public.game_schedule USING btree (game_date)`
- `idx_game_schedule_game_id`: `CREATE INDEX idx_game_schedule_game_id ON public.game_schedule USING btree (game_id)`
- `idx_game_schedule_season`: `CREATE INDEX idx_game_schedule_season ON public.game_schedule USING btree (season)`
- `idx_game_schedule_team_id`: `CREATE INDEX idx_game_schedule_team_id ON public.game_schedule USING btree (team_id)`

### `gamelogs`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `player_id` | bigint | NO |  |
| 2 | `game_id` | character varying | NO |  |
| 3 | `team_id` | bigint | NO |  |
| 4 | `points` | integer | YES |  |
| 5 | `assists` | integer | YES |  |
| 6 | `rebounds` | integer | YES |  |
| 7 | `steals` | integer | YES |  |
| 8 | `blocks` | integer | YES |  |
| 9 | `turnovers` | integer | YES |  |
| 10 | `minutes_played` | character varying | YES |  |
| 11 | `season` | character varying | NO |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17010_11_not_null` | CHECK |  |  |
| `2200_17010_1_not_null` | CHECK |  |  |
| `2200_17010_2_not_null` | CHECK |  |  |
| `2200_17010_3_not_null` | CHECK |  |  |
| `ck_gamelogs_season_canonical` | CHECK |  |  |
| `fk_gamelogs_game_schedule` | FOREIGN KEY | game_id, game_id, team_id, team_id | `game_schedule` (game_id, team_id) |
| `fk_gamelogs_player` | FOREIGN KEY | player_id | `players` (player_id) |
| `gamelogs_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `gamelogs_pkey` | PRIMARY KEY | player_id, player_id, game_id, game_id |  |

#### Indexes

- `gamelogs_game_idx`: `CREATE INDEX gamelogs_game_idx ON public.gamelogs USING btree (game_id)`
- `gamelogs_pkey`: `CREATE UNIQUE INDEX gamelogs_pkey ON public.gamelogs USING btree (player_id, game_id)`
- `gamelogs_player_game_idx`: `CREATE INDEX gamelogs_player_game_idx ON public.gamelogs USING btree (player_id, game_id)`
- `gamelogs_season_idx`: `CREATE INDEX gamelogs_season_idx ON public.gamelogs USING btree (season)`
- `idx_gamelogs_game_id`: `CREATE INDEX idx_gamelogs_game_id ON public.gamelogs USING btree (game_id)`
- `idx_gamelogs_minutes`: `CREATE INDEX idx_gamelogs_minutes ON public.gamelogs USING btree (minutes_played)`
- `idx_gamelogs_player_id`: `CREATE INDEX idx_gamelogs_player_id ON public.gamelogs USING btree (player_id)`
- `idx_gamelogs_player_season`: `CREATE INDEX idx_gamelogs_player_season ON public.gamelogs USING btree (player_id, season)`
- `idx_gamelogs_points`: `CREATE INDEX idx_gamelogs_points ON public.gamelogs USING btree (points)`
- `idx_gamelogs_season`: `CREATE INDEX idx_gamelogs_season ON public.gamelogs USING btree (season)`
- `idx_gamelogs_team_id`: `CREATE INDEX idx_gamelogs_team_id ON public.gamelogs USING btree (team_id)`

### `ingestion_runs`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `run_id` | character varying(36) | NO |  |
| 2 | `parent_run_id` | character varying(36) | YES |  |
| 3 | `run_type` | character varying(64) | NO |  |
| 4 | `source` | character varying(64) | NO |  |
| 5 | `season` | character varying(7) | YES |  |
| 6 | `season_type` | character varying(32) | YES |  |
| 7 | `target_date` | date | YES |  |
| 8 | `feature_cutoff` | timestamp with time zone | YES |  |
| 9 | `status` | character varying(16) | NO |  |
| 10 | `validation_status` | character varying(16) | NO |  |
| 11 | `started_at` | timestamp with time zone | NO | now() |
| 12 | `finished_at` | timestamp with time zone | YES |  |
| 13 | `rows_read` | integer | YES |  |
| 14 | `rows_written` | integer | YES |  |
| 15 | `provider` | character varying(128) | YES |  |
| 16 | `code_version` | character varying(128) | YES |  |
| 17 | `calculation_version` | character varying(128) | YES |  |
| 18 | `error_class` | character varying(255) | YES |  |
| 19 | `error_summary` | text | YES |  |
| 20 | `details` | jsonb | YES |  |
| 21 | `created_at` | timestamp with time zone | NO | now() |
| 22 | `updated_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17015_10_not_null` | CHECK |  |  |
| `2200_17015_11_not_null` | CHECK |  |  |
| `2200_17015_1_not_null` | CHECK |  |  |
| `2200_17015_21_not_null` | CHECK |  |  |
| `2200_17015_22_not_null` | CHECK |  |  |
| `2200_17015_3_not_null` | CHECK |  |  |
| `2200_17015_4_not_null` | CHECK |  |  |
| `2200_17015_9_not_null` | CHECK |  |  |
| `ck_ingestion_runs_status` | CHECK |  |  |
| `ck_ingestion_runs_validation_status` | CHECK |  |  |
| `ingestion_runs_parent_run_id_fkey` | FOREIGN KEY | parent_run_id | `ingestion_runs` (run_id) |
| `ingestion_runs_pkey` | PRIMARY KEY | run_id |  |

#### Indexes

- `idx_ingestion_runs_season_date`: `CREATE INDEX idx_ingestion_runs_season_date ON public.ingestion_runs USING btree (season, target_date)`
- `idx_ingestion_runs_started_at`: `CREATE INDEX idx_ingestion_runs_started_at ON public.ingestion_runs USING btree (started_at)`
- `idx_ingestion_runs_status`: `CREATE INDEX idx_ingestion_runs_status ON public.ingestion_runs USING btree (status)`
- `ingestion_runs_pkey`: `CREATE UNIQUE INDEX ingestion_runs_pkey ON public.ingestion_runs USING btree (run_id)`

### `ingestion_task_runs`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `task_run_id` | character varying(36) | NO |  |
| 2 | `run_id` | character varying(36) | NO |  |
| 3 | `task_name` | character varying(128) | NO |  |
| 4 | `source` | character varying(128) | YES |  |
| 5 | `status` | character varying(16) | NO |  |
| 6 | `started_at` | timestamp with time zone | NO | now() |
| 7 | `finished_at` | timestamp with time zone | YES |  |
| 8 | `rows_read` | integer | YES |  |
| 9 | `rows_written` | integer | YES |  |
| 10 | `provider` | character varying(128) | YES |  |
| 11 | `error_class` | character varying(255) | YES |  |
| 12 | `error_summary` | text | YES |  |
| 13 | `details` | jsonb | YES |  |
| 14 | `created_at` | timestamp with time zone | NO | now() |
| 15 | `updated_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17025_14_not_null` | CHECK |  |  |
| `2200_17025_15_not_null` | CHECK |  |  |
| `2200_17025_1_not_null` | CHECK |  |  |
| `2200_17025_2_not_null` | CHECK |  |  |
| `2200_17025_3_not_null` | CHECK |  |  |
| `2200_17025_5_not_null` | CHECK |  |  |
| `2200_17025_6_not_null` | CHECK |  |  |
| `ck_ingestion_task_runs_status` | CHECK |  |  |
| `ingestion_task_runs_run_id_fkey` | FOREIGN KEY | run_id | `ingestion_runs` (run_id) |
| `ingestion_task_runs_pkey` | PRIMARY KEY | task_run_id |  |
| `uq_ingestion_task_run_name` | UNIQUE | run_id, run_id, task_name, task_name |  |

#### Indexes

- `idx_ingestion_task_runs_run_status`: `CREATE INDEX idx_ingestion_task_runs_run_status ON public.ingestion_task_runs USING btree (run_id, status)`
- `idx_ingestion_task_runs_source`: `CREATE INDEX idx_ingestion_task_runs_source ON public.ingestion_task_runs USING btree (source)`
- `ingestion_task_runs_pkey`: `CREATE UNIQUE INDEX ingestion_task_runs_pkey ON public.ingestion_task_runs USING btree (task_run_id)`
- `uq_ingestion_task_run_name`: `CREATE UNIQUE INDEX uq_ingestion_task_run_name ON public.ingestion_task_runs USING btree (run_id, task_name)`

### `league_dash_team_stats`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `team_id` | integer | NO |  |
| 2 | `team_name` | character varying(50) | NO |  |
| 3 | `season` | character varying(10) | NO |  |
| 4 | `season_type` | character varying(15) | NO |  |
| 5 | `base_totals_gp` | integer | YES |  |
| 6 | `base_totals_w` | integer | YES |  |
| 7 | `base_totals_l` | integer | YES |  |
| 8 | `base_totals_w_pct` | double precision | YES |  |
| 9 | `base_totals_min` | double precision | YES |  |
| 10 | `base_totals_fgm` | integer | YES |  |
| 11 | `base_totals_fga` | integer | YES |  |
| 12 | `base_totals_fg_pct` | double precision | YES |  |
| 13 | `base_totals_fg3m` | integer | YES |  |
| 14 | `base_totals_fg3a` | integer | YES |  |
| 15 | `base_totals_fg3_pct` | double precision | YES |  |
| 16 | `base_totals_ftm` | integer | YES |  |
| 17 | `base_totals_fta` | integer | YES |  |
| 18 | `base_totals_ft_pct` | double precision | YES |  |
| 19 | `base_totals_oreb` | integer | YES |  |
| 20 | `base_totals_dreb` | integer | YES |  |
| 21 | `base_totals_reb` | integer | YES |  |
| 22 | `base_totals_ast` | integer | YES |  |
| 23 | `base_totals_tov` | integer | YES |  |
| 24 | `base_totals_stl` | integer | YES |  |
| 25 | `base_totals_blk` | integer | YES |  |
| 26 | `base_totals_blka` | integer | YES |  |
| 27 | `base_totals_pf` | integer | YES |  |
| 28 | `base_totals_pfd` | integer | YES |  |
| 29 | `base_totals_pts` | integer | YES |  |
| 30 | `base_totals_plus_minus` | double precision | YES |  |
| 31 | `base_totals_gp_rank` | integer | YES |  |
| 32 | `base_totals_w_rank` | integer | YES |  |
| 33 | `base_totals_l_rank` | integer | YES |  |
| 34 | `base_totals_w_pct_rank` | integer | YES |  |
| 35 | `base_totals_min_rank` | integer | YES |  |
| 36 | `base_totals_fgm_rank` | integer | YES |  |
| 37 | `base_totals_fga_rank` | integer | YES |  |
| 38 | `base_totals_fg_pct_rank` | integer | YES |  |
| 39 | `base_totals_fg3m_rank` | integer | YES |  |
| 40 | `base_totals_fg3a_rank` | integer | YES |  |
| 41 | `base_totals_fg3_pct_rank` | integer | YES |  |
| 42 | `base_totals_ftm_rank` | integer | YES |  |
| 43 | `base_totals_fta_rank` | integer | YES |  |
| 44 | `base_totals_ft_pct_rank` | integer | YES |  |
| 45 | `base_totals_oreb_rank` | integer | YES |  |
| 46 | `base_totals_dreb_rank` | integer | YES |  |
| 47 | `base_totals_reb_rank` | integer | YES |  |
| 48 | `base_totals_ast_rank` | integer | YES |  |
| 49 | `base_totals_tov_rank` | integer | YES |  |
| 50 | `base_totals_stl_rank` | integer | YES |  |
| 51 | `base_totals_blk_rank` | integer | YES |  |
| 52 | `base_totals_blka_rank` | integer | YES |  |
| 53 | `base_totals_pf_rank` | integer | YES |  |
| 54 | `base_totals_pfd_rank` | integer | YES |  |
| 55 | `base_totals_pts_rank` | integer | YES |  |
| 56 | `base_totals_plus_minus_rank` | integer | YES |  |
| 57 | `base_per48_gp` | integer | YES |  |
| 58 | `base_per48_l` | integer | YES |  |
| 59 | `base_per48_w` | integer | YES |  |
| 60 | `base_per48_w_pct` | double precision | YES |  |
| 61 | `base_per48_min` | double precision | YES |  |
| 62 | `base_per48_fgm` | integer | YES |  |
| 63 | `base_per48_fga` | integer | YES |  |
| 64 | `base_per48_fg_pct` | double precision | YES |  |
| 65 | `base_per48_fg3m` | integer | YES |  |
| 66 | `base_per48_fg3a` | integer | YES |  |
| 67 | `base_per48_fg3_pct` | double precision | YES |  |
| 68 | `base_per48_ftm` | integer | YES |  |
| 69 | `base_per48_fta` | integer | YES |  |
| 70 | `base_per48_ft_pct` | double precision | YES |  |
| 71 | `base_per48_oreb` | integer | YES |  |
| 72 | `base_per48_dreb` | integer | YES |  |
| 73 | `base_per48_reb` | integer | YES |  |
| 74 | `base_per48_ast` | integer | YES |  |
| 75 | `base_per48_tov` | integer | YES |  |
| 76 | `base_per48_stl` | integer | YES |  |
| 77 | `base_per48_blk` | integer | YES |  |
| 78 | `base_per48_blka` | integer | YES |  |
| 79 | `base_per48_pf` | integer | YES |  |
| 80 | `base_per48_pfd` | integer | YES |  |
| 81 | `base_per48_pts` | integer | YES |  |
| 82 | `base_per48_plus_minus` | double precision | YES |  |
| 83 | `base_per48_gp_rank` | integer | YES |  |
| 84 | `base_per48_w_rank` | integer | YES |  |
| 85 | `base_per48_l_rank` | integer | YES |  |
| 86 | `base_per48_w_pct_rank` | integer | YES |  |
| 87 | `base_per48_min_rank` | integer | YES |  |
| 88 | `base_per48_fgm_rank` | integer | YES |  |
| 89 | `base_per48_fga_rank` | integer | YES |  |
| 90 | `base_per48_fg_pct_rank` | integer | YES |  |
| 91 | `base_per48_fg3m_rank` | integer | YES |  |
| 92 | `base_per48_fg3a_rank` | integer | YES |  |
| 93 | `base_per48_fg3_pct_rank` | integer | YES |  |
| 94 | `base_per48_ftm_rank` | integer | YES |  |
| 95 | `base_per48_fta_rank` | integer | YES |  |
| 96 | `base_per48_ft_pct_rank` | integer | YES |  |
| 97 | `base_per48_oreb_rank` | integer | YES |  |
| 98 | `base_per48_dreb_rank` | integer | YES |  |
| 99 | `base_per48_reb_rank` | integer | YES |  |
| 100 | `base_per48_ast_rank` | integer | YES |  |
| 101 | `base_per48_tov_rank` | integer | YES |  |
| 102 | `base_per48_stl_rank` | integer | YES |  |
| 103 | `base_per48_blk_rank` | integer | YES |  |
| 104 | `base_per48_blka_rank` | integer | YES |  |
| 105 | `base_per48_pf_rank` | integer | YES |  |
| 106 | `base_per48_pfd_rank` | integer | YES |  |
| 107 | `base_per48_pts_rank` | integer | YES |  |
| 108 | `base_per48_plus_minus_rank` | integer | YES |  |
| 109 | `base_per100possessions_gp` | integer | YES |  |
| 110 | `base_per100possessions_l` | integer | YES |  |
| 111 | `base_per100possessions_w` | integer | YES |  |
| 112 | `base_per100possessions_w_pct` | double precision | YES |  |
| 113 | `base_per100possessions_min` | double precision | YES |  |
| 114 | `base_per100possessions_fgm` | integer | YES |  |
| 115 | `base_per100possessions_fga` | integer | YES |  |
| 116 | `base_per100possessions_fg_pct` | double precision | YES |  |
| 117 | `base_per100possessions_fg3m` | integer | YES |  |
| 118 | `base_per100possessions_fg3a` | integer | YES |  |
| 119 | `base_per100possessions_fg3_pct` | double precision | YES |  |
| 120 | `base_per100possessions_ftm` | integer | YES |  |
| 121 | `base_per100possessions_fta` | integer | YES |  |
| 122 | `base_per100possessions_ft_pct` | double precision | YES |  |
| 123 | `base_per100possessions_oreb` | integer | YES |  |
| 124 | `base_per100possessions_dreb` | integer | YES |  |
| 125 | `base_per100possessions_reb` | integer | YES |  |
| 126 | `base_per100possessions_ast` | integer | YES |  |
| 127 | `base_per100possessions_tov` | integer | YES |  |
| 128 | `base_per100possessions_stl` | integer | YES |  |
| 129 | `base_per100possessions_blk` | integer | YES |  |
| 130 | `base_per100possessions_blka` | integer | YES |  |
| 131 | `base_per100possessions_pf` | integer | YES |  |
| 132 | `base_per100possessions_pfd` | integer | YES |  |
| 133 | `base_per100possessions_pts` | integer | YES |  |
| 134 | `base_per100possessions_plus_minus` | double precision | YES |  |
| 135 | `base_per100possessions_gp_rank` | integer | YES |  |
| 136 | `base_per100possessions_w_rank` | integer | YES |  |
| 137 | `base_per100possessions_l_rank` | integer | YES |  |
| 138 | `base_per100possessions_w_pct_rank` | integer | YES |  |
| 139 | `base_per100possessions_min_rank` | integer | YES |  |
| 140 | `base_per100possessions_fgm_rank` | integer | YES |  |
| 141 | `base_per100possessions_fga_rank` | integer | YES |  |
| 142 | `base_per100possessions_fg_pct_rank` | integer | YES |  |
| 143 | `base_per100possessions_fg3m_rank` | integer | YES |  |
| 144 | `base_per100possessions_fg3a_rank` | integer | YES |  |
| 145 | `base_per100possessions_fg3_pct_rank` | integer | YES |  |
| 146 | `base_per100possessions_ftm_rank` | integer | YES |  |
| 147 | `base_per100possessions_fta_rank` | integer | YES |  |
| 148 | `base_per100possessions_ft_pct_rank` | integer | YES |  |
| 149 | `base_per100possessions_oreb_rank` | integer | YES |  |
| 150 | `base_per100possessions_dreb_rank` | integer | YES |  |
| 151 | `base_per100possessions_reb_rank` | integer | YES |  |
| 152 | `base_per100possessions_ast_rank` | integer | YES |  |
| 153 | `base_per100possessions_tov_rank` | integer | YES |  |
| 154 | `base_per100possessions_stl_rank` | integer | YES |  |
| 155 | `base_per100possessions_blk_rank` | integer | YES |  |
| 156 | `base_per100possessions_blka_rank` | integer | YES |  |
| 157 | `base_per100possessions_pf_rank` | integer | YES |  |
| 158 | `base_per100possessions_pfd_rank` | integer | YES |  |
| 159 | `base_per100possessions_pts_rank` | integer | YES |  |
| 160 | `base_per100possessions_plus_minus_rank` | integer | YES |  |
| 161 | `advanced_totals_gp` | integer | YES |  |
| 162 | `advanced_totals_w` | integer | YES |  |
| 163 | `advanced_totals_l` | integer | YES |  |
| 164 | `advanced_totals_w_pct` | double precision | YES |  |
| 165 | `advanced_totals_min` | double precision | YES |  |
| 166 | `advanced_totals_e_off_rating` | double precision | YES |  |
| 167 | `advanced_totals_off_rating` | double precision | YES |  |
| 168 | `advanced_totals_e_def_rating` | double precision | YES |  |
| 169 | `advanced_totals_def_rating` | double precision | YES |  |
| 170 | `advanced_totals_e_net_rating` | double precision | YES |  |
| 171 | `advanced_totals_net_rating` | double precision | YES |  |
| 172 | `advanced_totals_ast_pct` | double precision | YES |  |
| 173 | `advanced_totals_ast_to` | double precision | YES |  |
| 174 | `advanced_totals_ast_ratio` | double precision | YES |  |
| 175 | `advanced_totals_oreb_pct` | double precision | YES |  |
| 176 | `advanced_totals_dreb_pct` | double precision | YES |  |
| 177 | `advanced_totals_reb_pct` | double precision | YES |  |
| 178 | `advanced_totals_tm_tov_pct` | double precision | YES |  |
| 179 | `advanced_totals_efg_pct` | double precision | YES |  |
| 180 | `advanced_totals_ts_pct` | double precision | YES |  |
| 181 | `advanced_totals_e_pace` | double precision | YES |  |
| 182 | `advanced_totals_pace` | double precision | YES |  |
| 183 | `advanced_totals_pace_per40` | double precision | YES |  |
| 184 | `advanced_totals_poss` | integer | YES |  |
| 185 | `advanced_totals_pie` | double precision | YES |  |
| 186 | `advanced_totals_gp_rank` | integer | YES |  |
| 187 | `advanced_totals_w_rank` | integer | YES |  |
| 188 | `advanced_totals_l_rank` | integer | YES |  |
| 189 | `advanced_totals_w_pct_rank` | integer | YES |  |
| 190 | `advanced_totals_min_rank` | integer | YES |  |
| 191 | `advanced_totals_off_rating_rank` | integer | YES |  |
| 192 | `advanced_totals_def_rating_rank` | integer | YES |  |
| 193 | `advanced_totals_net_rating_rank` | integer | YES |  |
| 194 | `advanced_totals_ast_pct_rank` | integer | YES |  |
| 195 | `advanced_totals_ast_to_rank` | integer | YES |  |
| 196 | `advanced_totals_ast_ratio_rank` | integer | YES |  |
| 197 | `advanced_totals_oreb_pct_rank` | integer | YES |  |
| 198 | `advanced_totals_dreb_pct_rank` | integer | YES |  |
| 199 | `advanced_totals_reb_pct_rank` | integer | YES |  |
| 200 | `advanced_totals_tm_tov_pct_rank` | integer | YES |  |
| 201 | `advanced_totals_efg_pct_rank` | integer | YES |  |
| 202 | `advanced_totals_ts_pct_rank` | integer | YES |  |
| 203 | `advanced_totals_pace_rank` | integer | YES |  |
| 204 | `advanced_totals_pie_rank` | integer | YES |  |
| 205 | `advanced_per48_gp` | integer | YES |  |
| 206 | `advanced_per48_w` | integer | YES |  |
| 207 | `advanced_per48_l` | integer | YES |  |
| 208 | `advanced_per48_w_pct` | double precision | YES |  |
| 209 | `advanced_per48_min` | double precision | YES |  |
| 210 | `advanced_per48_e_off_rating` | double precision | YES |  |
| 211 | `advanced_per48_off_rating` | double precision | YES |  |
| 212 | `advanced_per48_e_def_rating` | double precision | YES |  |
| 213 | `advanced_per48_def_rating` | double precision | YES |  |
| 214 | `advanced_per48_e_net_rating` | double precision | YES |  |
| 215 | `advanced_per48_net_rating` | double precision | YES |  |
| 216 | `advanced_per48_ast_pct` | double precision | YES |  |
| 217 | `advanced_per48_ast_to` | double precision | YES |  |
| 218 | `advanced_per48_ast_ratio` | double precision | YES |  |
| 219 | `advanced_per48_oreb_pct` | double precision | YES |  |
| 220 | `advanced_per48_dreb_pct` | double precision | YES |  |
| 221 | `advanced_per48_reb_pct` | double precision | YES |  |
| 222 | `advanced_per48_tm_tov_pct` | double precision | YES |  |
| 223 | `advanced_per48_efg_pct` | double precision | YES |  |
| 224 | `advanced_per48_ts_pct` | double precision | YES |  |
| 225 | `advanced_per48_e_pace` | double precision | YES |  |
| 226 | `advanced_per48_pace` | double precision | YES |  |
| 227 | `advanced_per48_pace_per40` | double precision | YES |  |
| 228 | `advanced_per48_poss` | integer | YES |  |
| 229 | `advanced_per48_pie` | double precision | YES |  |
| 230 | `advanced_per48_gp_rank` | integer | YES |  |
| 231 | `advanced_per48_w_rank` | integer | YES |  |
| 232 | `advanced_per48_l_rank` | integer | YES |  |
| 233 | `advanced_per48_w_pct_rank` | integer | YES |  |
| 234 | `advanced_per48_min_rank` | integer | YES |  |
| 235 | `advanced_per48_off_rating_rank` | integer | YES |  |
| 236 | `advanced_per48_def_rating_rank` | integer | YES |  |
| 237 | `advanced_per48_net_rating_rank` | integer | YES |  |
| 238 | `advanced_per48_ast_pct_rank` | integer | YES |  |
| 239 | `advanced_per48_ast_to_rank` | integer | YES |  |
| 240 | `advanced_per48_ast_ratio_rank` | integer | YES |  |
| 241 | `advanced_per48_oreb_pct_rank` | integer | YES |  |
| 242 | `advanced_per48_dreb_pct_rank` | integer | YES |  |
| 243 | `advanced_per48_reb_pct_rank` | integer | YES |  |
| 244 | `advanced_per48_tm_tov_pct_rank` | integer | YES |  |
| 245 | `advanced_per48_efg_pct_rank` | integer | YES |  |
| 246 | `advanced_per48_ts_pct_rank` | integer | YES |  |
| 247 | `advanced_per48_pace_rank` | integer | YES |  |
| 248 | `advanced_per48_pie_rank` | integer | YES |  |
| 249 | `advanced_per100possessions_gp` | integer | YES |  |
| 250 | `advanced_per100possessions_w` | integer | YES |  |
| 251 | `advanced_per100possessions_l` | integer | YES |  |
| 252 | `advanced_per100possessions_w_pct` | double precision | YES |  |
| 253 | `advanced_per100possessions_min` | double precision | YES |  |
| 254 | `advanced_per100possessions_e_off_rating` | double precision | YES |  |
| 255 | `advanced_per100possessions_off_rating` | double precision | YES |  |
| 256 | `advanced_per100possessions_e_def_rating` | double precision | YES |  |
| 257 | `advanced_per100possessions_def_rating` | double precision | YES |  |
| 258 | `advanced_per100possessions_e_net_rating` | double precision | YES |  |
| 259 | `advanced_per100possessions_net_rating` | double precision | YES |  |
| 260 | `advanced_per100possessions_ast_pct` | double precision | YES |  |
| 261 | `advanced_per100possessions_ast_to` | double precision | YES |  |
| 262 | `advanced_per100possessions_ast_ratio` | double precision | YES |  |
| 263 | `advanced_per100possessions_oreb_pct` | double precision | YES |  |
| 264 | `advanced_per100possessions_dreb_pct` | double precision | YES |  |
| 265 | `advanced_per100possessions_reb_pct` | double precision | YES |  |
| 266 | `advanced_per100possessions_tm_tov_pct` | double precision | YES |  |
| 267 | `advanced_per100possessions_efg_pct` | double precision | YES |  |
| 268 | `advanced_per100possessions_ts_pct` | double precision | YES |  |
| 269 | `advanced_per100possessions_e_pace` | double precision | YES |  |
| 270 | `advanced_per100possessions_pace` | double precision | YES |  |
| 271 | `advanced_per100possessions_pace_per40` | double precision | YES |  |
| 272 | `advanced_per100possessions_poss` | integer | YES |  |
| 273 | `advanced_per100possessions_pie` | double precision | YES |  |
| 274 | `advanced_per100possessions_gp_rank` | integer | YES |  |
| 275 | `advanced_per100possessions_w_rank` | integer | YES |  |
| 276 | `advanced_per100possessions_l_rank` | integer | YES |  |
| 277 | `advanced_per100possessions_w_pct_rank` | integer | YES |  |
| 278 | `advanced_per100possessions_min_rank` | integer | YES |  |
| 279 | `advanced_per100possessions_off_rating_rank` | integer | YES |  |
| 280 | `advanced_per100possessions_def_rating_rank` | integer | YES |  |
| 281 | `advanced_per100possessions_net_rating_rank` | integer | YES |  |
| 282 | `advanced_per100possessions_ast_pct_rank` | integer | YES |  |
| 283 | `advanced_per100possessions_ast_to_rank` | integer | YES |  |
| 284 | `advanced_per100possessions_ast_ratio_rank` | integer | YES |  |
| 285 | `advanced_per100possessions_oreb_pct_rank` | integer | YES |  |
| 286 | `advanced_per100possessions_dreb_pct_rank` | integer | YES |  |
| 287 | `advanced_per100possessions_reb_pct_rank` | integer | YES |  |
| 288 | `advanced_per100possessions_tm_tov_pct_rank` | integer | YES |  |
| 289 | `advanced_per100possessions_efg_pct_rank` | integer | YES |  |
| 290 | `advanced_per100possessions_ts_pct_rank` | integer | YES |  |
| 291 | `advanced_per100possessions_pace_rank` | integer | YES |  |
| 292 | `advanced_per100possessions_pie_rank` | integer | YES |  |
| 293 | `misc_totals_gp` | integer | YES |  |
| 294 | `misc_totals_w` | integer | YES |  |
| 295 | `misc_totals_l` | integer | YES |  |
| 296 | `misc_totals_w_pct` | double precision | YES |  |
| 297 | `misc_totals_min` | double precision | YES |  |
| 298 | `misc_totals_pts_off_tov` | integer | YES |  |
| 299 | `misc_totals_pts_2nd_chance` | integer | YES |  |
| 300 | `misc_totals_pts_fb` | integer | YES |  |
| 301 | `misc_totals_pts_paint` | integer | YES |  |
| 302 | `misc_totals_opp_pts_off_tov` | integer | YES |  |
| 303 | `misc_totals_opp_pts_2nd_chance` | integer | YES |  |
| 304 | `misc_totals_opp_pts_fb` | integer | YES |  |
| 305 | `misc_totals_opp_pts_paint` | integer | YES |  |
| 306 | `misc_totals_gp_rank` | integer | YES |  |
| 307 | `misc_totals_w_rank` | integer | YES |  |
| 308 | `misc_totals_l_rank` | integer | YES |  |
| 309 | `misc_totals_w_pct_rank` | integer | YES |  |
| 310 | `misc_totals_min_rank` | integer | YES |  |
| 311 | `misc_totals_pts_off_tov_rank` | integer | YES |  |
| 312 | `misc_totals_pts_2nd_chance_rank` | integer | YES |  |
| 313 | `misc_totals_pts_fb_rank` | integer | YES |  |
| 314 | `misc_totals_pts_paint_rank` | integer | YES |  |
| 315 | `misc_totals_opp_pts_off_tov_rank` | integer | YES |  |
| 316 | `misc_totals_opp_pts_2nd_chance_rank` | integer | YES |  |
| 317 | `misc_totals_opp_pts_fb_rank` | integer | YES |  |
| 318 | `misc_totals_opp_pts_paint_rank` | integer | YES |  |
| 319 | `misc_per48_gp` | integer | YES |  |
| 320 | `misc_per48_w` | integer | YES |  |
| 321 | `misc_per48_l` | integer | YES |  |
| 322 | `misc_per48_w_pct` | double precision | YES |  |
| 323 | `misc_per48_min` | double precision | YES |  |
| 324 | `misc_per48_pts_off_tov` | integer | YES |  |
| 325 | `misc_per48_pts_2nd_chance` | integer | YES |  |
| 326 | `misc_per48_pts_fb` | integer | YES |  |
| 327 | `misc_per48_pts_paint` | integer | YES |  |
| 328 | `misc_per48_opp_pts_off_tov` | integer | YES |  |
| 329 | `misc_per48_opp_pts_2nd_chance` | integer | YES |  |
| 330 | `misc_per48_opp_pts_fb` | integer | YES |  |
| 331 | `misc_per48_opp_pts_paint` | integer | YES |  |
| 332 | `misc_per48_gp_rank` | integer | YES |  |
| 333 | `misc_per48_w_rank` | integer | YES |  |
| 334 | `misc_per48_l_rank` | integer | YES |  |
| 335 | `misc_per48_w_pct_rank` | integer | YES |  |
| 336 | `misc_per48_min_rank` | integer | YES |  |
| 337 | `misc_per48_pts_off_tov_rank` | integer | YES |  |
| 338 | `misc_per48_pts_2nd_chance_rank` | integer | YES |  |
| 339 | `misc_per48_pts_fb_rank` | integer | YES |  |
| 340 | `misc_per48_pts_paint_rank` | integer | YES |  |
| 341 | `misc_per48_opp_pts_off_tov_rank` | integer | YES |  |
| 342 | `misc_per48_opp_pts_2nd_chance_rank` | integer | YES |  |
| 343 | `misc_per48_opp_pts_fb_rank` | integer | YES |  |
| 344 | `misc_per48_opp_pts_paint_rank` | integer | YES |  |
| 345 | `misc_per100possessions_gp` | integer | YES |  |
| 346 | `misc_per100possessions_w` | integer | YES |  |
| 347 | `misc_per100possessions_l` | integer | YES |  |
| 348 | `misc_per100possessions_w_pct` | double precision | YES |  |
| 349 | `misc_per100possessions_min` | double precision | YES |  |
| 350 | `misc_per100possessions_pts_off_tov` | integer | YES |  |
| 351 | `misc_per100possessions_pts_2nd_chance` | integer | YES |  |
| 352 | `misc_per100possessions_pts_fb` | integer | YES |  |
| 353 | `misc_per100possessions_pts_paint` | integer | YES |  |
| 354 | `misc_per100possessions_opp_pts_off_tov` | integer | YES |  |
| 355 | `misc_per100possessions_opp_pts_2nd_chance` | integer | YES |  |
| 356 | `misc_per100possessions_opp_pts_fb` | integer | YES |  |
| 357 | `misc_per100possessions_opp_pts_paint` | integer | YES |  |
| 358 | `misc_per100possessions_gp_rank` | integer | YES |  |
| 359 | `misc_per100possessions_w_rank` | integer | YES |  |
| 360 | `misc_per100possessions_l_rank` | integer | YES |  |
| 361 | `misc_per100possessions_w_pct_rank` | integer | YES |  |
| 362 | `misc_per100possessions_min_rank` | integer | YES |  |
| 363 | `misc_per100possessions_pts_off_tov_rank` | integer | YES |  |
| 364 | `misc_per100possessions_pts_2nd_chance_rank` | integer | YES |  |
| 365 | `misc_per100possessions_pts_fb_rank` | integer | YES |  |
| 366 | `misc_per100possessions_pts_paint_rank` | integer | YES |  |
| 367 | `misc_per100possessions_opp_pts_off_tov_rank` | integer | YES |  |
| 368 | `misc_per100possessions_opp_pts_2nd_chance_rank` | integer | YES |  |
| 369 | `misc_per100possessions_opp_pts_fb_rank` | integer | YES |  |
| 370 | `misc_per100possessions_opp_pts_paint_rank` | integer | YES |  |
| 371 | `fourfactors_totals_gp` | integer | YES |  |
| 372 | `fourfactors_totals_w` | integer | YES |  |
| 373 | `fourfactors_totals_l` | integer | YES |  |
| 374 | `fourfactors_totals_w_pct` | double precision | YES |  |
| 375 | `fourfactors_totals_min` | double precision | YES |  |
| 376 | `fourfactors_totals_efg_pct` | double precision | YES |  |
| 377 | `fourfactors_totals_fta_rate` | double precision | YES |  |
| 378 | `fourfactors_totals_tm_tov_pct` | double precision | YES |  |
| 379 | `fourfactors_totals_oreb_pct` | double precision | YES |  |
| 380 | `fourfactors_totals_opp_efg_pct` | double precision | YES |  |
| 381 | `fourfactors_totals_opp_fta_rate` | double precision | YES |  |
| 382 | `fourfactors_totals_opp_tov_pct` | double precision | YES |  |
| 383 | `fourfactors_totals_opp_oreb_pct` | double precision | YES |  |
| 384 | `fourfactors_per48_gp` | integer | YES |  |
| 385 | `fourfactors_per48_w` | integer | YES |  |
| 386 | `fourfactors_per48_l` | integer | YES |  |
| 387 | `fourfactors_per48_w_pct` | double precision | YES |  |
| 388 | `fourfactors_per48_min` | double precision | YES |  |
| 389 | `fourfactors_per48_efg_pct` | double precision | YES |  |
| 390 | `fourfactors_per48_fta_rate` | double precision | YES |  |
| 391 | `fourfactors_per48_tm_tov_pct` | double precision | YES |  |
| 392 | `fourfactors_per48_oreb_pct` | double precision | YES |  |
| 393 | `fourfactors_per48_opp_efg_pct` | double precision | YES |  |
| 394 | `fourfactors_per48_opp_fta_rate` | double precision | YES |  |
| 395 | `fourfactors_per48_opp_tov_pct` | double precision | YES |  |
| 396 | `fourfactors_per48_opp_oreb_pct` | double precision | YES |  |
| 397 | `fourfactors_per100possessions_gp` | integer | YES |  |
| 398 | `fourfactors_per100possessions_w` | integer | YES |  |
| 399 | `fourfactors_per100possessions_l` | integer | YES |  |
| 400 | `fourfactors_per100possessions_w_pct` | double precision | YES |  |
| 401 | `fourfactors_per100possessions_min` | double precision | YES |  |
| 402 | `fourfactors_per100possessions_efg_pct` | double precision | YES |  |
| 403 | `fourfactors_per100possessions_fta_rate` | double precision | YES |  |
| 404 | `fourfactors_per100possessions_tm_tov_pct` | double precision | YES |  |
| 405 | `fourfactors_per100possessions_oreb_pct` | double precision | YES |  |
| 406 | `fourfactors_per100possessions_opp_efg_pct` | double precision | YES |  |
| 407 | `fourfactors_per100possessions_opp_fta_rate` | double precision | YES |  |
| 408 | `fourfactors_per100possessions_opp_tov_pct` | double precision | YES |  |
| 409 | `fourfactors_per100possessions_opp_oreb_pct` | double precision | YES |  |
| 410 | `scoring_totals_gp` | integer | YES |  |
| 411 | `scoring_totals_w` | integer | YES |  |
| 412 | `scoring_totals_l` | integer | YES |  |
| 413 | `scoring_totals_w_pct` | double precision | YES |  |
| 414 | `scoring_totals_min` | double precision | YES |  |
| 415 | `scoring_totals_pct_fga_2pt` | double precision | YES |  |
| 416 | `scoring_totals_pct_fga_3pt` | double precision | YES |  |
| 417 | `scoring_totals_pct_pts_2pt` | double precision | YES |  |
| 418 | `scoring_totals_pct_pts_2pt_mr` | double precision | YES |  |
| 419 | `scoring_totals_pct_pts_3pt` | double precision | YES |  |
| 420 | `scoring_totals_pct_pts_fb` | double precision | YES |  |
| 421 | `scoring_totals_pct_pts_ft` | double precision | YES |  |
| 422 | `scoring_totals_pct_pts_off_tov` | double precision | YES |  |
| 423 | `scoring_totals_pct_pts_paint` | double precision | YES |  |
| 424 | `scoring_totals_pct_ast_2pm` | double precision | YES |  |
| 425 | `scoring_totals_pct_uast_2pm` | double precision | YES |  |
| 426 | `scoring_totals_pct_ast_3pm` | double precision | YES |  |
| 427 | `scoring_totals_pct_uast_3pm` | double precision | YES |  |
| 428 | `scoring_totals_pct_ast_fgm` | double precision | YES |  |
| 429 | `scoring_totals_pct_uast_fgm` | double precision | YES |  |
| 430 | `scoring_totals_gp_rank` | integer | YES |  |
| 431 | `scoring_totals_w_rank` | integer | YES |  |
| 432 | `scoring_totals_l_rank` | integer | YES |  |
| 433 | `scoring_totals_w_pct_rank` | integer | YES |  |
| 434 | `scoring_totals_min_rank` | integer | YES |  |
| 435 | `scoring_totals_pct_fga_2pt_rank` | integer | YES |  |
| 436 | `scoring_totals_pct_fga_3pt_rank` | integer | YES |  |
| 437 | `scoring_totals_pct_pts_2pt_rank` | integer | YES |  |
| 438 | `scoring_totals_pct_pts_2pt_mr_rank` | integer | YES |  |
| 439 | `scoring_totals_pct_pts_3pt_rank` | integer | YES |  |
| 440 | `scoring_totals_pct_pts_fb_rank` | integer | YES |  |
| 441 | `scoring_totals_pct_pts_ft_rank` | integer | YES |  |
| 442 | `scoring_totals_pct_pts_off_tov_rank` | integer | YES |  |
| 443 | `scoring_totals_pct_pts_paint_rank` | integer | YES |  |
| 444 | `scoring_totals_pct_ast_2pm_rank` | integer | YES |  |
| 445 | `scoring_totals_pct_uast_2pm_rank` | integer | YES |  |
| 446 | `scoring_totals_pct_ast_3pm_rank` | integer | YES |  |
| 447 | `scoring_totals_pct_uast_3pm_rank` | integer | YES |  |
| 448 | `scoring_totals_pct_ast_fgm_rank` | integer | YES |  |
| 449 | `scoring_totals_pct_uast_fgm_rank` | integer | YES |  |
| 450 | `scoring_per48_gp` | integer | YES |  |
| 451 | `scoring_per48_w` | integer | YES |  |
| 452 | `scoring_per48_l` | integer | YES |  |
| 453 | `scoring_per48_w_pct` | double precision | YES |  |
| 454 | `scoring_per48_min` | double precision | YES |  |
| 455 | `scoring_per48_pct_fga_2pt` | double precision | YES |  |
| 456 | `scoring_per48_pct_fga_3pt` | double precision | YES |  |
| 457 | `scoring_per48_pct_pts_2pt` | double precision | YES |  |
| 458 | `scoring_per48_pct_pts_2pt_mr` | double precision | YES |  |
| 459 | `scoring_per48_pct_pts_3pt` | double precision | YES |  |
| 460 | `scoring_per48_pct_pts_fb` | double precision | YES |  |
| 461 | `scoring_per48_pct_pts_ft` | double precision | YES |  |
| 462 | `scoring_per48_pct_pts_off_tov` | double precision | YES |  |
| 463 | `scoring_per48_pct_pts_paint` | double precision | YES |  |
| 464 | `scoring_per48_pct_ast_2pm` | double precision | YES |  |
| 465 | `scoring_per48_pct_uast_2pm` | double precision | YES |  |
| 466 | `scoring_per48_pct_ast_3pm` | double precision | YES |  |
| 467 | `scoring_per48_pct_uast_3pm` | double precision | YES |  |
| 468 | `scoring_per48_pct_ast_fgm` | double precision | YES |  |
| 469 | `scoring_per48_pct_uast_fgm` | double precision | YES |  |
| 470 | `scoring_per48_gp_rank` | integer | YES |  |
| 471 | `scoring_per48_w_rank` | integer | YES |  |
| 472 | `scoring_per48_l_rank` | integer | YES |  |
| 473 | `scoring_per48_w_pct_rank` | integer | YES |  |
| 474 | `scoring_per48_min_rank` | integer | YES |  |
| 475 | `scoring_per48_pct_fga_2pt_rank` | integer | YES |  |
| 476 | `scoring_per48_pct_fga_3pt_rank` | integer | YES |  |
| 477 | `scoring_per48_pct_pts_2pt_rank` | integer | YES |  |
| 478 | `scoring_per48_pct_pts_2pt_mr_rank` | integer | YES |  |
| 479 | `scoring_per48_pct_pts_3pt_rank` | integer | YES |  |
| 480 | `scoring_per48_pct_pts_fb_rank` | integer | YES |  |
| 481 | `scoring_per48_pct_pts_ft_rank` | integer | YES |  |
| 482 | `scoring_per48_pct_pts_off_tov_rank` | integer | YES |  |
| 483 | `scoring_per48_pct_pts_paint_rank` | integer | YES |  |
| 484 | `scoring_per48_pct_ast_2pm_rank` | integer | YES |  |
| 485 | `scoring_per48_pct_uast_2pm_rank` | integer | YES |  |
| 486 | `scoring_per48_pct_ast_3pm_rank` | integer | YES |  |
| 487 | `scoring_per48_pct_uast_3pm_rank` | integer | YES |  |
| 488 | `scoring_per48_pct_ast_fgm_rank` | integer | YES |  |
| 489 | `scoring_per48_pct_uast_fgm_rank` | integer | YES |  |
| 490 | `scoring_per100possessions_gp` | integer | YES |  |
| 491 | `scoring_per100possessions_w` | integer | YES |  |
| 492 | `scoring_per100possessions_l` | integer | YES |  |
| 493 | `scoring_per100possessions_w_pct` | double precision | YES |  |
| 494 | `scoring_per100possessions_min` | double precision | YES |  |
| 495 | `scoring_per100possessions_pct_fga_2pt` | double precision | YES |  |
| 496 | `scoring_per100possessions_pct_fga_3pt` | double precision | YES |  |
| 497 | `scoring_per100possessions_pct_pts_2pt` | double precision | YES |  |
| 498 | `scoring_per100possessions_pct_pts_2pt_mr` | double precision | YES |  |
| 499 | `scoring_per100possessions_pct_pts_3pt` | double precision | YES |  |
| 500 | `scoring_per100possessions_pct_pts_fb` | double precision | YES |  |
| 501 | `scoring_per100possessions_pct_pts_ft` | double precision | YES |  |
| 502 | `scoring_per100possessions_pct_pts_off_tov` | double precision | YES |  |
| 503 | `scoring_per100possessions_pct_pts_paint` | double precision | YES |  |
| 504 | `scoring_per100possessions_pct_ast_2pm` | double precision | YES |  |
| 505 | `scoring_per100possessions_pct_uast_2pm` | double precision | YES |  |
| 506 | `scoring_per100possessions_pct_ast_3pm` | double precision | YES |  |
| 507 | `scoring_per100possessions_pct_uast_3pm` | double precision | YES |  |
| 508 | `scoring_per100possessions_pct_ast_fgm` | double precision | YES |  |
| 509 | `scoring_per100possessions_pct_uast_fgm` | double precision | YES |  |
| 510 | `scoring_per100possessions_gp_rank` | integer | YES |  |
| 511 | `scoring_per100possessions_w_rank` | integer | YES |  |
| 512 | `scoring_per100possessions_l_rank` | integer | YES |  |
| 513 | `scoring_per100possessions_w_pct_rank` | integer | YES |  |
| 514 | `scoring_per100possessions_min_rank` | integer | YES |  |
| 515 | `scoring_per100possessions_pct_fga_2pt_rank` | integer | YES |  |
| 516 | `scoring_per100possessions_pct_fga_3pt_rank` | integer | YES |  |
| 517 | `scoring_per100possessions_pct_pts_2pt_rank` | integer | YES |  |
| 518 | `scoring_per100possessions_pct_pts_2pt_mr_rank` | integer | YES |  |
| 519 | `scoring_per100possessions_pct_pts_3pt_rank` | integer | YES |  |
| 520 | `scoring_per100possessions_pct_pts_fb_rank` | integer | YES |  |
| 521 | `scoring_per100possessions_pct_pts_ft_rank` | integer | YES |  |
| 522 | `scoring_per100possessions_pct_pts_off_tov_rank` | integer | YES |  |
| 523 | `scoring_per100possessions_pct_pts_paint_rank` | integer | YES |  |
| 524 | `scoring_per100possessions_pct_ast_2pm_rank` | integer | YES |  |
| 525 | `scoring_per100possessions_pct_uast_2pm_rank` | integer | YES |  |
| 526 | `scoring_per100possessions_pct_ast_3pm_rank` | integer | YES |  |
| 527 | `scoring_per100possessions_pct_uast_3pm_rank` | integer | YES |  |
| 528 | `scoring_per100possessions_pct_ast_fgm_rank` | integer | YES |  |
| 529 | `scoring_per100possessions_pct_uast_fgm_rank` | integer | YES |  |
| 530 | `opponent_totals_gp` | integer | YES |  |
| 531 | `opponent_totals_w` | integer | YES |  |
| 532 | `opponent_totals_l` | integer | YES |  |
| 533 | `opponent_totals_w_pct` | double precision | YES |  |
| 534 | `opponent_totals_min` | double precision | YES |  |
| 535 | `opponent_totals_opp_fgm` | integer | YES |  |
| 536 | `opponent_totals_opp_fga` | integer | YES |  |
| 537 | `opponent_totals_opp_fg_pct` | double precision | YES |  |
| 538 | `opponent_totals_opp_fg3m` | integer | YES |  |
| 539 | `opponent_totals_opp_fg3a` | integer | YES |  |
| 540 | `opponent_totals_opp_fg3_pct` | double precision | YES |  |
| 541 | `opponent_totals_opp_ftm` | integer | YES |  |
| 542 | `opponent_totals_opp_fta` | integer | YES |  |
| 543 | `opponent_totals_opp_ft_pct` | double precision | YES |  |
| 544 | `opponent_totals_opp_oreb` | integer | YES |  |
| 545 | `opponent_totals_opp_dreb` | integer | YES |  |
| 546 | `opponent_totals_opp_reb` | integer | YES |  |
| 547 | `opponent_totals_opp_ast` | integer | YES |  |
| 548 | `opponent_totals_opp_tov` | integer | YES |  |
| 549 | `opponent_totals_opp_stl` | integer | YES |  |
| 550 | `opponent_totals_opp_blk` | integer | YES |  |
| 551 | `opponent_totals_opp_blka` | integer | YES |  |
| 552 | `opponent_totals_opp_pf` | integer | YES |  |
| 553 | `opponent_totals_opp_pfd` | integer | YES |  |
| 554 | `opponent_totals_opp_pts` | integer | YES |  |
| 555 | `opponent_totals_plus_minus` | double precision | YES |  |
| 556 | `opponent_totals_gp_rank` | integer | YES |  |
| 557 | `opponent_totals_w_rank` | integer | YES |  |
| 558 | `opponent_totals_l_rank` | integer | YES |  |
| 559 | `opponent_totals_w_pct_rank` | integer | YES |  |
| 560 | `opponent_totals_min_rank` | integer | YES |  |
| 561 | `opponent_totals_opp_fgm_rank` | integer | YES |  |
| 562 | `opponent_totals_opp_fga_rank` | integer | YES |  |
| 563 | `opponent_totals_opp_fg_pct_rank` | integer | YES |  |
| 564 | `opponent_totals_opp_fg3m_rank` | integer | YES |  |
| 565 | `opponent_totals_opp_fg3a_rank` | integer | YES |  |
| 566 | `opponent_totals_opp_fg3_pct_rank` | integer | YES |  |
| 567 | `opponent_totals_opp_ftm_rank` | integer | YES |  |
| 568 | `opponent_totals_opp_fta_rank` | integer | YES |  |
| 569 | `opponent_totals_opp_ft_pct_rank` | integer | YES |  |
| 570 | `opponent_totals_opp_oreb_rank` | integer | YES |  |
| 571 | `opponent_totals_opp_dreb_rank` | integer | YES |  |
| 572 | `opponent_totals_opp_reb_rank` | integer | YES |  |
| 573 | `opponent_totals_opp_ast_rank` | integer | YES |  |
| 574 | `opponent_totals_opp_tov_rank` | integer | YES |  |
| 575 | `opponent_totals_opp_stl_rank` | integer | YES |  |
| 576 | `opponent_totals_opp_blk_rank` | integer | YES |  |
| 577 | `opponent_totals_opp_blka_rank` | integer | YES |  |
| 578 | `opponent_totals_opp_pf_rank` | integer | YES |  |
| 579 | `opponent_totals_opp_pfd_rank` | integer | YES |  |
| 580 | `opponent_totals_opp_pfd1` | integer | YES |  |
| 581 | `opponent_totals_opp_pts_rank` | integer | YES |  |
| 582 | `opponent_totals_plus_minus_rank` | integer | YES |  |
| 583 | `opponent_per48_gp` | integer | YES |  |
| 584 | `opponent_per48_w` | integer | YES |  |
| 585 | `opponent_per48_l` | integer | YES |  |
| 586 | `opponent_per48_w_pct` | double precision | YES |  |
| 587 | `opponent_per48_min` | double precision | YES |  |
| 588 | `opponent_per48_opp_fgm` | integer | YES |  |
| 589 | `opponent_per48_opp_fga` | integer | YES |  |
| 590 | `opponent_per48_opp_fg_pct` | double precision | YES |  |
| 591 | `opponent_per48_opp_fg3m` | integer | YES |  |
| 592 | `opponent_per48_opp_fg3a` | integer | YES |  |
| 593 | `opponent_per48_opp_fg3_pct` | double precision | YES |  |
| 594 | `opponent_per48_opp_ftm` | integer | YES |  |
| 595 | `opponent_per48_opp_fta` | integer | YES |  |
| 596 | `opponent_per48_opp_ft_pct` | double precision | YES |  |
| 597 | `opponent_per48_opp_oreb` | integer | YES |  |
| 598 | `opponent_per48_opp_dreb` | integer | YES |  |
| 599 | `opponent_per48_opp_reb` | integer | YES |  |
| 600 | `opponent_per48_opp_ast` | integer | YES |  |
| 601 | `opponent_per48_opp_tov` | integer | YES |  |
| 602 | `opponent_per48_opp_stl` | integer | YES |  |
| 603 | `opponent_per48_opp_blk` | integer | YES |  |
| 604 | `opponent_per48_opp_blka` | integer | YES |  |
| 605 | `opponent_per48_opp_pf` | integer | YES |  |
| 606 | `opponent_per48_opp_pfd` | integer | YES |  |
| 607 | `opponent_per48_opp_pts` | integer | YES |  |
| 608 | `opponent_per48_plus_minus` | double precision | YES |  |
| 609 | `opponent_per48_gp_rank` | integer | YES |  |
| 610 | `opponent_per48_w_rank` | integer | YES |  |
| 611 | `opponent_per48_l_rank` | integer | YES |  |
| 612 | `opponent_per48_w_pct_rank` | integer | YES |  |
| 613 | `opponent_per48_min_rank` | integer | YES |  |
| 614 | `opponent_per48_opp_fgm_rank` | integer | YES |  |
| 615 | `opponent_per48_opp_fga_rank` | integer | YES |  |
| 616 | `opponent_per48_opp_fg_pct_rank` | integer | YES |  |
| 617 | `opponent_per48_opp_fg3m_rank` | integer | YES |  |
| 618 | `opponent_per48_opp_fg3a_rank` | integer | YES |  |
| 619 | `opponent_per48_opp_fg3_pct_rank` | integer | YES |  |
| 620 | `opponent_per48_opp_ftm_rank` | integer | YES |  |
| 621 | `opponent_per48_opp_fta_rank` | integer | YES |  |
| 622 | `opponent_per48_opp_ft_pct_rank` | integer | YES |  |
| 623 | `opponent_per48_opp_oreb_rank` | integer | YES |  |
| 624 | `opponent_per48_opp_dreb_rank` | integer | YES |  |
| 625 | `opponent_per48_opp_reb_rank` | integer | YES |  |
| 626 | `opponent_per48_opp_ast_rank` | integer | YES |  |
| 627 | `opponent_per48_opp_tov_rank` | integer | YES |  |
| 628 | `opponent_per48_opp_stl_rank` | integer | YES |  |
| 629 | `opponent_per48_opp_blk_rank` | integer | YES |  |
| 630 | `opponent_per48_opp_blka_rank` | integer | YES |  |
| 631 | `opponent_per48_opp_pf_rank` | integer | YES |  |
| 632 | `opponent_per48_opp_pfd_rank` | integer | YES |  |
| 633 | `opponent_per48_opp_pfd1` | integer | YES |  |
| 634 | `opponent_per48_opp_pts_rank` | integer | YES |  |
| 635 | `opponent_per48_plus_minus_rank` | integer | YES |  |
| 636 | `opponent_per100possessions_gp` | integer | YES |  |
| 637 | `opponent_per100possessions_w` | integer | YES |  |
| 638 | `opponent_per100possessions_l` | integer | YES |  |
| 639 | `opponent_per100possessions_w_pct` | double precision | YES |  |
| 640 | `opponent_per100possessions_min` | double precision | YES |  |
| 641 | `opponent_per100possessions_opp_fgm` | integer | YES |  |
| 642 | `opponent_per100possessions_opp_fga` | integer | YES |  |
| 643 | `opponent_per100possessions_opp_fg_pct` | double precision | YES |  |
| 644 | `opponent_per100possessions_opp_fg3m` | integer | YES |  |
| 645 | `opponent_per100possessions_opp_fg3a` | integer | YES |  |
| 646 | `opponent_per100possessions_opp_fg3_pct` | double precision | YES |  |
| 647 | `opponent_per100possessions_opp_ftm` | integer | YES |  |
| 648 | `opponent_per100possessions_opp_fta` | integer | YES |  |
| 649 | `opponent_per100possessions_opp_ft_pct` | double precision | YES |  |
| 650 | `opponent_per100possessions_opp_oreb` | integer | YES |  |
| 651 | `opponent_per100possessions_opp_dreb` | integer | YES |  |
| 652 | `opponent_per100possessions_opp_reb` | integer | YES |  |
| 653 | `opponent_per100possessions_opp_ast` | integer | YES |  |
| 654 | `opponent_per100possessions_opp_tov` | integer | YES |  |
| 655 | `opponent_per100possessions_opp_stl` | integer | YES |  |
| 656 | `opponent_per100possessions_opp_blk` | integer | YES |  |
| 657 | `opponent_per100possessions_opp_blka` | integer | YES |  |
| 658 | `opponent_per100possessions_opp_pf` | integer | YES |  |
| 659 | `opponent_per100possessions_opp_pfd` | integer | YES |  |
| 660 | `opponent_per100possessions_opp_pts` | integer | YES |  |
| 661 | `opponent_per100possessions_plus_minus` | double precision | YES |  |
| 662 | `opponent_per100possessions_gp_rank` | integer | YES |  |
| 663 | `opponent_per100possessions_w_rank` | integer | YES |  |
| 664 | `opponent_per100possessions_l_rank` | integer | YES |  |
| 665 | `opponent_per100possessions_w_pct_rank` | integer | YES |  |
| 666 | `opponent_per100possessions_min_rank` | integer | YES |  |
| 667 | `opponent_per100possessions_opp_fgm_rank` | integer | YES |  |
| 668 | `opponent_per100possessions_opp_fga_rank` | integer | YES |  |
| 669 | `opponent_per100possessions_opp_fg_pct_rank` | integer | YES |  |
| 670 | `opponent_per100possessions_opp_fg3m_rank` | integer | YES |  |
| 671 | `opponent_per100possessions_opp_fg3a_rank` | integer | YES |  |
| 672 | `opponent_per100possessions_opp_fg3_pct_rank` | integer | YES |  |
| 673 | `opponent_per100possessions_opp_ftm_rank` | integer | YES |  |
| 674 | `opponent_per100possessions_opp_fta_rank` | integer | YES |  |
| 675 | `opponent_per100possessions_opp_ft_pct_rank` | integer | YES |  |
| 676 | `opponent_per100possessions_opp_oreb_rank` | integer | YES |  |
| 677 | `opponent_per100possessions_opp_dreb_rank` | integer | YES |  |
| 678 | `opponent_per100possessions_opp_reb_rank` | integer | YES |  |
| 679 | `opponent_per100possessions_opp_ast_rank` | integer | YES |  |
| 680 | `opponent_per100possessions_opp_tov_rank` | integer | YES |  |
| 681 | `opponent_per100possessions_opp_stl_rank` | integer | YES |  |
| 682 | `opponent_per100possessions_opp_blk_rank` | integer | YES |  |
| 683 | `opponent_per100possessions_opp_blka_rank` | integer | YES |  |
| 684 | `opponent_per100possessions_opp_pf_rank` | integer | YES |  |
| 685 | `opponent_per100possessions_opp_pfd_rank` | integer | YES |  |
| 686 | `opponent_per100possessions_opp_pfd1` | integer | YES |  |
| 687 | `opponent_per100possessions_opp_pts_rank` | integer | YES |  |
| 688 | `opponent_per100possessions_plus_minus_rank` | integer | YES |  |
| 689 | `defense_totals_gp` | integer | YES |  |
| 690 | `defense_totals_w` | integer | YES |  |
| 691 | `defense_totals_l` | integer | YES |  |
| 692 | `defense_totals_w_pct` | double precision | YES |  |
| 693 | `defense_totals_min` | double precision | YES |  |
| 694 | `defense_totals_def_rating` | double precision | YES |  |
| 695 | `defense_totals_dreb` | integer | YES |  |
| 696 | `defense_totals_dreb_pct` | double precision | YES |  |
| 697 | `defense_totals_stl` | integer | YES |  |
| 698 | `defense_totals_blk` | integer | YES |  |
| 699 | `defense_totals_opp_pts_off_tov` | integer | YES |  |
| 700 | `defense_totals_opp_pts_2nd_chance` | integer | YES |  |
| 701 | `defense_totals_opp_pts_fb` | integer | YES |  |
| 702 | `defense_totals_opp_pts_paint` | integer | YES |  |
| 703 | `defense_totals_gp_rank` | integer | YES |  |
| 704 | `defense_totals_w_rank` | integer | YES |  |
| 705 | `defense_totals_l_rank` | integer | YES |  |
| 706 | `defense_totals_w_pct_rank` | integer | YES |  |
| 707 | `defense_totals_min_rank` | integer | YES |  |
| 708 | `defense_totals_def_rating_rank` | integer | YES |  |
| 709 | `defense_totals_dreb_rank` | integer | YES |  |
| 710 | `defense_totals_dreb_pct_rank` | integer | YES |  |
| 711 | `defense_totals_stl_rank` | integer | YES |  |
| 712 | `defense_totals_blk_rank` | integer | YES |  |
| 713 | `defense_totals_opp_pts_off_tov_rank` | integer | YES |  |
| 714 | `defense_totals_opp_pts_2nd_chance_rank` | integer | YES |  |
| 715 | `defense_totals_opp_pts_fb_rank` | integer | YES |  |
| 716 | `defense_totals_opp_pts_paint_rank` | integer | YES |  |
| 717 | `defense_per48_gp` | integer | YES |  |
| 718 | `defense_per48_w` | integer | YES |  |
| 719 | `defense_per48_l` | integer | YES |  |
| 720 | `defense_per48_w_pct` | double precision | YES |  |
| 721 | `defense_per48_min` | double precision | YES |  |
| 722 | `defense_per48_def_rating` | double precision | YES |  |
| 723 | `defense_per48_dreb` | integer | YES |  |
| 724 | `defense_per48_dreb_pct` | double precision | YES |  |
| 725 | `defense_per48_stl` | integer | YES |  |
| 726 | `defense_per48_blk` | integer | YES |  |
| 727 | `defense_per48_opp_pts_off_tov` | integer | YES |  |
| 728 | `defense_per48_opp_pts_2nd_chance` | integer | YES |  |
| 729 | `defense_per48_opp_pts_fb` | integer | YES |  |
| 730 | `defense_per48_opp_pts_paint` | integer | YES |  |
| 731 | `defense_per48_gp_rank` | integer | YES |  |
| 732 | `defense_per48_w_rank` | integer | YES |  |
| 733 | `defense_per48_l_rank` | integer | YES |  |
| 734 | `defense_per48_w_pct_rank` | integer | YES |  |
| 735 | `defense_per48_min_rank` | integer | YES |  |
| 736 | `defense_per48_def_rating_rank` | integer | YES |  |
| 737 | `defense_per48_dreb_rank` | integer | YES |  |
| 738 | `defense_per48_dreb_pct_rank` | integer | YES |  |
| 739 | `defense_per48_stl_rank` | integer | YES |  |
| 740 | `defense_per48_blk_rank` | integer | YES |  |
| 741 | `defense_per48_opp_pts_off_tov_rank` | integer | YES |  |
| 742 | `defense_per48_opp_pts_2nd_chance_rank` | integer | YES |  |
| 743 | `defense_per48_opp_pts_fb_rank` | integer | YES |  |
| 744 | `defense_per48_opp_pts_paint_rank` | integer | YES |  |
| 745 | `defense_per100possessions_gp` | integer | YES |  |
| 746 | `defense_per100possessions_w` | integer | YES |  |
| 747 | `defense_per100possessions_l` | integer | YES |  |
| 748 | `defense_per100possessions_w_pct` | double precision | YES |  |
| 749 | `defense_per100possessions_min` | double precision | YES |  |
| 750 | `defense_per100possessions_def_rating` | double precision | YES |  |
| 751 | `defense_per100possessions_dreb` | integer | YES |  |
| 752 | `defense_per100possessions_dreb_pct` | double precision | YES |  |
| 753 | `defense_per100possessions_stl` | integer | YES |  |
| 754 | `defense_per100possessions_blk` | integer | YES |  |
| 755 | `defense_per100possessions_opp_pts_off_tov` | integer | YES |  |
| 756 | `defense_per100possessions_opp_pts_2nd_chance` | integer | YES |  |
| 757 | `defense_per100possessions_opp_pts_fb` | integer | YES |  |
| 758 | `defense_per100possessions_opp_pts_paint` | integer | YES |  |
| 759 | `defense_per100possessions_gp_rank` | integer | YES |  |
| 760 | `defense_per100possessions_w_rank` | integer | YES |  |
| 761 | `defense_per100possessions_l_rank` | integer | YES |  |
| 762 | `defense_per100possessions_w_pct_rank` | integer | YES |  |
| 763 | `defense_per100possessions_min_rank` | integer | YES |  |
| 764 | `defense_per100possessions_def_rating_rank` | integer | YES |  |
| 765 | `defense_per100possessions_dreb_rank` | integer | YES |  |
| 766 | `defense_per100possessions_dreb_pct_rank` | integer | YES |  |
| 767 | `defense_per100possessions_stl_rank` | integer | YES |  |
| 768 | `defense_per100possessions_blk_rank` | integer | YES |  |
| 769 | `defense_per100possessions_opp_pts_off_tov_rank` | integer | YES |  |
| 770 | `defense_per100possessions_opp_pts_2nd_chance_rank` | integer | YES |  |
| 771 | `defense_per100possessions_opp_pts_fb_rank` | integer | YES |  |
| 772 | `defense_per100possessions_opp_pts_paint_rank` | integer | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17034_1_not_null` | CHECK |  |  |
| `2200_17034_2_not_null` | CHECK |  |  |
| `2200_17034_3_not_null` | CHECK |  |  |
| `2200_17034_4_not_null` | CHECK |  |  |
| `league_dash_team_stats_season_type_check` | CHECK |  |  |
| `league_dash_team_stats_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `league_dash_team_stats_pkey` | PRIMARY KEY | team_id, team_id, team_id, season, season, season, season_type, season_type, season_type |  |

#### Indexes

- `idx_league_dash_team_stats_season`: `CREATE INDEX idx_league_dash_team_stats_season ON public.league_dash_team_stats USING btree (season)`
- `idx_league_dash_team_stats_season_type`: `CREATE INDEX idx_league_dash_team_stats_season_type ON public.league_dash_team_stats USING btree (season_type)`
- `idx_league_dash_team_stats_team_id`: `CREATE INDEX idx_league_dash_team_stats_team_id ON public.league_dash_team_stats USING btree (team_id)`
- `league_dash_team_stats_pkey`: `CREATE UNIQUE INDEX league_dash_team_stats_pkey ON public.league_dash_team_stats USING btree (team_id, season, season_type)`

### `leaguedashplayerstats`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `player_id` | integer | NO |  |
| 2 | `player_name` | character varying(255) | YES |  |
| 3 | `season` | character varying(10) | NO |  |
| 4 | `team_id` | integer | YES |  |
| 5 | `team_abbreviation` | character varying(10) | YES |  |
| 6 | `age` | integer | YES |  |
| 7 | `gp` | integer | YES |  |
| 8 | `w` | integer | YES |  |
| 9 | `l` | integer | YES |  |
| 10 | `w_pct` | double precision | YES |  |
| 11 | `min` | double precision | YES |  |
| 12 | `fgm` | double precision | YES |  |
| 13 | `fga` | double precision | YES |  |
| 14 | `fg_pct` | double precision | YES |  |
| 15 | `fg3m` | double precision | YES |  |
| 16 | `fg3a` | double precision | YES |  |
| 17 | `fg3_pct` | double precision | YES |  |
| 18 | `ftm` | double precision | YES |  |
| 19 | `fta` | double precision | YES |  |
| 20 | `ft_pct` | double precision | YES |  |
| 21 | `oreb` | double precision | YES |  |
| 22 | `dreb` | double precision | YES |  |
| 23 | `reb` | double precision | YES |  |
| 24 | `ast` | double precision | YES |  |
| 25 | `tov` | double precision | YES |  |
| 26 | `stl` | double precision | YES |  |
| 27 | `blk` | double precision | YES |  |
| 28 | `blka` | double precision | YES |  |
| 29 | `pf` | double precision | YES |  |
| 30 | `pfd` | double precision | YES |  |
| 31 | `pts` | double precision | YES |  |
| 32 | `plus_minus` | double precision | YES |  |
| 33 | `nba_fantasy_pts` | double precision | YES |  |
| 34 | `dd2` | integer | YES |  |
| 35 | `td3` | integer | YES |  |
| 36 | `gp_rank` | integer | YES |  |
| 37 | `w_rank` | integer | YES |  |
| 38 | `l_rank` | integer | YES |  |
| 39 | `w_pct_rank` | integer | YES |  |
| 40 | `min_rank` | integer | YES |  |
| 41 | `fgm_rank` | integer | YES |  |
| 42 | `fga_rank` | integer | YES |  |
| 43 | `fg_pct_rank` | integer | YES |  |
| 44 | `fg3m_rank` | integer | YES |  |
| 45 | `fg3a_rank` | integer | YES |  |
| 46 | `fg3_pct_rank` | integer | YES |  |
| 47 | `ftm_rank` | integer | YES |  |
| 48 | `fta_rank` | integer | YES |  |
| 49 | `ft_pct_rank` | integer | YES |  |
| 50 | `oreb_rank` | integer | YES |  |
| 51 | `dreb_rank` | integer | YES |  |
| 52 | `reb_rank` | integer | YES |  |
| 53 | `ast_rank` | integer | YES |  |
| 54 | `tov_rank` | integer | YES |  |
| 55 | `stl_rank` | integer | YES |  |
| 56 | `blk_rank` | integer | YES |  |
| 57 | `blka_rank` | integer | YES |  |
| 58 | `pf_rank` | integer | YES |  |
| 59 | `pfd_rank` | integer | YES |  |
| 60 | `pts_rank` | integer | YES |  |
| 61 | `plus_minus_rank` | integer | YES |  |
| 62 | `nba_fantasy_pts_rank` | integer | YES |  |
| 63 | `dd2_rank` | integer | YES |  |
| 64 | `td3_rank` | integer | YES |  |
| 65 | `wnba_fantasy_pts` | double precision | YES |  |
| 66 | `wnba_fantasy_pts_rank` | integer | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17040_1_not_null` | CHECK |  |  |
| `2200_17040_3_not_null` | CHECK |  |  |
| `leaguedashplayerstats_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `leaguedashplayerstats_pkey` | PRIMARY KEY | player_id, player_id, season, season |  |

#### Indexes

- `idx_leaguedashplayerstats_player_id`: `CREATE INDEX idx_leaguedashplayerstats_player_id ON public.leaguedashplayerstats USING btree (player_id)`
- `idx_leaguedashplayerstats_season`: `CREATE INDEX idx_leaguedashplayerstats_season ON public.leaguedashplayerstats USING btree (season)`
- `idx_leaguedashplayerstats_team_id`: `CREATE INDEX idx_leaguedashplayerstats_team_id ON public.leaguedashplayerstats USING btree (team_id)`
- `leaguedashplayerstats_pkey`: `CREATE UNIQUE INDEX leaguedashplayerstats_pkey ON public.leaguedashplayerstats USING btree (player_id, season)`

### `player_consecutive_streak_snapshots`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | bigint | NO | nextval('player_consecutive_streak_snapshots_id_seq'::regclass) |
| 2 | `player_id` | bigint | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat` | character varying(16) | NO |  |
| 5 | `threshold` | integer | NO |  |
| 6 | `streak_games` | integer | NO |  |
| 7 | `start_game_id` | character varying | NO |  |
| 8 | `end_game_id` | character varying | NO |  |
| 9 | `start_date` | date | NO |  |
| 10 | `end_date` | date | NO |  |
| 11 | `is_active` | boolean | NO |  |
| 12 | `streak_kind` | character varying(16) | NO |  |
| 13 | `season` | character varying(7) | NO |  |
| 14 | `season_type` | character varying(32) | NO |  |
| 15 | `feature_as_of` | timestamp with time zone | NO |  |
| 16 | `data_available_at` | timestamp with time zone | NO |  |
| 17 | `calculation_version` | character varying(64) | NO |  |
| 18 | `source_run_id` | character varying(36) | NO |  |
| 19 | `completeness_status` | character varying(16) | NO |  |
| 20 | `missing_input_flags` | jsonb | NO | '{}'::jsonb |
| 21 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17043_10_not_null` | CHECK |  |  |
| `2200_17043_11_not_null` | CHECK |  |  |
| `2200_17043_12_not_null` | CHECK |  |  |
| `2200_17043_13_not_null` | CHECK |  |  |
| `2200_17043_14_not_null` | CHECK |  |  |
| `2200_17043_15_not_null` | CHECK |  |  |
| `2200_17043_16_not_null` | CHECK |  |  |
| `2200_17043_17_not_null` | CHECK |  |  |
| `2200_17043_18_not_null` | CHECK |  |  |
| `2200_17043_19_not_null` | CHECK |  |  |
| `2200_17043_1_not_null` | CHECK |  |  |
| `2200_17043_20_not_null` | CHECK |  |  |
| `2200_17043_21_not_null` | CHECK |  |  |
| `2200_17043_2_not_null` | CHECK |  |  |
| `2200_17043_3_not_null` | CHECK |  |  |
| `2200_17043_4_not_null` | CHECK |  |  |
| `2200_17043_5_not_null` | CHECK |  |  |
| `2200_17043_6_not_null` | CHECK |  |  |
| `2200_17043_7_not_null` | CHECK |  |  |
| `2200_17043_8_not_null` | CHECK |  |  |
| `2200_17043_9_not_null` | CHECK |  |  |
| `ck_player_streak_snapshot_completeness` | CHECK |  |  |
| `ck_player_streak_snapshot_kind` | CHECK |  |  |
| `player_consecutive_streak_snapshots_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `player_consecutive_streak_snapshots_source_run_id_fkey` | FOREIGN KEY | source_run_id | `ingestion_runs` (run_id) |
| `player_consecutive_streak_snapshots_pkey` | PRIMARY KEY | id |  |
| `uq_player_streak_snapshot_natural_key` | UNIQUE | player_id, player_id, player_id, player_id, player_id, player_id, player_id, player_id, stat, stat, stat, stat, stat, stat, stat, stat, threshold, threshold, threshold, threshold, threshold, threshold, threshold, threshold, season, season, season, season, season, season, season, season, season_type, season_type, season_type, season_type, season_type, season_type, season_type, season_type, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, streak_kind, streak_kind, streak_kind, streak_kind, streak_kind, streak_kind, streak_kind, streak_kind |  |

#### Indexes

- `idx_player_streak_snapshot_latest`: `CREATE INDEX idx_player_streak_snapshot_latest ON public.player_consecutive_streak_snapshots USING btree (season, season_type, calculation_version, completeness_status, feature_as_of)`
- `idx_player_streak_snapshot_player`: `CREATE INDEX idx_player_streak_snapshot_player ON public.player_consecutive_streak_snapshots USING btree (player_id, feature_as_of)`
- `player_consecutive_streak_snapshots_pkey`: `CREATE UNIQUE INDEX player_consecutive_streak_snapshots_pkey ON public.player_consecutive_streak_snapshots USING btree (id)`
- `uq_player_streak_snapshot_natural_key`: `CREATE UNIQUE INDEX uq_player_streak_snapshot_natural_key ON public.player_consecutive_streak_snapshots USING btree (player_id, stat, threshold, season, season_type, feature_as_of, calculation_version, streak_kind)`

### `player_consecutive_streaks`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('player_consecutive_streaks_id_seq'::regclass) |
| 2 | `player_id` | integer | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat` | text | NO |  |
| 5 | `threshold` | integer | NO |  |
| 6 | `season` | text | NO |  |
| 7 | `streak_games` | integer | NO |  |
| 8 | `start_game_id` | bigint | NO |  |
| 9 | `end_game_id` | bigint | NO |  |
| 10 | `start_date` | date | NO |  |
| 11 | `end_date` | date | NO |  |
| 12 | `is_active` | boolean | NO | true |
| 13 | `streak_kind` | text | NO |  |
| 14 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17053_10_not_null` | CHECK |  |  |
| `2200_17053_11_not_null` | CHECK |  |  |
| `2200_17053_12_not_null` | CHECK |  |  |
| `2200_17053_13_not_null` | CHECK |  |  |
| `2200_17053_14_not_null` | CHECK |  |  |
| `2200_17053_1_not_null` | CHECK |  |  |
| `2200_17053_2_not_null` | CHECK |  |  |
| `2200_17053_3_not_null` | CHECK |  |  |
| `2200_17053_4_not_null` | CHECK |  |  |
| `2200_17053_5_not_null` | CHECK |  |  |
| `2200_17053_6_not_null` | CHECK |  |  |
| `2200_17053_7_not_null` | CHECK |  |  |
| `2200_17053_8_not_null` | CHECK |  |  |
| `2200_17053_9_not_null` | CHECK |  |  |
| `player_consecutive_streaks_pkey` | PRIMARY KEY | id |  |
| `player_consecutive_streaks_unique` | UNIQUE | player_id, player_id, player_id, player_id, player_id, stat, stat, stat, stat, stat, threshold, threshold, threshold, threshold, threshold, season, season, season, season, season, streak_kind, streak_kind, streak_kind, streak_kind, streak_kind |  |

#### Indexes

- `idx_consecutive_streaks_active`: `CREATE INDEX idx_consecutive_streaks_active ON public.player_consecutive_streaks USING btree (is_active)`
- `idx_consecutive_streaks_kind`: `CREATE INDEX idx_consecutive_streaks_kind ON public.player_consecutive_streaks USING btree (streak_kind)`
- `idx_consecutive_streaks_player_id`: `CREATE INDEX idx_consecutive_streaks_player_id ON public.player_consecutive_streaks USING btree (player_id)`
- `idx_consecutive_streaks_season`: `CREATE INDEX idx_consecutive_streaks_season ON public.player_consecutive_streaks USING btree (season)`
- `idx_consecutive_streaks_stat`: `CREATE INDEX idx_consecutive_streaks_stat ON public.player_consecutive_streaks USING btree (stat)`
- `player_consecutive_streaks_pkey`: `CREATE UNIQUE INDEX player_consecutive_streaks_pkey ON public.player_consecutive_streaks USING btree (id)`
- `player_consecutive_streaks_unique`: `CREATE UNIQUE INDEX player_consecutive_streaks_unique ON public.player_consecutive_streaks USING btree (player_id, stat, threshold, season, streak_kind)`

### `player_consistency`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('player_consistency_id_seq'::regclass) |
| 2 | `player_id` | integer | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `season` | text | NO |  |
| 5 | `stat_name` | text | NO |  |
| 6 | `window_size` | integer | NO | 0 |
| 7 | `games_played` | integer | NO |  |
| 8 | `mean` | double precision | NO |  |
| 9 | `stddev` | double precision | NO |  |
| 10 | `cv` | double precision | NO |  |
| 11 | `min_val` | double precision | YES |  |
| 12 | `max_val` | double precision | YES |  |
| 13 | `median` | double precision | YES |  |
| 14 | `consistency_tier` | text | YES |  |
| 15 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17061_10_not_null` | CHECK |  |  |
| `2200_17061_15_not_null` | CHECK |  |  |
| `2200_17061_1_not_null` | CHECK |  |  |
| `2200_17061_2_not_null` | CHECK |  |  |
| `2200_17061_3_not_null` | CHECK |  |  |
| `2200_17061_4_not_null` | CHECK |  |  |
| `2200_17061_5_not_null` | CHECK |  |  |
| `2200_17061_6_not_null` | CHECK |  |  |
| `2200_17061_7_not_null` | CHECK |  |  |
| `2200_17061_8_not_null` | CHECK |  |  |
| `2200_17061_9_not_null` | CHECK |  |  |
| `player_consistency_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `player_consistency_pkey` | PRIMARY KEY | id |  |
| `player_consistency_unique` | UNIQUE | player_id, player_id, player_id, player_id, season, season, season, season, stat_name, stat_name, stat_name, stat_name, window_size, window_size, window_size, window_size |  |

#### Indexes

- `idx_player_consistency_cv`: `CREATE INDEX idx_player_consistency_cv ON public.player_consistency USING btree (cv)`
- `idx_player_consistency_player_id`: `CREATE INDEX idx_player_consistency_player_id ON public.player_consistency USING btree (player_id)`
- `idx_player_consistency_season`: `CREATE INDEX idx_player_consistency_season ON public.player_consistency USING btree (season)`
- `idx_player_consistency_stat_name`: `CREATE INDEX idx_player_consistency_stat_name ON public.player_consistency USING btree (stat_name)`
- `idx_player_consistency_tier`: `CREATE INDEX idx_player_consistency_tier ON public.player_consistency USING btree (consistency_tier)`
- `player_consistency_pkey`: `CREATE UNIQUE INDEX player_consistency_pkey ON public.player_consistency USING btree (id)`
- `player_consistency_unique`: `CREATE UNIQUE INDEX player_consistency_unique ON public.player_consistency USING btree (player_id, season, stat_name, window_size)`

### `player_consistency_snapshots`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | bigint | NO | nextval('player_consistency_snapshots_id_seq'::regclass) |
| 2 | `player_id` | bigint | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat_name` | character varying(16) | NO |  |
| 5 | `window_size` | integer | NO |  |
| 6 | `games_played` | integer | NO |  |
| 7 | `mean` | double precision | NO |  |
| 8 | `stddev` | double precision | NO |  |
| 9 | `cv` | double precision | NO |  |
| 10 | `min_val` | double precision | NO |  |
| 11 | `max_val` | double precision | NO |  |
| 12 | `median` | double precision | NO |  |
| 13 | `consistency_tier` | character varying(16) | NO |  |
| 14 | `season` | character varying(7) | NO |  |
| 15 | `season_type` | character varying(32) | NO |  |
| 16 | `feature_as_of` | timestamp with time zone | NO |  |
| 17 | `data_available_at` | timestamp with time zone | NO |  |
| 18 | `calculation_version` | character varying(64) | NO |  |
| 19 | `source_run_id` | character varying(36) | NO |  |
| 20 | `completeness_status` | character varying(16) | NO |  |
| 21 | `missing_input_flags` | jsonb | NO | '{}'::jsonb |
| 22 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17069_10_not_null` | CHECK |  |  |
| `2200_17069_11_not_null` | CHECK |  |  |
| `2200_17069_12_not_null` | CHECK |  |  |
| `2200_17069_13_not_null` | CHECK |  |  |
| `2200_17069_14_not_null` | CHECK |  |  |
| `2200_17069_15_not_null` | CHECK |  |  |
| `2200_17069_16_not_null` | CHECK |  |  |
| `2200_17069_17_not_null` | CHECK |  |  |
| `2200_17069_18_not_null` | CHECK |  |  |
| `2200_17069_19_not_null` | CHECK |  |  |
| `2200_17069_1_not_null` | CHECK |  |  |
| `2200_17069_20_not_null` | CHECK |  |  |
| `2200_17069_21_not_null` | CHECK |  |  |
| `2200_17069_22_not_null` | CHECK |  |  |
| `2200_17069_2_not_null` | CHECK |  |  |
| `2200_17069_3_not_null` | CHECK |  |  |
| `2200_17069_4_not_null` | CHECK |  |  |
| `2200_17069_5_not_null` | CHECK |  |  |
| `2200_17069_6_not_null` | CHECK |  |  |
| `2200_17069_7_not_null` | CHECK |  |  |
| `2200_17069_8_not_null` | CHECK |  |  |
| `2200_17069_9_not_null` | CHECK |  |  |
| `ck_player_consistency_snapshot_completeness` | CHECK |  |  |
| `player_consistency_snapshots_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `player_consistency_snapshots_source_run_id_fkey` | FOREIGN KEY | source_run_id | `ingestion_runs` (run_id) |
| `player_consistency_snapshots_pkey` | PRIMARY KEY | id |  |
| `uq_player_consistency_snapshot_natural_key` | UNIQUE | player_id, player_id, player_id, player_id, player_id, player_id, player_id, season, season, season, season, season, season, season, season_type, season_type, season_type, season_type, season_type, season_type, season_type, stat_name, stat_name, stat_name, stat_name, stat_name, stat_name, stat_name, window_size, window_size, window_size, window_size, window_size, window_size, window_size, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version |  |

#### Indexes

- `idx_player_consistency_snapshot_latest`: `CREATE INDEX idx_player_consistency_snapshot_latest ON public.player_consistency_snapshots USING btree (season, season_type, calculation_version, completeness_status, feature_as_of)`
- `idx_player_consistency_snapshot_player`: `CREATE INDEX idx_player_consistency_snapshot_player ON public.player_consistency_snapshots USING btree (player_id, feature_as_of)`
- `player_consistency_snapshots_pkey`: `CREATE UNIQUE INDEX player_consistency_snapshots_pkey ON public.player_consistency_snapshots USING btree (id)`
- `uq_player_consistency_snapshot_natural_key`: `CREATE UNIQUE INDEX uq_player_consistency_snapshot_natural_key ON public.player_consistency_snapshots USING btree (player_id, season, season_type, stat_name, window_size, feature_as_of, calculation_version)`

### `player_game_status`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('player_game_status_id_seq'::regclass) |
| 2 | `game_id` | character varying(20) | NO |  |
| 3 | `player_id` | integer | NO |  |
| 4 | `team_id` | integer | NO |  |
| 5 | `game_date` | date | NO |  |
| 6 | `season` | text | NO |  |
| 7 | `status` | character varying(20) | YES |  |
| 8 | `not_playing_reason` | character varying(50) | YES |  |
| 9 | `not_playing_description` | text | YES |  |
| 10 | `played` | boolean | NO | false |
| 11 | `player_name` | text | YES |  |
| 12 | `recorded_at` | timestamp with time zone | NO | now() |
| 13 | `updated_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17078_10_not_null` | CHECK |  |  |
| `2200_17078_12_not_null` | CHECK |  |  |
| `2200_17078_13_not_null` | CHECK |  |  |
| `2200_17078_1_not_null` | CHECK |  |  |
| `2200_17078_2_not_null` | CHECK |  |  |
| `2200_17078_3_not_null` | CHECK |  |  |
| `2200_17078_4_not_null` | CHECK |  |  |
| `2200_17078_5_not_null` | CHECK |  |  |
| `2200_17078_6_not_null` | CHECK |  |  |
| `player_game_status_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `player_game_status_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `player_game_status_pkey` | PRIMARY KEY | id |  |
| `player_game_status_unique` | UNIQUE | game_id, game_id, player_id, player_id |  |

#### Indexes

- `idx_player_game_status_game_date`: `CREATE INDEX idx_player_game_status_game_date ON public.player_game_status USING btree (game_date)`
- `idx_player_game_status_game_id`: `CREATE INDEX idx_player_game_status_game_id ON public.player_game_status USING btree (game_id)`
- `idx_player_game_status_player_id`: `CREATE INDEX idx_player_game_status_player_id ON public.player_game_status USING btree (player_id)`
- `idx_player_game_status_reason`: `CREATE INDEX idx_player_game_status_reason ON public.player_game_status USING btree (not_playing_reason)`
- `idx_player_game_status_season`: `CREATE INDEX idx_player_game_status_season ON public.player_game_status USING btree (season)`
- `idx_player_game_status_team_id`: `CREATE INDEX idx_player_game_status_team_id ON public.player_game_status USING btree (team_id)`
- `player_game_status_pkey`: `CREATE UNIQUE INDEX player_game_status_pkey ON public.player_game_status USING btree (id)`
- `player_game_status_unique`: `CREATE UNIQUE INDEX player_game_status_unique ON public.player_game_status USING btree (game_id, player_id)`

### `player_heat_index`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('player_heat_index_id_seq'::regclass) |
| 2 | `player_id` | integer | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat` | text | NO |  |
| 5 | `season` | text | NO |  |
| 6 | `window_size` | integer | NO |  |
| 7 | `season_avg` | double precision | NO |  |
| 8 | `season_std` | double precision | NO |  |
| 9 | `recent_avg` | double precision | NO |  |
| 10 | `z_score` | double precision | NO |  |
| 11 | `status` | text | NO |  |
| 12 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17087_10_not_null` | CHECK |  |  |
| `2200_17087_11_not_null` | CHECK |  |  |
| `2200_17087_12_not_null` | CHECK |  |  |
| `2200_17087_1_not_null` | CHECK |  |  |
| `2200_17087_2_not_null` | CHECK |  |  |
| `2200_17087_3_not_null` | CHECK |  |  |
| `2200_17087_4_not_null` | CHECK |  |  |
| `2200_17087_5_not_null` | CHECK |  |  |
| `2200_17087_6_not_null` | CHECK |  |  |
| `2200_17087_7_not_null` | CHECK |  |  |
| `2200_17087_8_not_null` | CHECK |  |  |
| `2200_17087_9_not_null` | CHECK |  |  |
| `player_heat_index_pkey` | PRIMARY KEY | id |  |
| `player_heat_index_unique` | UNIQUE | player_id, player_id, player_id, player_id, stat, stat, stat, stat, season, season, season, season, window_size, window_size, window_size, window_size |  |

#### Indexes

- `idx_heat_index_player_id`: `CREATE INDEX idx_heat_index_player_id ON public.player_heat_index USING btree (player_id)`
- `idx_heat_index_season`: `CREATE INDEX idx_heat_index_season ON public.player_heat_index USING btree (season)`
- `idx_heat_index_stat`: `CREATE INDEX idx_heat_index_stat ON public.player_heat_index USING btree (stat)`
- `idx_heat_index_status`: `CREATE INDEX idx_heat_index_status ON public.player_heat_index USING btree (status)`
- `idx_heat_index_window_size`: `CREATE INDEX idx_heat_index_window_size ON public.player_heat_index USING btree (window_size)`
- `idx_heat_index_z_score`: `CREATE INDEX idx_heat_index_z_score ON public.player_heat_index USING btree (z_score)`
- `player_heat_index_pkey`: `CREATE UNIQUE INDEX player_heat_index_pkey ON public.player_heat_index USING btree (id)`
- `player_heat_index_unique`: `CREATE UNIQUE INDEX player_heat_index_unique ON public.player_heat_index USING btree (player_id, stat, season, window_size)`

### `player_heat_index_snapshots`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | bigint | NO | nextval('player_heat_index_snapshots_id_seq'::regclass) |
| 2 | `player_id` | bigint | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat` | character varying(16) | NO |  |
| 5 | `window_size` | integer | NO |  |
| 6 | `games_played` | integer | NO |  |
| 7 | `recent_games_played` | integer | NO |  |
| 8 | `season_avg` | double precision | NO |  |
| 9 | `season_std` | double precision | NO |  |
| 10 | `recent_avg` | double precision | NO |  |
| 11 | `z_score` | double precision | NO |  |
| 12 | `status` | character varying(16) | NO |  |
| 13 | `season` | character varying(7) | NO |  |
| 14 | `season_type` | character varying(32) | NO |  |
| 15 | `feature_as_of` | timestamp with time zone | NO |  |
| 16 | `data_available_at` | timestamp with time zone | NO |  |
| 17 | `calculation_version` | character varying(64) | NO |  |
| 18 | `source_run_id` | character varying(36) | NO |  |
| 19 | `completeness_status` | character varying(16) | NO |  |
| 20 | `missing_input_flags` | jsonb | NO | '{}'::jsonb |
| 21 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17094_10_not_null` | CHECK |  |  |
| `2200_17094_11_not_null` | CHECK |  |  |
| `2200_17094_12_not_null` | CHECK |  |  |
| `2200_17094_13_not_null` | CHECK |  |  |
| `2200_17094_14_not_null` | CHECK |  |  |
| `2200_17094_15_not_null` | CHECK |  |  |
| `2200_17094_16_not_null` | CHECK |  |  |
| `2200_17094_17_not_null` | CHECK |  |  |
| `2200_17094_18_not_null` | CHECK |  |  |
| `2200_17094_19_not_null` | CHECK |  |  |
| `2200_17094_1_not_null` | CHECK |  |  |
| `2200_17094_20_not_null` | CHECK |  |  |
| `2200_17094_21_not_null` | CHECK |  |  |
| `2200_17094_2_not_null` | CHECK |  |  |
| `2200_17094_3_not_null` | CHECK |  |  |
| `2200_17094_4_not_null` | CHECK |  |  |
| `2200_17094_5_not_null` | CHECK |  |  |
| `2200_17094_6_not_null` | CHECK |  |  |
| `2200_17094_7_not_null` | CHECK |  |  |
| `2200_17094_8_not_null` | CHECK |  |  |
| `2200_17094_9_not_null` | CHECK |  |  |
| `ck_player_heat_snapshot_completeness` | CHECK |  |  |
| `player_heat_index_snapshots_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `player_heat_index_snapshots_source_run_id_fkey` | FOREIGN KEY | source_run_id | `ingestion_runs` (run_id) |
| `player_heat_index_snapshots_pkey` | PRIMARY KEY | id |  |
| `uq_player_heat_snapshot_natural_key` | UNIQUE | player_id, player_id, player_id, player_id, player_id, player_id, player_id, stat, stat, stat, stat, stat, stat, stat, season, season, season, season, season, season, season, season_type, season_type, season_type, season_type, season_type, season_type, season_type, window_size, window_size, window_size, window_size, window_size, window_size, window_size, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version |  |

#### Indexes

- `idx_player_heat_snapshot_latest`: `CREATE INDEX idx_player_heat_snapshot_latest ON public.player_heat_index_snapshots USING btree (season, season_type, calculation_version, completeness_status, feature_as_of)`
- `idx_player_heat_snapshot_player`: `CREATE INDEX idx_player_heat_snapshot_player ON public.player_heat_index_snapshots USING btree (player_id, feature_as_of)`
- `player_heat_index_snapshots_pkey`: `CREATE UNIQUE INDEX player_heat_index_snapshots_pkey ON public.player_heat_index_snapshots USING btree (id)`
- `uq_player_heat_snapshot_natural_key`: `CREATE UNIQUE INDEX uq_player_heat_snapshot_natural_key ON public.player_heat_index_snapshots USING btree (player_id, stat, season, season_type, window_size, feature_as_of, calculation_version)`

### `player_stat_window_snapshots`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | bigint | NO | nextval('player_stat_window_snapshots_id_seq'::regclass) |
| 2 | `player_id` | bigint | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat` | character varying(16) | NO |  |
| 5 | `threshold` | integer | NO |  |
| 6 | `window_size` | integer | NO |  |
| 7 | `games_played` | integer | NO |  |
| 8 | `games_hit` | integer | NO |  |
| 9 | `last_game_id` | character varying | NO |  |
| 10 | `last_game_date` | date | NO |  |
| 11 | `season` | character varying(7) | NO |  |
| 12 | `season_type` | character varying(32) | NO |  |
| 13 | `feature_as_of` | timestamp with time zone | NO |  |
| 14 | `data_available_at` | timestamp with time zone | NO |  |
| 15 | `calculation_version` | character varying(64) | NO |  |
| 16 | `source_run_id` | character varying(36) | NO |  |
| 17 | `completeness_status` | character varying(16) | NO |  |
| 18 | `missing_input_flags` | jsonb | NO | '{}'::jsonb |
| 19 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17103_10_not_null` | CHECK |  |  |
| `2200_17103_11_not_null` | CHECK |  |  |
| `2200_17103_12_not_null` | CHECK |  |  |
| `2200_17103_13_not_null` | CHECK |  |  |
| `2200_17103_14_not_null` | CHECK |  |  |
| `2200_17103_15_not_null` | CHECK |  |  |
| `2200_17103_16_not_null` | CHECK |  |  |
| `2200_17103_17_not_null` | CHECK |  |  |
| `2200_17103_18_not_null` | CHECK |  |  |
| `2200_17103_19_not_null` | CHECK |  |  |
| `2200_17103_1_not_null` | CHECK |  |  |
| `2200_17103_2_not_null` | CHECK |  |  |
| `2200_17103_3_not_null` | CHECK |  |  |
| `2200_17103_4_not_null` | CHECK |  |  |
| `2200_17103_5_not_null` | CHECK |  |  |
| `2200_17103_6_not_null` | CHECK |  |  |
| `2200_17103_7_not_null` | CHECK |  |  |
| `2200_17103_8_not_null` | CHECK |  |  |
| `2200_17103_9_not_null` | CHECK |  |  |
| `ck_player_window_hits_lte_games` | CHECK |  |  |
| `ck_player_window_snapshot_completeness` | CHECK |  |  |
| `player_stat_window_snapshots_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `player_stat_window_snapshots_source_run_id_fkey` | FOREIGN KEY | source_run_id | `ingestion_runs` (run_id) |
| `player_stat_window_snapshots_pkey` | PRIMARY KEY | id |  |
| `uq_player_window_snapshot_natural_key` | UNIQUE | player_id, player_id, player_id, player_id, player_id, player_id, player_id, player_id, stat, stat, stat, stat, stat, stat, stat, stat, threshold, threshold, threshold, threshold, threshold, threshold, threshold, threshold, season, season, season, season, season, season, season, season, season_type, season_type, season_type, season_type, season_type, season_type, season_type, season_type, window_size, window_size, window_size, window_size, window_size, window_size, window_size, window_size, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version |  |

#### Indexes

- `idx_player_window_snapshot_latest`: `CREATE INDEX idx_player_window_snapshot_latest ON public.player_stat_window_snapshots USING btree (season, season_type, calculation_version, completeness_status, feature_as_of)`
- `idx_player_window_snapshot_player`: `CREATE INDEX idx_player_window_snapshot_player ON public.player_stat_window_snapshots USING btree (player_id, feature_as_of)`
- `player_stat_window_snapshots_pkey`: `CREATE UNIQUE INDEX player_stat_window_snapshots_pkey ON public.player_stat_window_snapshots USING btree (id)`
- `uq_player_window_snapshot_natural_key`: `CREATE UNIQUE INDEX uq_player_window_snapshot_natural_key ON public.player_stat_window_snapshots USING btree (player_id, stat, threshold, season, season_type, window_size, feature_as_of, calculation_version)`

### `player_stat_windows`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('player_stat_windows_id_seq'::regclass) |
| 2 | `player_id` | integer | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat` | text | NO |  |
| 5 | `threshold` | integer | NO |  |
| 6 | `season` | text | NO |  |
| 7 | `window_size` | integer | NO |  |
| 8 | `games_played` | integer | NO |  |
| 9 | `games_hit` | integer | NO |  |
| 10 | `last_game_id` | bigint | NO |  |
| 11 | `last_game_date` | date | NO |  |
| 12 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17113_10_not_null` | CHECK |  |  |
| `2200_17113_11_not_null` | CHECK |  |  |
| `2200_17113_12_not_null` | CHECK |  |  |
| `2200_17113_1_not_null` | CHECK |  |  |
| `2200_17113_2_not_null` | CHECK |  |  |
| `2200_17113_3_not_null` | CHECK |  |  |
| `2200_17113_4_not_null` | CHECK |  |  |
| `2200_17113_5_not_null` | CHECK |  |  |
| `2200_17113_6_not_null` | CHECK |  |  |
| `2200_17113_7_not_null` | CHECK |  |  |
| `2200_17113_8_not_null` | CHECK |  |  |
| `2200_17113_9_not_null` | CHECK |  |  |
| `player_stat_windows_pkey` | PRIMARY KEY | id |  |
| `player_stat_windows_unique` | UNIQUE | player_id, player_id, player_id, player_id, player_id, stat, stat, stat, stat, stat, threshold, threshold, threshold, threshold, threshold, season, season, season, season, season, window_size, window_size, window_size, window_size, window_size |  |

#### Indexes

- `idx_stat_windows_player_id`: `CREATE INDEX idx_stat_windows_player_id ON public.player_stat_windows USING btree (player_id)`
- `idx_stat_windows_season`: `CREATE INDEX idx_stat_windows_season ON public.player_stat_windows USING btree (season)`
- `idx_stat_windows_stat`: `CREATE INDEX idx_stat_windows_stat ON public.player_stat_windows USING btree (stat)`
- `idx_stat_windows_window_size`: `CREATE INDEX idx_stat_windows_window_size ON public.player_stat_windows USING btree (window_size)`
- `player_stat_windows_pkey`: `CREATE UNIQUE INDEX player_stat_windows_pkey ON public.player_stat_windows USING btree (id)`
- `player_stat_windows_unique`: `CREATE UNIQUE INDEX player_stat_windows_unique ON public.player_stat_windows USING btree (player_id, stat, threshold, season, window_size)`

### `player_streaks`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('player_streaks_id_seq'::regclass) |
| 2 | `player_id` | integer | NO |  |
| 3 | `player_name` | text | NO |  |
| 4 | `stat` | text | NO |  |
| 5 | `threshold` | integer | NO |  |
| 6 | `streak_games` | integer | NO |  |
| 7 | `season` | text | NO |  |
| 8 | `created_at` | timestamp without time zone | NO |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17120_1_not_null` | CHECK |  |  |
| `2200_17120_2_not_null` | CHECK |  |  |
| `2200_17120_3_not_null` | CHECK |  |  |
| `2200_17120_4_not_null` | CHECK |  |  |
| `2200_17120_5_not_null` | CHECK |  |  |
| `2200_17120_6_not_null` | CHECK |  |  |
| `2200_17120_7_not_null` | CHECK |  |  |
| `2200_17120_8_not_null` | CHECK |  |  |
| `player_streaks_pkey` | PRIMARY KEY | id |  |
| `player_streaks_player_id_stat_season_threshold_key` | UNIQUE | player_id, player_id, player_id, player_id, stat, stat, stat, stat, season, season, season, season, threshold, threshold, threshold, threshold |  |

#### Indexes

- `idx_player_streaks_player_id`: `CREATE INDEX idx_player_streaks_player_id ON public.player_streaks USING btree (player_id)`
- `idx_player_streaks_season`: `CREATE INDEX idx_player_streaks_season ON public.player_streaks USING btree (season)`
- `idx_player_streaks_stat`: `CREATE INDEX idx_player_streaks_stat ON public.player_streaks USING btree (stat)`
- `player_streaks_pkey`: `CREATE UNIQUE INDEX player_streaks_pkey ON public.player_streaks USING btree (id)`
- `player_streaks_player_id_stat_season_threshold_key`: `CREATE UNIQUE INDEX player_streaks_player_id_stat_season_threshold_key ON public.player_streaks USING btree (player_id, stat, season, threshold)`

### `player_z_scores`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `player_id` | integer | NO |  |
| 2 | `pts_z_score` | double precision | YES |  |
| 3 | `reb_z_score` | double precision | YES |  |
| 4 | `ast_z_score` | double precision | YES |  |
| 5 | `stl_z_score` | double precision | YES |  |
| 6 | `blk_z_score` | double precision | YES |  |
| 7 | `tov_z_score` | double precision | YES |  |
| 8 | `fg3m_z_score` | double precision | YES |  |
| 9 | `dd2_z_score` | double precision | YES |  |
| 10 | `fg_pct_z_score` | double precision | YES |  |
| 11 | `ft_pct_z_score` | double precision | YES |  |
| 12 | `fg3_pct_z_score` | double precision | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17126_1_not_null` | CHECK |  |  |
| `player_z_scores_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `player_z_scores_pkey` | PRIMARY KEY | player_id |  |

#### Indexes

- `idx_player_z_scores_player_id`: `CREATE INDEX idx_player_z_scores_player_id ON public.player_z_scores USING btree (player_id)`
- `player_z_scores_pkey`: `CREATE UNIQUE INDEX player_z_scores_pkey ON public.player_z_scores USING btree (player_id)`

### `players`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `player_id` | integer | NO |  |
| 2 | `name` | character varying(255) | NO |  |
| 3 | `position` | character varying(50) | YES |  |
| 4 | `weight` | integer | YES |  |
| 5 | `born_date` | date | YES |  |
| 6 | `age` | integer | YES |  |
| 7 | `exp` | integer | YES |  |
| 8 | `school` | character varying(255) | YES |  |
| 9 | `available_seasons` | ARRAY | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17129_1_not_null` | CHECK |  |  |
| `2200_17129_2_not_null` | CHECK |  |  |
| `players_pkey` | PRIMARY KEY | player_id |  |

#### Indexes

- `idx_players_name`: `CREATE INDEX idx_players_name ON public.players USING btree (name)`
- `idx_players_position`: `CREATE INDEX idx_players_position ON public.players USING btree ("position")`
- `idx_players_seasons`: `CREATE INDEX idx_players_seasons ON public.players USING gin (available_seasons)`
- `player_id_idx`: `CREATE INDEX player_id_idx ON public.players USING btree (player_id)`
- `player_name_idx`: `CREATE INDEX player_name_idx ON public.players USING btree (name)`
- `players_pkey`: `CREATE UNIQUE INDEX players_pkey ON public.players USING btree (player_id)`

### `roster`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `team_id` | integer | NO |  |
| 2 | `player_id` | integer | NO |  |
| 3 | `player_name` | character varying(255) | YES |  |
| 4 | `player_number` | integer | YES |  |
| 5 | `position` | character varying(50) | YES |  |
| 6 | `how_acquired` | character varying(255) | YES |  |
| 7 | `season` | character varying(10) | NO |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17134_1_not_null` | CHECK |  |  |
| `2200_17134_2_not_null` | CHECK |  |  |
| `2200_17134_7_not_null` | CHECK |  |  |
| `ck_roster_season_canonical` | CHECK |  |  |
| `roster_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `roster_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `roster_pkey` | PRIMARY KEY | team_id, team_id, team_id, player_id, player_id, player_id, season, season, season |  |

#### Indexes

- `roster_pkey`: `CREATE UNIQUE INDEX roster_pkey ON public.roster USING btree (team_id, player_id, season)`

### `statistics`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `stat_id` | integer | NO | nextval('statistics_stat_id_seq'::regclass) |
| 2 | `player_id` | integer | NO |  |
| 3 | `season_year` | character varying(10) | YES |  |
| 4 | `points` | integer | YES |  |
| 5 | `rebounds` | integer | YES |  |
| 6 | `assists` | integer | YES |  |
| 7 | `steals` | integer | YES |  |
| 8 | `blocks` | integer | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17139_1_not_null` | CHECK |  |  |
| `2200_17139_2_not_null` | CHECK |  |  |
| `statistics_player_id_fkey` | FOREIGN KEY | player_id | `players` (player_id) |
| `statistics_pkey` | PRIMARY KEY | stat_id |  |

#### Indexes

- `idx_statistics_assists`: `CREATE INDEX idx_statistics_assists ON public.statistics USING btree (assists)`
- `idx_statistics_player_id`: `CREATE INDEX idx_statistics_player_id ON public.statistics USING btree (player_id)`
- `idx_statistics_player_season`: `CREATE INDEX idx_statistics_player_season ON public.statistics USING btree (player_id, season_year)`
- `idx_statistics_player_season_year`: `CREATE INDEX idx_statistics_player_season_year ON public.statistics USING btree (player_id, season_year)`
- `idx_statistics_points`: `CREATE INDEX idx_statistics_points ON public.statistics USING btree (points)`
- `idx_statistics_rebounds`: `CREATE INDEX idx_statistics_rebounds ON public.statistics USING btree (rebounds)`
- `idx_statistics_season`: `CREATE INDEX idx_statistics_season ON public.statistics USING btree (season_year)`
- `idx_statistics_season_year`: `CREATE INDEX idx_statistics_season_year ON public.statistics USING btree (season_year)`
- `statistics_pkey`: `CREATE UNIQUE INDEX statistics_pkey ON public.statistics USING btree (stat_id)`
- `stats_player_season_idx`: `CREATE INDEX stats_player_season_idx ON public.statistics USING btree (player_id, season_year)`
- `stats_season_idx`: `CREATE INDEX stats_season_idx ON public.statistics USING btree (season_year)`

### `team_daily_flags`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('team_daily_flags_id_seq'::regclass) |
| 2 | `stat_date` | date | NO |  |
| 3 | `season` | text | NO |  |
| 4 | `team_id` | integer | NO |  |
| 5 | `team_name` | text | NO |  |
| 6 | `flag_type` | text | NO |  |
| 7 | `severity` | double precision | YES |  |
| 8 | `details_json` | jsonb | YES |  |
| 9 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17143_1_not_null` | CHECK |  |  |
| `2200_17143_2_not_null` | CHECK |  |  |
| `2200_17143_3_not_null` | CHECK |  |  |
| `2200_17143_4_not_null` | CHECK |  |  |
| `2200_17143_5_not_null` | CHECK |  |  |
| `2200_17143_6_not_null` | CHECK |  |  |
| `2200_17143_9_not_null` | CHECK |  |  |
| `team_daily_flags_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `team_daily_flags_pkey` | PRIMARY KEY | id |  |
| `team_daily_flags_unique` | UNIQUE | stat_date, stat_date, stat_date, team_id, team_id, team_id, flag_type, flag_type, flag_type |  |

#### Indexes

- `idx_team_daily_flags_flag_type`: `CREATE INDEX idx_team_daily_flags_flag_type ON public.team_daily_flags USING btree (flag_type)`
- `idx_team_daily_flags_season`: `CREATE INDEX idx_team_daily_flags_season ON public.team_daily_flags USING btree (season)`
- `idx_team_daily_flags_stat_date`: `CREATE INDEX idx_team_daily_flags_stat_date ON public.team_daily_flags USING btree (stat_date)`
- `idx_team_daily_flags_team_id`: `CREATE INDEX idx_team_daily_flags_team_id ON public.team_daily_flags USING btree (team_id)`
- `team_daily_flags_pkey`: `CREATE UNIQUE INDEX team_daily_flags_pkey ON public.team_daily_flags USING btree (id)`
- `team_daily_flags_unique`: `CREATE UNIQUE INDEX team_daily_flags_unique ON public.team_daily_flags USING btree (stat_date, team_id, flag_type)`

### `team_daily_metrics`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('team_daily_metrics_id_seq'::regclass) |
| 2 | `stat_date` | date | NO |  |
| 3 | `season` | text | NO |  |
| 4 | `team_id` | integer | NO |  |
| 5 | `team_name` | text | NO |  |
| 6 | `window_size` | integer | NO | 10 |
| 7 | `off_rtg_season` | double precision | YES |  |
| 8 | `def_rtg_season` | double precision | YES |  |
| 9 | `net_rtg_season` | double precision | YES |  |
| 10 | `pace_season` | double precision | YES |  |
| 11 | `efg_season` | double precision | YES |  |
| 12 | `tov_pct_season` | double precision | YES |  |
| 13 | `orb_pct_season` | double precision | YES |  |
| 14 | `ftr_season` | double precision | YES |  |
| 15 | `pct_pts_3pt_season` | double precision | YES |  |
| 16 | `pct_pts_paint_season` | double precision | YES |  |
| 17 | `pct_pts_mid_season` | double precision | YES |  |
| 18 | `pct_pts_ft_season` | double precision | YES |  |
| 19 | `pct_pts_fb_season` | double precision | YES |  |
| 20 | `pct_pts_off_tov_season` | double precision | YES |  |
| 21 | `sec_chance_pts_per100_season` | double precision | YES |  |
| 22 | `fb_pts_per100_season` | double precision | YES |  |
| 23 | `paint_pts_per100_season` | double precision | YES |  |
| 24 | `opp_sec_chance_pts_per100_season` | double precision | YES |  |
| 25 | `opp_fb_pts_per100_season` | double precision | YES |  |
| 26 | `opp_paint_pts_per100_season` | double precision | YES |  |
| 27 | `off_rtg_lastn` | double precision | YES |  |
| 28 | `def_rtg_lastn` | double precision | YES |  |
| 29 | `net_rtg_lastn` | double precision | YES |  |
| 30 | `pace_lastn` | double precision | YES |  |
| 31 | `efg_lastn` | double precision | YES |  |
| 32 | `tov_pct_lastn` | double precision | YES |  |
| 33 | `orb_pct_lastn` | double precision | YES |  |
| 34 | `ftr_lastn` | double precision | YES |  |
| 35 | `pct_pts_3pt_lastn` | double precision | YES |  |
| 36 | `pct_pts_paint_lastn` | double precision | YES |  |
| 37 | `pct_pts_mid_lastn` | double precision | YES |  |
| 38 | `pct_pts_ft_lastn` | double precision | YES |  |
| 39 | `pct_pts_fb_lastn` | double precision | YES |  |
| 40 | `pct_pts_off_tov_lastn` | double precision | YES |  |
| 41 | `sec_chance_pts_per100_lastn` | double precision | YES |  |
| 42 | `fb_pts_per100_lastn` | double precision | YES |  |
| 43 | `paint_pts_per100_lastn` | double precision | YES |  |
| 44 | `opp_sec_chance_pts_per100_lastn` | double precision | YES |  |
| 45 | `opp_fb_pts_per100_lastn` | double precision | YES |  |
| 46 | `opp_paint_pts_per100_lastn` | double precision | YES |  |
| 47 | `off_rtg_delta` | double precision | YES |  |
| 48 | `def_rtg_delta` | double precision | YES |  |
| 49 | `net_rtg_delta` | double precision | YES |  |
| 50 | `pace_delta` | double precision | YES |  |
| 51 | `efg_delta` | double precision | YES |  |
| 52 | `tov_pct_delta` | double precision | YES |  |
| 53 | `orb_pct_delta` | double precision | YES |  |
| 54 | `ftr_delta` | double precision | YES |  |
| 55 | `pct_pts_3pt_delta` | double precision | YES |  |
| 56 | `pct_pts_paint_delta` | double precision | YES |  |
| 57 | `pct_pts_mid_delta` | double precision | YES |  |
| 58 | `pct_pts_ft_delta` | double precision | YES |  |
| 59 | `pct_pts_fb_delta` | double precision | YES |  |
| 60 | `pct_pts_off_tov_delta` | double precision | YES |  |
| 61 | `sec_chance_pts_per100_delta` | double precision | YES |  |
| 62 | `fb_pts_per100_delta` | double precision | YES |  |
| 63 | `paint_pts_per100_delta` | double precision | YES |  |
| 64 | `opp_sec_chance_pts_per100_delta` | double precision | YES |  |
| 65 | `opp_fb_pts_per100_delta` | double precision | YES |  |
| 66 | `opp_paint_pts_per100_delta` | double precision | YES |  |
| 67 | `created_at` | timestamp with time zone | NO | now() |
| 68 | `sos_net_season` | double precision | YES |  |
| 69 | `sos_net_last10` | double precision | YES |  |
| 70 | `sos_net_delta` | double precision | YES |  |
| 71 | `sos_off_season` | double precision | YES |  |
| 72 | `sos_def_season` | double precision | YES |  |
| 73 | `sos_off_last10` | double precision | YES |  |
| 74 | `sos_def_last10` | double precision | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17150_1_not_null` | CHECK |  |  |
| `2200_17150_2_not_null` | CHECK |  |  |
| `2200_17150_3_not_null` | CHECK |  |  |
| `2200_17150_4_not_null` | CHECK |  |  |
| `2200_17150_5_not_null` | CHECK |  |  |
| `2200_17150_67_not_null` | CHECK |  |  |
| `2200_17150_6_not_null` | CHECK |  |  |
| `team_daily_metrics_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `team_daily_metrics_pkey` | PRIMARY KEY | id |  |
| `team_daily_metrics_unique` | UNIQUE | stat_date, stat_date, stat_date, team_id, team_id, team_id, window_size, window_size, window_size |  |

#### Indexes

- `idx_team_daily_metrics_season`: `CREATE INDEX idx_team_daily_metrics_season ON public.team_daily_metrics USING btree (season)`
- `idx_team_daily_metrics_stat_date`: `CREATE INDEX idx_team_daily_metrics_stat_date ON public.team_daily_metrics USING btree (stat_date)`
- `idx_team_daily_metrics_team_id`: `CREATE INDEX idx_team_daily_metrics_team_id ON public.team_daily_metrics USING btree (team_id)`
- `idx_team_daily_metrics_window_size`: `CREATE INDEX idx_team_daily_metrics_window_size ON public.team_daily_metrics USING btree (window_size)`
- `team_daily_metrics_pkey`: `CREATE UNIQUE INDEX team_daily_metrics_pkey ON public.team_daily_metrics USING btree (id)`
- `team_daily_metrics_unique`: `CREATE UNIQUE INDEX team_daily_metrics_unique ON public.team_daily_metrics USING btree (stat_date, team_id, window_size)`

### `team_game_feature_snapshots`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | bigint | NO | nextval('team_game_feature_snapshots_id_seq'::regclass) |
| 2 | `game_id` | character varying(20) | NO |  |
| 3 | `team_id` | integer | NO |  |
| 4 | `opponent_team_id` | integer | NO |  |
| 5 | `game_date` | date | NO |  |
| 6 | `scheduled_tipoff` | timestamp with time zone | NO |  |
| 7 | `is_home` | boolean | NO |  |
| 8 | `window_size` | integer | NO |  |
| 9 | `source_latest_game_id` | character varying(20) | YES |  |
| 10 | `source_latest_game_date` | date | YES |  |
| 11 | `season_games_played` | integer | NO |  |
| 12 | `season_games_used` | integer | NO |  |
| 13 | `window_games_played` | integer | NO |  |
| 14 | `window_games_used` | integer | NO |  |
| 15 | `off_rtg_season` | double precision | YES |  |
| 16 | `def_rtg_season` | double precision | YES |  |
| 17 | `net_rtg_season` | double precision | YES |  |
| 18 | `pace_season` | double precision | YES |  |
| 19 | `efg_season` | double precision | YES |  |
| 20 | `tov_pct_season` | double precision | YES |  |
| 21 | `orb_pct_season` | double precision | YES |  |
| 22 | `ftr_season` | double precision | YES |  |
| 23 | `pct_pts_3pt_season` | double precision | YES |  |
| 24 | `off_rtg_lastn` | double precision | YES |  |
| 25 | `def_rtg_lastn` | double precision | YES |  |
| 26 | `net_rtg_lastn` | double precision | YES |  |
| 27 | `pace_lastn` | double precision | YES |  |
| 28 | `efg_lastn` | double precision | YES |  |
| 29 | `tov_pct_lastn` | double precision | YES |  |
| 30 | `orb_pct_lastn` | double precision | YES |  |
| 31 | `ftr_lastn` | double precision | YES |  |
| 32 | `pct_pts_3pt_lastn` | double precision | YES |  |
| 33 | `off_rtg_delta` | double precision | YES |  |
| 34 | `def_rtg_delta` | double precision | YES |  |
| 35 | `net_rtg_delta` | double precision | YES |  |
| 36 | `pace_delta` | double precision | YES |  |
| 37 | `efg_delta` | double precision | YES |  |
| 38 | `tov_pct_delta` | double precision | YES |  |
| 39 | `orb_pct_delta` | double precision | YES |  |
| 40 | `ftr_delta` | double precision | YES |  |
| 41 | `pct_pts_3pt_delta` | double precision | YES |  |
| 42 | `sos_net_season` | double precision | YES |  |
| 43 | `sos_net_lastn` | double precision | YES |  |
| 44 | `sos_net_delta` | double precision | YES |  |
| 45 | `days_rest` | integer | YES |  |
| 46 | `is_b2b` | boolean | NO | false |
| 47 | `is_3_in_4` | boolean | NO | false |
| 48 | `is_4_in_5` | boolean | NO | false |
| 49 | `is_5_in_7` | boolean | NO | false |
| 50 | `games_last_4_days` | integer | NO | 0 |
| 51 | `games_last_7_days` | integer | NO | 0 |
| 52 | `flags` | jsonb | NO | '[]'::jsonb |
| 53 | `season` | character varying(7) | NO |  |
| 54 | `season_type` | character varying(32) | NO |  |
| 55 | `feature_as_of` | timestamp with time zone | NO |  |
| 56 | `data_available_at` | timestamp with time zone | YES |  |
| 57 | `calculation_version` | character varying(64) | NO |  |
| 58 | `source_run_id` | character varying(36) | NO |  |
| 59 | `completeness_status` | character varying(16) | NO |  |
| 60 | `missing_input_flags` | jsonb | NO | '{}'::jsonb |
| 61 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17823_11_not_null` | CHECK |  |  |
| `2200_17823_12_not_null` | CHECK |  |  |
| `2200_17823_13_not_null` | CHECK |  |  |
| `2200_17823_14_not_null` | CHECK |  |  |
| `2200_17823_1_not_null` | CHECK |  |  |
| `2200_17823_2_not_null` | CHECK |  |  |
| `2200_17823_3_not_null` | CHECK |  |  |
| `2200_17823_46_not_null` | CHECK |  |  |
| `2200_17823_47_not_null` | CHECK |  |  |
| `2200_17823_48_not_null` | CHECK |  |  |
| `2200_17823_49_not_null` | CHECK |  |  |
| `2200_17823_4_not_null` | CHECK |  |  |
| `2200_17823_50_not_null` | CHECK |  |  |
| `2200_17823_51_not_null` | CHECK |  |  |
| `2200_17823_52_not_null` | CHECK |  |  |
| `2200_17823_53_not_null` | CHECK |  |  |
| `2200_17823_54_not_null` | CHECK |  |  |
| `2200_17823_55_not_null` | CHECK |  |  |
| `2200_17823_57_not_null` | CHECK |  |  |
| `2200_17823_58_not_null` | CHECK |  |  |
| `2200_17823_59_not_null` | CHECK |  |  |
| `2200_17823_5_not_null` | CHECK |  |  |
| `2200_17823_60_not_null` | CHECK |  |  |
| `2200_17823_61_not_null` | CHECK |  |  |
| `2200_17823_6_not_null` | CHECK |  |  |
| `2200_17823_7_not_null` | CHECK |  |  |
| `2200_17823_8_not_null` | CHECK |  |  |
| `ck_team_feature_snapshot_completeness` | CHECK |  |  |
| `ck_team_feature_snapshot_used_lte_played` | CHECK |  |  |
| `ck_team_feature_snapshot_window_lte_season` | CHECK |  |  |
| `fk_team_feature_snapshot_schedule` | FOREIGN KEY | game_id, game_id, team_id, team_id | `game_schedule` (game_id, team_id) |
| `team_game_feature_snapshots_opponent_team_id_fkey` | FOREIGN KEY | opponent_team_id | `teams` (team_id) |
| `team_game_feature_snapshots_source_run_id_fkey` | FOREIGN KEY | source_run_id | `ingestion_runs` (run_id) |
| `team_game_feature_snapshots_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `team_game_feature_snapshots_pkey` | PRIMARY KEY | id |  |
| `uq_team_feature_snapshot_natural_key` | UNIQUE | game_id, game_id, game_id, game_id, game_id, team_id, team_id, team_id, team_id, team_id, window_size, window_size, window_size, window_size, window_size, feature_as_of, feature_as_of, feature_as_of, feature_as_of, feature_as_of, calculation_version, calculation_version, calculation_version, calculation_version, calculation_version |  |

#### Indexes

- `idx_team_feature_snapshot_latest`: `CREATE INDEX idx_team_feature_snapshot_latest ON public.team_game_feature_snapshots USING btree (season, season_type, calculation_version, completeness_status, feature_as_of)`
- `idx_team_feature_snapshot_team`: `CREATE INDEX idx_team_feature_snapshot_team ON public.team_game_feature_snapshots USING btree (team_id, feature_as_of)`
- `team_game_feature_snapshots_pkey`: `CREATE UNIQUE INDEX team_game_feature_snapshots_pkey ON public.team_game_feature_snapshots USING btree (id)`
- `uq_team_feature_snapshot_natural_key`: `CREATE UNIQUE INDEX uq_team_feature_snapshot_natural_key ON public.team_game_feature_snapshots USING btree (game_id, team_id, window_size, feature_as_of, calculation_version)`

### `team_game_stats`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `game_id` | character varying | NO |  |
| 2 | `team_id` | integer | NO |  |
| 3 | `opponent_team_id` | integer | NO |  |
| 4 | `season` | character varying(10) | NO |  |
| 5 | `fg` | integer | YES |  |
| 6 | `fga` | integer | YES |  |
| 7 | `fg_pct` | double precision | YES |  |
| 8 | `fg3` | integer | YES |  |
| 9 | `fg3a` | integer | YES |  |
| 10 | `fg3_pct` | double precision | YES |  |
| 11 | `ft` | integer | YES |  |
| 12 | `fta` | integer | YES |  |
| 13 | `ft_pct` | double precision | YES |  |
| 14 | `reb` | integer | YES |  |
| 15 | `ast` | integer | YES |  |
| 16 | `stl` | integer | YES |  |
| 17 | `blk` | integer | YES |  |
| 18 | `tov` | integer | YES |  |
| 19 | `pts` | integer | YES |  |
| 20 | `game_date` | date | NO |  |
| 21 | `oreb` | integer | YES |  |
| 22 | `dreb` | integer | YES |  |
| 23 | `pf` | integer | YES |  |
| 24 | `matchup` | character varying(50) | YES |  |
| 25 | `wl` | character varying(1) | YES |  |
| 26 | `w` | integer | YES |  |
| 27 | `l` | integer | YES |  |
| 28 | `w_pct` | double precision | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17158_1_not_null` | CHECK |  |  |
| `2200_17158_20_not_null` | CHECK |  |  |
| `2200_17158_2_not_null` | CHECK |  |  |
| `2200_17158_3_not_null` | CHECK |  |  |
| `2200_17158_4_not_null` | CHECK |  |  |
| `team_game_stats_opponent_team_id_fkey` | FOREIGN KEY | opponent_team_id | `teams` (team_id) |
| `team_game_stats_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `team_game_stats_pkey` | PRIMARY KEY | game_id, game_id, team_id, team_id |  |

#### Indexes

- `idx_team_game_stats_game_date`: `CREATE INDEX idx_team_game_stats_game_date ON public.team_game_stats USING btree (game_date)`
- `idx_team_game_stats_season`: `CREATE INDEX idx_team_game_stats_season ON public.team_game_stats USING btree (season)`
- `idx_team_game_stats_team_id`: `CREATE INDEX idx_team_game_stats_team_id ON public.team_game_stats USING btree (team_id)`
- `team_game_stats_pkey`: `CREATE UNIQUE INDEX team_game_stats_pkey ON public.team_game_stats USING btree (game_id, team_id)`

### `team_schedule_factors`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `id` | integer | NO | nextval('team_schedule_factors_id_seq'::regclass) |
| 2 | `game_id` | character varying | NO |  |
| 3 | `team_id` | integer | NO |  |
| 4 | `opponent_id` | integer | NO |  |
| 5 | `game_date` | date | NO |  |
| 6 | `season` | text | NO |  |
| 7 | `days_rest` | integer | YES |  |
| 8 | `is_b2b` | boolean | NO | false |
| 9 | `is_3_in_4` | boolean | NO | false |
| 10 | `is_4_in_5` | boolean | NO | false |
| 11 | `is_5_in_7` | boolean | NO | false |
| 12 | `games_last_4` | integer | YES |  |
| 13 | `games_last_7` | integer | YES |  |
| 14 | `opponent_days_rest` | integer | YES |  |
| 15 | `rest_edge` | text | YES |  |
| 16 | `rest_diff` | integer | YES |  |
| 17 | `created_at` | timestamp with time zone | NO | now() |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17163_10_not_null` | CHECK |  |  |
| `2200_17163_11_not_null` | CHECK |  |  |
| `2200_17163_17_not_null` | CHECK |  |  |
| `2200_17163_1_not_null` | CHECK |  |  |
| `2200_17163_2_not_null` | CHECK |  |  |
| `2200_17163_3_not_null` | CHECK |  |  |
| `2200_17163_4_not_null` | CHECK |  |  |
| `2200_17163_5_not_null` | CHECK |  |  |
| `2200_17163_6_not_null` | CHECK |  |  |
| `2200_17163_8_not_null` | CHECK |  |  |
| `2200_17163_9_not_null` | CHECK |  |  |
| `fk_team_schedule_factors_game_schedule` | FOREIGN KEY | game_id, game_id, team_id, team_id | `game_schedule` (game_id, team_id) |
| `team_schedule_factors_opponent_id_fkey` | FOREIGN KEY | opponent_id | `teams` (team_id) |
| `team_schedule_factors_team_id_fkey` | FOREIGN KEY | team_id | `teams` (team_id) |
| `team_schedule_factors_pkey` | PRIMARY KEY | id |  |
| `team_schedule_factors_unique` | UNIQUE | game_id, game_id, team_id, team_id |  |

#### Indexes

- `idx_team_schedule_factors_game_date`: `CREATE INDEX idx_team_schedule_factors_game_date ON public.team_schedule_factors USING btree (game_date)`
- `idx_team_schedule_factors_is_b2b`: `CREATE INDEX idx_team_schedule_factors_is_b2b ON public.team_schedule_factors USING btree (is_b2b)`
- `idx_team_schedule_factors_rest_edge`: `CREATE INDEX idx_team_schedule_factors_rest_edge ON public.team_schedule_factors USING btree (rest_edge)`
- `idx_team_schedule_factors_season`: `CREATE INDEX idx_team_schedule_factors_season ON public.team_schedule_factors USING btree (season)`
- `idx_team_schedule_factors_team_id`: `CREATE INDEX idx_team_schedule_factors_team_id ON public.team_schedule_factors USING btree (team_id)`
- `team_schedule_factors_pkey`: `CREATE UNIQUE INDEX team_schedule_factors_pkey ON public.team_schedule_factors USING btree (id)`
- `team_schedule_factors_unique`: `CREATE UNIQUE INDEX team_schedule_factors_unique ON public.team_schedule_factors USING btree (game_id, team_id)`

### `teams`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `team_id` | integer | NO | nextval('teams_team_id_seq'::regclass) |
| 2 | `name` | character varying(255) | YES |  |
| 3 | `abbreviation` | character varying(10) | YES |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17174_1_not_null` | CHECK |  |  |
| `teams_pkey` | PRIMARY KEY | team_id |  |

#### Indexes

- `teams_pkey`: `CREATE UNIQUE INDEX teams_pkey ON public.teams USING btree (team_id)`

### `users`

#### Columns

| # | Column | Type | Nullable | Default |
| ---: | --- | --- | --- | --- |
| 1 | `user_id` | integer | NO | nextval('users_user_id_seq'::regclass) |
| 2 | `username` | character varying(50) | NO |  |
| 3 | `email` | character varying(255) | NO |  |
| 4 | `password_hash` | character varying(255) | NO |  |
| 5 | `created_at` | timestamp without time zone | NO |  |
| 6 | `last_login` | timestamp without time zone | YES |  |
| 7 | `is_active` | boolean | NO |  |
| 8 | `is_admin` | boolean | NO |  |

#### Constraints

| Name | Type | Columns | References |
| --- | --- | --- | --- |
| `2200_17178_1_not_null` | CHECK |  |  |
| `2200_17178_2_not_null` | CHECK |  |  |
| `2200_17178_3_not_null` | CHECK |  |  |
| `2200_17178_4_not_null` | CHECK |  |  |
| `2200_17178_5_not_null` | CHECK |  |  |
| `2200_17178_7_not_null` | CHECK |  |  |
| `2200_17178_8_not_null` | CHECK |  |  |
| `users_pkey` | PRIMARY KEY | user_id |  |
| `users_email_key` | UNIQUE | email |  |
| `users_username_key` | UNIQUE | username |  |

#### Indexes

- `idx_users_email`: `CREATE INDEX idx_users_email ON public.users USING btree (email)`
- `idx_users_username`: `CREATE INDEX idx_users_username ON public.users USING btree (username)`
- `users_email_key`: `CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email)`
- `users_pkey`: `CREATE UNIQUE INDEX users_pkey ON public.users USING btree (user_id)`
- `users_username_key`: `CREATE UNIQUE INDEX users_username_key ON public.users USING btree (username)`

## Row counts by season

### `game_environment_daily`

| Season | Rows |
| --- | ---: |
| 2025-26 | 74 |

### `game_environment_snapshots`

| Season | Rows |
| --- | ---: |
| 2025-26 | 9 |

### `game_odds`

| Season | Rows |
| --- | ---: |
| 2025-26 | 156 |

### `game_schedule`

| Season | Rows |
| --- | ---: |
| 2016-17 | 2812 |
| 2017-18 | 2764 |
| 2018-19 | 2756 |
| 2019-20 | 2482 |
| 2020-21 | 2440 |
| 2021-22 | 2778 |
| 2022-23 | 2770 |
| 2023-24 | 2766 |
| 2024-25 | 2806 |
| 2025-26 | 2592 |

### `gamelogs`

| Season | Rows |
| --- | ---: |
| 2020-21 | 22620 |
| 2021-22 | 25566 |
| 2022-23 | 25355 |
| 2023-24 | 26125 |
| 2024-25 | 26301 |
| 2025-26 | 28346 |

### `ingestion_runs`

| Season | Rows |
| --- | ---: |
| 2025-26 | 21 |

### `league_dash_team_stats`

| Season | Rows |
| --- | ---: |
| 2023-24 | 46 |
| 2024-25 | 46 |
| 2025-26 | 46 |

### `leaguedashplayerstats`

| Season | Rows |
| --- | ---: |
| 2016-17 | 486 |
| 2017-18 | 540 |
| 2018-19 | 530 |
| 2019-20 | 529 |
| 2020-21 | 540 |
| 2021-22 | 605 |
| 2022-23 | 539 |
| 2023-24 | 572 |
| 2024-25 | 547 |
| 2025-26 | 575 |

### `player_consecutive_streak_snapshots`

| Season | Rows |
| --- | ---: |
| 2025-26 | 1511870 |

### `player_consecutive_streaks`

| Season | Rows |
| --- | ---: |
| 2025-26 | 11458 |

### `player_consistency`

| Season | Rows |
| --- | ---: |
| 2025-26 | 7756 |

### `player_consistency_snapshots`

| Season | Rows |
| --- | ---: |
| 2025-26 | 997248 |

### `player_game_status`

| Season | Rows |
| --- | ---: |
| 2025-26 | 3027 |

### `player_heat_index`

| Season | Rows |
| --- | ---: |
| 2025-26 | 6870 |

### `player_heat_index_snapshots`

| Season | Rows |
| --- | ---: |
| 2025-26 | 909429 |

### `player_stat_window_snapshots`

| Season | Rows |
| --- | ---: |
| 2025-26 | 4591776 |

### `player_stat_windows`

| Season | Rows |
| --- | ---: |
| 2025-26 | 33096 |

### `player_streaks`

| Season | Rows |
| --- | ---: |
| 2025-26 | 1291 |

### `roster`

| Season | Rows |
| --- | ---: |
| 2025-26 | 530 |

### `statistics`

| Season | Rows |
| --- | ---: |
| 2016-17 | 486 |
| 2017-18 | 540 |
| 2018-19 | 530 |
| 2019-20 | 529 |
| 2020-21 | 540 |
| 2021-22 | 605 |
| 2022-23 | 539 |
| 2023-24 | 572 |
| 2024-25 | 569 |
| 2025-26 | 449 |

### `team_daily_flags`

| Season | Rows |
| --- | ---: |
| 2025-26 | 249 |

### `team_daily_metrics`

| Season | Rows |
| --- | ---: |
| 2025-26 | 300 |

### `team_game_feature_snapshots`

| Season | Rows |
| --- | ---: |
| 2025-26 | 18 |

### `team_game_stats`

| Season | Rows |
| --- | ---: |
| 2023-24 | 241 |
| 2024-25 | 2460 |
| 2025-26 | 2460 |

### `team_schedule_factors`

| Season | Rows |
| --- | ---: |
| 2025-26 | 2592 |

## Rows per season and team (sample)

Limited to 200 groups per table (highest row counts within each season ordering).

### `game_schedule`

| Season | Team ID | Rows |
| --- | ---: | ---: |
| 2016-17 | 1610612738 | 107 |
| 2016-17 | 1610612739 | 106 |
| 2016-17 | 1610612744 | 106 |
| 2016-17 | 1610612759 | 104 |
| 2016-17 | 1610612764 | 102 |
| 2016-17 | 1610612745 | 99 |
| 2016-17 | 1610612762 | 99 |
| 2016-17 | 1610612761 | 98 |
| 2016-17 | 1610612737 | 95 |
| 2016-17 | 1610612746 | 95 |
| 2016-17 | 1610612741 | 95 |
| 2016-17 | 1610612763 | 94 |
| 2016-17 | 1610612749 | 94 |
| 2016-17 | 1610612757 | 93 |
| 2016-17 | 1610612754 | 92 |
| 2016-17 | 1610612760 | 91 |
| 2016-17 | 1610612747 | 90 |
| 2016-17 | 1610612748 | 90 |
| 2016-17 | 1610612743 | 90 |
| 2016-17 | 1610612753 | 89 |
| 2016-17 | 1610612766 | 89 |
| 2016-17 | 1610612755 | 89 |
| 2016-17 | 1610612750 | 89 |
| 2016-17 | 1610612742 | 89 |
| 2016-17 | 1610612740 | 88 |
| 2016-17 | 1610612756 | 88 |
| 2016-17 | 1610612751 | 88 |
| 2016-17 | 1610612765 | 88 |
| 2016-17 | 1610612752 | 88 |
| 2016-17 | 1610612758 | 87 |
| 2017-18 | 1610612739 | 109 |
| 2017-18 | 1610612744 | 107 |
| 2017-18 | 1610612738 | 105 |
| 2017-18 | 1610612745 | 103 |
| 2017-18 | 1610612755 | 97 |
| 2017-18 | 1610612761 | 97 |
| 2017-18 | 1610612762 | 96 |
| 2017-18 | 1610612740 | 95 |
| 2017-18 | 1610612749 | 93 |
| 2017-18 | 1610612748 | 93 |
| 2017-18 | 1610612764 | 92 |
| 2017-18 | 1610612759 | 92 |
| 2017-18 | 1610612754 | 92 |
| 2017-18 | 1610612757 | 91 |
| 2017-18 | 1610612760 | 91 |
| 2017-18 | 1610612750 | 90 |
| 2017-18 | 1610612753 | 88 |
| 2017-18 | 1610612741 | 88 |
| 2017-18 | 1610612747 | 88 |
| 2017-18 | 1610612758 | 88 |
| 2017-18 | 1610612742 | 88 |
| 2017-18 | 1610612763 | 87 |
| 2017-18 | 1610612766 | 87 |
| 2017-18 | 1610612746 | 87 |
| 2017-18 | 1610612752 | 87 |
| 2017-18 | 1610612743 | 87 |
| 2017-18 | 1610612737 | 87 |
| 2017-18 | 1610612765 | 87 |
| 2017-18 | 1610612756 | 86 |
| 2017-18 | 1610612751 | 86 |
| 2018-19 | 1610612761 | 110 |
| 2018-19 | 1610612744 | 109 |
| 2018-19 | 1610612757 | 103 |
| 2018-19 | 1610612749 | 101 |
| 2018-19 | 1610612743 | 100 |
| 2018-19 | 1610612745 | 97 |
| 2018-19 | 1610612755 | 97 |
| 2018-19 | 1610612738 | 95 |
| 2018-19 | 1610612759 | 94 |
| 2018-19 | 1610612751 | 91 |
| 2018-19 | 1610612765 | 91 |
| 2018-19 | 1610612760 | 91 |
| 2018-19 | 1610612746 | 91 |
| 2018-19 | 1610612753 | 91 |
| 2018-19 | 1610612762 | 90 |
| 2018-19 | 1610612754 | 90 |
| 2018-19 | 1610612747 | 88 |
| 2018-19 | 1610612748 | 88 |
| 2018-19 | 1610612750 | 87 |
| 2018-19 | 1610612763 | 87 |
| … | … | (120 more groups truncated) |

### `gamelogs`

| Season | Team ID | Rows |
| --- | ---: | ---: |
| 2020-21 | 1610612755 | 829 |
| 2020-21 | 1610612762 | 820 |
| 2020-21 | 1610612743 | 815 |
| 2020-21 | 1610612764 | 801 |
| 2020-21 | 1610612742 | 799 |
| 2020-21 | 1610612759 | 792 |
| 2020-21 | 1610612747 | 784 |
| 2020-21 | 1610612749 | 783 |
| 2020-21 | 1610612744 | 777 |
| 2020-21 | 1610612763 | 773 |
| 2020-21 | 1610612741 | 772 |
| 2020-21 | 1610612737 | 771 |
| 2020-21 | 1610612746 | 769 |
| 2020-21 | 1610612756 | 753 |
| 2020-21 | 1610612761 | 748 |
| 2020-21 | 1610612751 | 746 |
| 2020-21 | 1610612754 | 744 |
| 2020-21 | 1610612757 | 741 |
| 2020-21 | 1610612748 | 738 |
| 2020-21 | 1610612740 | 736 |
| 2020-21 | 1610612760 | 735 |
| 2020-21 | 1610612739 | 734 |
| 2020-21 | 1610612766 | 730 |
| 2020-21 | 1610612753 | 725 |
| 2020-21 | 1610612758 | 719 |
| 2020-21 | 1610612752 | 716 |
| 2020-21 | 1610612765 | 715 |
| 2020-21 | 1610612745 | 700 |
| 2020-21 | 1610612738 | 679 |
| 2020-21 | 1610612750 | 676 |
| 2021-22 | 1610612750 | 927 |
| 2021-22 | 1610612763 | 926 |
| 2021-22 | 1610612744 | 916 |
| 2021-22 | 1610612743 | 901 |
| 2021-22 | 1610612742 | 891 |
| 2021-22 | 1610612737 | 884 |
| 2021-22 | 1610612738 | 884 |
| 2021-22 | 1610612762 | 882 |
| 2021-22 | 1610612764 | 875 |
| 2021-22 | 1610612745 | 867 |
| 2021-22 | 1610612749 | 864 |
| 2021-22 | 1610612739 | 858 |
| 2021-22 | 1610612760 | 852 |
| 2021-22 | 1610612755 | 843 |
| 2021-22 | 1610612761 | 843 |
| 2021-22 | 1610612759 | 842 |
| 2021-22 | 1610612752 | 840 |
| 2021-22 | 1610612753 | 840 |
| 2021-22 | 1610612766 | 839 |
| 2021-22 | 1610612741 | 838 |
| 2021-22 | 1610612754 | 838 |
| 2021-22 | 1610612748 | 837 |
| 2021-22 | 1610612757 | 835 |
| 2021-22 | 1610612747 | 824 |
| 2021-22 | 1610612751 | 814 |
| 2021-22 | 1610612756 | 812 |
| 2021-22 | 1610612740 | 811 |
| 2021-22 | 1610612746 | 808 |
| 2021-22 | 1610612765 | 807 |
| 2021-22 | 1610612758 | 768 |
| 2022-23 | 1610612758 | 948 |
| 2022-23 | 1610612749 | 901 |
| 2022-23 | 1610612756 | 898 |
| 2022-23 | 1610612759 | 890 |
| 2022-23 | 1610612755 | 888 |
| 2022-23 | 1610612763 | 888 |
| 2022-23 | 1610612762 | 885 |
| 2022-23 | 1610612745 | 884 |
| 2022-23 | 1610612742 | 878 |
| 2022-23 | 1610612751 | 875 |
| 2022-23 | 1610612750 | 867 |
| 2022-23 | 1610612737 | 865 |
| 2022-23 | 1610612760 | 858 |
| 2022-23 | 1610612740 | 851 |
| 2022-23 | 1610612746 | 849 |
| 2022-23 | 1610612744 | 848 |
| 2022-23 | 1610612753 | 848 |
| 2022-23 | 1610612741 | 846 |
| 2022-23 | 1610612743 | 845 |
| 2022-23 | 1610612764 | 839 |
| … | … | (100 more groups truncated) |

### `team_game_stats`

| Season | Team ID | Rows |
| --- | ---: | ---: |
| 2023-24 | 1610612737 | 17 |
| 2023-24 | 1610612739 | 16 |
| 2023-24 | 1610612740 | 16 |
| 2023-24 | 1610612744 | 14 |
| 2023-24 | 1610612738 | 14 |
| 2023-24 | 1610612742 | 14 |
| 2023-24 | 1610612741 | 13 |
| 2023-24 | 1610612743 | 13 |
| 2023-24 | 1610612751 | 12 |
| 2023-24 | 1610612746 | 12 |
| 2023-24 | 1610612745 | 11 |
| 2023-24 | 1610612747 | 10 |
| 2023-24 | 1610612749 | 10 |
| 2023-24 | 1610612748 | 10 |
| 2023-24 | 1610612755 | 8 |
| 2023-24 | 1610612753 | 8 |
| 2023-24 | 1610612750 | 7 |
| 2023-24 | 1610612752 | 6 |
| 2023-24 | 1610612756 | 5 |
| 2023-24 | 1610612758 | 5 |
| 2023-24 | 1610612759 | 5 |
| 2023-24 | 1610612760 | 4 |
| 2023-24 | 1610612754 | 3 |
| 2023-24 | 1610612757 | 3 |
| 2023-24 | 1610612763 | 2 |
| 2023-24 | 1610612761 | 2 |
| 2023-24 | 1610612764 | 1 |
| 2024-25 | 1610612745 | 82 |
| 2024-25 | 1610612758 | 82 |
| 2024-25 | 1610612755 | 82 |
| 2024-25 | 1610612754 | 82 |
| 2024-25 | 1610612756 | 82 |
| 2024-25 | 1610612762 | 82 |
| 2024-25 | 1610612746 | 82 |
| 2024-25 | 1610612741 | 82 |
| 2024-25 | 1610612761 | 82 |
| 2024-25 | 1610612752 | 82 |
| 2024-25 | 1610612764 | 82 |
| 2024-25 | 1610612739 | 82 |
| 2024-25 | 1610612750 | 82 |
| 2024-25 | 1610612738 | 82 |
| 2024-25 | 1610612737 | 82 |
| 2024-25 | 1610612743 | 82 |
| 2024-25 | 1610612748 | 82 |
| 2024-25 | 1610612749 | 82 |
| 2024-25 | 1610612744 | 82 |
| 2024-25 | 1610612759 | 82 |
| 2024-25 | 1610612757 | 82 |
| 2024-25 | 1610612766 | 82 |
| 2024-25 | 1610612763 | 82 |
| 2024-25 | 1610612760 | 82 |
| 2024-25 | 1610612765 | 82 |
| 2024-25 | 1610612751 | 82 |
| 2024-25 | 1610612742 | 82 |
| 2024-25 | 1610612747 | 82 |
| 2024-25 | 1610612753 | 82 |
| 2024-25 | 1610612740 | 82 |
| 2025-26 | 1610612741 | 82 |
| 2025-26 | 1610612750 | 82 |
| 2025-26 | 1610612754 | 82 |
| 2025-26 | 1610612757 | 82 |
| 2025-26 | 1610612760 | 82 |
| 2025-26 | 1610612752 | 82 |
| 2025-26 | 1610612761 | 82 |
| 2025-26 | 1610612737 | 82 |
| 2025-26 | 1610612751 | 82 |
| 2025-26 | 1610612753 | 82 |
| 2025-26 | 1610612748 | 82 |
| 2025-26 | 1610612766 | 82 |
| 2025-26 | 1610612759 | 82 |
| 2025-26 | 1610612762 | 82 |
| 2025-26 | 1610612764 | 82 |
| 2025-26 | 1610612755 | 82 |
| 2025-26 | 1610612745 | 82 |
| 2025-26 | 1610612756 | 82 |
| 2025-26 | 1610612746 | 82 |
| 2025-26 | 1610612744 | 82 |
| 2025-26 | 1610612747 | 82 |
| 2025-26 | 1610612742 | 82 |
| 2025-26 | 1610612765 | 82 |
| … | … | (7 more groups truncated) |

### `leaguedashplayerstats`

| Season | Team ID | Rows |
| --- | ---: | ---: |
| 2016-17 | 1610612739 | 19 |
| 2016-17 | 1610612742 | 19 |
| 2016-17 | 1610612753 | 18 |
| 2016-17 | 1610612737 | 18 |
| 2016-17 | 1610612751 | 18 |
| 2016-17 | 1610612743 | 17 |
| 2016-17 | 1610612749 | 17 |
| 2016-17 | 1610612764 | 17 |
| 2016-17 | 1610612766 | 17 |
| 2016-17 | 1610612756 | 17 |
| 2016-17 | 1610612740 | 17 |
| 2016-17 | 1610612763 | 16 |
| 2016-17 | 1610612761 | 16 |
| 2016-17 | 1610612759 | 16 |
| 2016-17 | 1610612744 | 16 |
| 2016-17 | 1610612747 | 16 |
| 2016-17 | 1610612741 | 16 |
| 2016-17 | 1610612754 | 16 |
| 2016-17 | 1610612758 | 16 |
| 2016-17 | 1610612755 | 16 |
| 2016-17 | 1610612760 | 15 |
| 2016-17 | 1610612738 | 15 |
| 2016-17 | 1610612745 | 15 |
| 2016-17 | 1610612765 | 15 |
| 2016-17 | 1610612746 | 15 |
| 2016-17 | 1610612762 | 15 |
| 2016-17 | 1610612752 | 15 |
| 2016-17 | 1610612750 | 15 |
| 2016-17 | 1610612748 | 14 |
| 2016-17 | 1610612757 | 14 |
| 2017-18 | 1610612763 | 22 |
| 2017-18 | 1610612742 | 21 |
| 2017-18 | 1610612747 | 20 |
| 2017-18 | 1610612745 | 20 |
| 2017-18 | 1610612754 | 19 |
| 2017-18 | 1610612749 | 19 |
| 2017-18 | 1610612740 | 19 |
| 2017-18 | 1610612765 | 19 |
| 2017-18 | 1610612737 | 19 |
| 2017-18 | 1610612755 | 19 |
| 2017-18 | 1610612738 | 19 |
| 2017-18 | 1610612741 | 19 |
| 2017-18 | 1610612762 | 19 |
| 2017-18 | 1610612756 | 18 |
| 2017-18 | 1610612752 | 18 |
| 2017-18 | 1610612751 | 18 |
| 2017-18 | 1610612748 | 18 |
| 2017-18 | 1610612753 | 18 |
| 2017-18 | 1610612766 | 17 |
| 2017-18 | 1610612739 | 17 |
| 2017-18 | 1610612743 | 17 |
| 2017-18 | 1610612759 | 17 |
| 2017-18 | 1610612744 | 17 |
| 2017-18 | 1610612746 | 17 |
| 2017-18 | 1610612760 | 17 |
| 2017-18 | 1610612761 | 16 |
| 2017-18 | 1610612758 | 16 |
| 2017-18 | 1610612750 | 15 |
| 2017-18 | 1610612757 | 15 |
| 2017-18 | 1610612764 | 15 |
| 2018-19 | 1610612763 | 22 |
| 2018-19 | 1610612739 | 21 |
| 2018-19 | 1610612747 | 20 |
| 2018-19 | 1610612745 | 20 |
| 2018-19 | 1610612746 | 19 |
| 2018-19 | 1610612755 | 19 |
| 2018-19 | 1610612764 | 19 |
| 2018-19 | 1610612750 | 18 |
| 2018-19 | 1610612737 | 18 |
| 2018-19 | 1610612743 | 18 |
| 2018-19 | 1610612741 | 18 |
| 2018-19 | 1610612761 | 18 |
| 2018-19 | 1610612749 | 18 |
| 2018-19 | 1610612740 | 17 |
| 2018-19 | 1610612752 | 17 |
| 2018-19 | 1610612760 | 17 |
| 2018-19 | 1610612766 | 17 |
| 2018-19 | 1610612765 | 17 |
| 2018-19 | 1610612753 | 17 |
| 2018-19 | 1610612744 | 17 |
| … | … | (120 more groups truncated) |

### `league_dash_team_stats`

| Season | Team ID | Rows |
| --- | ---: | ---: |
| 2023-24 | 1610612753 | 2 |
| 2023-24 | 1610612746 | 2 |
| 2023-24 | 1610612747 | 2 |
| 2023-24 | 1610612749 | 2 |
| 2023-24 | 1610612742 | 2 |
| 2023-24 | 1610612754 | 2 |
| 2023-24 | 1610612760 | 2 |
| 2023-24 | 1610612748 | 2 |
| 2023-24 | 1610612743 | 2 |
| 2023-24 | 1610612755 | 2 |
| 2023-24 | 1610612756 | 2 |
| 2023-24 | 1610612752 | 2 |
| 2023-24 | 1610612750 | 2 |
| 2023-24 | 1610612738 | 2 |
| 2023-24 | 1610612740 | 2 |
| 2023-24 | 1610612739 | 2 |
| 2023-24 | 1610612764 | 1 |
| 2023-24 | 1610612759 | 1 |
| 2023-24 | 1610612763 | 1 |
| 2023-24 | 1610612744 | 1 |
| 2023-24 | 1610612737 | 1 |
| 2023-24 | 1610612745 | 1 |
| 2023-24 | 1610612758 | 1 |
| 2023-24 | 1610612751 | 1 |
| 2023-24 | 1610612766 | 1 |
| 2023-24 | 1610612761 | 1 |
| 2023-24 | 1610612757 | 1 |
| 2023-24 | 1610612765 | 1 |
| 2023-24 | 1610612762 | 1 |
| 2023-24 | 1610612741 | 1 |
| 2024-25 | 1610612744 | 2 |
| 2024-25 | 1610612745 | 2 |
| 2024-25 | 1610612760 | 2 |
| 2024-25 | 1610612746 | 2 |
| 2024-25 | 1610612765 | 2 |
| 2024-25 | 1610612752 | 2 |
| 2024-25 | 1610612748 | 2 |
| 2024-25 | 1610612747 | 2 |
| 2024-25 | 1610612753 | 2 |
| 2024-25 | 1610612743 | 2 |
| 2024-25 | 1610612754 | 2 |
| 2024-25 | 1610612738 | 2 |
| 2024-25 | 1610612750 | 2 |
| 2024-25 | 1610612739 | 2 |
| 2024-25 | 1610612749 | 2 |
| 2024-25 | 1610612763 | 2 |
| 2024-25 | 1610612761 | 1 |
| 2024-25 | 1610612755 | 1 |
| 2024-25 | 1610612741 | 1 |
| 2024-25 | 1610612759 | 1 |
| 2024-25 | 1610612762 | 1 |
| 2024-25 | 1610612758 | 1 |
| 2024-25 | 1610612764 | 1 |
| 2024-25 | 1610612742 | 1 |
| 2024-25 | 1610612751 | 1 |
| 2024-25 | 1610612740 | 1 |
| 2024-25 | 1610612757 | 1 |
| 2024-25 | 1610612756 | 1 |
| 2024-25 | 1610612737 | 1 |
| 2024-25 | 1610612766 | 1 |
| 2025-26 | 1610612756 | 2 |
| 2025-26 | 1610612755 | 2 |
| 2025-26 | 1610612737 | 2 |
| 2025-26 | 1610612752 | 2 |
| 2025-26 | 1610612750 | 2 |
| 2025-26 | 1610612739 | 2 |
| 2025-26 | 1610612738 | 2 |
| 2025-26 | 1610612747 | 2 |
| 2025-26 | 1610612743 | 2 |
| 2025-26 | 1610612757 | 2 |
| 2025-26 | 1610612761 | 2 |
| 2025-26 | 1610612759 | 2 |
| 2025-26 | 1610612760 | 2 |
| 2025-26 | 1610612753 | 2 |
| 2025-26 | 1610612745 | 2 |
| 2025-26 | 1610612765 | 2 |
| 2025-26 | 1610612748 | 1 |
| 2025-26 | 1610612740 | 1 |
| 2025-26 | 1610612749 | 1 |
| 2025-26 | 1610612744 | 1 |
| … | … | (10 more groups truncated) |

### `roster`

| Season | Team ID | Rows |
| --- | ---: | ---: |
| 2025-26 | 1610612764 | 18 |
| 2025-26 | 1610612752 | 18 |
| 2025-26 | 1610612743 | 18 |
| 2025-26 | 1610612750 | 18 |
| 2025-26 | 1610612739 | 18 |
| 2025-26 | 1610612746 | 18 |
| 2025-26 | 1610612740 | 18 |
| 2025-26 | 1610612763 | 18 |
| 2025-26 | 1610612741 | 18 |
| 2025-26 | 1610612757 | 18 |
| 2025-26 | 1610612754 | 18 |
| 2025-26 | 1610612742 | 18 |
| 2025-26 | 1610612744 | 18 |
| 2025-26 | 1610612760 | 18 |
| 2025-26 | 1610612762 | 18 |
| 2025-26 | 1610612756 | 18 |
| 2025-26 | 1610612766 | 18 |
| 2025-26 | 1610612759 | 18 |
| 2025-26 | 1610612758 | 18 |
| 2025-26 | 1610612751 | 18 |
| 2025-26 | 1610612737 | 18 |
| 2025-26 | 1610612748 | 17 |
| 2025-26 | 1610612747 | 17 |
| 2025-26 | 1610612753 | 17 |
| 2025-26 | 1610612749 | 17 |
| 2025-26 | 1610612761 | 17 |
| 2025-26 | 1610612745 | 17 |
| 2025-26 | 1610612755 | 17 |
| 2025-26 | 1610612765 | 17 |
| 2025-26 | 1610612738 | 16 |

### `player_game_status`

| Season | Team ID | Rows |
| --- | ---: | ---: |
| 2025-26 | 1610612758 | 144 |
| 2025-26 | 1610612757 | 125 |
| 2025-26 | 1610612739 | 124 |
| 2025-26 | 1610612760 | 121 |
| 2025-26 | 1610612762 | 117 |
| 2025-26 | 1610612740 | 116 |
| 2025-26 | 1610612754 | 116 |
| 2025-26 | 1610612749 | 114 |
| 2025-26 | 1610612763 | 113 |
| 2025-26 | 1610612748 | 110 |
| 2025-26 | 1610612742 | 108 |
| 2025-26 | 1610612755 | 107 |
| 2025-26 | 1610612743 | 104 |
| 2025-26 | 1610612741 | 103 |
| 2025-26 | 1610612765 | 103 |
| 2025-26 | 1610612750 | 102 |
| 2025-26 | 1610612744 | 101 |
| 2025-26 | 1610612759 | 100 |
| 2025-26 | 1610612738 | 98 |
| 2025-26 | 1610612745 | 96 |
| 2025-26 | 1610612761 | 92 |
| 2025-26 | 1610612747 | 87 |
| 2025-26 | 1610612737 | 86 |
| 2025-26 | 1610612766 | 86 |
| 2025-26 | 1610612751 | 84 |
| 2025-26 | 1610612752 | 81 |
| 2025-26 | 1610612746 | 81 |
| 2025-26 | 1610612753 | 74 |
| 2025-26 | 1610612764 | 72 |
| 2025-26 | 1610612756 | 62 |

## Game date bounds

### `game_schedule`

- `min_game_date`: 2016-10-01 00:00:00
- `max_game_date`: 2026-04-13 00:30:00
- `min_completed_date`: 2016-10-01 00:00:00
- `max_completed_date`: 2026-04-13 00:30:00

### `team_game_stats`

- `min_game_date`: 2024-03-15
- `max_game_date`: 2026-04-12

## Null rates (important columns)

### `game_schedule`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `game_id` | 0 | 26966 | 0.00% |
| `team_id` | 0 | 26966 | 0.00% |
| `opponent_team_id` | 0 | 26966 | 0.00% |
| `season` | 0 | 26966 | 0.00% |
| `game_date` | 0 | 26966 | 0.00% |
| `home_or_away` | 0 | 26966 | 0.00% |
| `result` | 27 | 26966 | 0.10% |
| `score` | 27 | 26966 | 0.10% |

### `gamelogs`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `player_id` | 0 | 154313 | 0.00% |
| `game_id` | 0 | 154313 | 0.00% |
| `team_id` | 0 | 154313 | 0.00% |
| `season` | 0 | 154313 | 0.00% |
| `points` | 0 | 154313 | 0.00% |
| `rebounds` | 0 | 154313 | 0.00% |
| `assists` | 0 | 154313 | 0.00% |
| `minutes_played` | 0 | 154313 | 0.00% |

### `team_game_stats`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `game_id` | 0 | 5161 | 0.00% |
| `team_id` | 0 | 5161 | 0.00% |
| `opponent_team_id` | 0 | 5161 | 0.00% |
| `season` | 0 | 5161 | 0.00% |
| `game_date` | 0 | 5161 | 0.00% |
| `pts` | 0 | 5161 | 0.00% |
| `fg_pct` | 0 | 5161 | 0.00% |
| `reb` | 0 | 5161 | 0.00% |
| `ast` | 0 | 5161 | 0.00% |

### `players`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `player_id` | 0 | 1583 | 0.00% |
| `name` | 0 | 1583 | 0.00% |
| `position` | 59 | 1583 | 3.73% |
| `available_seasons` | 2 | 1583 | 0.13% |

### `teams`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `team_id` | 0 | 30 | 0.00% |
| `name` | 0 | 30 | 0.00% |
| `abbreviation` | 0 | 30 | 0.00% |

### `roster`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `team_id` | 0 | 530 | 0.00% |
| `player_id` | 0 | 530 | 0.00% |
| `season` | 0 | 530 | 0.00% |
| `player_name` | 0 | 530 | 0.00% |
| `position` | 0 | 530 | 0.00% |

### `leaguedashplayerstats`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `player_id` | 0 | 5463 | 0.00% |
| `season` | 0 | 5463 | 0.00% |
| `team_id` | 0 | 5463 | 0.00% |
| `gp` | 0 | 5463 | 0.00% |
| `pts` | 0 | 5463 | 0.00% |
| `min` | 0 | 5463 | 0.00% |

### `league_dash_team_stats`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `team_id` | 0 | 138 | 0.00% |
| `season` | 0 | 138 | 0.00% |
| `season_type` | 0 | 138 | 0.00% |
| `team_name` | 0 | 138 | 0.00% |

### `game_odds`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `game_id` | 0 | 156 | 0.00% |
| `game_date` | 0 | 156 | 0.00% |
| `home_ml_odds` | 0 | 156 | 0.00% |
| `away_ml_odds` | 0 | 156 | 0.00% |
| `home_spread` | 0 | 156 | 0.00% |
| `recorded_at` | 0 | 156 | 0.00% |

### `player_game_status`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `game_id` | 0 | 3027 | 0.00% |
| `player_id` | 0 | 3027 | 0.00% |
| `team_id` | 0 | 3027 | 0.00% |
| `status` | 0 | 3027 | 0.00% |
| `played` | 0 | 3027 | 0.00% |
| `not_playing_reason` | 857 | 3027 | 28.31% |

### `player_heat_index`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `player_id` | 0 | 6870 | 0.00% |
| `stat` | 0 | 6870 | 0.00% |
| `season` | 0 | 6870 | 0.00% |
| `z_score` | 0 | 6870 | 0.00% |
| `status` | 0 | 6870 | 0.00% |

### `player_consistency`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `player_id` | 0 | 7756 | 0.00% |
| `season` | 0 | 7756 | 0.00% |
| `stat_name` | 0 | 7756 | 0.00% |
| `cv` | 0 | 7756 | 0.00% |
| `consistency_tier` | 0 | 7756 | 0.00% |

### `team_daily_metrics`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `stat_date` | 0 | 300 | 0.00% |
| `team_id` | 0 | 300 | 0.00% |
| `window_size` | 0 | 300 | 0.00% |
| `net_rtg_season` | 0 | 300 | 0.00% |

### `team_schedule_factors`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `game_id` | 0 | 2592 | 0.00% |
| `team_id` | 0 | 2592 | 0.00% |
| `days_rest` | 30 | 2592 | 1.16% |
| `is_b2b` | 0 | 2592 | 0.00% |

### `team_game_feature_snapshots`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `game_id` | 0 | 18 | 0.00% |
| `team_id` | 0 | 18 | 0.00% |
| `opponent_team_id` | 0 | 18 | 0.00% |
| `season` | 0 | 18 | 0.00% |
| `feature_as_of` | 0 | 18 | 0.00% |
| `calculation_version` | 0 | 18 | 0.00% |
| `completeness_status` | 0 | 18 | 0.00% |
| `season_games_played` | 0 | 18 | 0.00% |
| `season_games_used` | 0 | 18 | 0.00% |

### `game_environment_snapshots`

| Column | Nulls | Total | Null rate |
| --- | ---: | ---: | ---: |
| `game_id` | 0 | 9 | 0.00% |
| `home_team_id` | 0 | 9 | 0.00% |
| `away_team_id` | 0 | 9 | 0.00% |
| `season` | 0 | 9 | 0.00% |
| `feature_as_of` | 0 | 9 | 0.00% |
| `calculation_version` | 0 | 9 | 0.00% |
| `completeness_status` | 0 | 9 | 0.00% |

## Duplicate primary / candidate keys

| Table | Key columns | Duplicate groups | Extra rows |
| --- | --- | ---: | ---: |
| `game_schedule` | `game_id`, `team_id` | 0 | 0 |
| `gamelogs` | `player_id`, `game_id` | 0 | 0 |
| `team_game_stats` | `game_id`, `team_id` | 0 | 0 |
| `roster` | `team_id`, `player_id`, `season` | 0 | 0 |
| `leaguedashplayerstats` | `player_id`, `season` | 0 | 0 |
| `league_dash_team_stats` | `team_id`, `season`, `season_type` | 0 | 0 |
| `statistics` | `player_id`, `season_year` | 0 | 0 |
| `player_streaks` | `player_id`, `stat`, `season`, `threshold` | 0 | 0 |
| `player_heat_index` | `player_id`, `stat`, `season`, `window_size` | 0 | 0 |
| `player_consistency` | `player_id`, `season`, `stat_name`, `window_size` | 0 | 0 |
| `team_daily_metrics` | `stat_date`, `team_id`, `window_size` | 0 | 0 |
| `team_daily_flags` | `stat_date`, `team_id`, `flag_type` | 0 | 0 |
| `team_schedule_factors` | `game_id`, `team_id` | 0 | 0 |
| `game_odds` | `game_id`, `sportsbook_id` | 0 | 0 |
| `player_game_status` | `game_id`, `player_id` | 0 | 0 |
| `game_environment_daily` | `game_id`, `game_date` | 0 | 0 |
| `player_consecutive_streak_snapshots` | `player_id`, `stat`, `threshold`, `season`, `season_type`, `feature_as_of`, `calculation_version`, `streak_kind` | 0 | 0 |
| `player_stat_window_snapshots` | `player_id`, `stat`, `threshold`, `season`, `season_type`, `window_size`, `feature_as_of`, `calculation_version` | 0 | 0 |
| `player_heat_index_snapshots` | `player_id`, `stat`, `season`, `season_type`, `window_size`, `feature_as_of`, `calculation_version` | 0 | 0 |
| `player_consistency_snapshots` | `player_id`, `season`, `season_type`, `stat_name`, `window_size`, `feature_as_of`, `calculation_version` | 0 | 0 |
| `team_game_feature_snapshots` | `game_id`, `team_id`, `window_size`, `feature_as_of`, `calculation_version` | 0 | 0 |
| `game_environment_snapshots` | `game_id`, `window_size`, `feature_as_of`, `calculation_version` | 0 | 0 |

## Orphan counts

| Check | Child | Parent | Orphan rows |
| --- | --- | --- | ---: |
| gamelogs missing schedule row | `gamelogs` | `game_schedule` | 0 |
| team_game_stats missing schedule row | `team_game_stats` | `game_schedule` | 0 |
| team feature snapshot missing schedule row | `team_game_feature_snapshots` | `game_schedule` | 0 |
| game environment snapshot missing home schedule row | `game_environment_snapshots` | `game_schedule` | 0 |
| game environment snapshot missing away schedule row | `game_environment_snapshots` | `game_schedule` | 0 |
| roster missing player | `roster` | `players` | 0 |
| roster missing team | `roster` | `teams` | 0 |
| gamelogs missing player | `gamelogs` | `players` | 0 |
| statistics missing player | `statistics` | `players` | 0 |
| player_game_status missing player | `player_game_status` | `players` | 0 |
| game_odds missing known schedule game | `game_odds` | `game_schedule` | 0 |

## Two-rows-per-game failures

### `game_schedule`

- Total distinct `game_id`: 13483
- Paired (exactly 2 rows): 13483
- Failures (≠ 2): 0
- Singletons: 0
- Overfull (>2): 0

### `team_game_stats`

- Total distinct `game_id`: 2701
- Paired (exactly 2 rows): 2460
- Failures (≠ 2): 241
- Singletons: 241
- Overfull (>2): 0

| game_id | row_count |
| --- | ---: |
| `0022300589` | 1 |
| `0022300961` | 1 |
| `0022300962` | 1 |
| `0022300963` | 1 |
| `0022300964` | 1 |
| `0022300965` | 1 |
| `0022300966` | 1 |
| `0022300967` | 1 |
| `0022300968` | 1 |
| `0022300969` | 1 |
| `0022300970` | 1 |
| `0022300971` | 1 |
| `0022300972` | 1 |
| `0022300973` | 1 |
| `0022300974` | 1 |

## Latest completed game coverage

- Latest completed date: `2026-04-13`
- Games on date: 8
- Fully covered (schedule+team stats+player logs): 8
- Coverage rate: 100.0%

| game_id | schedule_rows | results | team_game_stats | gamelogs | ok |
| --- | ---: | ---: | ---: | ---: | --- |
| `0022501193` | 2 | 2 | 2 | 18 | True |
| `0022501194` | 2 | 2 | 2 | 16 | True |
| `0022501195` | 2 | 2 | 2 | 16 | True |
| `0022501196` | 2 | 2 | 2 | 17 | True |
| `0022501197` | 2 | 2 | 2 | 21 | True |
| `0022501198` | 2 | 2 | 2 | 22 | True |
| `0022501199` | 2 | 2 | 2 | 23 | True |
| `0022501200` | 2 | 2 | 2 | 23 | True |

## Derived-table counts by calculation date

### `team_daily_metrics.stat_date` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-07-09 | 30 |
| 2026-03-03 | 30 |
| 2026-01-29 | 30 |
| 2026-01-25 | 30 |
| 2025-12-17 | 30 |
| 2025-12-12 | 30 |
| 2025-12-06 | 30 |
| 2025-12-04 | 30 |
| 2025-12-03 | 30 |
| 2025-12-02 | 30 |

### `team_daily_flags.stat_date` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-07-09 | 33 |
| 2026-03-03 | 20 |
| 2026-01-29 | 34 |
| 2026-01-25 | 33 |
| 2025-12-17 | 25 |
| 2025-12-12 | 26 |
| 2025-12-06 | 21 |
| 2025-12-04 | 19 |
| 2025-12-03 | 20 |
| 2025-12-02 | 18 |

### `game_environment_daily.game_date` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-03-03 | 10 |
| 2026-01-29 | 8 |
| 2026-01-25 | 8 |
| 2025-12-17 | 2 |
| 2025-12-12 | 7 |
| 2025-12-06 | 7 |
| 2025-12-04 | 5 |
| 2025-12-03 | 9 |
| 2025-12-02 | 6 |
| 2025-12-01 | 12 |

### `team_schedule_factors.game_date` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-04-13 | 16 |
| 2026-04-12 | 14 |
| 2026-04-11 | 18 |
| 2026-04-10 | 16 |
| 2026-04-09 | 16 |
| 2026-04-08 | 18 |
| 2026-04-07 | 14 |
| 2026-04-06 | 8 |
| 2026-04-05 | 18 |
| 2026-04-04 | 16 |
| 2026-04-03 | 16 |
| 2026-04-02 | 16 |
| 2026-04-01 | 16 |
| 2026-03-31 | 16 |
| 2026-03-30 | 6 |
| 2026-03-29 | 20 |
| 2026-03-28 | 22 |
| 2026-03-27 | 6 |
| 2026-03-26 | 20 |
| 2026-03-25 | 14 |
| 2026-03-24 | 14 |
| 2026-03-23 | 14 |
| 2026-03-22 | 18 |
| 2026-03-21 | 16 |
| 2026-03-20 | 16 |
| 2026-03-19 | 16 |
| 2026-03-18 | 14 |
| 2026-03-17 | 16 |
| 2026-03-16 | 12 |
| 2026-03-15 | 16 |

### `player_heat_index.created_at` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-07-09 | 6870 |

### `player_consistency.created_at` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-07-09 | 7756 |

### `player_consecutive_streaks.created_at` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-07-09 | 11458 |

### `player_stat_windows.created_at` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-07-09 | 33096 |

### `player_streaks.created_at` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2025-11-21 | 1291 |

### `game_odds.game_date` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-03-03 | 21 |
| 2026-01-29 | 24 |
| 2026-01-25 | 22 |
| 2025-12-17 | 24 |
| 2025-12-12 | 15 |
| 2025-12-06 | 26 |
| 2025-12-04 | 15 |
| 2025-12-03 | 9 |

### `player_game_status.game_date` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-03-02 | 11 |
| 2026-03-01 | 65 |
| 2026-02-28 | 63 |
| 2026-02-27 | 59 |
| 2026-02-26 | 70 |
| 2026-02-25 | 104 |
| 2026-02-24 | 17 |
| 2026-02-23 | 8 |
| 2026-01-28 | 40 |
| 2026-01-27 | 28 |
| 2026-01-26 | 27 |
| 2026-01-25 | 52 |
| 2026-01-24 | 106 |
| 2026-01-23 | 75 |
| 2026-01-22 | 37 |
| 2026-01-21 | 68 |
| 2026-01-20 | 23 |
| 2026-01-19 | 96 |
| 2026-01-18 | 87 |
| 2026-01-17 | 63 |
| 2025-12-16 | 74 |
| 2025-12-15 | 60 |
| 2025-12-14 | 71 |
| 2025-12-13 | 125 |
| 2025-12-12 | 55 |
| 2025-12-11 | 21 |
| 2025-12-10 | 7 |
| 2025-12-09 | 60 |
| 2025-12-08 | 41 |
| 2025-12-07 | 130 |

### `player_consecutive_streak_snapshots.feature_as_of` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-04-12 | 12732 |
| 2026-04-10 | 12602 |
| 2026-04-09 | 12523 |
| 2026-04-08 | 12492 |
| 2026-04-07 | 12393 |
| 2026-04-06 | 12353 |
| 2026-04-05 | 12170 |
| 2026-04-04 | 12184 |
| 2026-04-03 | 12201 |
| 2026-04-02 | 12183 |
| 2026-04-01 | 12065 |
| 2026-03-31 | 12152 |
| 2026-03-30 | 12083 |
| 2026-03-29 | 12046 |
| 2026-03-28 | 12092 |
| 2026-03-27 | 12035 |
| 2026-03-26 | 12031 |
| 2026-03-25 | 12001 |
| 2026-03-24 | 12008 |
| 2026-03-23 | 11966 |
| 2026-03-22 | 11944 |
| 2026-03-21 | 11913 |
| 2026-03-20 | 11936 |
| 2026-03-19 | 11813 |
| 2026-03-18 | 11870 |
| 2026-03-17 | 11830 |
| 2026-03-16 | 11827 |
| 2026-03-15 | 11762 |
| 2026-03-14 | 11727 |
| 2026-03-13 | 11719 |

### `player_stat_window_snapshots.feature_as_of` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-04-12 | 31528 |
| 2026-04-10 | 31528 |
| 2026-04-09 | 31528 |
| 2026-04-08 | 31528 |
| 2026-04-07 | 31472 |
| 2026-04-06 | 31472 |
| 2026-04-05 | 31472 |
| 2026-04-04 | 31472 |
| 2026-04-03 | 31416 |
| 2026-04-02 | 31416 |
| 2026-04-01 | 31416 |
| 2026-03-31 | 31360 |
| 2026-03-30 | 31360 |
| 2026-03-29 | 31360 |
| 2026-03-28 | 31360 |
| 2026-03-27 | 31360 |
| 2026-03-26 | 31304 |
| 2026-03-25 | 31304 |
| 2026-03-24 | 31304 |
| 2026-03-23 | 31248 |
| 2026-03-22 | 31192 |
| 2026-03-21 | 31192 |
| 2026-03-20 | 31192 |
| 2026-03-19 | 31024 |
| 2026-03-18 | 30912 |
| 2026-03-17 | 30912 |
| 2026-03-16 | 30856 |
| 2026-03-15 | 30800 |
| 2026-03-14 | 30744 |
| 2026-03-13 | 30576 |

### `player_heat_index_snapshots.feature_as_of` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-04-12 | 6630 |
| 2026-04-10 | 6609 |
| 2026-04-09 | 6609 |
| 2026-04-08 | 6585 |
| 2026-04-07 | 6570 |
| 2026-04-06 | 6558 |
| 2026-04-05 | 6546 |
| 2026-04-04 | 6546 |
| 2026-04-03 | 6537 |
| 2026-04-02 | 6537 |
| 2026-04-01 | 6525 |
| 2026-03-31 | 6522 |
| 2026-03-30 | 6522 |
| 2026-03-29 | 6498 |
| 2026-03-28 | 6486 |
| 2026-03-27 | 6477 |
| 2026-03-26 | 6477 |
| 2026-03-25 | 6477 |
| 2026-03-24 | 6477 |
| 2026-03-23 | 6456 |
| 2026-03-22 | 6450 |
| 2026-03-21 | 6450 |
| 2026-03-20 | 6450 |
| 2026-03-19 | 6438 |
| 2026-03-18 | 6396 |
| 2026-03-17 | 6396 |
| 2026-03-16 | 6384 |
| 2026-03-15 | 6384 |
| 2026-03-14 | 6384 |
| 2026-03-13 | 6384 |

### `player_consistency_snapshots.feature_as_of` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2026-04-12 | 7462 |
| 2026-04-10 | 7448 |
| 2026-04-09 | 7448 |
| 2026-04-08 | 7434 |
| 2026-04-07 | 7420 |
| 2026-04-06 | 7420 |
| 2026-04-05 | 7420 |
| 2026-04-04 | 7420 |
| 2026-04-03 | 7420 |
| 2026-04-02 | 7406 |
| 2026-04-01 | 7378 |
| 2026-03-31 | 7364 |
| 2026-03-30 | 7350 |
| 2026-03-29 | 7336 |
| 2026-03-28 | 7336 |
| 2026-03-27 | 7322 |
| 2026-03-26 | 7322 |
| 2026-03-25 | 7308 |
| 2026-03-24 | 7294 |
| 2026-03-23 | 7280 |
| 2026-03-22 | 7252 |
| 2026-03-21 | 7238 |
| 2026-03-20 | 7238 |
| 2026-03-19 | 7238 |
| 2026-03-18 | 7224 |
| 2026-03-17 | 7210 |
| 2026-03-16 | 7154 |
| 2026-03-15 | 7154 |
| 2026-03-14 | 7140 |
| 2026-03-13 | 7112 |

### `team_game_feature_snapshots.feature_as_of` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2025-11-10 | 18 |

### `game_environment_snapshots.feature_as_of` (latest 30 dates)

| Date | Rows |
| --- | ---: |
| 2025-11-10 | 9 |

## Durable snapshot coverage

### `player_consecutive_streak_snapshots`

| Season | Version | Completeness | Rows | Cutoffs | Earliest | Latest | Invalid availability |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 2025-26 | player-v2.1 | complete | 1511870 | 163 | 2025-10-22 10:00:00-04:00 | 2026-04-12 10:00:00-04:00 | 0 |

### `player_stat_window_snapshots`

| Season | Version | Completeness | Rows | Cutoffs | Earliest | Latest | Invalid availability |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 2025-26 | player-v2.1 | complete | 4591776 | 163 | 2025-10-22 10:00:00-04:00 | 2026-04-12 10:00:00-04:00 | 0 |

### `player_heat_index_snapshots`

| Season | Version | Completeness | Rows | Cutoffs | Earliest | Latest | Invalid availability |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 2025-26 | player-v2.1 | complete | 909429 | 160 | 2025-10-25 10:00:00-04:00 | 2026-04-12 10:00:00-04:00 | 0 |

### `player_consistency_snapshots`

| Season | Version | Completeness | Rows | Cutoffs | Earliest | Latest | Invalid availability |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 2025-26 | player-v2.1 | complete | 997248 | 156 | 2025-10-29 10:00:00-04:00 | 2026-04-12 10:00:00-04:00 | 0 |

### `team_game_feature_snapshots`

| Season | Version | Completeness | Rows | Cutoffs | Earliest | Latest | Invalid availability |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 2025-26 | team-v2.1 | complete | 11 | 1 | 2025-11-10 10:00:00-05:00 | 2025-11-10 10:00:00-05:00 | 0 |
| 2025-26 | team-v2.1 | partial | 7 | 1 | 2025-11-10 10:00:00-05:00 | 2025-11-10 10:00:00-05:00 | 0 |

### `game_environment_snapshots`

| Season | Version | Completeness | Rows | Cutoffs | Earliest | Latest | Invalid availability |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| 2025-26 | team-v2.1 | complete | 3 | 1 | 2025-11-10 10:00:00-05:00 | 2025-11-10 10:00:00-05:00 | 0 |
| 2025-26 | team-v2.1 | partial | 6 | 1 | 2025-11-10 10:00:00-05:00 | 2025-11-10 10:00:00-05:00 | 0 |

## Odds and availability observations by game

### `game_odds`

- `observation_rows`: 156
- `distinct_games`: 156
- `distinct_books`: 1

| game_id | game_date | observations | extra |
| --- | --- | ---: | --- |
| `0022500874` | 2026-03-03 | 1 | 1 |
| `0022500876` | 2026-03-03 | 1 | 1 |
| `0022500877` | 2026-03-03 | 1 | 1 |
| `0022500878` | 2026-03-03 | 1 | 1 |
| `0022500879` | 2026-03-03 | 1 | 1 |
| `0022500880` | 2026-03-03 | 1 | 1 |
| `0022500881` | 2026-03-03 | 1 | 1 |
| `0022500882` | 2026-03-03 | 1 | 1 |
| `0022500883` | 2026-03-03 | 1 | 1 |
| `0022500884` | 2026-03-03 | 1 | 1 |
| `0022500885` | 2026-03-03 | 1 | 1 |
| `0022500886` | 2026-03-03 | 1 | 1 |
| `0022500887` | 2026-03-03 | 1 | 1 |
| `0022500888` | 2026-03-03 | 1 | 1 |
| `0022500889` | 2026-03-03 | 1 | 1 |
| `0022500890` | 2026-03-03 | 1 | 1 |
| `0022500891` | 2026-03-03 | 1 | 1 |
| `0022500892` | 2026-03-03 | 1 | 1 |
| `0022500893` | 2026-03-03 | 1 | 1 |
| `0022500894` | 2026-03-03 | 1 | 1 |
| `0022500897` | 2026-03-03 | 1 | 1 |
| `0022500529` | 2026-01-29 | 1 | 1 |
| `0022500664` | 2026-01-29 | 1 | 1 |
| `0022500665` | 2026-01-29 | 1 | 1 |
| `0022500666` | 2026-01-29 | 1 | 1 |
| `0022500667` | 2026-01-29 | 1 | 1 |
| `0022500668` | 2026-01-29 | 1 | 1 |
| `0022500669` | 2026-01-29 | 1 | 1 |
| `0022500670` | 2026-01-29 | 1 | 1 |
| `0022500671` | 2026-01-29 | 1 | 1 |
| `0022500672` | 2026-01-29 | 1 | 1 |
| `0022500673` | 2026-01-29 | 1 | 1 |
| `0022500674` | 2026-01-29 | 1 | 1 |
| `0022500675` | 2026-01-29 | 1 | 1 |
| `0022500676` | 2026-01-29 | 1 | 1 |
| `0022500677` | 2026-01-29 | 1 | 1 |
| `0022500678` | 2026-01-29 | 1 | 1 |
| `0022500679` | 2026-01-29 | 1 | 1 |
| `0022500680` | 2026-01-29 | 1 | 1 |
| `0022500681` | 2026-01-29 | 1 | 1 |

### `player_game_status`

- `observation_rows`: 3027
- `distinct_games`: 221
- `inactive_rows`: 2022
- `played_true_rows`: 19

| game_id | game_date | observations | extra |
| --- | --- | ---: | --- |
| `0022500878` | 2026-03-02 | 11 | 9 |
| `0022500869` | 2026-03-01 | 16 | 10 |
| `0022500875` | 2026-03-01 | 15 | 8 |
| `0022500867` | 2026-03-01 | 13 | 9 |
| `0022500870` | 2026-03-01 | 12 | 11 |
| `0022500873` | 2026-03-01 | 9 | 6 |
| `0022500858` | 2026-02-28 | 16 | 8 |
| `0022500862` | 2026-02-28 | 16 | 9 |
| `0022500861` | 2026-02-28 | 16 | 12 |
| `0022500860` | 2026-02-28 | 8 | 8 |
| `0022500859` | 2026-02-28 | 7 | 7 |
| `0022500849` | 2026-02-27 | 16 | 7 |
| `0022500854` | 2026-02-27 | 15 | 12 |
| `0022500857` | 2026-02-27 | 15 | 9 |
| `0022500848` | 2026-02-27 | 13 | 10 |
| `0022500844` | 2026-02-26 | 16 | 11 |
| `0022500846` | 2026-02-26 | 16 | 9 |
| `0022500842` | 2026-02-26 | 14 | 9 |
| `0022500845` | 2026-02-26 | 13 | 10 |
| `0022500847` | 2026-02-26 | 11 | 8 |
| `0022500837` | 2026-02-25 | 15 | 6 |
| `0022500838` | 2026-02-25 | 15 | 10 |
| `0022500841` | 2026-02-25 | 15 | 5 |
| `0022500834` | 2026-02-25 | 14 | 10 |
| `0022500831` | 2026-02-25 | 13 | 10 |
| `0022500832` | 2026-02-25 | 12 | 10 |
| `0022500836` | 2026-02-25 | 12 | 11 |
| `0022500835` | 2026-02-25 | 8 | 6 |
| `0022500829` | 2026-02-24 | 17 | 12 |
| `0022500824` | 2026-02-23 | 8 | 5 |
| `0022500665` | 2026-01-28 | 17 | 7 |
| `0022500670` | 2026-01-28 | 13 | 11 |
| `0022500666` | 2026-01-28 | 10 | 7 |
| `0022500660` | 2026-01-27 | 15 | 7 |
| `0022500658` | 2026-01-27 | 13 | 9 |
| `0022500653` | 2026-01-26 | 16 | 9 |
| `0022500655` | 2026-01-26 | 11 | 7 |
| `0022500647` | 2026-01-25 | 15 | 8 |
| `0022500648` | 2026-01-25 | 15 | 9 |
| `0022500646` | 2026-01-25 | 14 | 9 |

## Last three ingestion / validation results

### Result 1: `data/last_validation.json`

- mtime (UTC): `2026-07-15T23:35:17.673932+00:00`
- ok: `True`
- season: `2025-26`
- date: `2025-11-10`
- timestamp: `2026-07-15T19:35:17`

| Check | Severity | Passed | Message |
| --- | --- | --- | --- |
| schedule_completeness | critical | True | DB has 9 unique games on 2025-11-10 (offline) |
| schedule_result_consistency | critical | True | Team-game source games=9; schedule games needing reconciliation=0; blocked source pairs=0 |
| final_scores_wl | critical | True | Checked 0 completed games; 0 mismatches |
| gamelog_orphans | critical | True | Season 2025-26: 28346 logs; orphan_team_samples=0 orphan_game_samples=0 |
| gamelog_stat_ranges | critical | True | Found 0 out-of-range gamelog rows |
| roster_gamelog_coverage | warning | True | Coverage 99% (524/530); missing=6 |
| heat_index_present | warning | True | player_heat_index rows for 2025-26: 6870 |
| consecutive_streaks_present | warning | True | player_consecutive_streaks rows for 2025-26: 11458 |
| game_environment_freshness | warning | False | game_environment_daily rows for 2025-11-10 or prior day: 0 |
| player_snapshot_integrity | warning | True | cutoff=2025-11-10T10:00:00-05:00 counts={'streaks': 6749, 'windows': 25424, 'heat': 4884, 'consistency': 5054} invalid_availability=0 |
| team_snapshot_integrity | warning | True | cutoff=2025-11-10T15:00:00+00:00 counts={'games': 9, 'team_features': 18, 'game_environments': 9, 'invalid_availability': 0, 'invalid_source_date': 0, 'invalid_pregame_cutoff': 0} |
| odds_coverage | warning | False | Odds for 0/9 games on 2025-11-10 (0%) |
| injury_coverage | warning | True | player_game_status rows in last 14d: 0 (completed games: 0) |

---

*Regenerate with:* `python scripts/generate_database_profile.py` (venv activated; `DATABASE_URL` set).
