# Analytics Architecture Phase 5 Rollout Runbook

Status: local analytics checkpoint; supervised historical apply only. No
production backfill or deployment is authorized by this document.

Reviewed: 2026-09-13 against the regenerated local PostgreSQL profile and the
sanitized [database profile](DATABASE_PROFILE.md).

## Current local checkpoint

Phases 2–4 are implemented. The local database is migrated through Alembic
head `i5j6k7l8m9n0`. The C7
Advanced V3 fact head, and C7 player facts are complete for six reviewed
Regular Season backfills from 2020-21 through 2025-26. Program D is complete
for the approved 2024-25 and 2025-26 feature layers; all historical applies
remain local and supervised. The database profile is the source of truth for
current row counts and quality findings.

| Dataset | Local coverage | Integrity state |
| --- | ---: | --- |
| 2025-26 player v2 snapshots | 8,010,323 rows across four families | zero invalid availability rows |
| 2025-26 team feature snapshots | 2,460 rows / 164 cutoffs | 2,160 complete, 300 honest early-season partial; zero duplicate/orphan keys |
| 2025-26 game environment snapshots | 1,230 rows / 164 cutoffs | 1,075 complete, 155 honest early-season partial; zero duplicate/orphan keys |
| 2025-26 schedule | 2,592 team-perspective rows | available for full slate range |
| 2025-26 team game facts | 2,460 rows / 1,230 regular-season games | full regular-season estimate |
| 2025-26 roster | 530 canonical rows | season `2025-26`; zero legacy four-digit rows |
| 2024-25 player facts | 32,515 Traditional + 32,515 Advanced rows / 1,230 games | zero missing or blocked games |
| 2025-26 player facts | 32,179 Traditional + 32,179 Advanced rows / 1,230 games | zero missing or blocked games |
| 2020-21 player facts | 28,859 Traditional + 28,859 Advanced rows / 1,080 games | shortened season; zero missing or blocked games |
| 2021-22 player facts | 31,321 Traditional + 31,321 Advanced rows / 1,230 games | zero missing or blocked games |
| 2022-23 player facts | 31,542 Traditional + 31,542 Advanced rows / 1,230 games | zero missing or blocked games |
| 2023-24 player facts | 32,385 Traditional + 32,385 Advanced rows / 1,230 games | zero missing or blocked games |
| 2024-25 D1 snapshot chunk | 1,087,476 player rows; 470 team rows; 235 environments | applied through 2024-11-21; duplicate and cutoff checks pass |
| 2024-25 D2 snapshot chunk | 1,475,342 player rows; 456 team rows; 228 environments | applied through 2024-12-27; validation and exact no-op reruns pass |
| 2024-25 D3 snapshot chunk | 1,571,211 player rows; 446 team rows; 223 environments | applied through 2025-01-27; validation and exact no-op reruns pass |
| 2024-25 D4 snapshot chunk | 1,641,700 player rows; 476 team rows; 238 environments | applied through 2025-03-04; validation and exact no-op reruns pass |
| 2024-25 D5 snapshot chunk | 1,728,510 player rows; 472 team rows; 236 environments | applied through 2025-04-04; validation and exact no-op reruns pass |
| 2024-25 D6 snapshot chunk | 399,426 player rows; 136 team rows; 68 environments | applied through 2025-04-12; validation and exact no-op reruns pass |
| 2024-25 opening-night repair | no player rows; 4 team rows; 2 environments | corrected canonical slate date `2024-10-21`; team validation and exact replay pass |

## Database analytics update — 2026-09-03

The regenerated profile reports complete canonical C7 coverage for the six
reviewed Regular Season backfills:

