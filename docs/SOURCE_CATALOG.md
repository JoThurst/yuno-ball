# Yuno Ball Source Catalog

Status: canonical inventory of external data sources feeding Yuno Ball
Reviewed: 2026-07-24 against fetch utilities, recovery scripts, forward collectors, daily pipeline, and `DATA_DICTIONARY.md`.

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
| NBA schedule | `nba_api.stats.endpoints.ScheduleLeagueV2` with explicit season; validated CDN `scheduleLeagueV2_1.json` fallback | team-perspective game `(game_id, team_id)` | one season request per bounded run; daily current/future slate; historical coverage repair before injury identity resolution | multi-season; explicit Play-In/Playoffs included | one Stats API call per season; CDN fallback is one master-payload call | `daily_fetch.schedule` / `future`; `scripts/repair_schedule_coverage.py` | Stats API is primary for historical repair; CDN fallback must match requested season and contain game dates; canonical inserts require exact reciprocal rows and never rewrite existing games |
| PlayerGameLogs | `PlayerGameLogs` | player-game | daily current season; historical by player/season | box scores for requested seasons | high (hundreds of calls) | `daily_fetch.gamelogs` | rate-limit sleep; atomic mutable-field upsert refreshes corrected boxes without zero-filling missing values |
| Traditional player box score V3 | `BoxScoreTraditionalV3` -> immutable revisions + `player_game_facts` | player-team-game, including DNP/status rows | explicit bounded batches only; no scheduler | completed games with canonical reciprocal schedule identity | one call per game | `collect_traditional_player_game_facts.py` | max 25 explicit games; validate the full batch and team points before one publication transaction; preserve raw source/hash and parser corrections |
| Advanced player box score V3 | `BoxScoreAdvancedV3` -> immutable revisions + `player_game_advanced_facts` | advanced player-team-game, including DNP/status rows | after Traditional publication for the same explicit bounded games | completed games covered by the endpoint and Traditional canonical facts | one call per game | `collect_advanced_player_game_facts.py` | max 25 explicit games; collapse only an empty duplicate placeholder when a higher-quality row exists and retain it in raw provenance; fail closed on ambiguous duplicates or Traditional identity mismatch; played/unknown rows require strict player-season identity; DNP-only source roster rows may use a source-only player identity with no claimed NBA season; exact replay is a no-op |
| TeamGameLog | `TeamGameLog` → `team_game_stats` | team-game | daily / seasonal backfill after schedule; feeds local schedule-result reconciliation | requires schedule FK rows | medium–high | `daily_fetch.teamstats` → `schedule_reconcile` | skip games lacking schedule; partial/conflicting result pairs block reconciliation; plus/minus historically forced 0 |
| LeagueDashPlayerStats | `LeagueDashPlayerStats` | player-season | daily current; seasonal backfill | season aggregates + ranks | medium | `daily_fetch.leagueplayer` | update on conflict; traded-player grain ambiguous |
| LeagueDashTeamStats | `LeagueDashTeamStats` (measures × per-modes × season types) | team-season-season_type | daily current; seasonal backfill | wide endpoint-shaped columns | medium–high | `daily_fetch.leagueteam` | dynamic column allowlist required; partial measure failure should not drop other measures |
| Live box score player status | Live BoxScore / status fetcher → `player_game_status` | postgame player-game status | daily for recent/completed games | sparse historically; best for recent windows | medium (batched) | `daily_fetch.injury` | not a pregame injury-report source; never use a prior-game status as today's availability |
| NBA live odds | NBA odds endpoint → bounded adapter → `market_observation_headers` + `market_observation_selections` | game × sportsbook × market observation with immutable selections | not approved for scheduled collection; bounded evaluation only | current source path returned 403 direct and an error redirect loop through the configured proxy on 2026-07-24; not a historical closing-line archive | low–medium, pending route validation | `collect_nba_live_market_observations.py` / `nba_live_market_observation_adapter` | fail closed on provider/network errors; never classify blocked response as empty slate; legacy `game_odds` remains compatibility-only |
| Program B market-observation contract | approved historical artifact or evaluated forward provider → `market_observation_headers` + `market_observation_selections` | immutable source/book/game/market header plus selection rows | append-only per source observation | historical timing may be unknown; forward source must declare precision | source/provider dependent; bounded evaluation required | `market_observation_service` registration boundary | storage contract only today; no provider is approved, no historical promotion occurs, and legacy `game_odds` is not rewritten |
| Derived streaks | canonical-first player-game reader with `gamelogs` fallback | player-stat-threshold-season | daily calculate | snapshot tables rebuilt; not pregame historical | medium | `daily_calculate.streaks` | canonical rows win by exact key; legacy fills uncovered history; empty if both sources are missing |
| Heat index | canonical-first player-game reader with `gamelogs` fallback | player-stat-season-window | daily calculate | current-season snapshot | medium | `daily_calculate.heat` | skip players with <3 played games; preserve nulls |
| Consistency | canonical-first player-game reader with `gamelogs` fallback | player-stat-season-window | daily calculate | current-season snapshot | medium | `daily_calculate.consistency` | skip <5 played games; mean 0 → undefined CV |
| Team daily metrics / flags (legacy) | `league_dash_team_stats` + unbounded `team_game_stats` | team × date × window | daily compatibility projection | current endpoint state only; unsafe historical labels | medium | `daily_calculate.metrics` / `flags` | never use for historical reconstruction; retained for current UI compatibility |
| Team/game analytical snapshots | paired pre-cutoff `team_game_stats` + `game_schedule` | scheduled game/team/cutoff/version plus paired game environment | daily after schedule factors; bounded backfill | reproducible for validated team-game coverage | medium | `daily_calculate.team_snapshots`; `backfill_team_game_snapshots.py` | excludes target/future games, reports incomplete pairs as partial, publishes both grains transactionally |
| Schedule factors | `game_schedule` | team-game | daily calculate | rebuildable for any scheduled season in DB | low–medium | `daily_calculate.schedule` | missing prior game → null rest |
| Game environment (legacy) | schedule + legacy metrics | game-date | daily compatibility projection | today's context oriented | low | `daily_calculate.environment` | not a historical feature source; use `game_environment_snapshots` |
| External source artifact manifests | `scripts/register_external_dataset.py` -> `external_dataset_imports` | one file/version/hash/transformation registration | ad hoc, before any approved import phase | whatever immutable artifact is retained at the durable locator | proportional to local file scan | external manifest registry | dry-run never opens the database; failed apply writes no manifest; this boundary does not import source rows |
| Stat Surge historical availability checkpoints | registered CSV -> staging -> versioned exact identity reconciliation | player/team/matchup/report-date daily checkpoint | bounded historical staging | 2021-10-19 through 2024-06-17 | seconds for 35,522 rows | external Stat Surge staging | 35,234 rows fully identity-resolved, 288 partial, zero conflicts; all cutoff timing remains unknown; no public consumer |
| Official NBA injury-report PDFs | current forward collection still uses optional season-page discovery -> allowlisted PDF provider -> `availability_report_download_attempts` -> `availability_report_documents` plus durable raw archive; bounded historical/recovery collection probes the CDN filename directly; durable PDFs feed the separate parser -> `availability_observations` and `team_report_submission_status` boundary -> read-only daily slate adapter | one durable attempt row per discovered/probed source URL; one document revision per source URL/content hash; one parser-lineage observation per source row | two-hour forward polling; historical scans in at most 31-date chunks; bounded season parsing | forward page discovery plus direct-CDN recovery; index-page history is incomplete; legacy reports use hour precision while newer reports use minute precision | seconds per bounded direct-CDN run; historical probe cost scales with candidates; parsing cost scales with archived PDFs | official injury document collector / observation parser / slate availability adapter | every direct candidate is retained; transient failures remain pending for retry, validated historical filename-probe 403/404 absence responses become terminal `not_found`; 403s from other NBA endpoints are not classified as absence; only validated PDFs enter the document archive; invalid host/path, non-PDF content, or hash/storage conflicts fail closed; unresolved identities remain queryable and daily payloads expose partial/unknown states |
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
* Official PDF collection preserves exact filename-derived publication time and
  first retrieval time at raw-document grain. Raw bytes live only in the
  configured durable archive outside Git. The daily slate adapter supports
  read-only, pregame availability display using canonical game IDs and strict
  scheduled-tipoff publication cutoffs; it does not publish model features,
  transitions, or health claims from missing evidence.
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
