"""Run a read-only input-coverage audit for Program E Style Collision Map."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.services.metric_research_service import STYLE_COLLISION_EDGE_CATALOG


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit read-only Style Collision Map input coverage"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    return parser.parse_args()


def _aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _field_summary(rows: list[object], field_name: str) -> dict:
    if not hasattr(TeamGameFeatureSnapshotORM, field_name):
        return {
            "exists_in_snapshot_model": False,
            "rows": len(rows),
            "non_null": 0,
            "null": len(rows),
        }
    values = [getattr(row, field_name) for row in rows]
    return {
        "exists_in_snapshot_model": True,
        "rows": len(values),
        "non_null": sum(value is not None for value in values),
        "null": sum(value is None for value in values),
    }


def _load_safe_rows(db, args: argparse.Namespace) -> tuple[list[object], int, Counter]:
    query = db.query(TeamGameFeatureSnapshotORM).filter(
        TeamGameFeatureSnapshotORM.season == args.season,
        TeamGameFeatureSnapshotORM.season_type == args.season_type,
        TeamGameFeatureSnapshotORM.completeness_status == "complete",
    )
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

    environment_games = {
        str(row[0])
        for row in db.query(GameEnvironmentSnapshotORM.game_id)
        .filter(
            GameEnvironmentSnapshotORM.season == args.season,
            GameEnvironmentSnapshotORM.season_type == args.season_type,
            GameEnvironmentSnapshotORM.completeness_status == "complete",
        )
        .distinct()
        .all()
    }
    rows_by_game = defaultdict(list)
    for snapshot in selected.values():
        rows_by_game[str(snapshot.game_id)].append(snapshot)

    rejection_counts = Counter()
    safe_games = set()
    for game_id, team_rows in rows_by_game.items():
        if game_id not in environment_games:
            rejection_counts["missing_complete_environment"] += 1
            continue
        if len(team_rows) != 2:
            rejection_counts["not_exactly_two_team_rows"] += 1
            continue
        if len({row.feature_as_of for row in team_rows}) != 1:
            rejection_counts["pair_cutoff_mismatch"] += 1
            continue
        if len({row.calculation_version for row in team_rows}) != 1:
            rejection_counts["pair_version_mismatch"] += 1
            continue
        safe = True
        for row in team_rows:
            cutoff = _aware_utc(row.feature_as_of)
            tipoff = _aware_utc(row.scheduled_tipoff)
            available = _aware_utc(row.data_available_at)
            if cutoff is None or tipoff is None or available is None:
                rejection_counts["missing_cutoff_metadata"] += 1
                safe = False
            elif cutoff >= tipoff:
                rejection_counts["cutoff_not_pregame"] += 1
                safe = False
            elif available > cutoff:
                rejection_counts["input_after_cutoff"] += 1
                safe = False
        if safe:
            safe_games.add(game_id)

    safe_rows = [
        snapshot
        for (game_id, _), snapshot in selected.items()
        if game_id in safe_games
        and (args.start_date is None or snapshot.game_date >= args.start_date)
        and (args.end_date is None or snapshot.game_date <= args.end_date)
    ]
    return safe_rows, len(safe_games), rejection_counts


def run_audit(args: argparse.Namespace) -> dict:
    db = SessionLocal()
    try:
        rows, safe_games, rejections = _load_safe_rows(db, args)
        existing_fields = sorted(
            {
                field_name
                for edge in STYLE_COLLISION_EDGE_CATALOG
                for field_name in edge.required_inputs
                if hasattr(TeamGameFeatureSnapshotORM, field_name)
            }
        )
        field_summaries = {
            field_name: _field_summary(rows, field_name)
            for field_name in existing_fields
        }
        edges = []
        for edge in STYLE_COLLISION_EDGE_CATALOG:
            missing_inputs = [
                field_name
                for field_name in edge.required_inputs
                if not hasattr(TeamGameFeatureSnapshotORM, field_name)
            ]
            edges.append(
                {
                    **edge.as_dict(),
                    "missing_inputs": missing_inputs,
                    "eligible_for_prototype": not missing_inputs,
                }
            )
        return {
            "mode": "read-only-audit",
            "research_track": "style_collision_map",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "safe_source_games": safe_games,
            "safe_source_rows": len(rows),
            "cutoff_rejections": dict(sorted(rejections.items())),
            "existing_input_summaries": field_summaries,
            "edge_catalog": edges,
            "supported_edge_count": sum(edge["status"] == "supported" for edge in edges),
            "blocked_edge_count": sum(edge["status"] == "blocked" for edge in edges),
            "writes_performed": False,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_audit(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
