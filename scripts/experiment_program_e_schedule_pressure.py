"""Read-only sensitivity and outcome comparison for Schedule Pressure v0.1.

The score is calculated from pregame inputs first. Final team results are
joined afterward only as retrospective evaluation labels. This script never
writes metric rows or alters source tables.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
from app.services.metric_research_service import (
    SchedulePressureObservation,
    calculate_schedule_pressure,
)


WEIGHT_SCENARIOS = {
    "baseline_v0_1": (0.45, 0.35, 0.20),
    "equal_components": (1 / 3, 1 / 3, 1 / 3),
    "rest_heavy": (0.60, 0.25, 0.15),
    "density_heavy": (0.25, 0.60, 0.15),
    "opponent_disadvantage_heavy": (0.35, 0.25, 0.40),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the read-only Schedule Pressure sensitivity experiment"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    return parser.parse_args()


def _score(components: dict[str, float], weights: tuple[float, float, float]) -> float:
    value = 100 * sum(
        component * weight
        for component, weight in zip(
            (
                components["short_rest_pressure"],
                components["schedule_density_pressure"],
                components["opponent_rest_disadvantage"],
            ),
            weights,
        )
    )
    return round(max(0.0, min(100.0, value)), 4)


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_sum = sum((x - left_mean) ** 2 for x in left)
    right_sum = sum((y - right_mean) ** 2 for y in right)
    denominator = (left_sum * right_sum) ** 0.5
    return round(numerator / denominator, 4) if denominator else None


def _assign_quartiles(rows: list[dict]) -> None:
    """Assign balanced rank quartiles with deterministic tie-breaking."""
    ordered = sorted(
        rows,
        key=lambda row: (row["baseline_score"], row["game_id"], row["team_id"]),
    )
    labels = (
        "Q1_lowest_pressure",
        "Q2",
        "Q3",
        "Q4_highest_pressure",
    )
    for position, row in enumerate(ordered):
        row["quartile"] = labels[min(3, position * 4 // len(ordered))]


def _outcome_summary(rows: list[dict], score_key: str) -> dict:
    eligible = [row for row in rows if row["won"] is not None]
    if not eligible:
        return {"rows": 0, "win_rate": None, "mean_point_diff": None}
    return {
        "rows": len(eligible),
        "win_rate": round(sum(row["won"] for row in eligible) / len(eligible), 4),
        "mean_point_diff": round(
            sum(row["point_diff"] for row in eligible) / len(eligible), 4
        ),
        "mean_score": round(sum(row[score_key] for row in eligible) / len(eligible), 4),
    }


def run_experiment(args: argparse.Namespace) -> dict:
    db = SessionLocal()
    try:
        snapshot_query = db.query(TeamGameFeatureSnapshotORM).filter(
            TeamGameFeatureSnapshotORM.season == args.season,
            TeamGameFeatureSnapshotORM.season_type == args.season_type,
            TeamGameFeatureSnapshotORM.completeness_status == "complete",
        )
        if args.start_date:
            snapshot_query = snapshot_query.filter(
                TeamGameFeatureSnapshotORM.game_date >= args.start_date
            )
        if args.end_date:
            snapshot_query = snapshot_query.filter(
                TeamGameFeatureSnapshotORM.game_date <= args.end_date
            )
        snapshots = snapshot_query.order_by(
            TeamGameFeatureSnapshotORM.game_date,
            TeamGameFeatureSnapshotORM.game_id,
            TeamGameFeatureSnapshotORM.team_id,
            TeamGameFeatureSnapshotORM.feature_as_of,
        ).all()

        selected = {}
        for snapshot in snapshots:
            key = (str(snapshot.game_id), snapshot.team_id)
            if key not in selected or snapshot.feature_as_of > selected[key].feature_as_of:
                selected[key] = snapshot

        environment_query = db.query(GameEnvironmentSnapshotORM.game_id).filter(
            GameEnvironmentSnapshotORM.season == args.season,
            GameEnvironmentSnapshotORM.season_type == args.season_type,
            GameEnvironmentSnapshotORM.completeness_status == "complete",
        )
        if args.start_date:
            environment_query = environment_query.filter(
                GameEnvironmentSnapshotORM.game_date >= args.start_date
            )
        if args.end_date:
            environment_query = environment_query.filter(
                GameEnvironmentSnapshotORM.game_date <= args.end_date
            )
        environment_games = {row[0] for row in environment_query.distinct().all()}

        game_teams = defaultdict(set)
        for snapshot in selected.values():
            game_teams[str(snapshot.game_id)].add(snapshot.team_id)
        paired_games = {
            game_id for game_id, teams in game_teams.items() if len(teams) == 2
        } & environment_games

        factor_rows = db.query(TeamScheduleFactorsORM).filter(
            TeamScheduleFactorsORM.season == args.season
        ).all()
        factors = {(str(row.game_id), row.team_id): row for row in factor_rows}

        outcome_query = db.query(TeamGameStatsORM).filter(
            TeamGameStatsORM.season == args.season,
            TeamGameStatsORM.game_id.in_(paired_games),
        )
        outcomes = {
            (str(row.game_id), row.team_id): row for row in outcome_query.all()
        }
        outcome_pairs = {}
        for (game_id, team_id), row in outcomes.items():
            opponent = outcomes.get((game_id, row.opponent_team_id))
            outcome_pairs[(game_id, team_id)] = {
                "won": 1 if row.wl == "W" else 0 if row.wl == "L" else None,
                "result": row.wl,
                "point_diff": (
                    row.pts - opponent.pts
                    if row.pts is not None and opponent is not None and opponent.pts is not None
                    else None
                ),
            }

        status_counts = Counter()
        rows = []
        for snapshot in selected.values():
            game_id = str(snapshot.game_id)
            if game_id not in paired_games:
                continue
            factor = factors.get((game_id, snapshot.team_id))
            if factor is None:
                status_counts["missing_schedule_factor"] += 1
                continue
            result = calculate_schedule_pressure(
                SchedulePressureObservation(
                    game_id=game_id,
                    team_id=snapshot.team_id,
                    season=snapshot.season,
                    season_type=snapshot.season_type,
                    feature_as_of=snapshot.feature_as_of,
                    data_available_at=snapshot.data_available_at,
                    days_rest=factor.days_rest,
                    opponent_days_rest=factor.opponent_days_rest,
                    rest_diff=factor.rest_diff,
                    is_b2b=factor.is_b2b,
                    is_3_in_4=factor.is_3_in_4,
                    is_4_in_5=factor.is_4_in_5,
                    is_5_in_7=factor.is_5_in_7,
                    games_last_4=factor.games_last_4,
                    games_last_7=factor.games_last_7,
                )
            )
            status_counts[result.completeness_status] += 1
            if result.value is None:
                continue
            outcome = outcome_pairs.get((game_id, snapshot.team_id), {})
            rows.append(
                {
                    "game_id": game_id,
                    "team_id": snapshot.team_id,
                    "baseline_score": result.value,
                    "components": dict(result.components),
                    "won": outcome.get("won"),
                    "result": outcome.get("result"),
                    "point_diff": outcome.get("point_diff"),
                }
            )

        _assign_quartiles(rows)

        outcome_rows = [row for row in rows if row["won"] is not None and row["point_diff"] is not None]
        baseline_scores = [row["baseline_score"] for row in outcome_rows]
        wins = [float(row["won"]) for row in outcome_rows]
        diffs = [float(row["point_diff"]) for row in outcome_rows]
        quartiles = {}
        for label in ("Q1_lowest_pressure", "Q2", "Q3", "Q4_highest_pressure"):
            quartiles[label] = _outcome_summary(
                [row for row in outcome_rows if row["quartile"] == label],
                "baseline_score",
            )

        rows_by_game = defaultdict(list)
        for row in outcome_rows:
            rows_by_game[row["game_id"]].append(row)
        paired_game_comparisons = []
        for game_id, game_rows in rows_by_game.items():
            if len(game_rows) != 2 or {row["result"] for row in game_rows} != {"W", "L"}:
                continue
            winner = next(row for row in game_rows if row["result"] == "W")
            loser = next(row for row in game_rows if row["result"] == "L")
            paired_game_comparisons.append(
                {
                    "winner_pressure": winner["baseline_score"],
                    "loser_pressure": loser["baseline_score"],
                    "winner_minus_loser_pressure": (
                        winner["baseline_score"] - loser["baseline_score"]
                    ),
                }
            )
        winner_pressure_deltas = [
            row["winner_minus_loser_pressure"] for row in paired_game_comparisons
        ]
        paired_game_evaluation = {
            "games": len(paired_game_comparisons),
            "mean_winner_minus_loser_pressure": round(
                sum(winner_pressure_deltas) / len(winner_pressure_deltas), 4
            )
            if winner_pressure_deltas
            else None,
            "winner_had_higher_pressure_rate": round(
                sum(delta > 0 for delta in winner_pressure_deltas)
                / len(winner_pressure_deltas),
                4,
            )
            if winner_pressure_deltas
            else None,
            "winner_had_lower_pressure_rate": round(
                sum(delta < 0 for delta in winner_pressure_deltas)
                / len(winner_pressure_deltas),
                4,
            )
            if winner_pressure_deltas
            else None,
            "pressure_tie_rate": round(
                sum(delta == 0 for delta in winner_pressure_deltas)
                / len(winner_pressure_deltas),
                4,
            )
            if winner_pressure_deltas
            else None,
        }

        sensitivity = {}
        baseline_top = {
            (row["game_id"], row["team_id"])
            for row in sorted(rows, key=lambda item: item["baseline_score"], reverse=True)[
                : max(1, len(rows) // 4)
            ]
        }
        for name, weights in WEIGHT_SCENARIOS.items():
            scores = [_score(row["components"], weights) for row in rows]
            for row, score in zip(rows, scores):
                row[f"scenario_{name}"] = score
            scenario_top = {
                (row["game_id"], row["team_id"])
                for row in sorted(rows, key=lambda item: item[f"scenario_{name}"], reverse=True)[: max(1, len(rows) // 4)]
            }
            deltas = [abs(score - row["baseline_score"]) for row, score in zip(rows, scores)]
            sensitivity[name] = {
                "weights": weights,
                "score_min": min(scores) if scores else None,
                "score_max": max(scores) if scores else None,
                "mean_absolute_delta_from_baseline": round(sum(deltas) / len(deltas), 4)
                if deltas
                else None,
                "rank_correlation_to_baseline": _pearson(
                    [row["baseline_score"] for row in rows], scores
                ),
                "top_quartile_overlap": round(
                    len(baseline_top & scenario_top) / len(baseline_top), 4
                )
                if baseline_top
                else None,
            }

        return {
            "mode": "read-only",
            "metric_id": "schedule_pressure_index",
            "metric_version": "schedule-pressure-v0.1",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "selection_rule": "latest feature_as_of per (game_id, team_id)",
            "paired_complete_environment_games": len(paired_games),
            "scored_team_rows": len(rows),
            "score_status_counts": dict(sorted(status_counts.items())),
            "outcome_rows_with_wl_and_point_diff": len(outcome_rows),
            "outcome_coverage": round(len(outcome_rows) / len(rows), 4) if rows else None,
            "baseline_outcome_correlation": {
                "score_vs_win_indicator": _pearson(baseline_scores, wins),
                "score_vs_point_diff": _pearson(baseline_scores, diffs),
            },
            "baseline_quartile_outcomes": quartiles,
            "paired_game_evaluation": paired_game_evaluation,
            "sensitivity": sensitivity,
            "interpretation": "Descriptive retrospective comparison only; no causal or predictive claim.",
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_experiment(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
