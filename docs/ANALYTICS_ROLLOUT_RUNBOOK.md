# Analytics Architecture Phase 5 Rollout Runbook

Status: planning and dry-run package only. No production backfill or deployment
is authorized by this document.

Reviewed: 2026-07-15 against local PostgreSQL revision `m3n4o5p6q7r8` and the
sanitized [database profile](DATABASE_PROFILE.md).

## Current local checkpoint

Phases 2–4 are implemented. The local database is migrated, and the 2025-26
player plus team/game snapshot backfills are complete through 2026-04-12.

| Dataset | Local coverage | Integrity state |
| --- | ---: | --- |
| 2025-26 player v2 snapshots | 8,010,323 rows across four families | zero invalid availability rows |
| 2025-26 team feature snapshots | 2,460 rows / 164 cutoffs | 2,160 complete, 300 honest early-season partial; zero duplicate/orphan keys |
| 2025-26 game environment snapshots | 1,230 rows / 164 cutoffs | 1,075 complete, 155 honest early-season partial; zero duplicate/orphan keys |
| 2025-26 schedule | 2,592 team-perspective rows | available for full slate range |
| 2025-26 team game facts | 2,460 rows / 1,230 regular-season games | full regular-season estimate |
| 2025-26 roster | 530 canonical rows | season `2025-26`; zero legacy four-digit rows |

The two known validation warnings at the checkpoint are unrelated to snapshots:
legacy `game_environment_daily` freshness and missing historical odds.

## Eligible seasons

Eligibility requires schedule rows, canonical player gamelogs, zero relevant
orphans, and—when team/game snapshots are requested—paired `team_game_stats`.

| Season | Player snapshots | Team/game snapshots | Decision |
| --- | --- | --- | --- |
| 2025-26 | complete locally | complete locally | validated stopping-point baseline |
| 2024-25 | eligible (26,301 gamelogs) | eligible (2,460 team rows) | next full historical season |
| 2023-24 | eligible (26,125 gamelogs) | not yet eligible (241 team rows) | player-only unless team facts are repaired |
| 2022-23 | eligible (25,355 gamelogs) | not eligible; no team facts | optional player-only expansion |
| 2021-22 | eligible (25,566 gamelogs) | not eligible; no team facts | optional player-only expansion |
| 2020-21 | eligible (22,620 gamelogs) | not eligible; no team facts | optional player-only expansion |
| 2016-17 through 2019-20 | schedule exists but canonical gamelogs are absent | not eligible | ingest/validate facts before planning |

Do not treat 2023-24 as team-ready merely because some team rows exist. Partial
source coverage is a blocker, not a reason to publish partial historical truth.

## Date and count preflight

Derive exact regular-season bounds from the target database; do not copy dates
from this document into an unrelated environment.

```sql
SELECT
    season,
    MIN((game_date AT TIME ZONE 'America/New_York')::date) AS from_date,
    MAX((game_date AT TIME ZONE 'America/New_York')::date) AS to_date,
    COUNT(*) AS schedule_rows,
    COUNT(DISTINCT game_id) AS games
FROM game_schedule
WHERE season IN ('2025-26', '2024-25')
  AND game_id LIKE '002%'
GROUP BY season
ORDER BY season;
```

Expected team/game writes for a complete regular season are approximately one
team feature per `team_game_stats` row and one environment per paired game. On
the current local profile:

| Season | Team feature estimate | Environment estimate | Existing | Estimated remaining |
| --- | ---: | ---: | ---: | ---: |
| 2025-26 | 2,460 | 1,230 | 2,460 / 1,230 | 0 / 0 |
| 2024-25 | 2,460 | 1,230 | 0 / 0 | 2,460 / 1,230 |

Player output expands each player/game sample across stats, thresholds, and
windows. Use the player backfill `--dry-run` counts as the estimate of record
writes; do not infer storage from the 2025-26 total alone. Record database size
before and after each applied chunk:

```sql
SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size;
```

The first 2024-25 readiness chunk (`2024-10-22` through `2024-11-21`) was run
locally in dry-run mode only. Its estimated writes were:

| Family | Dry-run rows |
| --- | ---: |
| player streak snapshots | 171,591 |
| player stat-window snapshots | 703,864 |
| player heat snapshots | 112,059 |
| player consistency snapshots | 100,338 |
| team feature snapshots | 470 |
| game environment snapshots | 234 |

## Bounded dry runs

Run from an environment whose `DATABASE_URL` has first been printed in sanitized
form and confirmed to target the intended database. The examples are dry-run
only and remain capped at 31 calendar dates.

