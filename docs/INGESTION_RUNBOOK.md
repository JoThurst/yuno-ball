# Yuno Ball Ingestion Runbook

Status: canonical operating procedure plus documented gaps
Reviewed: 2026-07-15 against `ingest_data.py`, `daily_ingest.py`, `daily_fetch.py`, `daily_calculate.py`, fetch/get utilities, and scheduling wrappers.

## Safety rules

1. Back up or snapshot the database before first-load or schema-changing work.
2. Run schedule ingestion before `team_game_stats`; the latter has a foreign key to `game_schedule` and needs opponent IDs.
3. Treat reruns as normal. Every persisted dataset should upsert at its declared grain.
4. Run one NBA pipeline at a time. The authoritative daily entry points enforce this with a shared PostgreSQL advisory lock; exit code `3` means another run holds it.
5. On EC2, verify NBA connectivity before a long job and use one worker unless the current proxy/direct path has been load-tested.
6. Never expose ingestion as an unauthenticated public GET request.

## Current entry points

| Entry point | Intended use | Current behavior |
| --- | --- | --- |
| `ingest_data.py` | initial/weekly | currently runs player discovery and player career stats; most historical tasks are commented examples |
| `daily_ingest.py` | daily orchestrator | owns the run/lock; runs fetch then calculate; validates unless `--skip-validate`; publishes the success marker only after full validation |
| `daily_fetch.py` | NBA API fetch phase | records one durable task per source operation; standalone use owns the same run/lock |
| `daily_calculate.py` | derived analytics phase | records one durable task per calculation; standalone use owns the same run/lock and exits non-zero if any task fails |
| `scripts/register_external_dataset.py` | external raw-artifact manifest | hashes one file, validates CSV shape when applicable, and supports explicit dry-run/apply; it never imports source rows |
| `scripts/import_statsurge_availability.py` | Stat Surge historical availability staging | verifies the registered hash/license/row count, stages valid checkpoint rows, and quarantines invalid rows; no canonical promotion |
| `scripts/reconcile_statsurge_identities.py` | Stat Surge staging identity resolution | dry-runs exact team/player/game rules, then optionally persists version/run/method evidence under the staging lock; cutoff stays unknown |
| `scripts/import_kaggle_games.py` | Kaggle source game staging | stages all paired game/team rows with source missingness and promotion eligibility; canonical reconciliation is deferred |
| `scripts/import_kaggle_markets.py` | Kaggle historical market staging | atomically stages registered moneyline/spread/totals against verified source games and quarantines semantic anomalies |
| `cache_warmer.py` | precompute expensive page data | today's matchups, per-matchup data, and enhanced teams |
| `scripts/run_daily_ingest.ps1` | Windows Task Scheduler wrapper | activates venv and runs `daily_ingest.py` |
| `scripts/setup_cron.sh` | Linux cron installer | daily and weekly system cron scripts under `/etc/cron.*` |

Proxy / direct network policy: see [PROXY.md](PROXY.md).

## Initial load order

Use explicit season arguments in a controlled script or Python shell; do not blindly uncomment every historical loop.

1. Create/seed `teams` with NBA team IDs.
2. Fetch `players` (`static.players` + `CommonPlayerInfo`).
3. Fetch `statistics` from `PlayerCareerStats` if the simplified career table is still required.
4. Fetch current `roster` after players exist.
5. Populate `game_schedule` for each desired season.
6. Backfill `team_game_stats` after schedule rows exist.
7. Reconcile null final schedule results from validated paired team-game facts.
8. Backfill `gamelogs` for desired players/seasons after completed schedule IDs are current.
9. Backfill `leaguedashplayerstats` per season.
10. Backfill `league_dash_team_stats` per season, including regular season/playoffs and all configured measure/per-mode combinations.
11. Build `player_streaks` for the current season.
12. Run row-count, key-uniqueness, null-rate, and two-row-per-game checks.
13. Warm caches only after database validation passes.

## Historical/seasonal backfill

For season start year `Y`, format the season as `Y-(Y+1 last two digits)`. Process one season at a time. Daily commands now write `ingestion_runs` and `ingestion_task_runs`; resumable historical backfill checkpoints are still deferred to the bounded Phase 5 tools in `HISTORICAL_SNAPSHOT_AUDIT.md`.

Recommended per-season order:

