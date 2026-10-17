"""Run the read-only Program G historical naive baseline experiment."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.services.model_baseline_experiment_service import (
    BaselineGame,
    run_calibrated_elo_baseline_experiment,
    run_feature_family_ablation,
    run_elo_baseline_experiment,
    run_naive_baseline_experiment,
)
from app.services.model_input_audit_service import audit_model_inputs
from app.services.model_input_audit_service import select_latest_model_rows
from app.utils.season_utils import get_current_season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Program G naive baselines without writing")
    parser.add_argument("--season", default=None)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--min-train-games", type=int, default=50)
    parser.add_argument("--blocks", type=int, default=3)
    return parser.parse_args()


def _latest(rows, key_fields):
    return select_latest_model_rows(rows, key_fields)


def _safe_pregame_row(row) -> bool:
    feature_as_of = getattr(row, "feature_as_of", None)
    scheduled_tipoff = getattr(row, "scheduled_tipoff", None)
    if not isinstance(feature_as_of, datetime) or not isinstance(scheduled_tipoff, datetime):
        return False
    if feature_as_of >= scheduled_tipoff:
        return False
    data_available_at = getattr(row, "data_available_at", None)
    if isinstance(data_available_at, datetime) and data_available_at > feature_as_of:
        return False
    source_latest_game_date = getattr(row, "source_latest_game_date", None)
    game_date = getattr(row, "game_date", None)
    if isinstance(source_latest_game_date, date) and isinstance(game_date, date) and source_latest_game_date >= game_date:
        return False
    return not any(getattr(row, field, None) is not None for field in (
        "result", "wl", "pts", "point_diff", "home_score", "away_score",
    ))


def _build_games(team_rows, environment_rows, outcome_rows) -> tuple[list[BaselineGame], list[str]]:
    latest_team = _latest(team_rows, ("game_id", "team_id"))
    latest_environment = _latest(environment_rows, ("game_id",))
    outcomes = {(str(row.game_id), row.team_id): row for row in outcome_rows}
    by_game: defaultdict[str, list] = defaultdict(list)
    for row in latest_team.values():
        by_game[str(row.game_id)].append(row)

    games = []
    invalid_game_ids = []
    for game_id, perspectives in by_game.items():
        environment = latest_environment.get((game_id,))
        if environment is None or len(perspectives) != 2:
            continue
        home = next((row for row in perspectives if row.is_home), None)
        away = next((row for row in perspectives if not row.is_home), None)
        if (
            not home
            or not away
            or not _safe_pregame_row(home)
            or not _safe_pregame_row(away)
            or not _safe_pregame_row(environment)
            or environment.scheduled_tipoff != home.scheduled_tipoff
        ):
            invalid_game_ids.append(game_id)
            continue
        home_result = outcomes.get((game_id, home.team_id)) if home else None
        away_result = outcomes.get((game_id, away.team_id)) if away else None
        if not home or not away or not home_result or not away_result:
            continue
        if home_result.pts is None or away_result.pts is None:
            continue
        games.append(
            BaselineGame(
                game_id=game_id,
                scheduled_tipoff=home.scheduled_tipoff,
                home_win=int(home_result.pts > away_result.pts),
                home_margin=float(home_result.pts - away_result.pts),
                game_total=float(home_result.pts + away_result.pts),
                home_team_id=home.team_id,
                away_team_id=away.team_id,
                family_scores={
                    "strength": float(home.net_rtg_season - away.net_rtg_season)
                    if home.net_rtg_season is not None and away.net_rtg_season is not None else None,
                    "form": float(home.net_rtg_lastn - away.net_rtg_lastn)
                    if home.net_rtg_lastn is not None and away.net_rtg_lastn is not None else None,
                    "schedule": float((home.days_rest or 0) - (away.days_rest or 0))
                    if home.days_rest is not None and away.days_rest is not None else None,
                    # Positive values consistently mean the home team has the
                    # schedule advantage for every binary edge below.
                    "b2b_edge": float(int(bool(away.is_b2b)) - int(bool(home.is_b2b)))
                    if home.is_b2b is not None and away.is_b2b is not None else None,
                    "three_in_four_edge": float(
                        int(bool(away.is_3_in_4)) - int(bool(home.is_3_in_4))
                    )
                    if home.is_3_in_4 is not None and away.is_3_in_4 is not None else None,
                    "four_in_five_edge": float(
                        int(bool(away.is_4_in_5)) - int(bool(home.is_4_in_5))
                    )
                    if home.is_4_in_5 is not None and away.is_4_in_5 is not None else None,
                    "five_in_seven_edge": float(
                        int(bool(away.is_5_in_7)) - int(bool(home.is_5_in_7))
                    )
                    if home.is_5_in_7 is not None and away.is_5_in_7 is not None else None,
                    "rest_asymmetry": float((home.days_rest or 0) - (away.days_rest or 0))
                    if home.days_rest is not None and away.days_rest is not None else None,
                    # Pace is the only fully supported style interaction in
                    # the current snapshot grain; broader style edges remain
                    # a later experiment rather than a mixed-unit average.
                    "matchup_context": float(home.pace_lastn - away.pace_lastn)
                    if home.pace_lastn is not None and away.pace_lastn is not None else None,
                },
            )
        )
    return games, sorted(set(invalid_game_ids))


def main() -> int:
    args = parse_args()
    season = args.season or get_current_season()
    db = SessionLocal()
    try:
        team_rows = db.query(TeamGameFeatureSnapshotORM).filter(
            TeamGameFeatureSnapshotORM.season == season,
            TeamGameFeatureSnapshotORM.season_type == args.season_type,
            TeamGameFeatureSnapshotORM.completeness_status == "complete",
        ).all()
        environment_rows = db.query(GameEnvironmentSnapshotORM).filter(
            GameEnvironmentSnapshotORM.season == season,
            GameEnvironmentSnapshotORM.season_type == args.season_type,
            GameEnvironmentSnapshotORM.completeness_status == "complete",
        ).all()
        game_ids = {str(row.game_id) for row in team_rows}
        outcome_rows = db.query(TeamGameStatsORM).filter(
            TeamGameStatsORM.season == season,
            TeamGameStatsORM.game_id.in_(game_ids or {"__none__"}),
        ).all()
        audit = audit_model_inputs(
            season=season,
            season_type=args.season_type,
            team_rows=team_rows,
            environment_rows=environment_rows,
            outcome_rows=outcome_rows,
        )
        if audit["status"] != "ready_for_baseline_experiment":
            print(json.dumps({
                "status": audit["status"],
                "season": season,
                "season_type": args.season_type,
                "experiment": "chronological_naive_baselines_v1",
                "audit": audit,
                "writes_performed": False,
            }, indent=2, default=str))
            return 2
        games, builder_violations = _build_games(team_rows, environment_rows, outcome_rows)
        if builder_violations:
            print(json.dumps({
                "status": "blocked_builder_integrity",
                "season": season,
                "season_type": args.season_type,
                "invalid_game_ids": builder_violations,
                "writes_performed": False,
            }, indent=2, default=str))
            return 2
        naive_report = run_naive_baseline_experiment(
            games,
            min_train_games=args.min_train_games,
            blocks=args.blocks,
        )
        elo_report = run_elo_baseline_experiment(
            games,
            min_train_games=args.min_train_games,
            blocks=args.blocks,
        )
        calibrated_elo_report = run_calibrated_elo_baseline_experiment(
            games,
            min_train_games=args.min_train_games,
            blocks=args.blocks,
        )
        ablation_report = run_feature_family_ablation(
            games,
            min_train_games=args.min_train_games,
            blocks=args.blocks,
        )
        report = {
            "status": "complete" if all(
                item["status"] == "complete"
                for item in (naive_report, elo_report, calibrated_elo_report, ablation_report)
            ) else "blocked_baseline",
            "naive": naive_report,
            "elo": elo_report,
            "elo_calibrated": calibrated_elo_report,
            "feature_ablation": ablation_report,
            "writes_performed": False,
        }
        report.update({
            "season": season,
            "season_type": args.season_type,
            "input_games": len(games),
            "audit_status": audit["status"],
            "audit_eligible_games": audit["eligible_games"],
            "experiment": "chronological_naive_baselines_v1",
        })
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "complete" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
