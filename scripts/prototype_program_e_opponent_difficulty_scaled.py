"""Render read-only raw-plus-percentile Opponent Difficulty wording examples."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_sqlalchemy import TeamORM
from app.services.metric_research_service import (
    OpponentDifficultyObservation,
    build_opponent_difficulty_scaled_prototype,
    calculate_pregame_percentile,
)


MINIMUM_REFERENCE_SIZE = 20
FIELD_NAMES = (
    "target_opponent_net_rtg_season",
    "target_opponent_net_rtg_lastn",
    "team_sos_net_season",
    "team_sos_net_lastn",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render non-persistent Opponent Difficulty raw-plus-percentile wording examples"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--minimum-reference-size", type=int, default=MINIMUM_REFERENCE_SIZE)
    return parser.parse_args()


def _aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _field_value(field_name: str, snapshot, opponent) -> Optional[float]:
    if field_name == "target_opponent_net_rtg_season":
        value = opponent.net_rtg_season if opponent else None
    elif field_name == "target_opponent_net_rtg_lastn":
        value = opponent.net_rtg_lastn if opponent else None
    elif field_name == "team_sos_net_season":
        value = snapshot.sos_net_season
    else:
        value = snapshot.sos_net_lastn
    return float(value) if value is not None and isfinite(value) else None


def _load_safe_rows(db, args: argparse.Namespace) -> dict:
    snapshots = (
        db.query(TeamGameFeatureSnapshotORM)
        .filter(
            TeamGameFeatureSnapshotORM.season == args.season,
            TeamGameFeatureSnapshotORM.season_type == args.season_type,
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

    safe_games = set()
    for game_id, team_rows in rows_by_game.items():
        if game_id not in environment_games or len(team_rows) != 2:
            continue
        cutoffs = {snapshot.feature_as_of for snapshot in team_rows}
        versions = {snapshot.calculation_version for snapshot in team_rows}
        if len(cutoffs) != 1 or len(versions) != 1:
            continue
        if all(
            _aware_utc(snapshot.feature_as_of) is not None
            and _aware_utc(snapshot.scheduled_tipoff) is not None
            and _aware_utc(snapshot.data_available_at) is not None
            and _aware_utc(snapshot.feature_as_of) < _aware_utc(snapshot.scheduled_tipoff)
            and _aware_utc(snapshot.data_available_at) <= _aware_utc(snapshot.feature_as_of)
            for snapshot in team_rows
        ):
            safe_games.add(game_id)

    return {
        key: snapshot
        for key, snapshot in selected.items()
        if key[0] in safe_games
    }


def _is_target(snapshot, args: argparse.Namespace) -> bool:
    if args.start_date is not None and snapshot.game_date < args.start_date:
        return False
    if args.end_date is not None and snapshot.game_date > args.end_date:
        return False
    return True


def _sample(rows: list[dict], limit: int) -> list[dict]:
    if not rows:
        return []
    if limit == 1:
        return [rows[len(rows) // 2]]
    indexes = {
        round(index * (len(rows) - 1) / (limit - 1))
        for index in range(limit)
    }
    return [rows[index] for index in sorted(indexes)]


def run_prototype(args: argparse.Namespace) -> dict:
    if args.limit < 1:
        raise ValueError("--limit must be positive")
    if args.minimum_reference_size < 2:
        raise ValueError("--minimum-reference-size must be at least 2")

    db = SessionLocal()
    try:
        eligible = _load_safe_rows(db, args)
        rows_by_game = defaultdict(list)
        for snapshot in eligible.values():
            rows_by_game[str(snapshot.game_id)].append(snapshot)
        teams = {row.team_id: row.name for row in db.query(TeamORM).all()}
        cutoff_groups = defaultdict(list)
        for snapshot in eligible.values():
            cutoff_groups[_aware_utc(snapshot.feature_as_of)].append(snapshot)
        reference_values = {field_name: [] for field_name in FIELD_NAMES}
        renderable = []
        target_games = set()
        withheld_target_rows = 0

        for cutoff in sorted(cutoff_groups):
            group = cutoff_groups[cutoff]
            for snapshot in group:
                if not _is_target(snapshot, args):
                    continue
                game_id = str(snapshot.game_id)
                target_games.add(game_id)
                opponent = next(
                    (
                        candidate
                        for candidate in rows_by_game[game_id]
                        if candidate.team_id == snapshot.opponent_team_id
                    ),
                    None,
                )
                results = {
                    field_name: calculate_pregame_percentile(
                        _field_value(field_name, snapshot, opponent),
                        reference_values[field_name],
                        minimum_reference_size=args.minimum_reference_size,
                    )
                    for field_name in FIELD_NAMES
                }
                if any(result.completeness_status != "complete" for result in results.values()):
                    withheld_target_rows += 1
                    continue
                observation = OpponentDifficultyObservation(
                    game_id=game_id,
                    team_id=snapshot.team_id,
                    season=snapshot.season,
                    season_type=snapshot.season_type,
                    feature_as_of=snapshot.feature_as_of,
                    data_available_at=snapshot.data_available_at,
                    opponent_net_rtg_season=_field_value(
                        "target_opponent_net_rtg_season", snapshot, opponent
                    ),
                    opponent_net_rtg_lastn=_field_value(
                        "target_opponent_net_rtg_lastn", snapshot, opponent
                    ),
                    team_sos_net_season=_field_value(
                        "team_sos_net_season", snapshot, opponent
                    ),
                    team_sos_net_lastn=_field_value(
                        "team_sos_net_lastn", snapshot, opponent
                    ),
                )
                team_name = teams.get(snapshot.team_id, f"Team {snapshot.team_id}")
                opponent_name = teams.get(
                    snapshot.opponent_team_id,
                    f"Team {snapshot.opponent_team_id}",
                )
                renderable.append(
                    {
                        "snapshot": snapshot,
                        "opponent": opponent,
                        "observation": observation,
                        "team_name": team_name,
                        "opponent_name": opponent_name,
                        "opponent_recent": observation.opponent_net_rtg_lastn,
                        "styles": {
                            style: build_opponent_difficulty_scaled_prototype(
                                observation,
                                opponent_season_percentile=results[
                                    "target_opponent_net_rtg_season"
                                ].percentile,
                                opponent_recent_percentile=results[
                                    "target_opponent_net_rtg_lastn"
                                ].percentile,
                                team_sos_season_percentile=results[
                                    "team_sos_net_season"
                                ].percentile,
                                team_sos_recent_percentile=results[
                                    "team_sos_net_lastn"
                                ].percentile,
                                style=style,
                                team_name=team_name,
                                opponent_name=opponent_name,
                            ).as_dict()
                            for style in (
                                "raw_plus_percentile",
                                "percentile_first",
                                "compact",
                            )
                        },
                    }
                )
            for snapshot in group:
                game_id = str(snapshot.game_id)
                opponent = next(
                    (
                        candidate
                        for candidate in rows_by_game[game_id]
                        if candidate.team_id == snapshot.opponent_team_id
                    ),
                    None,
                )
                for field_name in FIELD_NAMES:
                    value = _field_value(field_name, snapshot, opponent)
                    if value is not None:
                        reference_values[field_name].append(value)

        renderable.sort(key=lambda row: row["opponent_recent"])
        examples = []
        for row in _sample(renderable, args.limit):
            snapshot = row["snapshot"]
            examples.append(
                {
                    "game_id": str(snapshot.game_id),
                    "game_date": snapshot.game_date.isoformat(),
                    "team_id": snapshot.team_id,
                    "opponent_team_id": snapshot.opponent_team_id,
                    "styles": row["styles"],
                }
            )
        return {
            "mode": "read-only",
            "research_track": "opponent_difficulty_strength_of_schedule",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "reference_scope": "same-season eligible team rows with strictly earlier feature_as_of",
            "minimum_reference_size": args.minimum_reference_size,
            "eligible_rows": len(eligible),
            "target_games": len(target_games),
            "renderable_rows": len(renderable),
            "withheld_target_rows": withheld_target_rows,
            "examples": examples,
            "writes_performed": False,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_prototype(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