```text
schedule -> team game stats -> schedule result reconciliation -> player game logs -> player season stats -> team season stats
```

Verification after each season:

```sql
SELECT season, COUNT(*) FROM game_schedule GROUP BY season ORDER BY season;
SELECT season, COUNT(*) FROM gamelogs GROUP BY season ORDER BY season;
SELECT season, COUNT(*) FROM team_game_stats GROUP BY season ORDER BY season;
SELECT season, COUNT(*) FROM leaguedashplayerstats GROUP BY season ORDER BY season;
SELECT season, season_type, COUNT(*)
FROM league_dash_team_stats
GROUP BY season, season_type
ORDER BY season, season_type;
```

Expected invariants:

* Completed standard NBA games normally have two `game_schedule` rows.
* `team_game_stats` has at most two rows per game and each row has the opposite team as `opponent_team_id`.
* `gamelogs.team_id` joins the matching team-perspective schedule row.
* Team season aggregates normally contain 30 regular-season teams.
* Playoff rows are fewer and must not overwrite regular season.

## Daily pipeline

### Quick start

```bash
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

python daily_ingest.py         # full pipeline
python daily_ingest.py --fetch-only
python daily_ingest.py --calc-only
python daily_ingest.py --list
python daily_ingest.py --proxy # or --local
python daily_ingest.py --season 2025-26
python daily_ingest.py --validate-only --date 2026-03-03
```

Selective runs:

```bash
python daily_ingest.py --fetch-tasks players rosters gamelogs
python daily_ingest.py --calc-tasks streaks heat consistency
python daily_ingest.py --exclude-fetch injury odds --exclude-calc flags
python daily_fetch.py --tasks schedule future odds
python daily_calculate.py --tasks metrics flags environment
```

### Fetch tasks (`daily_fetch.py`)

Default order respects dependencies:

| Task | Description | Notes |
| --- | --- | --- |
| `players` | Sync active players / available seasons | critical |
| `rosters` | Current team rosters | critical |
| `schedule` | Game schedule with results | critical |
| `future` | Upcoming games (CDN) | non-critical; schedule task retains the last known slate on failure |
| `teamstats` | Team game stats | critical |
| `schedule_reconcile` | Fill null final schedule results from validated paired team stats | critical; local/transactional; no HTTP |
| `gamelogs` | Player game logs (current season) | critical; heavy; runs after result reconciliation |
| `leagueteam` | League-wide team stats | critical |
| `leagueplayer` | League-wide player stats | critical |
| `injury` | Injury/status from boxscores | non-critical; slow |
| `odds` | Today's betting odds | non-critical |

If any critical fetch fails, calculations are skipped unless `--force-calc` is set.

### Calculate tasks (`daily_calculate.py`)

| Task | Description | Depends on |
| --- | --- | --- |
| `streaks` | Consecutive streaks / recent form windows | gamelogs |
| `heat` | Hot/cold vs season baseline | gamelogs |
| `consistency` | Volatility / CV per stat | gamelogs |
| `schedule` | B2B, rest days, rest advantage | schedule |
| `metrics` | Team performance + SOS | teamstats, schedule |
| `flags` | Qualitative team tags | metrics |
| `environment` | Today's game context | metrics, schedule |

### Orchestrator sequence notes

Historical `daily_ingest.py` narrative (still reflected in defects below):

1. Update current rosters.
2. Fetch current-season player game logs.
3. Populate schedule/results.
4. Fetch future games from NBA CDN.
5. Refresh `LeagueDashTeamStats` across measures/modes/season types.
6. Refresh current-season `LeagueDashPlayerStats`.
7. Clear and rebuild player streaks; clean redundant thresholds.

The daily entry points validate canonical `YYYY-YY` overrides and otherwise use schedule-aware season selection. During July-September, ingestion stays on the latest known season until the upcoming season appears in the future schedule. Remaining hard-coded defaults in legacy routes/services are tracked separately.

Historical `--date` is intentionally accepted only with `--validate-only`. The current replacement-style derived tables are not point-in-time safe, so daily calculation rejects a historical date instead of labelling current inputs as historical.

After a successful daily job:

* invalidate date/current-season/team/standings/matchup cache namespaces;
* warm only today's shared views and matchups;
* confirm the job log reports every required task completed;
* spot-check the latest completed game in schedule, team stats, and player logs.

### Validation

