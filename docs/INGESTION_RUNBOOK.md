# Yuno Ball Ingestion Runbook

Status: canonical operating procedure plus documented gaps
Reviewed: 2026-10-16 against the live database profile at Alembic head `i5j6k7l8m9n0`, `ingest_data.py`, `daily_ingest.py`, `daily_fetch.py`, `daily_calculate.py`, forward collector utilities, and scheduling wrappers. The scheduling examples below are not staging verification or approved production automation.

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
| `scripts/collect_official_injury_reports.py` | Official NBA injury-report raw documents | discovers one Eastern report date from the season page, downloads at most 96 allowlisted PDFs, and on apply writes content-addressed raw files plus immutable document/run metadata; no parsing or public consumer |
| `scripts/parse_official_injury_reports.py` | Official NBA injury-report observation parser | reads durable PDFs by season/date range, preserves parser lineage and unresolved source names, supports bounded dry-run/apply, and records parse failures; parsed rows feed the read-only daily slate adapter and no model consumer |
| `scripts/repair_schedule_coverage.py` | Canonical historical schedule coverage repair | uses one explicit-season `ScheduleLeagueV2` request, validates exact reciprocal rows, and supports bounded dry-run/apply; CDN is an explicit validated fallback |
| `scripts/audit_legacy_redundancy.py` | Read-only legacy/canonical table inventory | reports table grain, row/season coverage, canonical overlap, and preservation decisions; never writes or deletes |
| `scripts/reconcile_official_availability_identities.py` | Official injury observation identity reconciliation | exact report-date/matchup game/team repair with versioned run lineage; player-name resolution is a separate opt-in gate and unresolved rows remain nullable |
| `scripts/import_kaggle_games.py` | Kaggle source game staging | stages all paired game/team rows with source missingness and promotion eligibility; canonical reconciliation is deferred |
| `scripts/import_kaggle_markets.py` | Kaggle historical market staging | atomically stages registered moneyline/spread/totals against verified source games and quarantines semantic anomalies |
| `app/services/nba_live_market_observation_adapter.py` | bounded game-market adapter | converts one NBA live-odds response into immutable moneyline/spread/total registration payloads; no network call or database write |
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
5. Populate `game_schedule` for each desired season. For historical gaps, use `ScheduleLeagueV2` through `scripts/repair_schedule_coverage.py`; repair Play-In/Playoffs coverage before injury identity work.
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
| `player_facts` | Completed-game Traditional then Advanced V3 canonical facts | critical; bounded at 25 games; C5-gated |
| `leagueteam` | League-wide team stats | critical |
| `leagueplayer` | League-wide player stats | critical |
| `injury` | Injury/status from boxscores | non-critical; slow |
| `odds` | Today's betting odds | non-critical |

If any critical fetch fails, calculations are skipped unless `--force-calc` is set.

The `teamstats` task is fail-closed at the season boundary. Each team fetch must
return an explicit success result with processed rows; empty payloads, missing
schedule opponents, and transport/provider exceptions are failures. The season
task raises with the failed team IDs and errors instead of allowing a partial
team-stat load to be reported as successful. Validate database coverage after a
retry before continuing to reconciliation or player-fact ingestion.

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

For the descriptive Daily/history beta, the production schedule is not
approved until its exact definition has passed in staging. It must use a
protected environment file, one service identity, the managed PostgreSQL
target, private Redis/network policy, a hard runtime limit, captured exit code
and logs, and alerts for non-zero/timeout/missing runs. Keep the database
advisory lock enabled and treat exit code `3` as an operational collision that
requires investigation. Monitor `ingestion_runs`/`ingestion_task_runs` and the
age of the last successful validated run; the host-local success marker is
secondary evidence only. Disable every personal-PC schedule before enabling a
managed-environment writer. See the migration, monitoring, and evidence gates
in [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md).

### Preseason / season-open checklist

Short dry-run before automating the next season:

1. Connectivity — activate venv, confirm `DATABASE_URL`, run `python scripts/verify_proxy_setup.py` (or `--local`).
2. Season string — `python -c "from app.utils.season_utils import get_current_season; print(get_current_season())"` (October+ → new season).
3. Confirm the released schedule is available, then run the light fetch for the explicit current season: `python daily_fetch.py --tasks players rosters schedule future --season <current-season> --local`.
4. Validate reciprocal schedule rows, season/type, date bounds, and any NBA Cup games whose final opponents are initially TBD.
5. Validate a known completed slate with `python scripts/validate_daily_data.py --season <current-season> --date <completed-date>`.
6. Full quiet-day run — `python daily_ingest.py --local`, then confirm success/validation markers.
7. Schedule `scripts/run_daily_ingest.ps1` (or cron) only after the quiet-day run succeeds.

