"""Render read-only user-language examples for Schedule Pressure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import TeamGameFeatureSnapshotORM
from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
from app.models.team_sqlalchemy import TeamORM
from app.services.metric_research_service import (
    SchedulePressureObservation,
    build_schedule_pressure_prototype,
    calculate_schedule_pressure,
)
from app.utils.season_utils import normalize_season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render non-persistent Schedule Pressure user-language examples"
    )
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--limit", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    season = normalize_season(args.season)
    db = SessionLocal()
    try:
        snapshots = (
            db.query(TeamGameFeatureSnapshotORM)
            .filter(
                TeamGameFeatureSnapshotORM.season == season,
                TeamGameFeatureSnapshotORM.season_type == "Regular Season",
                TeamGameFeatureSnapshotORM.completeness_status == "complete",
            )
            .order_by(
                TeamGameFeatureSnapshotORM.game_date,
                TeamGameFeatureSnapshotORM.game_id,
                TeamGameFeatureSnapshotORM.team_id,
                TeamGameFeatureSnapshotORM.feature_as_of,
            )
            .all()
        )
        latest = {}
        for snapshot in snapshots:
            key = (str(snapshot.game_id), snapshot.team_id)
            if key not in latest or snapshot.feature_as_of > latest[key].feature_as_of:
                latest[key] = snapshot

        factors = {
            (str(row.game_id), row.team_id): row
            for row in db.query(TeamScheduleFactorsORM).filter(
                TeamScheduleFactorsORM.season == season
            )
        }
        teams = {row.team_id: row.name for row in db.query(TeamORM).all()}
        scored = []
        for snapshot in latest.values():
            factor = factors.get((str(snapshot.game_id), snapshot.team_id))
            if factor is None:
                continue
            observation = SchedulePressureObservation(
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
            result = calculate_schedule_pressure(observation)
            if result.value is None:
                continue
            prototype = build_schedule_pressure_prototype(
                observation,
                result,
                team_name=teams.get(snapshot.team_id, f"Team {snapshot.team_id}"),
                opponent_name=teams.get(
                    snapshot.opponent_team_id,
                    f"Team {snapshot.opponent_team_id}",
                ),
            )
            scored.append(
                {
                    "game_id": str(snapshot.game_id),
                    "game_date": snapshot.game_date.isoformat(),
                    "team_id": snapshot.team_id,
                    "opponent_team_id": snapshot.opponent_team_id,
                    "score": result.value,
                    "prototype": prototype.as_dict(),
                }
            )

        scored.sort(key=lambda row: row["score"])
        indexes = sorted({0, len(scored) // 2, len(scored) - 1}) if scored else []
        examples = [scored[index] for index in indexes[: args.limit]]
        print(json.dumps({"mode": "read-only", "season": season, "examples": examples}, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
