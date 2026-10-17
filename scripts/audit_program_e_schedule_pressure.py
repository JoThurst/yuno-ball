"""Read-only Program E gate for the Schedule Pressure research candidate."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
from app.services.metric_research_service import (
    SchedulePressureObservation,
    calculate_schedule_pressure,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the read-only Program E Schedule Pressure cohort"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    return parser.parse_args()


def run_audit(args: argparse.Namespace) -> dict:
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
        selected_snapshots = {}
        for snapshot in snapshots:
            key = (str(snapshot.game_id), snapshot.team_id)
            current = selected_snapshots.get(key)
            if current is None or snapshot.feature_as_of > current.feature_as_of:
                selected_snapshots[key] = snapshot

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
        complete_environment_games = {row[0] for row in environment_query.distinct().all()}

        factor_rows = db.query(TeamScheduleFactorsORM).filter(
            TeamScheduleFactorsORM.season == args.season
        ).all()
        factors = {(str(row.game_id), row.team_id): row for row in factor_rows}

        game_rows = {}
        for snapshot in selected_snapshots.values():
            game_rows.setdefault(str(snapshot.game_id), set()).add(snapshot.team_id)
        snapshot_game_ids = set(game_rows)
        exact_pair_games = {
            game_id for game_id, teams in game_rows.items() if len(teams) == 2
        }
        non_pair_games = snapshot_game_ids - exact_pair_games
        paired_games = exact_pair_games & complete_environment_games

        status_counts = Counter()
        consistency_failures = Counter()
        missing_schedule_rows = 0
        scored_values = []
        for snapshot in selected_snapshots.values():
            game_id = str(snapshot.game_id)
            factor = factors.get((game_id, snapshot.team_id))
            if factor is None:
                missing_schedule_rows += 1
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
            for failure in result.missing_inputs:
                consistency_failures[failure] += 1
            if game_id in paired_games and result.value is not None:
                scored_values.append(result.value)

        return {
            "mode": "read-only",
            "metric_id": "schedule_pressure_index",
            "metric_version": "schedule-pressure-v0.1",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "complete_team_snapshot_rows": len(snapshots),
            "selected_team_snapshot_rows": len(selected_snapshots),
            "selection_rule": "latest feature_as_of per (game_id, team_id)",
            "collapsed_versioned_rows": len(snapshots) - len(selected_snapshots),
            "complete_team_snapshot_games": len(snapshot_game_ids),
            "exactly_paired_team_snapshot_games": len(exact_pair_games),
            "complete_environment_games": len(complete_environment_games),
            "paired_complete_environment_games": len(paired_games),
            "non_pair_team_snapshot_games": len(non_pair_games),
            "snapshot_only_games": len(snapshot_game_ids - complete_environment_games),
            "environment_only_games": len(complete_environment_games - snapshot_game_ids),
            "extra_team_rows_beyond_pair": sum(
                max(0, len(teams) - 2) for teams in game_rows.values()
            ),
            "missing_schedule_factor_rows": missing_schedule_rows,
            "result_status_counts": dict(sorted(status_counts.items())),
            "result_consistency_failures": dict(sorted(consistency_failures.items())),
            "scored_paired_team_rows": len(scored_values),
            "score_min": min(scored_values) if scored_values else None,
            "score_max": max(scored_values) if scored_values else None,
            "score_mean": round(sum(scored_values) / len(scored_values), 4)
            if scored_values
            else None,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_audit(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
