"""Run the read-only Program G16 frozen feature holdout sweep."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.model_baseline_experiment_service import (
    SCHEDULE_COMPONENT_VARIANTS,
    run_feature_family_season_heldout_sweep,
)
from app.services.model_input_audit_service import audit_model_inputs
from scripts.run_program_g_window_sweep import _build_games, _load_season
from scripts.program_g_heldout_monitoring import summarize_heldout_incremental_lift


G15_CANDIDATES = (
    "strength_form_b2b",
    "strength_form_4_in_5",
    "strength_form_5_in_7",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Program G16 frozen source-season feature holdout review"
    )
    parser.add_argument("--season", action="append", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--candidate", action="append", choices=tuple(G15_CANDIDATES))
    parser.add_argument("--min-train-games", type=int, default=50)
    parser.add_argument("--minimum-heldout-coverage", type=float, default=0.95)
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

        selected = args.candidate or G15_CANDIDATES
        definitions = {
            "strength_form_control": ("strength", "form"),
            **{name: SCHEDULE_COMPONENT_VARIANTS[name] for name in selected},
        }
        report = run_feature_family_season_heldout_sweep(
            games_by_season,
            definitions,
            min_train_games=args.min_train_games,
            minimum_heldout_coverage=args.minimum_heldout_coverage,
        )
        report.update({
            "season_type": args.season_type,
            "candidates": list(definitions),
            "audits": {
                season: {
                    "status": audit["status"],
                    "eligible_games": audit["eligible_games"],
                }
                for season, audit in audits.items()
            },
            "experiment": "program_g_feature_heldout_v1",
        })
        report["incremental_lift_monitoring"] = summarize_heldout_incremental_lift(report)
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "complete" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
