"""Run the supported Style Collision Map pace interaction read-only experiment."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.metric_research_service import calculate_style_collision_pace
from scripts.audit_program_e_style_collision import _load_safe_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the read-only Style Collision pace interaction experiment"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--minimum-reference-size", type=int, default=20)
    return parser.parse_args()


def _is_target(snapshot, args: argparse.Namespace) -> bool:
    return (
        (args.start_date is None or snapshot.game_date >= args.start_date)
        and (args.end_date is None or snapshot.game_date <= args.end_date)
    )


def _summary(results: list[dict]) -> dict:
    complete = [row for row in results if row["status"] == "complete"]
    withheld = [row for row in results if row["status"] != "complete"]
    combined = [row["combined_value"] for row in complete]
    contrast = [row["contrast"] for row in complete]
    percentiles = [row["combined_percentile"] for row in complete]
    reasons = defaultdict(int)
    for row in withheld:
        for reason in row["missing_inputs"]:
            reasons[reason] += 1
    return {
        "target_games": len(results),
        "complete_games": len(complete),
        "withheld_games": len(withheld),
        "withheld_reasons": dict(sorted(reasons.items())),
        "combined_pace_min": min(combined) if combined else None,
        "combined_pace_max": max(combined) if combined else None,
        "combined_pace_mean": round(sum(combined) / len(combined), 4) if combined else None,
        "contrast_min": min(contrast) if contrast else None,
        "contrast_max": max(contrast) if contrast else None,
        "contrast_mean": round(sum(contrast) / len(contrast), 4) if contrast else None,
        "percentile_mean": round(sum(percentiles) / len(percentiles), 4) if percentiles else None,
    }


def run_experiment(args: argparse.Namespace) -> dict:
    if args.minimum_reference_size < 2:
        raise ValueError("--minimum-reference-size must be at least 2")
    db = SessionLocal()
    try:
        source_args = copy.copy(args)
        source_args.start_date = None
        source_args.end_date = None
        all_rows, safe_source_games, cutoff_rejections = _load_safe_rows(db, source_args)
        rows_by_game = defaultdict(list)
        for snapshot in all_rows:
            rows_by_game[str(snapshot.game_id)].append(snapshot)
        target_game_ids = {
            game_id
            for game_id, rows in rows_by_game.items()
            if any(_is_target(row, args) for row in rows)
        }
        cutoff_groups = defaultdict(list)
        for snapshot in all_rows:
            cutoff_groups[snapshot.feature_as_of].append(snapshot)

        prior_combined_paces = []
        results = []
        for cutoff in sorted(cutoff_groups):
            group = cutoff_groups[cutoff]
            target_group_ids = {
                str(snapshot.game_id)
                for snapshot in group
                if str(snapshot.game_id) in target_game_ids
            }
            for game_id in sorted(target_group_ids):
                team_rows = rows_by_game[game_id]
                home_rows = [row for row in team_rows if row.is_home]
                away_rows = [row for row in team_rows if not row.is_home]
                if len(home_rows) != 1 or len(away_rows) != 1:
                    continue
                result = calculate_style_collision_pace(
                    home_rows[0].pace_lastn,
                    away_rows[0].pace_lastn,
                    prior_combined_paces,
                    minimum_reference_size=args.minimum_reference_size,
                ).as_dict()
                results.append(
                    {
                        "game_id": game_id,
                        "game_date": home_rows[0].game_date.isoformat(),
                        "feature_as_of": cutoff.isoformat(),
                        **result,
                    }
                )
            for game_id, team_rows in rows_by_game.items():
                if not any(row.feature_as_of == cutoff for row in team_rows):
                    continue
                home_rows = [row for row in team_rows if row.is_home]
                away_rows = [row for row in team_rows if not row.is_home]
                if len(home_rows) == 1 and len(away_rows) == 1:
                    home_pace = home_rows[0].pace_lastn
                    away_pace = away_rows[0].pace_lastn
                    if home_pace is not None and away_pace is not None:
                        prior_combined_paces.append((home_pace + away_pace) / 2)

        complete_results = [row for row in results if row["status"] == "complete"]
        complete_results.sort(key=lambda row: row["combined_value"])
        examples = []
        if complete_results:
            indexes = sorted({0, len(complete_results) // 2, len(complete_results) - 1})
            examples = [complete_results[index] for index in indexes]
        return {
            "mode": "read-only-experiment",
            "research_track": "style_collision_map",
            "edge_id": "pace_preference_interaction",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "reference_scope": "same-season safe paired games with strictly earlier feature_as_of",
            "minimum_reference_size": args.minimum_reference_size,
            "safe_source_games": safe_source_games,
            "safe_source_rows": len(all_rows),
            "cutoff_rejections": dict(sorted(cutoff_rejections.items())),
            "summary": _summary(results),
            "examples": examples,
            "writes_performed": False,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_experiment(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
