"""Run Program G's read-only held-out validation across chronological windows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.services.model_baseline_experiment_service import (
    run_season_heldout_window_sweep,
)
from app.services.model_input_audit_service import audit_model_inputs
from scripts.run_program_g_baseline import _build_games


WINDOWS = {
    "50_25_25": (0.50, 0.25),
    "60_20_20": (0.60, 0.20),
    "70_15_15": (0.70, 0.15),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Program G held-out calibration across read-only time windows"
    )
    parser.add_argument("--source-season", required=True)
    parser.add_argument("--heldout-season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--profile", choices=tuple(WINDOWS), action="append")
    parser.add_argument("--min-train-games", type=int, default=50)
    parser.add_argument("--min-calibration-games", type=int, default=100)
    return parser.parse_args()


def _load_season(db, season: str, season_type: str) -> tuple[list, list, list]:
    team_rows = db.query(TeamGameFeatureSnapshotORM).filter(
        TeamGameFeatureSnapshotORM.season == season,
        TeamGameFeatureSnapshotORM.season_type == season_type,
        TeamGameFeatureSnapshotORM.completeness_status == "complete",
    ).all()
    environment_rows = db.query(GameEnvironmentSnapshotORM).filter(
        GameEnvironmentSnapshotORM.season == season,
        GameEnvironmentSnapshotORM.season_type == season_type,
        GameEnvironmentSnapshotORM.completeness_status == "complete",
    ).all()
    game_ids = {str(row.game_id) for row in team_rows}
    outcome_rows = db.query(TeamGameStatsORM).filter(
        TeamGameStatsORM.season == season,
        TeamGameStatsORM.game_id.in_(game_ids or {"__none__"}),
    ).all()
    return team_rows, environment_rows, outcome_rows


def _blocked(source_season: str, heldout_season: str, audits: dict) -> int:
    print(json.dumps({
        "status": "blocked_input_audit",
        "source_season": source_season,
        "heldout_season": heldout_season,
        "audits": audits,
        "writes_performed": False,
    }, indent=2, default=str))
    return 2


def main() -> int:
    args = parse_args()
    selected = args.profile or list(WINDOWS)
    windows = [
        (name, WINDOWS[name][0], WINDOWS[name][1])
        for name in selected
    ]
    db = SessionLocal()
    try:
        audits = {}
        games_by_season = {}
        for season in (args.source_season, args.heldout_season):
            team_rows, environment_rows, outcome_rows = _load_season(
                db, season, args.season_type
            )
            audit = audit_model_inputs(
                season=season,
                season_type=args.season_type,
                team_rows=team_rows,
                environment_rows=environment_rows,
                outcome_rows=outcome_rows,
            )
            audits[season] = audit
            if audit["status"] != "ready_for_baseline_experiment":
                continue
            games, builder_violations = _build_games(
                team_rows, environment_rows, outcome_rows
            )
            if builder_violations:
                return _blocked(args.source_season, args.heldout_season, audits)
            games_by_season[season] = games

        if len(games_by_season) != 2:
            return _blocked(args.source_season, args.heldout_season, audits)

        report = run_season_heldout_window_sweep(
            games_by_season[args.source_season],
            games_by_season[args.heldout_season],
            windows=windows,
            min_train_games=args.min_train_games,
            min_calibration_games=args.min_calibration_games,
        )
        report.update({
            "source_season": args.source_season,
            "heldout_season": args.heldout_season,
            "season_type": args.season_type,
            "audits": {
                season: {
                    "status": audit["status"],
                    "eligible_games": audit["eligible_games"],
                }
                for season, audit in audits.items()
            },
            "experiment": "program_g_window_sweep_v1",
        })
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "complete" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