```powershell
python .\scripts\backfill_team_game_snapshots.py `
  --season 2025-26 `
  --from-date 2025-10-21 `
  --to-date 2025-11-20 `
  --calculation-version team-v2.1 `
  --max-dates 31 `
  --dry-run

python .\scripts\backfill_player_snapshots.py `
  --season 2024-25 `
  --from-date <from_date_from_preflight> `
  --to-date <first_31_day_chunk_end> `
  --calculation-version player-v2.1 `
  --max-dates 31 `
  --dry-run

python .\scripts\backfill_team_game_snapshots.py `
  --season 2024-25 `
  --from-date <from_date_from_preflight> `
  --to-date <first_31_day_chunk_end> `
  --calculation-version team-v2.1 `
  --max-dates 31 `
  --dry-run
```

Capture the per-date and total counts in the rollout record. Any traceback,
critical validation failure, invalid availability count, source date at/after
the slate date, or unexpected row-count collapse blocks `--apply`.

## Apply and checkpoint procedure

`--apply` is authorized only after the target environment and dry-run report are
reviewed. Use exactly the reviewed chunk; do not expand the range at apply time.

1. Take a database backup and record current Alembic revision and database size.
2. Apply one 31-day-or-smaller chunk.
3. Record the resulting ingestion `run_id`, calculation version, last completed
   slate date, family counts, elapsed time, and database size.
4. Validate the chunk end date offline.
5. Query duplicate keys, orphan keys, invalid availability, and source-date
   leakage before starting the next chunk.
6. If interrupted, rerun the same chunk with `--resume-after YYYY-MM-DD`. Upserts
   are idempotent, so rerunning an uncertain final date is safe.

Example continuation shape (not an authorization to apply):

```powershell
python .\scripts\backfill_team_game_snapshots.py `
  --season 2025-26 `
  --from-date 2025-10-21 `
  --to-date 2025-11-20 `
  --resume-after 2025-11-10 `
  --calculation-version team-v2.1 `
  --max-dates 31 `
  --apply
```

## Validation gate

Run after every chunk:

```powershell
python .\scripts\validate_daily_data.py `
  --season <season> `
  --date <chunk_end_date> `
  --offline
```

Release acceptance requires:

- zero critical validation failures;
- zero duplicate natural keys in every v2 table;
- zero snapshot-to-schedule or ingestion-run orphans;
- zero `data_available_at > feature_as_of` rows;
- zero source games on/after the target slate date;
- paired team features and one environment for every complete scheduled game;
- a second run of the same bounded chunk produces no duplicate-key growth;
- a historical slate without an eligible cutoff returns missing, never a later
  snapshot or legacy current aggregate.

Regenerate `DATABASE_PROFILE.md` after the final accepted local/staging chunk.

## Cache invalidation

The v2 snapshot readers are currently uncached, so historical backfill does not
require a Redis deletion. If a deployment also changes a cached home/team
payload, prefer a cache-key version bump. Targeted invalidation may include the
affected dated `nba_games_YYYY-MM-DD` entry and owned home/team keys; do not use
Redis `KEYS` in production. See [CACHE_CATALOG.md](CACHE_CATALOG.md).

## Deployment gate

1. Confirm backup, target environment, code commit, and migration head
   `m3n4o5p6q7r8`.
2. Deploy code before scheduling new daily tasks, then run `alembic upgrade head`
   and `alembic check`.
3. Run one current-date calculation smoke and offline validation.
4. Verify `/daily/` and `/daily/betting` display snapshot provenance and honest
   partial/missing states.
5. Enable the daily snapshot tasks only after the smoke passes.
6. Keep historical backfill as a separate supervised operation; never bundle it
   into application deployment.

No production deployment or backfill has been run as part of Phase 5.

## Rollback

Application rollback comes first. Phase 3 code can still read canonical roster
seasons, so rolling back the Phase 4 application does not require converting
roster values back to four-digit years.

If schema rollback is required, downgrade only to the explicitly reviewed
revision. The Phase 4 downgrade removes its constraints/comment but intentionally
keeps canonical roster season values. Downgrading Phase 2/3 drops snapshot tables
and destroys their rows.

Backfill rollback is by recorded `source_run_id` and calculation version, inside
an explicit transaction after a backup. Preview counts before any delete. Never
delete by season alone and never remove legacy facts (`gamelogs`, schedule,
roster, or `team_game_stats`) to undo a derived snapshot run.

## Recommended stopping point

The recommended local stopping point has been reached: 2025-26 player and
team/game history is complete and validated, idempotency is confirmed, and the
first 2024-25 player/team chunk has a reviewed dry-run estimate. Applying
2024-25 or older history is a later supervised operational decision and is not
required before code review. The draft PR should remain draft until the known
Python environment/auth-test collection blockers are either repaired or
explicitly accepted as pre-existing release risks.
