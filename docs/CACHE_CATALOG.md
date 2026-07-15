# Yuno Ball Cache Catalog

Status: canonical inventory of implemented Redis keys and required ownership rules
Reviewed: 2026-07-12. Redis is configured as `localhost:6379`, database 0.

## Policy

* PostgreSQL is durable; every Redis key may be deleted without data loss.
* Keys must have a named owner, explicit TTL, and invalidation trigger.
* Cache serialized JSON only. Current serializer converts datetimes and NumPy integers to strings.
* Use one key naming convention: `yunoball:{environment}:{domain}:{version}:{dimensions}`.
* Never use broad `KEYS` deletion in production; track namespaces and use `SCAN` or version bumps.

## Implemented keys

| Key pattern                            | Owner / producer     | Payload                                         | TTL    | Consumers                                     | Invalidation                                                                         |
| -------------------------------------- | -------------------- | ----------------------------------------------- | ------ | --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `nba_games_{YYYY-MM-DD}`               | `fetch_todays_games` | scoreboard games plus East/West standings       | 86400s | dashboard, teams, navbar/services             | expire at next logical scoreboard refresh; invalidate after schedule/results refresh |
| `standings_data`                       | `Team.get_all_teams` | team ID to record/conference lookup             | 21600s | team list and dependent services              | after standings refresh; at season rollover                                          |
| `teams`                                | `/team/list`         | enhanced teams grouped by conference            | 3600s  | teams page                                    | after roster, standings, team identity, or today's-games changes                     |
| `matchup:{team1_id}:{team2_id}`        | matchup route        | teams, lineup stats, recent logs, opponent logs | 86400s | `/dashboard/matchup`                          | after either team's roster/log/lineup update; date rollover                          |
| `home_dashboard_{season}_{YYYY-MM-DD}` | dashboard service    | assembled home-page data                        | 3600s  | `/home`                                       | after any component refresh; date rollover                                           |
| `today_matchups_{YYYY-MM-DD}`          | dashboard service    | today's games for navbar                        | 3600s  | application context processor/navbar          | after scoreboard change; date rollover                                               |
| `today_matchups`                       | `cache_warmer.py`    | today's games                                   | 6000s  | no matching reviewed consumer confirmed       | remove or align with dated key                                                       |
| `teams_data`                           | `cache_warmer.py`    | enhanced team data                              | 86400s | no matching reviewed route consumer confirmed | remove or align with `teams`                                                         |

## Known inconsistencies

* The warmer writes `today_matchups`, while the navbar service reads `today_matchups_{date}`.
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
| `yunoball:{env}:navbar_matchups:v1:{date}`                      | 15m                                | small shared view                                      |

## Warm-up behavior

Warm only after ingestion and validation succeed:

1. scoreboard/standings for the current date;
2. navbar matchups;
3. home dashboard;
4. teams page;
5. today's matchup pairs, with canonical team ordering.

A single failed matchup must not abort the entire warmer. Log per-key timing and failure, and ensure `matchup_data` is non-null before normalization.

## Invalidation matrix

| Data change                       | Invalidate                                                                 |
| --------------------------------- | -------------------------------------------------------------------------- |
| schedule/result/scoreboard        | scoreboard, navbar, home, teams, all affected matchup pairs, standings     |
| roster                            | teams, home, affected team matchups, affected player views if cached later |
| player game logs                  | home, affected team matchups, player views/streaks if cached later         |
| player streaks                    | home and any streak page cache                                             |
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