The 2026-27 schedule was officially released on August 13, 2026. The local
checkpoint now contains 2,400 identified Regular Season schedule rows for
1,200 games, plus 582 roster rows across all 30 teams. Seven unresolved
NBA Cup/TBD placeholders remain intentionally excluded until their opponents
are identified; the next schedule refresh must re-run the inventory rather
than inventing reciprocal rows.

### Current-season canonical V3 bridge

The bounded Traditional and Advanced V3 collectors remain explicit historical
tools capped at 25 games. The `player_facts` daily task now provides the
current-season bridge with this order:

1. identify newly completed, eligible games;
2. collect Traditional V3 and publish its validated canonical projection;
3. collect Advanced V3 for the same game set;
4. run reconciliation and no-op replay checks;
5. publish the validated role-history projection;
6. publish the durable run/task result without waiting on historical backfills.

The task selects only completed reciprocal games with paired team stats that
are missing Traditional or Advanced canonical facts. It processes at most 25
games per batch, keeps external calls outside database transactions, resolves
missing player parents, and fails closed unless C5 reconciliation passes. C5
now runs against the same uncommitted batch session, so a failed reconciliation
rolls the facts back instead of leaving a partially published batch. A
quiet-day run returns `no_op` when there are no eligible pending games. A live
completed-game smoke proof remains before launch; until that proof exists,
the existing PlayerGameLogs path remains the operational fallback.

For the forward H1 role-baseline path, each newly collected canonical fact must
retain its collection-time `data_available_at` alongside `retrieved_at`. That
timestamp is eligible for a future game's strict pregame cutoff only when it is
at or before the exact scheduled tipoff; historical backfill timestamps must not
be treated as if they were original publication times. Date-only schedule rows
cannot produce a strict pregame role baseline. Audit readiness with:

```bash
python scripts/audit_program_h_source_timing.py --season 2025-26 --season-type "Regular Season"
```

The audit is read-only. A failed timing audit leaves H1 baselines unknown and
does not authorize Daily or Rotation Shock consumption.
Inspect `source_event_order` as well as target cutoff coverage: availability
before an exact source-game tipoff fails readiness, while date-only or missing
source schedules are reported as unverifiable. At-or-after-tipoff timestamps
alone do not establish source publication provenance or forward calibration.

After a successful C5 reconciliation, the daily bridge now upserts the
corresponding deterministic `player_role_history` rows in the same database
transaction. This keeps forward role history current without making the
uncalibrated pregame baseline a Daily dependency. If reconciliation fails, the
role-history projection is not advanced.

Until the completed-game smoke proof passes, the existing PlayerGameLogs daily
path remains a deliberate compatibility fallback. Program E metrics must use
an explicit input allowlist. `team_game_stats.plus_minus` is now available as
a nullable derived value, but only when the exact reciprocal team rows and
both points values are present; it is never zero-filled. The stale single-game
fetch helper no longer passes an invalid provider field into the ORM. The 2024-25 team-value repair is complete, so approved team-based
Program E research may use the repaired 2024-25 snapshots; it must still
honor each snapshot's completeness and cutoff state.

Out of scope for this checklist: MLB (`mlb_temp/`), schema redesign.

## Idempotency behavior

| Dataset | Current conflict behavior | Required policy |
| --- | --- | --- |
| players | update all mutable fields | keep |
| statistics | update season aggregate | keep |
| roster | canonical team-player-season upsert plus requested-season reconciliation | empty/unresolved payload fails closed; previous seasons are untouched |
| game schedule | update result/score and metadata; bounded coverage repair inserts only missing exact reciprocal games | keep; coverage repair is zero-write on exact rerun and fails closed on conflicts |
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

## Program C bounded player-game facts

Program C collectors are manual, explicit-game tools. They are not daily tasks
and each invocation is capped at 25 canonical completed games. Preview
Traditional V3 first:

```bash
python scripts/collect_traditional_player_game_facts.py --game-id <id> [--game-id <id> ...] --max-games <count> --dry-run
```

After reviewing game identities, player/DNP counts, and reciprocal team-point
reconciliation, repeat with `--apply`. The full batch fetches and validates
before one publication transaction. Repeating the exact apply is a no-op;
source or parser corrections append immutable revisions and update only the
canonical projection.