`daily_ingest.py` runs `scripts/validate_daily_data.py` unless `--skip-validate` is set.

```bash
python scripts/validate_daily_data.py
python scripts/validate_daily_data.py --season 2025-26 --date 2026-03-03
python scripts/validate_daily_data.py --offline
python daily_ingest.py --validate-only
```

Critical failures (schedule gaps, W/L mismatches, orphan gamelogs, impossible stats) exit with code 1. Warnings (sparse odds/injury, empty derived tables in offseason) do not fail the run.

Durable status is in `ingestion_runs` and `ingestion_task_runs`. `data/last_ingest_success.json` advances only for a full, non-partial run whose validation passed; a failed or partial run preserves the previous published marker. `data/last_validation.json` remains the validator's file output.

Useful operational query:

```sql
SELECT run_id, run_type, season, target_date, status, validation_status,
       started_at, finished_at, error_class, error_summary
FROM ingestion_runs
ORDER BY started_at DESC
LIMIT 20;
```

### Scheduling

**Windows Task Scheduler** (recommended for local/dev hosts):

1. Create a daily task.
2. Program: `powershell.exe`
3. Arguments: `-ExecutionPolicy Bypass -File C:\Code\sports_analytics\scripts\run_daily_ingest.ps1` (append `-Proxy` if needed)
4. Start in: project root
5. Confirm `data\last_ingest_success.json` after the first run

**Linux cron:**

```bash
0 6 * * * cd /path/to/sports_analytics && source venv/bin/activate && python daily_ingest.py >> /var/log/nba_ingest.log 2>&1
```

On AWS/EC2, scripts typically force `MAX_WORKERS=1`. Prefer environment file + lock/timeout once available.

### Preseason / season-open checklist

Short dry-run before automating the next season:

1. Connectivity — activate venv, confirm `DATABASE_URL`, run `python scripts/verify_proxy_setup.py` (or `--local`).
2. Season string — `python -c "from app.utils.season_utils import get_current_season; print(get_current_season())"` (October+ → new season).
3. Light fetch — `python daily_fetch.py --tasks players rosters schedule future --local` (add `--season` once CDN has it).
4. Validate a known completed slate — `python scripts/validate_daily_data.py --season 2025-26 --date 2026-03-03`.
5. Full quiet-day run — `python daily_ingest.py --local`, then confirm success/validation markers.
6. Schedule `scripts/run_daily_ingest.ps1` (or cron) only after the quiet-day run succeeds.

Out of scope for this checklist: MLB (`mlb_temp/`), schema redesign.

## Idempotency behavior

| Dataset | Current conflict behavior | Required policy |
| --- | --- | --- |
| players | update all mutable fields | keep |
| statistics | update season aggregate | keep |
| roster | canonical team-player-season upsert plus requested-season reconciliation | empty/unresolved payload fails closed; previous seasons are untouched |
| game schedule | update result/score and metadata | keep |
| player game logs | atomic update of mutable box-score fields | canonical IDs/seasons; missing values remain NULL; schedule/player FKs enforced |
| team game stats | update box score and date | keep; fix plus/minus source |
| player season stats | update aggregate/ranks | keep; resolve traded-player grain |
| team season stats | dynamic update of supplied columns | keep with column allowlist and transaction validation |
| player streaks | clear then insert `DO NOTHING` | acceptable snapshot behavior; use one transaction/staging swap |
| versioned player snapshots | append with natural-key upsert by cutoff/version | keep; all four metric families publish in one transaction and readers pin one anchor cutoff |
| versioned team/game snapshots | append with natural-key upsert by game/team/cutoff/version | keep; team features and paired environments publish in one transaction from pre-cutoff game facts |
| external dataset manifests | append once per source/dataset/version/hash/transformation | exact metadata reruns are no-ops; conflicting immutable metadata fails closed; no source rows are imported |
| Stat Surge availability staging | append once per manifest/logical source row/parser | exact reruns write zero rows; corrected files require a new manifest; invalid rows enter the rejection ledger |
| Kaggle source games | append once per manifest/logical source row/parser | full file preserved; exact reruns write zero; structural pair failures enter rejection ledger |
| Kaggle historical markets | append once per manifest/logical source row/parser | all three files commit atomically; anomalies are separate; exact pack rerun writes zero |

### Phase 2 player snapshot operations

