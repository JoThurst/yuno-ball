# Yuno Ball Route Catalog

Status: canonical route inventory from the six registered blueprints
Reviewed: 2026-07-15.

## Server-rendered routes

| Method/path                    | Purpose                                                | Primary dependencies                                                                            | Known weaknesses / next action                                                                                                                   |
| ------------------------------ | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET, POST /`                  | welcome/landing page; POST returns `OK`                | `welcome.html`; global matchup context                                                          | unexplained POST surface and debug logging; make GET-only unless a real integration requires POST                                                |
| `GET /home`                    | combined daily dashboard                               | scoreboard/standings, teams/rosters, team/player league stats, player streaks, home cache       | very heavy assembly, repeated team/API lookups, hard-coded season, some placeholders/rank-as-value confusion; precompute and standardize metrics |
| `GET /team/list`               | conference team cards with record and today's opponent | `teams`, `roster`, scoreboard/standings, `teams` cache                                          | marked TODO; POST branch is unreachable because route declares GET only; key differs from warmer                                                 |
| `GET /team/<team_id>`          | team profile, stats, schedules, lineups                | team service, `teams`, `roster`, `league_dash_team_stats`, `game_schedule`, NBA lineup endpoint | hard-coded season; service mixes DB and live calls; add as-of state and missing-data handling                                                    |
| `GET /team/stats-visuals`      | team chart page                                        | `teams`, `team_stats_visuals.html`                                                              | marked TODO and does not pass statistics; either implement from curated metrics or remove                                                        |
| `GET /players/`                | searchable/listed players                              | player service, `players`                                                                       | potentially large unpaginated response; distinguish active vs historical players                                                                 |
| `GET /players/<player_id>`     | player profile and recent/season stats                 | `players`, `roster`, `statistics`, `leaguedashplayerstats`, `gamelogs`, `game_schedule`         | positional tuple normalization is brittle; minutes/score formatting can fail; add season selector and named rows                                 |
| `GET /players/streaks`         | hot-streak table                                       | `player_streaks`, player service                                                                | no today's-game/team filtering in current route; “streak” is last-10 count, not necessarily consecutive; team abbreviation is often blank        |
| `GET /dashboard/`              | player-stat dashboard                                  | `leaguedashplayerstats`, `teams`                                                                | marked TODO; large table needs server-side pagination/filtering and explicit units                                                               |
| `GET /dashboard/games`         | today's games and conference standings                 | live `fetch_todays_games` / scoreboard cache                                                    | prints debug data; no robust stale/as-of state or live refresh strategy                                                                          |
| `GET, POST /dashboard/matchup` | two-team player/lineup comparison                      | teams, rosters, lineups, last-10 player logs, opponent logs, matchup cache                      | N+1 queries and live lineup calls; 24h stale cache; POST only redirects; matchup formatting remains brittle                                      |
| `GET /daily/`                  | fan-oriented historical/current slate                  | schedule, versioned player/team/game snapshots, odds/injuries when available                    | complete snapshots are required for historical analytics; missing cutoffs render without falling forward                                        |
| `GET /daily/betting`           | betting-oriented historical/current slate              | same cutoff-safe slate service plus stored odds                                                  | odds completeness remains source-dependent; analytical features use the same pregame cutoff as the fan slate                                     |

The application-wide context processor calls `get_today_matchups()` for every rendered template. Its cache reduces load, but failure or slowness affects every page request.

## JSON/API routes

| Method/path                                          | Purpose                          | Dependencies                            | Known weaknesses / next action                                                                                                      |
| ---------------------------------------------------- | -------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/team-stats?team_id=&season=`               | team ranks and last ten games    | teams, league team stats, game schedule | game mapping expects fields not returned by `get_last_n_games_by_team`; mixes ranks with actual values; needs response schema tests |
| `GET /api/player-comparison?player1_id=&player2_id=` | normalized two-player comparison | player service and stored stats         | validate numeric IDs, season, and current-team semantics; remove debug payload logging                                              |
| `GET /api/fetch-player-streaks`                      | triggers full streak refresh     | NBA API, `player_streaks`               | critical: destructive/expensive mutation on unauthenticated GET; move to protected CLI/job or authenticated POST                    |

## Blueprint and URL ownership

* `main`: `/`, `/home`
* `team`: `/team/*`
* `player`: `/players/*`
* `dashboard`: `/dashboard/*`
* `api`: `/api/*`
* `daily`: `/daily/*`

## UX priorities

1. Make `/home` the primary product page and decide whether `/` remains a marketing landing page.
2. Replace hard-coded season defaults with a shared season selector/context.
3. Show data freshness and partial-data states instead of silently returning zeros.

Daily slate contexts now receive a structured `freshness` object from `app/utils/freshness.py` with `source`, `run_id`, UTC `as_of`, `target_date`, season, validation state, completeness, age, and stale state. The compatibility file advances only after a fully validated non-partial ingestion run; routes must not infer freshness from process exit time alone.

Daily slate contexts also expose `player_snapshot` and `team_snapshot`
metadata. Historical team/game reads select the newest complete snapshot whose
`feature_as_of` and `data_available_at` are both at or before the requested
pregame cutoff. A missing historical cutoff returns an explicit missing state;
the current legacy projections are never used as a historical fallback.
4. Standardize stat semantics: total, per-game, per-48, per-100, percentage, and league rank must be visually distinct.
5. Optimize matchup data as a precomputed service payload; avoid per-player sequential database work at request time.
6. Add pagination/search/filter state to player and dashboard tables.
7. Improve streak filters for today's matchups and team rosters, while naming the metric honestly.
8. Add API versioning and typed response contracts before external consumers depend on these endpoints.

## Route acceptance checks

* Every route returns a useful empty state when NBA API or Redis is unavailable.
* All DB-only pages can render without external NBA calls.
* No public GET performs a write.
* Current season is derived centrally and can be overridden for historical views.
* Template payloads use dictionaries/typed DTOs, not undocumented tuple positions.
* Expensive pages record cache hit/miss and render latency without logging sensitive configuration.