Advanced V3 requires Traditional canonical facts for the same games:

```bash
python scripts/collect_advanced_player_game_facts.py --game-id <id> [--game-id <id> ...] --max-games <count> --dry-run
python scripts/collect_advanced_player_game_facts.py --game-id <id> [--game-id <id> ...] --max-games <count> --apply
python scripts/validate_player_game_facts.py --game-id <id> [--game-id <id> ...] --max-games <count>
```

Advanced publication fails closed unless player/team identity exactly matches
Traditional. The validator is read-only and checks reciprocal schedule
identity, canonical uniqueness, team totals, source parity, correction
lineage, and legacy overlap. Preserve `gamelogs`: migrated consumers read
canonical facts first and use it for uncovered history. Do not schedule a
full-season backfill or remove older tables until historical coverage and the
analytics-roadmap redundancy audit are complete.

Before selecting a batch, generate the read-only coverage inventory:

```bash
python scripts/generate_player_game_fact_coverage.py --season 2025-26 --season-type "Regular Season" --max-batch-size 25 --summary
```

The inventory is the source of truth for eligible completed games and emits
deterministic Traditional/Advanced batch lists. A timeout or provider failure
before the collector's publication transaction leaves the whole batch
unpublished; resume from the same batch only after the access path is healthy.

The preferred operator interface is the deterministic batch runner. It selects
pending game IDs from the inventory, persists the exact manifest in the
ingestion run, fetches Traditional before Advanced, and leaves a replayable run
ID for the no-op proof:

```bash
python scripts/collect_player_game_fact_batch.py --batch 1 --max-games 25 --dry-run
python scripts/collect_player_game_fact_batch.py --batch 1 --max-games 25 --apply
python scripts/collect_player_game_fact_batch.py --replay-run-id <successful-run-id> --max-games 25 --apply
# Optional provider re-fetch instead of the default database-only replay:
python scripts/collect_player_game_fact_batch.py --replay-run-id <successful-run-id> --max-games 25 --network-replay --apply
```

For unattended sequential expansion, use the fail-fast orchestrator. It
recalculates the pending inventory before every iteration, performs one full
Traditional + Advanced network collection per batch, then runs C5 and a
database-only exact-manifest replay. It stops on the first failure. Add
`--preflight-dry-run` for one initial full dry-run; it is not repeated for
every batch. Omit `--max-batches` to continue until no pending batches remain;
use it as a safety cap for a controlled session:

```bash
python scripts/collect_player_game_fact_batches_until_complete.py --max-batches 10 --pause-seconds 2 --preflight-dry-run
```

The orchestrator never skips ahead: each iteration selects the current
pending `--batch 1`. It does not schedule collection or alter legacy tables.

The batch runner resolves any missing player parents through the authoritative
CommonPlayerInfo endpoint before publication. External calls occur outside the
database transaction; publication and C5 reconciliation occur only after the
Traditional/Advanced in-memory identity check passes. A provider timeout or
unresolved player identity fails the batch before fact publication and does not
advance the coverage inventory. C7 uses its own advisory lock and does not hold
the daily-ingestion lock.

Daily `fetch.player_facts` tasks retain a versioned `replay_manifest` in the
durable task details. It records parent run ID, task/attempt IDs, season/type,
endpoint families, distinct batch game IDs, response hashes, and timezone-aware
retrieval timestamps captured immediately after each response returns. The
bounded batch scope is persisted before provider calls. Each game's evidence is
persisted immediately after its endpoint response returns, before parsing or
validation, so a later game, parse, or endpoint failure retains earlier response
hashes and timestamps. Each
batch's fact/revision publication, C5 reconciliation, role-history publication,
and `completed` manifest state commit in one database transaction. A crash
before that transaction leaves the batch pending/collecting; a crash after it
leaves a completed, replayable batch even if the parent task is still running.
Failures preserve prior completed batches and mark the active batch failed;
partial provider evidence remains available for diagnosis but is not replayable.
An inventory `no_op` records no replay manifest and is not replay evidence.

Replay one exact completed batch from a daily task with:

```bash
python scripts/collect_player_game_fact_batch.py --replay-task-id <task-run-id> --batch-number 1 --apply
```

For an explicitly bounded daily capture, run only the player-facts task and
select one exact completed game:

```bash
python daily_fetch.py --tasks player_facts --player-facts-game-id <game-id> --season <current-season>
```