The default `daily_calculate.py` task list publishes `player_snapshots` after
the legacy player calculations. Legacy tables remain latest-state compatibility
projections; historical serving and modeling must use the v2 tables.

Preview a bounded historical range without writing:

```bash
python scripts/backfill_player_snapshots.py --season 2024-25 --from-date 2024-10-22 --to-date 2024-11-05 --calculation-version player-v2.1 --dry-run
```

After explicit approval, apply the same bounded range with `--apply`. Resume an
interrupted range with `--resume-after YYYY-MM-DD`. The command processes only
scheduled slate dates and refuses more than 31 dates unless `--max-dates` is
raised explicitly. Never run an unreviewed production backfill.

### Phase 3 team/game snapshot operations

The default calculation order publishes `team_snapshots` after schedule factors
and before the legacy team daily compatibility projections. The publisher
derives both team perspectives and the paired game environment from local
`team_game_stats` and `game_schedule` rows strictly before the 10:00 ET target
slate cutoff. It never reads `league_dash_team_stats` for historical features.

Preview one bounded range without writing:

```bash
python scripts/backfill_team_game_snapshots.py --season 2025-26 --from-date 2025-10-21 --to-date 2025-11-10 --calculation-version team-v2.1 --dry-run
```

After reviewing the per-date team/game counts, rerun with `--apply`. Use
`--resume-after YYYY-MM-DD` after interruption, `--team-id` for a bounded team
feature repair, and `--window-size` only when intentionally publishing the same
calculation version at another declared window. The default limit is 31
scheduled slate dates. A team-only run does not publish game environments
because the reciprocal team snapshot is intentionally absent.

Rerunning the same natural keys is idempotent. A correction or formula/source
availability change that alters already published meaning must use a new
`--calculation-version`. Validate an applied date with
`scripts/validate_daily_data.py --offline`; `team_snapshot_integrity` requires
two team perspectives and one environment per Regular Season game, pregame
cutoffs, and no source date on or after the target slate.

### Bounded historical schedule-result reconciliation

When `team_game_stats` contains a complete final team pair but the matching
`game_schedule.result` values are null, repair the redundant schedule result
locally instead of requiring another NBA CDN download. Preview first:

```bash
python scripts/reconcile_schedule_results.py --season 2025-26 --from-date 2026-03-03 --to-date 2026-04-12 --dry-run
```

The command requires two reciprocal schedule rows, two reciprocal team-game
rows, matching season/date/team IDs, one W and one L, non-tied numeric scores,
and no conflicting stored score. Legacy empty score sentinels (`0-0`, blank,
or `-`) are treated as missing and replaced with the validated home-away score.
It only plans rows whose schedule results are both null. Any ambiguous game
blocks the entire range. After reviewing a clean plan, rerun with `--apply`; the write is transactional and records an
`ingestion_runs` entry with provider `team_game_stats`.

The default safety bounds are 62 inclusive calendar days and 500 games. Split
larger repairs or explicitly raise `--max-days` / `--max-games`. Do not overlap
this command with schedule ingestion or snapshot publication. Validate the
repaired target dates before rerunning dependent player snapshots.

The normal `daily_fetch.py` task order now runs the same fail-closed service as
critical task `schedule_reconcile` immediately after `teamstats` and before
`gamelogs`. It scans only Regular Season games that have local team-game facts;
future games without facts are ignored. A partial or conflicting final pair
fails the fetch phase and blocks downstream calculations. The bounded CLI
remains the explicit recovery/backfill interface, not the primary daily fix.

## External dataset manifest registration

External data starts with a manifest-only safety gate. Files under
`dataSource/archive` are temporary, ignored working copies; retain the durable
source copy elsewhere and record that location. Registration hashes and
inspects one artifact, records provenance and licensing state, and creates no
staging, canonical, feature, or serving rows.

Preview each artifact before any database write:

```bash
python scripts/register_external_dataset.py --file dataSource/archive/<file>.csv --source-name <source> --dataset-name <dataset> --dataset-version <version> --storage-locator "<durable-private-locator>" --license-status needs_review --commercial-use-status unknown --dry-run
```

The JSON preview includes byte size, SHA-256, media type, CSV header and logical
record count where applicable, blank rows, and row-width mismatches. A PDF or
other non-CSV artifact is hashed and registered without inventing a row count.
Resolve unexpected shape findings and confirm the durable locator, source URL,
download timestamp precision, license identifier/status, and commercial-use
status before changing only the final flag to `--apply`.

