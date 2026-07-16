# Yuno Ball Source Catalog

Status: canonical inventory of external data sources feeding Yuno Ball
Reviewed: 2026-07-15 against fetch utilities, daily pipeline, and `DATA_DICTIONARY.md`.

This catalog describes **where data comes from**, not what is currently populated.
Use `DATABASE_PROFILE.md` for live coverage.

## Conventions

* Refresh cadence is intended production behavior; local/dev may run ad hoc.
* Latency is expected wall time for a healthy path (direct or approved proxy), not a SLA.
* Failure behavior is what operators should expect today.

## Sources

| Source | Endpoint / module | Grain | Refresh cadence | Historical availability | Expected latency | Owner | Failure behavior |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NBA static players | `nba_api.stats.static.players` + `CommonPlayerInfo` via `player_fetcher` | one player | weekly / discovery; also daily `players` task | career identity; `available_seasons` text | minutes–tens of minutes for full discovery | ingestion / `daily_fetch.players` | retry with rate limit; skip failed IDs; do not wipe `players` |
| NBA team identity | static / seed team list → `teams` | one team | rare (season verify) | franchise IDs are stable | seconds | ingestion seed | abort if NBA IDs missing; never remapped |
| CommonTeamRoster | `CommonTeamRoster` via roster fetch | player-team-season | daily in season | canonical requested season; earlier seasons retained | ~30 team calls | `daily_fetch.rosters` | per-team retry; empty/unresolved payload fails closed before requested-season reconciliation |
| LeagueGameFinder / schedule | `LeagueGameFinder` + CDN `scheduleLeagueV2_1.json`; null-result repair may use validated paired `team_game_stats` | team-perspective game `(game_id, team_id)` | daily results + future slate; local reconciliation after team stats and before gamelogs; bounded CLI for recovery | multi-season backfill supported | seconds–minutes per season | `daily_fetch.schedule` / `future` / `schedule_reconcile`; `reconcile_schedule_results.py` | CDN timeout → keep last DB schedule; reconciliation requires reciprocal two-row W/L and score agreement or fails closed before calculations |
| PlayerGameLogs | `PlayerGameLogs` | player-game | daily current season; historical by player/season | box scores for requested seasons | high (hundreds of calls) | `daily_fetch.gamelogs` | rate-limit sleep; atomic mutable-field upsert refreshes corrected boxes without zero-filling missing values |
| TeamGameLog | `TeamGameLog` → `team_game_stats` | team-game | daily / seasonal backfill after schedule; feeds local schedule-result reconciliation | requires schedule FK rows | medium–high | `daily_fetch.teamstats` → `schedule_reconcile` | skip games lacking schedule; partial/conflicting result pairs block reconciliation; plus/minus historically forced 0 |
| LeagueDashPlayerStats | `LeagueDashPlayerStats` | player-season | daily current; seasonal backfill | season aggregates + ranks | medium | `daily_fetch.leagueplayer` | update on conflict; traded-player grain ambiguous |
| LeagueDashTeamStats | `LeagueDashTeamStats` (measures × per-modes × season types) | team-season-season_type | daily current; seasonal backfill | wide endpoint-shaped columns | medium–high | `daily_fetch.leagueteam` | dynamic column allowlist required; partial measure failure should not drop other measures |
| Live box score injuries | Live BoxScore / injury fetcher → `player_game_status` | player-game status | daily for recent/upcoming games | sparse historically; best for recent windows | medium (batched) | `daily_fetch.injury` | offseason empty is OK; warn if completed games have zero status |
| NBA live odds | NBA odds endpoint → `game_odds` | game × sportsbook observation | daily for today's slate | not a historical closing-line archive | low–medium | `daily_fetch.odds` / `odds_service` | skip when slate empty; never invent lines |
| Derived streaks | calculated from `gamelogs` | player-stat-threshold-season | daily calculate | snapshot tables rebuilt; not pregame historical | medium | `daily_calculate.streaks` | clear/rebuild season slice; empty if logs missing |
| Heat index | calculated from `gamelogs` | player-stat-season-window | daily calculate | current-season snapshot | medium | `daily_calculate.heat` | skip players with <3 games |
| Consistency | calculated from `gamelogs` | player-stat-season-window | daily calculate | current-season snapshot | medium | `daily_calculate.consistency` | skip <5 games; mean 0 → undefined CV |
| Team daily metrics / flags (legacy) | `league_dash_team_stats` + unbounded `team_game_stats` | team × date × window | daily compatibility projection | current endpoint state only; unsafe historical labels | medium | `daily_calculate.metrics` / `flags` | never use for historical reconstruction; retained for current UI compatibility |
| Team/game analytical snapshots | paired pre-cutoff `team_game_stats` + `game_schedule` | scheduled game/team/cutoff/version plus paired game environment | daily after schedule factors; bounded backfill | reproducible for validated team-game coverage | medium | `daily_calculate.team_snapshots`; `backfill_team_game_snapshots.py` | excludes target/future games, reports incomplete pairs as partial, publishes both grains transactionally |
| Schedule factors | `game_schedule` | team-game | daily calculate | rebuildable for any scheduled season in DB | low–medium | `daily_calculate.schedule` | missing prior game → null rest |
| Game environment (legacy) | schedule + legacy metrics | game-date | daily compatibility projection | today's context oriented | low | `daily_calculate.environment` | not a historical feature source; use `game_environment_snapshots` |
| External source artifact manifests | `scripts/register_external_dataset.py` -> `external_dataset_imports` | one file/version/hash/transformation registration | ad hoc, before any approved import phase | whatever immutable artifact is retained at the durable locator | proportional to local file scan | external manifest registry | dry-run never opens the database; failed apply writes no manifest; this boundary does not import source rows |
| Stat Surge historical availability checkpoints | registered CSV -> staging -> versioned exact identity reconciliation | player/team/matchup/report-date daily checkpoint | bounded historical staging | 2021-10-19 through 2024-06-17 | seconds for 35,522 rows | external Stat Surge staging | 35,234 rows fully identity-resolved, 288 partial, zero conflicts; all cutoff timing remains unknown; no public consumer |
| Kaggle historical team games | registered `nba_games_all.csv` -> `stg_kaggle_games`; exact playoff subset -> `game_schedule` | game/team perspective | bounded staging and reviewed promotion | 1950-51 through partial 2018-19; canonical promotion currently limited to 2006-07 through 2017-18 playoffs | minutes for 125,624 staged rows | external Kaggle game staging / playoff schedule promotion | pair/identity/date/result states preserved; promotion uses exact IDs, shared pipeline lock, full row lineage, atomic verification, and zero-write reruns |
| Kaggle historical market pack | registered moneyline/spread/totals -> atomic market staging -> read-only exact identity report | game/book/away-home selection source row; later canonical selections are separate | bounded staging | 2006-07 through 2017-18 plus source event-type remnants | minutes for 388,362 rows | external Kaggle market staging | 95,516 eligible rows match canonical games, 292,008 remain canonical-missing, zero conflicts; unknown timing explicit; 173 anomalies quarantined; no public consumer |

