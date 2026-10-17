"""Audit cutoff-safe inputs before beginning Program G baseline experiments.

This command is read-only. It reports whether a season has paired, pregame
team features and final team-game labels suitable for a baseline experiment.
"""

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
from app.services.model_input_audit_service import audit_model_inputs
from app.utils.season_utils import get_current_season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Program G pregame model inputs without writing"
    )
    parser.add_argument("--season", default=None)
    parser.add_argument("--season-type", default="Regular Season")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    season = args.season or get_current_season()
    db = SessionLocal()
    try:
        team_rows = (
            db.query(TeamGameFeatureSnapshotORM)
            .filter(
                TeamGameFeatureSnapshotORM.season == season,
                TeamGameFeatureSnapshotORM.season_type == args.season_type,
                TeamGameFeatureSnapshotORM.completeness_status == "complete",
            )
            .all()
        )
        environment_rows = (
            db.query(GameEnvironmentSnapshotORM)
            .filter(
                GameEnvironmentSnapshotORM.season == season,
                GameEnvironmentSnapshotORM.season_type == args.season_type,
                GameEnvironmentSnapshotORM.completeness_status == "complete",
            )
            .all()
        )
        game_ids = {str(row.game_id) for row in team_rows}
        outcome_rows = (
            db.query(TeamGameStatsORM)
            .filter(
                TeamGameStatsORM.season == season,
                TeamGameStatsORM.game_id.in_(game_ids or {"__none__"}),
            )
            .all()
        )
        report = audit_model_inputs(
            season=season,
            season_type=args.season_type,
            team_rows=team_rows,
            environment_rows=environment_rows,
            outcome_rows=outcome_rows,
        )
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "ready_for_baseline_experiment" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
