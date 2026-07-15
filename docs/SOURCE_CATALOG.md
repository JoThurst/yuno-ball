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
| CommonTeamRoster | `CommonTeamRoster` via roster fetch | player-team-season | daily in season | current season reliable; historical wipe risk if delete-all refresh used | ~30 team calls | `daily_fetch.rosters` | per-team retry; known defect: refresh may delete non-current seasons |
| LeagueGameFinder / schedule | `LeagueGameFinder` + CDN `scheduleLeagueV2_1.json`; null-result repair may use validated paired `team_game_stats` | team-perspective game `(game_id, team_id)` | daily results + future slate; local reconciliation after team stats and before gamelogs; bounded CLI for recovery | multi-season backfill supported | seconds–minutes per season | `daily_fetch.schedule` / `future` / `schedule_reconcile`; `reconcile_schedule_results.py` | CDN timeout → keep last DB schedule; reconciliation requires reciprocal two-row W/L and score agreement or fails closed before calculations |
| PlayerGameLogs | `PlayerGameLogs` | player-game | daily current season; historical by player/season | box scores for requested seasons | high (hundreds of calls) | `daily_fetch.gamelogs` | rate-limit sleep; current insert `DO NOTHING` leaves stale boxes |
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

## Ownership notes

* External NBA HTTP stays behind `app/utils/fetch/` (and related services). Routes must not grow new direct endpoint clients.
* PostgreSQL is durable; Redis is disposable cache (`CACHE_CATALOG.md`).
* `daily_ingest.py`, standalone `daily_fetch.py`, and standalone `daily_calculate.py` share one PostgreSQL advisory lock and write per-task source status. Legacy initial/backfill utilities remain outside that lock and must not overlap the daily pipeline.

## Related docs

* `DATA_DICTIONARY.md` — table grains
* `INGESTION_RUNBOOK.md` — order, idempotency, recovery
* `DATABASE_PROFILE.md` — live row counts and quality
* `METRIC_CATALOG.md` — derived metric formulas