The selector fails closed unless that ID is in the daily completed,
team-stat-eligible inventory. It does not fetch schedule/team stats, skip C5
prerequisites, or widen to other pending games. If the game is already fully
covered, the task records the current Traditional/Advanced response hashes and
requires each response to match before publication; a mismatch leaves a failed
manifest and publishes nothing. Without this option, the normal daily task
continues to process its full pending inventory in bounded batches.

The selected task batch must be uniquely numbered, bounded, completed, and have
matching Traditional/Advanced response hashes and retrieval timestamps. Replay
is database-only by default: it republishes the selected batch's immutable
source revisions, role history, and C5 reconciliation, and must be an exact
no-op. Daily-task replay acquires the shared daily pipeline lock to prevent
overlap with another ingestion writer. `--network-replay` explicitly re-fetches
the provider for only that
selected batch and is a separate operation. The older `--replay-run-id`
continues to accept only the C7 batch-run contract; it does not read daily task
manifests.

Advanced V3 can expose the same player/team key twice when one row is an empty
statistical placeholder and another row contains the played-game statistics.
The adapter keeps the higher-quality row, retains the discarded placeholder in
the selected row's raw provenance, and fails closed when duplicate rows are
ambiguous rather than silently choosing between two populated observations.

Identity resolution remains strict for played or unknown rows. A player who is
present only as a source-listed DNP row may be resolved from CommonPlayerInfo
without an active-season match, such as a G League-only or inactive roster
listing. The DNP fact is retained, the player dimension row carries no claimed
NBA season, and any later played or unknown fact still requires strict season
validation.

The same runner is season-agnostic. For the approved 2024-25 Regular Season
expansion, use:

```bash
python scripts/collect_player_game_fact_batches_until_complete.py \
  --season 2024-25 --season-type "Regular Season" \
  --max-games 25 --pause-seconds 2 --preflight-dry-run
```

This performs one preflight dry-run, then one Traditional + Advanced network
collection per pending batch, C5 reconciliation, and a database-only replay
proof. `--max-batches 10` is an optional safety cap; omit it only when the
operator intentionally wants the runner to continue until the requested
season has no pending batches. The season must be rechecked with the read-only
coverage inventory after completion.

### Historical C7 completion checkpoint — 2026-09-03

The bounded C7 runner has completed the Regular Season fact foundation for
2020-21 through 2025-26. Final canonical Traditional/Advanced player-fact
counts are 28,859/28,859 for 2020-21, 31,321/31,321 for 2021-22,
31,542/31,542 for 2022-23, 32,385/32,385 for 2023-24, 32,515/32,515 for
2024-25, and 32,179/32,179 for 2025-26. The first season uses 1,080 eligible
games; each later season uses 1,230. Final inventories report zero missing or
blocked games, with C5 reconciliation and an exact database-only replay after
each reviewed batch. `gamelogs` and other legacy tables remain intact.

The team-stat fetcher now fails closed if any requested team returns an empty,
incomplete, or exception result. During the 2020-21 expansion, three teams
needed narrow retries after transient `ZeroDivisionError` responses; each
retry produced 72 rows and reciprocal coverage was rechecked before player
facts were collected. Future historical runs should use this same pattern:
bounded retries, fail-closed validation, then a fresh coverage inventory before
downstream fact collection.

For a targeted identity repair or a new database, use the same authoritative
resolver directly:

```bash
python scripts/resolve_player_identity.py --player-id <nba-player-id> --season 2025-26
```

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

## Program B market-observation contract

The append-only market boundary is represented by
`market_observation_headers` plus `market_observation_selections`. Register one
header and its selections through `MarketObservationService` inside the
caller-owned ingestion transaction. Historical static rows must link to an
`external_dataset_imports` artifact and declare `timing_precision = unknown`;
forward rows must declare timing precision and an observed/provider timestamp.
The registration key is `(source_name, source_observation_key,
parser_version)` and conflicting replays fail closed rather than overwrite.

This is a storage contract plus an unapproved bounded collector. No provider
is approved for scheduled collection, no historical market rows are promoted,
and the mutable `game_odds` path is not a source for immutable history. The
collector must pass a successful live dry-run and source licensing, schema,
timestamp precision, cost, and bounded replay checks before `--apply` or
scheduling is enabled. See
`docs/research/PROGRAM_B_GAME_ODDS_PROVIDER_EVALUATION.md` for the current
blocked-provider result.

## Official injury-report document collection

