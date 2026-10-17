# Yuno Ball Cache Catalog

Status: canonical inventory of implemented Redis keys and required ownership rules
Reviewed: 2026-10-14 against the descriptive Daily/history beta integration checkout. Redis is configured as `localhost:6379`, database 0. This is a code inventory, not evidence of staging or production cache behavior.

## Policy

* PostgreSQL is durable; every Redis key may be deleted without data loss.
* Keys must have a named owner, explicit TTL, and invalidation trigger.
* Cache serialized JSON only. Current serializer converts datetimes and NumPy integers to strings.
* Use one key naming convention: `yunoball:{environment}:{domain}:{version}:{dimensions}`.
* Never use broad `KEYS` deletion in production; track namespaces and use `SCAN` or version bumps.
* Redis is disposable. `/health/ready` reports `degraded_ready` with HTTP 200
  when PostgreSQL is healthy but Redis is unavailable; cache loss must not make
  PostgreSQL-backed Daily/history pages unready. PostgreSQL loss remains HTTP 503.
* Versioned player and team/game snapshot readers are currently PostgreSQL-only.
  If cached later, keys must include season, requested cutoff, calculation
  version, completeness policy, and environment; they must not share a key with
  legacy latest-state projections.

## Implemented keys

| Key pattern                            | Owner / producer     | Payload                                         | TTL    | Consumers                                     | Invalidation                                                                         |
| -------------------------------------- | -------------------- | ----------------------------------------------- | ------ | --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `nba_games_{YYYY-MM-DD}`               | `fetch_todays_games` | scoreboard games plus East/West standings       | 86400s | legacy fetch utility consumers; not the navbar context processor | expire at next logical scoreboard refresh; invalidate after schedule/results refresh |
| `standings_data`                       | `Team.get_all_teams` | team ID to record/conference lookup             | 21600s | team list and dependent services              | after standings refresh; at season rollover                                          |
| `teams`                                | `/team/list`         | enhanced teams grouped by conference            | 3600s  | teams page                                    | after roster, standings, team identity, or today's-games changes                     |
| `matchup:{team1_id}:{team2_id}`        | `cache_warmer.py`    | teams, lineup stats, recent logs, opponent logs | 86400s | warmer writes it; no registered route or cache reader found | warmer is manual/legacy; key has no season or date dimension                          |
| `home_dashboard_{season}_{YYYY-MM-DD}` | dashboard service helper | assembled home-page data                        | 3600s  | no registered home-dashboard consumer; `/home` redirects to Daily | after any component refresh; date rollover                                           |
| `today_matchups_{YYYY-MM-DD}`          | dashboard service helper | today's games                        | 3600s  | no application navbar consumer; navbar reads persisted schedule rows | after scoreboard change; date rollover                                               |
| `today_matchups`                       | `cache_warmer.py`    | today's games                                   | 6000s  | no matching reviewed consumer confirmed       | remove or align with dated key                                                       |
| `teams_data`                           | `cache_warmer.py`    | enhanced team data                              | 86400s | no matching reviewed route consumer confirmed | remove or align with `teams`                                                         |

## Known inconsistencies

* The application navbar context reads persisted schedule rows directly; it does not use Redis. Dashboard service helpers still define `home_dashboard_{season}_{date}` and `today_matchups_{date}`, but no current registered home/dashboard route consumes those cached payloads.
* The warmer writes `teams_data`, while `/team/list` reads `teams`.
* A matchup is direction-sensitive in the key. `A:B` and `B:A` duplicate expensive data even though they represent the same pair.
* A 24-hour scoreboard TTL can serve stale live/final state. Use shorter TTLs on game days and phase-aware caching.
* Ingestion defines mock cache functions but does not centrally invalidate real cache keys after writes.

## Target key scheme

| Target key                                                      | Suggested TTL                      | Notes                                                  |
| --------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------ |
| `yunoball:{env}:scoreboard:v1:{date}`                           | pregame 15m; live 30-60s; final 1h | response should include retrieval/as-of timestamp      |
| `yunoball:{env}:standings:v1:{season}:{date}`                   | 1h-6h                              | refresh after completed games                          |
| `yunoball:{env}:teams:v1:{season}:{date}`                       | 1h                                 | assembled teams page                                   |
| `yunoball:{env}:matchup:v1:{date}:{low_team_id}:{high_team_id}` | 1h-24h                             | canonicalize pair; shorter after new games             |
| `yunoball:{env}:home:v1:{season}:{date}`                        | 15m-1h                             | invalidate by version bump after schema/payload change |
| `yunoball:{env}:navbar_matchups:v1:{date}`                      | 15m                                | proposed only if navbar moves to a cache-backed read; current navbar reads PostgreSQL directly |

## Warm-up behavior

The application navbar reads persisted schedule rows and does not need a Redis warm-up. The legacy warmer still writes `today_matchups` and `teams_data`, but no matching consumers were confirmed during this review. Warm only a key with an identified active consumer after ingestion and validation succeed. For matchup warm-ups, one failed matchup must not abort the full run; log per-key timing and failure, and ensure `matchup_data` is non-null before normalization.

## Invalidation matrix

| Data change                       | Invalidate                                                                 |
| --------------------------------- | -------------------------------------------------------------------------- |
| schedule/result/scoreboard        | scoreboard, legacy dashboard helper payloads, teams, all affected matchup pairs, standings |
| roster                            | teams, legacy dashboard helper payloads, affected team matchups, affected player views if cached later |
| player game logs                  | legacy dashboard helper payloads, affected team matchups, player views/streaks if cached later         |
| player streaks                    | legacy dashboard helper payloads and any streak page cache                                             |
| versioned player/team snapshot publication | only snapshot-aware namespaces at that cutoff/version; none implemented today |
| league team/player aggregates     | home, teams, dashboard, affected matchup/team detail keys                  |
| deploy changing payload structure | bump key version; do not rely only on TTL                                  |

## Operational checks

```bash
redis-cli ping
redis-cli INFO memory
redis-cli INFO stats
redis-cli --scan --pattern 'yunoball:*' | head
```

Track hit rate, misses, evictions, serialized byte size, producer latency, and age/as-of timestamp. Avoid logging full cached player payloads.
