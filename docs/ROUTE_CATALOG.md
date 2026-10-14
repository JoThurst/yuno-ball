# Yuno Ball Route Catalog

Status: canonical route inventory from the registered blueprints and preserved legacy aliases
Reviewed: 2026-10-14; cross-program status is consolidated in [`PROJECT_STATUS.md`](PROJECT_STATUS.md). Route presence is not an access-control or deployment-readiness assertion.

## Server-rendered routes

| Method/path                    | Purpose                                                | Primary dependencies                                                                            | Known weaknesses / next action                                                                                                                   |
| ------------------------------ | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET, POST /`                  | welcome/landing page; POST returns `OK`                | `welcome.html`; global matchup context                                                          | unexplained POST surface; decide whether it has a real integration consumer before retaining it                                                |
| `GET /home`                    | compatibility redirect to canonical Daily                  | Daily route                                                     | redirects to `/daily/` while preserving optional `date` and `season` query parameters |
| `GET /team/list`               | conference team cards with record and today's opponent | `teams`, `roster`, scoreboard/standings, `teams` cache                                          | marked TODO; POST branch is unreachable because route declares GET only; key differs from warmer                                                 |
| `GET /team/<team_id>`          | team profile, stats, schedules, lineups                | team service, `teams`, `roster`, `league_dash_team_stats`, `game_schedule`, NBA lineup endpoint | hard-coded season; service mixes DB and live calls; add as-of state and missing-data handling                                                    |
| `GET /team/stats-visuals`      | retired generic team chart alias                     | Daily route                                                                                     | redirects to Daily; retain useful team/date context there rather than a disconnected chart page |
| `GET /players/`                | searchable/listed players                              | player service, `players`                                                                       | potentially large unpaginated response; distinguish active vs historical players                                                                 |
| `GET /players/<player_id>`     | player profile and recent/season stats                 | `players`, `roster`, `statistics`, `leaguedashplayerstats`, `gamelogs`, `game_schedule`         | positional tuple normalization is brittle; minutes/score formatting can fail; add season selector and named rows                                 |
| `GET /players/streaks`         | retired unscoped streak alias                         | Daily route                                                                                     | redirects to Daily; contextual player signals belong in a dated game story |
| `GET /dashboard/`              | read-only research/data-quality console                | release status constants, route links, evidence checklist                                       | returns 404 in production for the descriptive Daily/history beta; available only in local/development |
| `GET /dashboard/games`         | compatibility alias for Games lookup                 | `/games` archive service                                                                         | redirects to canonical `/games` |
| `GET, POST /dashboard/matchup` | retired duplicate matchup alias                      | Daily route                                                                                     | redirects to canonical date-scoped Daily; old unscoped comparison flow is no longer a product destination |
| `GET /games`                   | canonical historical game lookup/archive              | durable Regular Season schedule rows, Daily archive index                                       | bounded read-only lookup; open a date lens or a date-scoped matchup story |
| `GET /daily/`                  | public Daily Intelligence V1 slate                    | typed Daily V1 package, versioned player/team/game snapshots, cutoff-aware official availability, optional canonical market observations, and completed-game outcomes | public descriptive product; plain-language availability readouts plus explicit empty/stale/partial states; completed games may show observed final context; no predictions or unsupported market edge claims |
| `GET /daily/archive`           | bounded historical Daily date index                  | durable Regular Season schedule rows, date-level game and completion counts | read-only archive navigation; bounded and source-derived |
| `GET /daily/YYYY-MM-DD`        | canonical historical Daily Intelligence V1 page      | same typed Daily V1 package at the requested date/cutoff | permanent indexable date destination; no fall-forward to later snapshots |
| `GET /daily/betting`           | experimental betting-oriented historical/current slate | legacy stored odds and official availability                                                     | returns 404 in production; excluded from descriptive Daily/history beta |
| `GET /daily/api/v1`            | versioned Daily Intelligence V1 package               | cutoff-safe slate service, snapshots, schedule factors, official availability, optional canonical market observations, durable schedule results, and canonical player-game facts with row-level completeness and partial game coverage | descriptive read-only payload; completed games expose `actual` postgame context without revising pregame signals; compact `actual.box_score.leaders` remains available alongside additive team rows; no predictions, SoS promotion, or live external calls |
| `GET /design/daily-v1`         | interactive read-only HTML design lab for Daily V1    | same Daily Intelligence V1 package; demo/current query presets                                    | returns 404 in production for the descriptive Daily/history beta; available only in local/development |
| `GET /design/status`           | visual read-only program status and gate map          | repository-backed program status constants; roadmap evidence                                      | returns 404 in production; local-only status snapshot is not launch evidence |
| `GET /health/ready`            | bounded PostgreSQL/Redis connectivity probe            | PostgreSQL `SELECT 1`; Redis `PING`                                                              | production limits are 10 requests per IP per minute per worker in memory plus the global Redis-backed 60/minute limit; checks connectivity only, not schema, freshness, or page behavior |
| `GET /matchup/YYYY-MM-DD/AWAY-HOME` | canonical historical matchup page               | date-scoped Daily V1 game, insights, provenance, cutoff metadata, and optional observed postgame record | permanent matchup destination; final games show durable score/result plus available canonical traditional player-game rows for each team; row coverage is explicitly partial or missing because full official game coverage is not certified; scheduled games remain pregame-only; descriptive only |

The legacy `/teams`, `/teams/<team_id>`, `/teams/<team_id>/stats-visuals`,
`/games-dashboard`, and `/matchup/<team1_id>/<team2_id>` paths remain
compatibility surfaces. Retired dashboard, streak, chart, and matchup aliases
redirect to the current blueprint/service boundary; they are not new product
destinations. The descriptive Daily/history beta exposes the landing page,
Daily, archive, matchup, and supporting history routes. Research/design pages
and the experimental betting page return 404 in production; local and
development access remains available. Readiness is rate-limited in production
and reports dependency connectivity only.

The application-wide context processor reads today's persisted schedule rows for
navbar matchups. It does not call an external provider or the Redis-backed
`get_today_matchups` cache helper during rendering; a provider outage cannot
stall every page request, and missing schedule rows remain an explicit empty
navbar state.

## JSON/API routes

| Method/path                                          | Purpose                          | Dependencies                            | Known weaknesses / next action                                                                                                      |
| ---------------------------------------------------- | -------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `GET /api/team-stats?team_id=&season=`               | team ranks and last ten games    | teams, league team stats, game schedule | game mapping expects fields not returned by `get_last_n_games_by_team`; mixes ranks with actual values; needs response schema tests |
| `GET /api/player-comparison?player1_id=&player2_id=` | normalized two-player comparison | player service and stored stats         | validate numeric IDs, season, and current-team semantics; remove debug payload logging                                              |
The previously documented `GET /api/fetch-player-streaks` route is not
registered in the current API blueprint and is omitted from this inventory.

## Blueprint and URL ownership

* `main`: `/`, `/home`, `/games`
* `team`: `/team/*`
* `player`: `/players/*`
* `dashboard`: `/dashboard/*`
* `api`: `/api/*`
* `daily`: `/daily/*`
* `design`: `/design/*` (read-only prototype surfaces; available locally, hidden in production for this beta)

## UX priorities

1. Keep `/daily/` as the canonical Daily destination; `/home` redirects there. Decide whether `/` remains a landing page or redirects to Daily.
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

Official availability is assembled by the slate service from the immutable
official-report observations. Each game uses its canonical scheduled tipoff as
the strict publication cutoff, preserves `source`, `as_of`, completeness,
unknown reason, unresolved counts, and explicit team submission states, and
never infers health from missing evidence. The Daily V1 payload also preserves
safe player/status/reason rows and a human readout per team so public pages can
say “4 out · 5 questionable” or “availability unknown” without losing the
underlying audit metadata. Resolved non-available statuses may appear in
player callouts; unresolved observations remain game-level evidence.

## Route acceptance checks

* Every route returns a useful empty state when NBA API or Redis is unavailable.
* Daily and shared templates expose a keyboard skip link, labeled loading
  status, semantic main landmark, and stateful menu controls.
* All DB-only pages can render without external NBA calls.
* No public GET performs a write.
* Current season is derived centrally and can be overridden for historical views.
* Template payloads use dictionaries/typed DTOs, not undocumented tuple positions.
* Expensive pages record cache hit/miss and render latency without logging sensitive configuration.