| Season | Eligible games | Paired `team_game_stats` rows | Traditional facts | Advanced facts |
| --- | ---: | ---: | ---: | ---: |
| 2020-21 | 1,080 | 2,160 | 28,859 | 28,859 |
| 2021-22 | 1,230 | 2,460 | 31,321 | 31,321 |
| 2022-23 | 1,230 | 2,460 | 31,542 | 31,542 |
| 2023-24 | 1,230 | 2,460 | 32,385 | 32,385 |
| 2024-25 | 1,230 | 2,460 | 32,515 | 32,515 |
| 2025-26 | 1,230 | 2,460 | 32,179 | 32,179 |

The quality checks that matter for the analytical boundary are green: the
profile reports zero duplicate candidate keys in the canonical and legacy
fact grains, all 7,230 stored team-game IDs have exactly two reciprocal rows,
and the C7 coverage inventories report zero missing or blocked games for each
reviewed season. `player_game_facts` and `player_game_advanced_facts` are the
canonical facts; immutable revision tables retain source lineage; `gamelogs`
remains a preserved compatibility source and is not redundant by policy yet.

This does not mean the entire database is production-current. The latest
profiled completed event is a 2025-26 playoff game (`0042500405`) with schedule
rows but no team stats or player logs. The 2026-27 released schedule and
rosters are now onboarded locally: 1,200 identified Regular Season games
(2,400 schedule rows) and 582 roster rows across 30 teams. Seven unresolved
NBA Cup/TBD placeholders remain excluded until their opponents are known.
The daily Traditional-then-Advanced C7 bridge is implemented but still needs
a completed-game smoke proof before launch; these operational gates remain
separate from the completed Regular Season historical foundation.

## Pre-Program E and 2026-27 readiness