An apply run acquires the distinct external-manifest advisory lock and writes
an `ingestion_runs` record linked from the new manifest. Repeating identical
metadata is idempotent. Reusing the same
source/dataset/version/hash/transformation key with different immutable
metadata fails closed. Register multiple files as separate commands; never
delete, transform, or import the source file as part of this step. A license
status of `needs_review` permits provenance registration only and does not
authorize analytical, public, or commercial use.

### Stat Surge availability staging

Use only the approved manifest and its hash-matching preserved artifact. Preview
the complete parser partition without database access:

```bash
python scripts/import_statsurge_availability.py --manifest-id <manifest-uuid> --file "<durable-path>/Injury Database - Oct 2021 - June 2024.csv" --dry-run
```

The preview must reconcile `source_row_count = staged_row_count +
rejected_row_count` and report the expected status/date coverage. Apply the same
command with `--apply` only after reviewing any rejection reasons. Apply uses a
distinct advisory lock, verifies source/dataset identity, SHA-256, manifest row
count, public approval, and commercial-use permission, then writes the staged
and rejected partitions in one transaction.

An exact rerun records a successful operational run with zero rows written.
Changed file bytes must be registered as a new manifest instead of overwriting
the existing staging partition. Staging deliberately leaves player/team/game
IDs unresolved and does not invent an exact publication timestamp. Do not use
these rows as strict pregame features until identity and early-tip cutoff checks
are implemented in a separate promotion phase.

After staging, reconcile identities without fuzzy matching:

```bash
python scripts/reconcile_statsurge_identities.py --manifest-id <manifest-uuid> --dry-run --report docs/STATSURGE_IDENTITY_RECONCILIATION_REPORT.md
python scripts/reconcile_statsurge_identities.py --manifest-id <manifest-uuid> --apply --report docs/STATSURGE_IDENTITY_RECONCILIATION_REPORT.md
```

The apply command reuses the Stat Surge staging advisory lock and changes only
resolved identity fields, identity/completeness/cutoff states, and versioned
resolution evidence. It never changes `raw_values` or promotes availability.
Exact team names plus one reviewed Clippers alias, strict `AAA@BBB` date/team
pairs, and exactly one normalized player candidate are required. All rows keep
`cutoff_status = unknown`; unresolved names and cancelled/postponed games stay
queryable. The validated first apply changed 35,522 rows, and its exact rerun
changed zero.

### Kaggle game and market staging

Stage and verify games before markets:

```bash
python scripts/import_kaggle_games.py --manifest-id <game-manifest> --file "<durable-path>/nba_games_all.csv" --dry-run
python scripts/import_kaggle_games.py --manifest-id <game-manifest> --file "<durable-path>/nba_games_all.csv" --apply
```

The importer preserves the entire source file and marks, rather than deletes,
pre-2006, unsupported event types, incomplete results, and partial 2018-19
rows. Validate two reciprocal rows per game before continuing.

The three markets are one atomic command:

```bash
python scripts/import_kaggle_markets.py --game-manifest-id <game-manifest> --moneyline-manifest-id <moneyline-manifest> --moneyline-file "<durable-path>/nba_betting_money_line.csv" --spread-manifest-id <spread-manifest> --spread-file "<durable-path>/nba_betting_spread.csv" --totals-manifest-id <totals-manifest> --totals-file "<durable-path>/nba_betting_totals.csv" --dry-run
```

Review anomaly counts, then rerun with `--apply`. Apply verifies all four
manifests, hashes, row counts, permissions, and every market game/team pair
against `stg_kaggle_games`; it commits moneyline, spread, totals, anomalies, and
parser rejections together. A run is `partial` when declared semantic anomalies
are quarantined even though validation passes. Exact reruns must write zero.
Do not infer opening/closing timing, silently force inverse lines, or treat a
missing canonical Yuno playoff game as an invalid external row.

Generate the exact market identity report after schedule reconciliation:

```bash
python scripts/reconcile_kaggle_markets.py --game-manifest-id <game-manifest> --moneyline-manifest-id <moneyline-manifest> --spread-manifest-id <spread-manifest> --totals-manifest-id <totals-manifest> --report docs/KAGGLE_MARKET_RECONCILIATION_REPORT.md
```

