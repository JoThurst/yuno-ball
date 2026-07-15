# Yuno Ball Metric Catalog

Status: canonical definitions for Yuno-derived metrics
Reviewed: 2026-07-15 against services in `app/services/` and daily calculate tasks.

Use this for interpretation and leakage-safe evaluation. Endpoint-native NBA fields
(e.g. raw `pts` from box scores) are documented in `DATA_DICTIONARY.md`, not duplicated here.

## Contract fields

For each metric:

* **Formula** — exact definition used in code
* **Grain** — uniqueness / observation unit
* **As-of rules** — what time cut the value represents
* **Version** — logical version string for this contract
* **Interpretation** — how to read the number
* **Prohibited uses** — what not to do

---

## Player heat index

| Field | Value |
| --- | --- |
| Metric ID | `player.heat_index` |
| Version | `player-v2.1` (`heat_index.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_heat_index_snapshots`; `HeatIndexService` → legacy `player_heat_index` |
| Formula | `z = (recent_avg(stat, window) - season_avg(stat)) / season_std(stat)`; status `on_fire` if `z ≥ 1.0`, `ice_cold` if `z ≤ -1.0`, else neutral. Stats: PTS, REB, AST, PRA (`PTS+REB+AST`). Windows: 3, 5, 10. Requires ≥3 season games and enough recent games for the window. |
| Grain | `(player_id, stat, season, season_type, window_size, feature_as_of, calculation_version)` |
| As-of rules | v2 uses only source games on Eastern calendar dates strictly before the target slate date, ordered by the canonical schedule timestamp. Canonical publication is 10:00 ET; source availability is scheduled tipoff + 6h. |
| Interpretation | Positive z = recent form above that player's own season distribution. |
| Prohibited uses | Do not treat as league-relative strength. Do not use the legacy table as a historical feature. A missing PTS/REB/AST component makes PRA missing; never replace it with zero. |

---

## Player consistency (CV)

| Field | Value |
| --- | --- |
| Metric ID | `player.consistency_cv` |
| Version | `player-v2.1` (`consistency.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_consistency_snapshots`; `ConsistencyService` → legacy `player_consistency` |
| Formula | `CV = stddev(stat) / mean(stat)` over season game logs. Tiers: `steady` if `CV < 0.35`, `volatile` if `CV > 0.55`, else mid. Stats: pts, reb, ast, pra, stl, blk, tov. Requires ≥5 games. |
| Grain | `(player_id, season, season_type, stat_name, window_size, feature_as_of, calculation_version)` |
| As-of rules | Same strict pre-slate v2 cutoff and availability rule as heat index. Only complete player/stat samples with at least five games publish. |
| Interpretation | Lower CV ⇒ more predictable game-to-game volume for that stat. |
| Prohibited uses | Do not compare CV across stats with different means without context; do not use when mean≈0; not a shooting-efficiency volatility metric. |

---

## Consecutive streaks

| Field | Value |
| --- | --- |
| Metric ID | `player.consecutive_streak` |
| Version | `player-v2.1` (`consecutive_streak.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_consecutive_streak_snapshots`; `StreakCalculationService` → legacy `player_consecutive_streaks` |
| Formula | Count consecutive games (ordered by game date) where `stat ≥ threshold`. Also tracks season max. Thresholds e.g. PTS 10/15/20/25/30, REB 4/6/8/10/12, AST 2/4/6/8/10, STL/BLK 1–4, PRA 20–40. |
| Grain | `(player_id, stat, threshold, season, season_type, feature_as_of, calculation_version, streak_kind)` |
| As-of rules | v2 uses only games strictly before the target slate date and orders by schedule event time. Missing source values prevent a complete player/stat publication. |
| Interpretation | True consecutive hit streak, unlike legacy `player_streaks` “X of last 10”. |
| Prohibited uses | Do not label legacy `player_streaks` as consecutive; do not use FG3M until present on gamelogs. |

---

## Stat windows (recent form hits)

| Field | Value |
| --- | --- |
| Metric ID | `player.stat_window` |
| Version | `player-v2.1` (`stat_window.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_stat_window_snapshots`; `StreakCalculationService` → legacy `player_stat_windows` |
| Formula | Count of games in last N where `stat ≥ threshold` (recent form), plus related season hit-rate fields persisted by the service. |
| Grain | `(player_id, stat, threshold, season, season_type, window_size, feature_as_of, calculation_version)` |
| As-of rules | v2 recent windows end at the latest eligible pre-slate game and record actual games played when fewer than N exist. Readers pin all metric families to the stat-window anchor cutoff. |
| Interpretation | “X of last N” rate at a threshold. |
| Prohibited uses | Do not call this a consecutive streak. |

---

## Legacy player streaks

| Field | Value |
| --- | --- |
| Metric ID | `player.legacy_streaks` |
| Version | `player_streaks.v0` |
| Implementation | `player_streaks` table / older streak path |
| Formula | Qualifying games among last 10 vs fixed thresholds (PTS/REB/AST/FG3M families). |
| Grain | `(player_id, stat, season, threshold)` |
| As-of rules | Table cleared/rebuilt daily — latest snapshot only. |
| Interpretation | Recent hit density, not necessarily consecutive. |
| Prohibited uses | Do not use as historical pregame training labels; prefer `player_consecutive_streaks` / `player_stat_windows`. |

---

## Team daily metrics (season vs recent)

| Field | Value |
| --- | --- |
| Metric ID | `team.daily_metrics` |
| Version | `team_daily_metrics.v1` (+ SoS columns `sos.v1`) |
| Implementation | `TeamMetricsService` → `team_daily_metrics` |
| Formula | Season-to-date efficiency/pace/four-factors from `league_dash_team_stats` (Regular Season) compared to trailing `window_size` (default 10) team-game averages from `team_game_stats`. Deltas = recent − season. SoS columns summarize opponent strength faced in-window. Percent fields normalized to 0–1 when stored as 0–100. |
| Grain | `(stat_date, team_id, window_size)` |
| As-of rules | `stat_date` is the calculation date. Season endpoint slice is **current endpoint state** unless rebuilt from game-level history — dangerous for historical reconstruction (see `MODEL_FEATURE_PLAN.md`). |
| Interpretation | Positive net-rating delta ⇒ recent form stronger than season baseline. |
| Prohibited uses | Do not backfill historical `stat_date` rows using today's season aggregates; do not use `team_game_stats.plus_minus` until ingestion stops forcing 0. |

---

## Team daily flags

| Field | Value |
| --- | --- |
| Metric ID | `team.daily_flags` |
| Version | `team_daily_flags.v1` |
| Implementation | `TeamFlagsService` → `team_daily_flags` |
| Formula | Qualitative tags derived from deltas / thresholds on `team_daily_metrics` for a `stat_date`. |
| Grain | `(stat_date, team_id, flag_type)` |
| As-of rules | Same as parent metrics for that `stat_date`. |
| Interpretation | Human-readable performance tags for daily UI. |
| Prohibited uses | Not a calibrated probability; do not treat as model features without encoding version. |

---

## Schedule factors

| Field | Value |
| --- | --- |
| Metric ID | `team.schedule_factors` |
| Version | `schedule_factors.v1` |
| Implementation | `ScheduleAnalysisService` → `team_schedule_factors` |
| Formula | `days_rest = game_date - previous_game_date - 1` (team perspective); `is_b2b = (days_rest == 0)`; rest edge vs opponent when both sides available; denser windows (e.g. 3-in-4 / 4-in-6) as implemented in service. |
| Grain | `(game_id, team_id)` |
| As-of rules | Uses schedule rows known for that game; safe if prior games are historical facts. |
| Interpretation | Schedule pressure / rest advantage entering the game. |
| Prohibited uses | Do not use post-game reschedule artifacts without actual tip semantics; exclude All-Star/special games from modeling sets. |

---

## Game environment (daily context)

| Field | Value |
| --- | --- |
| Metric ID | `game.environment_daily` |
| Version | `game_environment.v1` |
| Implementation | daily environment calc → `game_environment_daily` |
| Formula | Assembles matchup context from schedule factors + team metrics for a game date (see service/table columns). |
| Grain | `(game_id, game_date)` |
| As-of rules | Oriented to the calculation day's slate; verify column-level sources before modeling. |
| Interpretation | Packaged pregame context for daily UI. |
| Prohibited uses | Do not assume leakage-safe historical rebuild until each input is pinned to pre-tipoff snapshots. |

---

## Odds observations

| Field | Value |
| --- | --- |
| Metric ID | `game.odds_observation` |
| Version | `game_odds.v1` |
| Implementation | `OddsService` / `game_odds` |
| Formula | Store sportsbook moneyline + spread (current/open/trend) as returned by NBA odds feed at `recorded_at`. |
| Grain | `(game_id, sportsbook_id)` observation (updated in place) |
| As-of rules | Timestamped by `recorded_at` / `updated_at`. Not guaranteed closing line. |
| Interpretation | Market snapshot for today's games. |
| Prohibited uses | Do not backfill historical model evaluation with later lines; do not treat as full multi-book consensus without book coverage checks. |

---

## Availability / injury observations

| Field | Value |
| --- | --- |
| Metric ID | `player.game_status` |
| Version | `player_game_status.v1` |
| Implementation | injury/boxscore fetch → `player_game_status` |
| Formula | Per player-game: ACTIVE/INACTIVE, reason codes, description, `played` flag from live boxscore. |
| Grain | `(game_id, player_id)` |
| As-of rules | Captured at fetch time (`recorded_at`); may lag true injury news. |
| Interpretation | Availability observation for a game, not a medical diagnosis. |
| Prohibited uses | Do not invent historical injury timelines; sparse coverage ≠ healthy roster. |

---

## Planned (not implemented as production metrics)

See `MODEL_FEATURE_PLAN.md` for future `team_game_features`, labels, and model predictions. Those must record immutable `model_version`, `feature_version`, prediction time, training cutoff, and input completeness before product use.

## Related docs

* `SOURCE_CATALOG.md` — upstream endpoints
* `DATABASE_PROFILE.md` — live coverage / null rates
* `MODEL_FEATURE_PLAN.md` — leakage rules
* `DATA_DICTIONARY.md` — raw table columns
