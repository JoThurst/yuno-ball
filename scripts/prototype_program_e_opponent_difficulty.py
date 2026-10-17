"""Render read-only raw-unit examples for Opponent Difficulty / SoS."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_sqlalchemy import TeamORM
from app.services.metric_research_service import (
    OpponentDifficultyObservation,
    build_opponent_difficulty_prototype,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render non-persistent Opponent Difficulty / SoS examples"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--limit", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")

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
        environment_games = {str(row[0]) for row in environment_query.distinct().all()}
        game_teams = {}
        for snapshot in selected.values():
            game_teams.setdefault(str(snapshot.game_id), set()).add(snapshot.team_id)
        eligible_games = {
            game_id for game_id, teams in game_teams.items() if len(teams) == 2
        } & environment_games
        eligible = {
            key: snapshot
            for key, snapshot in selected.items()
            if str(snapshot.game_id) in eligible_games
        }
        teams = {row.team_id: row.name for row in db.query(TeamORM).all()}

        rows = []
        for key, snapshot in eligible.items():
            opponent = eligible.get((key[0], snapshot.opponent_team_id))
            if opponent is None:
                continue
            rows.append((snapshot, opponent))
        rows.sort(key=lambda pair: pair[1].net_rtg_lastn)
        indexes = sorted({0, len(rows) // 2, len(rows) - 1})
        examples = []
        for snapshot, opponent in (rows[index] for index in indexes[: args.limit]):
            observation = OpponentDifficultyObservation(
                game_id=str(snapshot.game_id),
                team_id=snapshot.team_id,
                season=snapshot.season,
                season_type=snapshot.season_type,
                feature_as_of=snapshot.feature_as_of,
                data_available_at=snapshot.data_available_at,
                opponent_net_rtg_season=opponent.net_rtg_season,
                opponent_net_rtg_lastn=opponent.net_rtg_lastn,
                team_sos_net_season=snapshot.sos_net_season,
                team_sos_net_lastn=snapshot.sos_net_lastn,
            )
            prototype = build_opponent_difficulty_prototype(
                observation,
                team_name=teams.get(snapshot.team_id, f"Team {snapshot.team_id}"),
                opponent_name=teams.get(
                    snapshot.opponent_team_id,
                    f"Team {snapshot.opponent_team_id}",
                ),
            )
            examples.append(
                {
                    "game_id": str(snapshot.game_id),
                    "game_date": snapshot.game_date.isoformat(),
                    "team_id": snapshot.team_id,
                    "opponent_team_id": snapshot.opponent_team_id,
                    "prototype": prototype.as_dict(),
                }
            )

        print(
            json.dumps(
                {
                    "mode": "read-only",
                    "research_track": "opponent_difficulty_strength_of_schedule",
                    "season": args.season,
                    "season_type": args.season_type,
                    "eligible_rows": len(eligible),
                    "examples": examples,
                    "writes_performed": False,
                },
                indent=2,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
