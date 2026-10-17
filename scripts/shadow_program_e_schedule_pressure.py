"""Run a read-only shadow evaluation for Schedule Pressure v0.1."""

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
    build_schedule_pressure_prototype,
    calculate_schedule_pressure,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a read-only Schedule Pressure v0.1 shadow evaluation"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    return parser.parse_args()


def _observation(snapshot, factor) -> SchedulePressureObservation:
    return SchedulePressureObservation(
        game_id=str(snapshot.game_id),
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


def run_shadow(args: argparse.Namespace) -> dict:
    db = SessionLocal()
    try:
        query = db.query(TeamGameFeatureSnapshotORM).filter(
            TeamGameFeatureSnapshotORM.season == args.season,
            TeamGameFeatureSnapshotORM.season_type == args.season_type,
            TeamGameFeatureSnapshotORM.completeness_status == "complete",
        )
        if args.start_date:
            query = query.filter(TeamGameFeatureSnapshotORM.game_date >= args.start_date)
        if args.end_date:
            query = query.filter(TeamGameFeatureSnapshotORM.game_date <= args.end_date)

        snapshots = query.order_by(
            TeamGameFeatureSnapshotORM.game_date,
            TeamGameFeatureSnapshotORM.game_id,
            TeamGameFeatureSnapshotORM.team_id,
            TeamGameFeatureSnapshotORM.feature_as_of,
        ).all()
        selected = {}
        for snapshot in snapshots:
            key = (str(snapshot.game_id), snapshot.team_id)
            current = selected.get(key)
            if current is None or snapshot.feature_as_of > current.feature_as_of:
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
        complete_environment_games = {
            str(row[0]) for row in environment_query.distinct().all()
        }
        game_teams = {}
        for snapshot in selected.values():
            game_teams.setdefault(str(snapshot.game_id), set()).add(snapshot.team_id)
        exactly_paired_games = {
            game_id for game_id, teams in game_teams.items() if len(teams) == 2
        }
        eligible_games = exactly_paired_games & complete_environment_games
        eligible = {
            key: snapshot
            for key, snapshot in selected.items()
            if str(snapshot.game_id) in eligible_games
        }

        factor_rows = db.query(TeamScheduleFactorsORM).filter(
            TeamScheduleFactorsORM.season == args.season
        ).all()
        factors = {(str(row.game_id), row.team_id): row for row in factor_rows}

        status_counts = Counter()
        label_counts = Counter()
        missing_factor_rows = 0
        replay_mismatches = []
        scores = []
        for snapshot in eligible.values():
            key = (str(snapshot.game_id), snapshot.team_id)
            factor = factors.get(key)
            if factor is None:
                missing_factor_rows += 1
                status_counts["missing_schedule_factor"] += 1
                continue

            observation = _observation(snapshot, factor)
            first = calculate_schedule_pressure(observation)
            replay = calculate_schedule_pressure(observation)
            if first.as_dict() != replay.as_dict():
                replay_mismatches.append(
                    {"game_id": key[0], "team_id": key[1]}
                )

            status_counts[first.completeness_status] += 1
            if first.value is None:
                continue
            prototype = build_schedule_pressure_prototype(observation, first)
            label_counts[prototype.label] += 1
            scores.append(first.value)

        return {
            "mode": "read-only-shadow",
            "metric_id": "schedule_pressure_index",
            "metric_version": "schedule-pressure-v0.1",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "source_snapshot_rows": len(snapshots),
            "selected_snapshot_rows": len(selected),
            "eligible_snapshot_rows": len(eligible),
            "selection_rule": "latest feature_as_of per (game_id, team_id)",
            "collapsed_versioned_rows": len(snapshots) - len(selected),
            "complete_environment_games": len(complete_environment_games),
            "exactly_paired_games": len(exactly_paired_games),
            "eligible_paired_environment_games": len(eligible_games),
            "excluded_snapshot_rows": len(selected) - len(eligible),
            "missing_schedule_factor_rows": missing_factor_rows,
            "result_status_counts": dict(sorted(status_counts.items())),
            "label_counts": dict(sorted(label_counts.items())),
            "replay_mismatch_count": len(replay_mismatches),
            "replay_mismatches": replay_mismatches,
            "scored_rows": len(scores),
            "score_min": min(scores) if scores else None,
            "score_max": max(scores) if scores else None,
            "score_mean": round(sum(scores) / len(scores), 4) if scores else None,
            "writes_performed": False,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_shadow(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
