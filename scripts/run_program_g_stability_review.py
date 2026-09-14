"""Run the read-only Program G12 candidate stability review."""

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
    compare_review_ready_feature_variants,
    review_feature_family_stability,
    run_feature_family_ablation,
)
from app.services.model_input_audit_service import audit_model_inputs
from scripts.run_program_g_window_sweep import _build_games, _load_season


G11_CANDIDATES = (
    "strength_form_schedule",
    "strength_form_schedule_matchup",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stress-test Program G candidates across chronological segments"
    )
    parser.add_argument("--season", action="append", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--min-train-games", type=int, default=50)
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--minimum-block-coverage", type=float, default=0.95)
    parser.add_argument(
        "--candidate",
        action="append",
        help="G11 candidate variant to stress-test; repeat for multiple candidates",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.blocks < 2:
        raise SystemExit("--blocks must be at least 2 for a segment review")
    db = SessionLocal()
    try:
        ablations = {}
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
            ablations[season] = run_feature_family_ablation(
                games,
                min_train_games=args.min_train_games,
                blocks=args.blocks,
            )

        if len(ablations) != len(args.season):
            print(json.dumps({
                "status": "blocked_input_audit",
                "audits": audits,
                "writes_performed": False,
            }, indent=2, default=str))
            return 2

        candidates = args.candidate or list(G11_CANDIDATES)
        candidate_reports = {
            season: {
                **report,
                "variants": {
                    name: report.get("variants", {})[name]
                    for name in candidates
                    if name in report.get("variants", {})
                },
            }
            for season, report in ablations.items()
        }
        comparison = compare_review_ready_feature_variants(candidate_reports)
        stability = review_feature_family_stability(
            ablations,
            candidates,
            minimum_block_coverage=args.minimum_block_coverage,
        )
        report = {
            **stability,
            "comparison": comparison,
            "season_type": args.season_type,
            "audits": {
                season: {
                    "status": audit["status"],
                    "eligible_games": audit["eligible_games"],
                }
                for season, audit in audits.items()
            },
            "experiment": "program_g_stability_review_v1",
        }
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "complete" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
