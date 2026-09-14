"""Run the read-only Program G14 schedule-component stability sweep."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.model_baseline_experiment_service import (
    SCHEDULE_COMPONENT_VARIANTS,
    run_schedule_component_sweep,
)
from app.services.model_input_audit_service import audit_model_inputs
from scripts.run_program_g_window_sweep import _build_games, _load_season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Program G14 schedule component stability review"
    )
    parser.add_argument("--season", action="append", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--component", action="append", choices=tuple(SCHEDULE_COMPONENT_VARIANTS))
    parser.add_argument("--min-train-games", type=int, default=50)
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--minimum-block-coverage", type=float, default=0.95)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        games_by_season = {}
        audits = {}
        for season in args.season:
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
                continue
            games_by_season[season] = games

        if len(games_by_season) != len(args.season):
            print(json.dumps({
                "status": "blocked_input_audit",
                "audits": audits,
                "writes_performed": False,
            }, indent=2, default=str))
            return 2

        selected = args.component or tuple(SCHEDULE_COMPONENT_VARIANTS)
        definitions = {name: SCHEDULE_COMPONENT_VARIANTS[name] for name in selected}
        report = run_schedule_component_sweep(
            games_by_season,
            definitions=definitions,
            min_train_games=args.min_train_games,
            blocks=args.blocks,
            minimum_block_coverage=args.minimum_block_coverage,
        )
        report.update({
            "season_type": args.season_type,
            "audits": {
                season: {
                    "status": audit["status"],
                    "eligible_games": audit["eligible_games"],
                }
                for season, audit in audits.items()
            },
            "experiment": "program_g_schedule_components_v1",
        })
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "complete" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