## Ownership notes

* External NBA HTTP stays behind `app/utils/fetch/` (and related services). Routes must not grow new direct endpoint clients.
* PostgreSQL is durable; Redis is disposable cache (`CACHE_CATALOG.md`).
* `daily_ingest.py`, standalone `daily_fetch.py`, and standalone `daily_calculate.py` share one PostgreSQL advisory lock and write per-task source status. Legacy initial/backfill utilities remain outside that lock and must not overlap the daily pipeline.
* `external_dataset_imports` is a manifest-only provenance boundary with its own advisory lock. It has no staging or canonical consumer in this change.
* `dataSource/archive` is temporary and ignored. A manifest must point to the separately retained durable copy; `needs_review` license state records uncertainty and is not approval for analytical, public, or commercial use.
* The eight external-pack artifacts registered on 2026-07-16 record
  `permission-confirmed-no-formal-license`, `approved_public`, and `permitted`
  based on project-owner confirmation. No standalone Kaggle or Stat Surge
  license file accompanies the preserved artifacts.
* Stat Surge staging preserves the author's documented daily 2 p.m. checkpoint
  methodology but stores no exact `source_published_at`. Missing players or
  teams cannot be interpreted as healthy, available, or submitted.
  Identity resolution is versioned and reproducible but does not change this
  cutoff limitation or create a canonical availability fact.
* Kaggle markets are linked to source game identity first. The 999 eligible
  playoff games now reconcile exactly in `game_schedule`: 161 pre-existing and
  838 promoted with row-level provenance. Regular-season canonical coverage is
  still incomplete, so later reconciliation must preserve `canonical_missing`
  rather than dropping or guessing those games.

## Related docs

* `DATA_DICTIONARY.md` — table grains
* `INGESTION_RUNBOOK.md` — order, idempotency, recovery
* `DATABASE_PROFILE.md` — live row counts and quality
* `METRIC_CATALOG.md` — derived metric formulas
