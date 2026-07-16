# Yuno Ball Model Feature Plan

Status: Phase 3 feature-snapshot foundation implemented; no production model is confirmed
Reviewed: 2026-07-15 using the leakage-safe team/game snapshot implementation plus existing source coverage.

## First modeling objective

Start with calibrated pregame team models, not player props:

1. home-team win probability (binary classification);
2. expected home margin (regression);
3. expected game total (regression).

These share the same team-game feature snapshot and create a clean base for spread/total comparisons later. Betting-market data is not currently stored, so “against the spread” and closing-line value are out of scope until timestamped odds are ingested.

## Canonical observation grain

One row per game with home and away features computed strictly as of a pregame cutoff. The implemented underlying grain is `(game_id, team_id, window_size, feature_as_of, calculation_version)` in `team_game_feature_snapshots`; paired context is stored in `game_environment_snapshots` at the same cutoff/version.

Phase 3 currently implements the stable game-fact-derived subset: season/recent
efficiency and four-factor metrics, deltas, opponent net-strength summaries,
rest/density factors, flags, and paired game environments. Labels, training
datasets, walk-forward evaluation, and predictions remain future phases.

Recommended labels after final status:

* `home_win = home_score > away_score`
* `home_margin = home_score - away_score`
* `game_total = home_score + away_score`

Do not train on unfinished games, All-Star/special-event teams, or rows missing a consistent opponent pair.

## Feature groups

| Group                  | Initial features                                                                                                      | Source / computation                                                                         |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Team strength          | trailing 5/10/20 and season-to-date offensive rating, defensive rating, net rating, pace, eFG%, TOV%, ORB%, FT rate   | derive from `team_game_stats`; validate against curated fields from `league_dash_team_stats` |
| Opponent-adjusted form | team's recent offense vs opponents' pregame defensive strength; recent defense vs opponents' pregame offense          | rolling joins by prior game date only                                                        |
| Schedule               | home/away, rest days, back-to-back, 3-in-4, 4-in-6, travel proxy, rest differential                                   | `game_schedule`; venue/location data is future enrichment                                    |
| Matchup                | offense-vs-defense deltas, pace interaction, shooting profile vs opponent allowed profile, rebound and turnover edges | pregame rolling team and opponent features                                                   |
| Availability           | expected active rotation, missing minutes/usage, roster continuity                                                    | roster plus future injury/availability source; current roster alone is insufficient          |
| Season context         | season phase, games played, playoffs flag                                                                             | schedule and season type                                                                     |
| Stable priors          | previous-season strength blended down as current-season sample grows                                                  | prior seasons, with explicit decay                                                           |

Initial formulas:

* `rest_days = game_date - previous_game_date - 1`, capped for long breaks.
* `is_b2b = rest_days == 0`.
* `games_last_4_days`, `games_last_6_days` count games strictly before tipoff.
* `rest_advantage = home_rest_days - away_rest_days`.
* rolling metrics use `shift(1)` before every rolling/expanding calculation.
* matchup edges use `home_feature - away_feature`; retain raw home and away values as well.

## Leakage rules

These rules are mandatory:

* Feature timestamps must be earlier than scheduled tipoff. Store `feature_as_of` and `data_available_at` where possible.
* Never use the target game's result, score, box score, plus/minus, or postgame season totals.
* NBA season-to-date endpoint responses are dangerous for historical reconstruction because a query made today contains later games. Prefer rolling aggregates rebuilt from game-level tables.
* Shift rolling windows by one game. A row cannot contribute to its own features.
* Standings, rankings, streaks, injuries, rosters, and odds must be the version known before the game, not the current version.
* Split by time, never random row split. Keep both team perspectives of a game in the same fold.
* Fit scalers, imputers, encoders, calibration, and feature selection only on the training window.
* Do not use `team_game_stats.plus_minus` until ingestion stops forcing it to zero.
* Do not treat the current `player_streaks` table as historical pregame data; it is a latest snapshot rebuilt daily.
* Exclude rescheduled/postponed games until scheduled and actual tipoff semantics are represented.

## Dataset construction

1. Canonicalize completed games into one row per game from paired schedule rows.
2. Validate scores and home/away identities.
3. Build team-game derived metrics from `team_game_stats`.
4. Sort by team and actual game time.
5. Calculate shifted rolling and expanding features.
6. Join the opposing team's snapshot for the same game.
7. Add schedule features using only prior schedule rows.
8. Materialize `feature_version`, `feature_as_of`, source cutoffs, and missingness flags.
9. Create labels in a separate step/table.

## Baselines and evaluation

| Target   | Baseline                                         | Candidate models                                        | Primary metrics                                   |
| -------- | ------------------------------------------------ | ------------------------------------------------------- | ------------------------------------------------- |
| home win | home-team rate; logistic regression              | regularized logistic regression, gradient-boosted trees | log loss, Brier score, ROC AUC, calibration error |
| margin   | predict historical home-court mean; linear/ridge | gradient boosting / XGBoost-style trees                 | MAE, RMSE; residuals by season/team/rest bucket   |
| total    | trailing league mean; linear/ridge               | gradient boosting                                       | MAE, RMSE; residuals by pace/season               |

Use walk-forward evaluation, for example train through season N-1 and validate/test on later chronological blocks. Report results by season and compare against a naive baseline. Accuracy alone is insufficient for probability products; calibration plots and Brier/log loss matter.

## Model registry and prediction output

Every prediction should record:

* `game_id`, scheduled tipoff, home/away team IDs;
* model name/version and feature version;
* training cutoff and prediction timestamp;
* win probability, expected margin, expected total;
* uncertainty or prediction interval where supported;
* input completeness flags and fallback path.

Never overwrite a prediction made earlier. Append revisions so the product and evaluation can distinguish morning, pregame, and later predictions.

## Implementation roadmap

1. Repair score, schedule, team-game, roster-history, and corrected-box-score data quality.
2. Reproducible game-level feature builder with cutoff, missingness, rerun, and leakage tests — implemented in Phase 3 (`team-v2.1`).
3. Establish simple logistic/ridge baselines and walk-forward evaluation.
4. Add boosted-tree models only after baselines and calibration are stable.
5. Persist predictions and show model/as-of metadata in the UI.
6. Add timestamped odds later for market comparison; never backfill historical predictions using future closing lines.