This command is read-only. It validates manifest/parser scope, exact game/team/
opponent/date/season/type identity, away-selection semantics, canonical-missing
coverage, and source-season coverage. It does not update staging status or
promote market rows. Historical timing remains unknown.

Reconcile staged games read-only before changing canonical coverage:

```bash
python scripts/reconcile_kaggle_games.py --game-manifest-id <game-manifest> --player-game-manifest-id <player-game-manifest> --player-game-file "<durable-path>/nba_player_game.csv" --report docs/KAGGLE_GAME_RECONCILIATION_REPORT.md
```

The reconciliation uses exact NBA game IDs and reciprocal team pairs only. It
does not fuzzy-match, repair, or write canonical rows. Review conflicts,
missing coverage, and unanimous date-repair evidence before promotion.

Promote only the validated missing playoff scope after applying Alembic head:

```bash
python scripts/promote_kaggle_playoff_schedules.py --manifest-id <game-manifest> --dry-run
python scripts/promote_kaggle_playoff_schedules.py --manifest-id <game-manifest> --apply
```

Apply shares the daily NBA pipeline advisory lock and inserts two reciprocal
rows per missing final playoff game in one transaction. It requires parsed
dates, known teams, W/L and numeric-score agreement, exact manifest licensing,
and complete row-level lineage. The first validated run inserted 838 games /
1,676 rows; its exact rerun inserted and updated zero domain rows. Do not expand
this command to regular-season games or market observations without a new
reviewed scope and reconciliation result.

## Rate limits and concurrency

* Shared fetch utility limiter: 30 requests per 25 seconds.
* Streak fetch limiter: 15 requests per 30 seconds, batches of three, plus sleeps.
* Retries: commonly three attempts; timeouts usually wait five seconds.
* `MAX_WORKERS` is configuration-driven; `daily_ingest.py` forces `1` when it detects EC2.

The NBA API does not publish a dependable application quota for this usage pattern. Treat these values as observed safeguards, not guarantees. Prefer endpoint-level batching and avoid nested requests: current team-game backfill calls `TeamGameLog` once to list games and again for every game, which is unnecessarily expensive.

## Failure recovery

1. Inspect the latest `ingestion_runs` row and its `ingestion_task_runs`; capture the failed task, season/team/player IDs, exception type, and last successful run.
2. Verify network path (`direct`, IPv6, or approved proxy) before retrying. See [PROXY.md](PROXY.md).
3. Check database connectivity and whether the connection pool is exhausted.
4. Retry only the failed unit/season, relying on upserts.
5. If a legacy job cleared a latest-state table before failing, rerun it immediately or restore from backup. A failed v2 player publication rolls back all four families and leaves the last complete anchor intact.
6. Do not warm caches after a partial database refresh.
7. Run invariants and invalidate affected cache namespaces after recovery.

For a failed external-manifest apply, verify that the artifact is unchanged,
correct the metadata or database issue, and rerun the same command. Do not
alter the file to make its hash match an existing manifest.

Useful logs:

* `daily_ingest.log`
* `daily_fetch.log`
* `daily_calculate.log`
* `ingest.log`
* `/var/log/yunoball-daily-ingest.log`
* system cron mail/logs, depending on Ubuntu configuration

Common operational notes:

* Missing `DATABASE_URL` — set it in `.env` or the process environment.
* "No games found" / 0 records — normal in offseason, on empty slates, or when data is already present.
* Long runs — `injury` batch boxscore backfills can take 30–60+ minutes; exclude during development.

## Known implementation defects to fix before trusting unattended ingestion

* Hard-coded past season in the daily task and several services.
* `PlayerStreaks` closes a pooled connection and then attempts to release it.
* Provider minutes remain stored as text and require a future bounded numeric migration.
* Current-season roster membership has season grain, not effective-date transfer history.
* Team-game `plus_minus` is always zero.
* Player-stat expected-field list has a missing comma between `wnba_fantasy_pts` and `gp_rank`.
* Dynamic team-stat SQL lacks a strict identifier allowlist.
* Cron wrappers still need a timeout, alerting, and an explicit environment file; command-level database locking is implemented.

## Historical analytics rollout

The bounded historical rollout sequence, eligibility gates, estimates,
checkpoint/resume procedure, cache handling, and rollback plan are maintained in
[`ANALYTICS_ROLLOUT_RUNBOOK.md`](ANALYTICS_ROLLOUT_RUNBOOK.md).