The NBA released the complete 2026-27 Regular Season schedule on August 13,
2026 ([official release](https://www.nba.com/news/2026-27-nba-regular-season-schedule)).
The local database now has the identified schedule and all 30 current rosters.
Season launch still requires a separate onboarding proof:

1. Re-run the schedule coverage inventory after each release refresh and
   confirm reciprocal team rows, dates, event types, Cup/TBD handling, and
   current-season bounds.
2. Reconcile 2026-27 roster refreshes without changing prior seasons.
3. Run a quiet-day daily-ingestion proof and confirm the durable success marker.
4. Run one completed-game proof of the daily Traditional-then-Advanced C7
   bridge, including C5 reconciliation and a no-op replay.

The C7 bridge is not a Program E blocker. Until its completed-game smoke proof
passes, the existing daily PlayerGameLogs path remains the current-season
operational fallback, while the bounded V3 collectors remain a supervised
historical/backfill interface.
`team_game_stats.plus_minus` is now a nullable, derived Program E input: team
points minus the exact reciprocal opponent points. The migration and ORM write
paths leave it NULL for incomplete or conflicting pairs, and no code may
default it to zero.

Preseason schedule rows are retained as schedule evidence but are not part of
the Regular Season C7 fact or daily-bridge gate. The identified 2026-27
Regular Season schedule and rosters are onboarding state only; do not run the
first-game smoke proof until a completed game exists.

## Operational concerns checkpoint — 2026-09-05

The first operational pass is complete without deleting or rewriting legacy
tables:

1. 2026-27 onboarding contains 1,200 identified Regular Season games (2,400
   schedule rows) and 582 roster rows across 30 teams. Seven unresolved
   NBA Cup/TBD placeholders remain excluded until their opponents are known.
2. `daily_fetch.player_facts` is implemented as a bounded Traditional-then-
   Advanced bridge. It selects only completed reciprocal games with paired
   team stats, caps each batch at 25 games, resolves missing player parents,
   and requires C5 reconciliation. A pre-season quiet-day run returned a
   clean `no_op`; a completed-game smoke proof remains pending until the
   season produces a finished game.
3. `team_game_stats.plus_minus` has an explicit derived contract and migration.
   The stale single-game helper no longer passes `plus_minus=0`; complete
   reciprocal pairs are derived after writes and incomplete pairs remain NULL.
4. The Rotation Shock audit found 32,515 complete 2024-25 player facts but
   only 390 with known starter/bench provenance. Availability observations
   contain 22,608 pregame-timed rows across 952 games; the team-report
   coverage audit now accounts for all 2,460 completed game-team slots, while
   player-level availability remains source-dependent. No lineup/rotation
   table exists. The role-disruption proxy remains scoped research, not a
   universal starter feature.
5. `scripts/audit_legacy_redundancy.py` added a read-only inventory for the
   final redundancy/rollback gate. Its 2024-25 baseline shows all 1,230
   schedule games overlap between `gamelogs` and `player_game_facts`, while
   legacy current-state projections remain separately populated (`team_daily_metrics`
   300 rows, `team_daily_flags` 249, `game_environment_daily` 74). Similar
   shape is not treated as redundancy; consumer migration and rollback proof
are still required before any removal decision.

The 2026-09-05 SoS gate is complete for research: each approved Regular
Season has 1,075 paired games / 2,150 eligible team rows, all six candidate
fields are populated, and no pair or cutoff failures were found. Rolling
prior-opponent SoS remains separate from target-game Opponent Difficulty and
is not approved for shadow, durable, route, cache, or model use. The detailed
evidence is in `research/PROGRAM_E_SOS_RESEARCH_GATE_2026-09-05.md`.

The two-track Rotation Shock work remains bounded. The observed-risk proxy is
read-only and withholds panels missing a prior same-team role baseline. The
Live BoxScore starter collector now uses the proxy-aware CDN provider, but a
two-game dry-run received CDN 403 responses after proxy rotation. It then used
the reviewed Traditional V2 fallback for two 2024-25 games, adding 50
immutable evidence rows and projecting 20 explicit starters; the exact replay
added no rows or fact updates. Explicit starter rows remain the only
promotable evidence, and absent/non-starter rows remain unknown.

Run the inventory with:

```powershell
python scripts/audit_legacy_redundancy.py --season 2024-25
```

The inventory is evidence only. It performs no writes or deletions.

### 2024-25 team-value audit and repair

The structural D coverage counts are complete, but a live value audit on
2026-08-25 found `oreb`, `dreb`, and `wl` null in all 2,460 2024-25
`team_game_stats` rows. The snapshot publisher correctly marked the dependent
possession, efficiency, form, strength-of-schedule, and environment values as
missing instead of substituting zeros. The 2024-25 team layer is therefore
structurally present but not analytically value-complete at the initial audit.

Repository-history tracing identified the likely ingestion cause: the 2024-25
rows were loaded before commit `14bc7df` added explicit `TeamGameLog` mappings
for `OREB`, `DREB`, `WL`, `W`, `L`, and `W_PCT` in
`app/utils/fetch/team_fetcher.py`. The current fetcher includes those mappings,
and the 2025-26 rows have all six fields populated. This is a repairable source
projection defect, not evidence that the historical games lacked those values.

The bounded repair completed on 2026-08-25: all 2,460 rows now have populated
`oreb`, `dreb`, `wl`, `w`, `l`, and `w_pct`; the five self-opponent rows were
corrected from reciprocal `game_schedule` identities; and the derived team
snapshots were rebuilt with 2,460 team features and 1,230 environments. A
separate schedule-factor rebuild produced 2,806 factors across 1,403 games.

The repair used a separate bounded operation: first fetch and validate the
2024-25 TeamGameLog payloads in dry-run mode, then apply only after reciprocal
game identity, points, rebounds, result, and field-coverage checks pass. Rebuild
the affected snapshots only after the source-row repair is committed.

The repaired 2024-25 range is now eligible for team-based Program E
replication; the player snapshot families were unaffected.

D1 run lineage:

- player full-chunk no-op proof: `3807ebeb-23c3-461f-9be8-780fa0197bdf`;
- team full-chunk apply: `1cd5411f-66b0-4638-b4a0-a2e3fa74781f`;
- team full-chunk no-op proof: `a19ceeff-cda0-4457-854c-96477bb91abe`;
- the player apply was safely resumed after an interrupted process; the
  interrupted run is retained as failed evidence rather than hidden.

D2 applied and validated:

Target range: `2024-11-22` through `2024-12-27`, 31 scheduled slate dates.

| Family | Rows |
| --- | ---: |
| player streak snapshots | 255,458 |
| player stat-window snapshots | 862,064 |
| player heat snapshots | 169,758 |
| player consistency snapshots | 188,062 |
| team feature snapshots | 456 |
| game environment snapshots | 228 |

Total durable player rows: 1,475,342. The apply and exact no-op replay both
returned the same family totals. D2 run lineage:

- player apply: `0878bca8-4d22-47a6-9ab8-c58216bd4a56`;
- player exact no-op proof: `e30eb4e8-4bea-4bf2-ba67-3ab0ecbcf766`;
- team apply: `ac65da26-43b5-401f-8091-45e7e066c0a2`;
- team exact no-op proof: `27bea6a6-407a-42b6-984d-ecd4f84059e9`.

The D3-D6 ranges were selected as the next scheduled slate dates from
`game_schedule`. The opening-night repair used canonical slate date
`2024-10-21`; its player dry-run correctly returned zero rows because there is
no prior game history at the first cutoff. Do not replace that honest missing
state with invented preseason values.

Program D final coverage audit:

- scheduled games: `1,230`; environment games: `1,230`;
- team feature rows: `2,460`; unpaired feature games: `0`;
- duplicate natural keys: `0` in all six snapshot families;
- `data_available_at > feature_as_of`: `0` in player, team, and environment
  snapshots;
- advisory locks held after completion: `0`.

The validation gate reports five non-critical compatibility warnings that do
not invalidate the versioned snapshots: no historical 2024-25 roster rows,
empty legacy current-state `player_heat_index` and
`player_consecutive_streaks`, absent legacy `game_environment_daily` freshness,
and missing historical odds. The versioned snapshot tables pass their own
cutoff, completeness, and paired-coverage checks; these legacy warnings remain
separate follow-up work.

## C7 historical completion checkpoint

The season-agnostic C7 runner has completed the 2020-21, 2021-22, and
2022-23 Regular Season expansions after the earlier 2024-25 and 2025-26
backfills. Each season was processed in reviewed batches of at most 25 games,
with Traditional fetched before Advanced, C5 reconciliation after publication,
and an exact database-only replay after every batch. The 2020-21 season uses
its correct shortened 1,080-game scope. The final coverage inventory must be
run after any future backfill; runner completion by itself is not the gate.

The hardened team-stat fetcher now fails closed when any team returns an empty,
incomplete, or exception result. During 2020-21 ingestion three teams first
returned transient `ZeroDivisionError` failures; narrow retries succeeded at
72 rows each, and reciprocal coverage was then rechecked before player facts
were collected. This is the required recovery pattern for future seasons.

## Eligible seasons

Eligibility requires schedule rows, canonical player gamelogs, zero relevant
orphans, and—when team/game snapshots are requested—paired `team_game_stats`.

| Season | Player snapshots | Team/game snapshots | Decision |
| --- | --- | --- | --- |
| 2025-26 | complete locally | complete locally | validated stopping-point baseline |
| 2024-25 | C7 and Program D complete locally | eligible (2,460 team rows) | approved feature-season baseline |
| 2023-24 | C7 complete (32,385 facts/source) | eligible (2,460 team rows) | historical team/player foundation |
| 2022-23 | C7 complete (31,542 facts/source) | eligible (2,460 team rows) | historical team/player foundation |
| 2021-22 | C7 complete (31,321 facts/source) | eligible (2,460 team rows) | historical team/player foundation |
| 2020-21 | C7 complete (28,859 facts/source) | eligible (2,160 team rows) | shortened-season historical foundation |
| 2016-17 through 2019-20 | schedule exists but canonical gamelogs are absent | not eligible | ingest/validate facts before planning |

The four seasons above are now team-ready for fact-level historical analysis.
Program D snapshots remain intentionally limited to the approved 2024-25 and
2025-26 feature seasons; C7 fact coverage does not automatically authorize
retrospective snapshot publication for every season.

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

The first 2024-25 D1 chunk (`2024-10-22` through `2024-11-21`) was reviewed in
dry-run mode and then applied. Its final durable row counts are:

| Family | Rows |
| --- | ---: |
| player streak snapshots | 171,570 |
| player stat-window snapshots | 703,752 |
| player heat snapshots | 112,026 |
| player consistency snapshots | 100,128 |
| team feature snapshots | 470 |
| game environment snapshots | 235 |

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

The historical C7 foundation now passes for six Regular Seasons from 2020-21
through 2025-26. Program D has passed its full 2024-25 coverage, validation,
cutoff, and replay gates, with 2025-26 snapshots also populated locally.
Program E has begun with a non-persistent, versioned research
metric contract and Schedule Pressure candidate. The first bounded Schedule
Pressure coverage gate passed for 1,075 exactly paired 2025-26 games / 2,150
team rows; 10 snapshot-only games were excluded explicitly. The
sensitivity/outcome and paired-game comparisons completed with near-zero
outcome relationships. The repaired 2024-25 replication also passed for 1,075
paired games / 2,150 team rows with 100% outcome coverage. The Schedule
Pressure v0.1 contract and neutral user-language wording are now locked, and
the read-only shadow evaluation passed for both approved seasons: 2,150
eligible team rows across 1,075 paired games per season, zero missing schedule
factors, and zero replay mismatches. Schedule Pressure v0.1 is approved for
descriptive shadow use only. The next bounded step is the separate Opponent
Difficulty / Strength of Schedule research audit. The non-persistent
`scripts/shadow_program_e_schedule_pressure.py` runner, which replays every
selected row and reports status/label coverage without writing metric rows.
This does not authorize production metric publication or consumer integration.
The SoS kickoff audit is read-only through
`scripts/audit_program_e_opponent_difficulty.py`; it must pass coverage,
pairing, cutoff, and distribution checks before a formula or consumer is
introduced. That audit and the raw-unit formula comparison through
`scripts/experiment_program_e_opponent_difficulty.py` have passed for both
approved seasons. Target-opponent net rating and team SoS remain separate
research fields. The raw-unit language prototype is available through
`scripts/prototype_program_e_opponent_difficulty.py` and has been reviewed and
approved for research use. The pregame-safe scaling study is now available
through `scripts/experiment_program_e_opponent_difficulty_scaling.py`. It uses
only strictly earlier same-season feature cutoffs, withholds the first 20
reference rows, and leaves all source and metric tables untouched. The study
was stable across the approved 2024-25 and 2025-26 cohorts, but this does not
approve a 0-100 presentation, consumer, or persistence decision; those require
a separate wording review and production gate. The wording prototype is
available through `scripts/prototype_program_e_opponent_difficulty_scaled.py`
with raw-value-first, percentile-first, and compact styles. It remains
read-only and non-persistent until a style and production scale are explicitly
approved.
The Style Collision input audit is available through
`scripts/audit_program_e_style_collision.py`, and the supported pace
interaction through `scripts/experiment_program_e_style_collision.py`. Both
are read-only. Only pace interaction is currently supportable; seven planned
edges remain blocked until their missing defensive or possession-level inputs
are sourced. User language and production approval remain separate gates.
Target Opponent Difficulty and Pace are approved for descriptive shadow use
only; prior SoS context and Rotation Shock remain research-only. Current-season
2026-27 refresh discipline and the completed-game C7 smoke proof remain
operational work, not reasons to pause retrospective Program E research.

Do not delete `gamelogs`, `team_daily_metrics`, `team_daily_flags`,
`game_environment_daily`, or other legacy tables. The read-only redundancy
inventory has now started, but consumer migration and rollback proof still
require the final production-boundary audit before any removal decision.
Additional Program D
snapshot seasons require a separately reviewed feature-backfill decision.