Operational dependency: this collector can preserve and parse injury reports
before canonical game coverage is complete, but identity repair must wait for
the matching `game_schedule` rows. Do not treat unresolved `game_id` or
`player_id` as a status. After the identity reconciliation handoff, the
read-only daily slate adapter may expose observations using canonical game IDs
and a strict scheduled-tipoff publication cutoff; unresolved rows remain
partial evidence and missing rows remain unknown.

This is the first Program B forward-collector boundary. Configure a durable
archive outside the repository, for example under the project-owner archive,
without placing raw PDFs in Git:

```powershell
$env:YUNOBALL_INJURY_REPORT_ARCHIVE_DIR = 'C:\AI\GPT\Project Resources\YunoBall\archive'
python scripts/collect_official_injury_reports.py --report-date YYYY-MM-DD --dry-run
python scripts/collect_official_injury_reports.py --report-date YYYY-MM-DD --apply
```

The default season comes from the shared season helper, the default date is the
current Eastern date, and every report date is bounded to at most 96 documents.
The Python CLI defaults to the explicitly requested date; use
`--lookback-days N` (bounded to seven) to inspect prior Eastern dates in
oldest-to-newest order. The Windows wrapper defaults to a seven-day lookback so
a laptop that was asleep or offline can catch up recent publication dates when
it next runs. Use
`--max-documents` to reduce the scope further and `--timeout-seconds` to bound
each HTTP attempt. When Python requests times out against the official CDN, use
`--download-transport curl` to select the bounded system-curl path directly;
that path pins IPv4 and HTTP/1.1 because the CDN has timed out intermittently
under automatic protocol selection, and it retries bounded transport failures
before returning a failed document. PDF retrieval uses the canonical query-free
official URL and does not add browser identity headers or cache-busting query
parameters, because the retained CDN can stall valid reports when those are
added. `auto` tries requests and then curl. Use a timezone-aware
`--published-at-or-before` cutoff to intentionally lag newly listed documents
when the CDN has not propagated them yet. `--dry-run` performs discovery,
download, PDF signature/hash, and HTTP metadata validation in memory with no
file or database writes. `--apply` acquires the official-document advisory lock,
writes content-addressed files atomically, then registers all metadata rows in
one database transaction linked to an ingestion run.

On apply, discovery is persisted before PDF retrieval. Each official URL has
one row in `availability_report_download_attempts`; direct filename probes
persist every candidate before attempting it. Only unresolved rows whose
`next_retry_at` is due are attempted by the forward queue. A transient failure
records its bounded error and becomes eligible again after two hours by default
(`--retry-interval-hours 2`).
A later run retries it automatically, while successful URLs are skipped. Run
the collector every two hours during the operational publication window; for
cron, use an explicit environment file and an entry such as `0 12-22/2 * * *`
in the server's configured timezone. Confirm the intended timezone before
deployment. The collector itself remains date- and season-safe and does not
silently abandon a URL.
Pending reports older than four hours are reported through `overdue_count`,
make the ingestion run partial, and cause a non-zero process exit for scheduler
alerting. Override only with the bounded `--freshness-threshold-hours` option.

On Windows Task Scheduler, invoke
`scripts/run_injury_report_collector.ps1` with `powershell.exe -NoProfile
-ExecutionPolicy Bypass -File ...`; it uses the repository virtualenv, requires
the durable archive root, and preserves the collector exit code. Configure the
task to repeat every two hours only after a manual task run succeeds. In the
Task Scheduler Conditions/Settings, enable **Run task as soon as possible after
a scheduled start is missed**. The wrapper's seven-day lookback then discovers
recent dates again; successful URLs remain skipped and pending/transient URLs
remain retryable through the attempt ledger. A gap longer than seven days still
requires a reviewed direct-CDN backfill because the live page is not a complete
historical manifest.

The season page is only the current/live discovery surface and is not a
historical manifest. For retained CDN documents whose links have rotated off
that page, use the separate bounded filename probe. Dry-run generates candidate
URLs without network or writes; apply confirms each candidate through the
official PDF provider and persists only validated PDFs. For the bounded
historical injury filename probe specifically, a validated CDN 403/404 absence
response is
retained as a terminal `not_found` candidate rather than silently disappearing;
this rule does not classify a 403 from a season page, schedule endpoint, or
other provider as absence;
transient CDN failures are retryable and make the run partial so the same date
chunk can be replayed:

```powershell
.\scripts\run_injury_report_backfill.ps1 -StartDate 2026-03-03 -EndDate 2026-03-03 -DryRun
.\scripts\run_injury_report_backfill.ps1 -StartDate 2026-03-03 -EndDate 2026-03-03 -ArchiveRoot 'C:\AI\GPT\Project Resources\YunoBall\archive'
```

The default candidate window is 12:00 through 23:45 Eastern at 15-minute
intervals. The provider maps legacy dates to hourly filenames and newer dates
to 15-minute filenames, so duplicate legacy candidates are removed before any
network request. A run is limited to seven dates by default and can never
exceed 31 dates / 1,488 candidates. Backfill a season in reviewed date chunks;
do not schedule an unbounded year scan. Use `-StartTime` and `-EndTime` when
known publication hours can safely reduce probes. Historical probes deliberately
default to a five-second timeout and zero internal curl retries so nonexistent
or stalled candidates cannot hold a date chunk for minutes; progress is printed
for every candidate and a transient failure is retried by replaying the bounded
chunk.
When direct CDN retrieval returns zero bytes, the Windows historical launcher
supports `-UseProxy`; it enables the configured approved proxy only for that
invocation, and both requests and curl then use the same route. Do not enable
it implicitly or copy proxy credentials into a task argument or source file.

An exact URL/hash rerun writes zero document rows. Changed bytes at the same URL
create a retained revision. Failed downloads make the run partial, persist
their next retry time, and remain retryable; confirmed historical filename-probe
403/404 absence responses remain queryable without being treated as transient
failures; either dry-run or apply exits
non-zero when an attempted download fails. A run with no due URLs succeeds with
zero writes. This
command does not resolve player identities, derive transitions, update
`player_game_status`, publish features, invalidate caches, or change routes.

After raw documents are present, parse them in season order with a bounded
document count. Start with `2024-25`, inspect the result, then run `2025-26`:

```powershell
python scripts/parse_official_injury_reports.py --season 2024-25 --dry-run
python scripts/parse_official_injury_reports.py --season 2024-25 --apply
python scripts/parse_official_injury_reports.py --season 2025-26 --dry-run
python scripts/parse_official_injury_reports.py --season 2025-26 --apply
```

Use `--start-date`, `--end-date`, and `--max-documents` for reviewed chunks.
An exact parser rerun writes zero new observation rows; a new parser version
retains a separate lineage rather than silently overwriting an earlier parse.
The parser preserves raw source names and leaves unresolved IDs `NULL`.
`NOT YET SUBMITTED` is stored in `team_report_submission_status`, not as a
player status. The daily slate adapter preserves these team-level states and
does not convert them into player health or availability. This boundary does
not publish availability as model features.

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
* `team_game_stats.plus_minus` is derived, not fetched from `TeamGameLog`.
  `TeamGameStatsORM` refreshes it after single-row and bulk writes, and the
  `h4i5j6k7l8` migration backfills complete reciprocal pairs. Never use NULL as
  zero and never publish the field without checking pair completeness.

* Starter evidence has two explicit paths: the reviewed Traditional V2 trial
  and the Live BoxScore adapter (`collect_program_e_starter_evidence.py
  --source live_boxscore`). Live BoxScore's explicit `starter="1"` is
  promotable; missing or non-starter flags remain `unknown`. V3 player facts
  still do not infer starter status from minutes or participation. The
  collector prefers the proxy-aware CDN provider and rotates bounded attempts;
  when the CDN transport fails or returns no explicit starters, the reviewed
  Traditional V2 path may be used when
  `STARTER_EVIDENCE_FALLBACK_SOURCE=traditional_v2` (the default). The
  fallback retains its own source/parser provenance and still fails closed if
  V2 has no explicit starter positions. Live CDN failures do not create Live
  evidence.

* The daily pipeline now runs `starter_evidence` after canonical
  `player_facts`. It selects completed reciprocal games that lack complete
  starter evidence from either approved source, processes at most 25 games per
  run, and records explicit starter/unknown rows under the parent ingestion
  run. It is operationally non-critical: a source outage must not block the
  core box-score pipeline.
* Player-stat expected-field list has a missing comma between `wnba_fantasy_pts` and `gp_rank`.
* Dynamic team-stat SQL lacks a strict identifier allowlist.
* Cron wrappers still need a timeout, alerting, and an explicit environment file; command-level database locking is implemented.

## Historical analytics rollout

The bounded historical rollout sequence, eligibility gates, estimates,
checkpoint/resume procedure, cache handling, and rollback plan are maintained in
[`ANALYTICS_ROLLOUT_RUNBOOK.md`](ANALYTICS_ROLLOUT_RUNBOOK.md).
