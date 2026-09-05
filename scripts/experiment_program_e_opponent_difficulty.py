"""Run a read-only formula comparison for Opponent Difficulty / SoS."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM


CANDIDATES = {
    "target_opponent_net_rtg_lastn": lambda row: row["opponent_net_rtg_lastn"],
    "target_opponent_net_rtg_season": lambda row: row["opponent_net_rtg_season"],
    "target_opponent_net_rtg_blend_60_recent_40_season": lambda row: _blend(
        row["opponent_net_rtg_lastn"], row["opponent_net_rtg_season"]
    ),
    "team_sos_net_lastn": lambda row: row["team_sos_net_lastn"],
    "team_sos_net_season": lambda row: row["team_sos_net_season"],
    "team_sos_net_blend_60_recent_40_season": lambda row: _blend(
        row["team_sos_net_lastn"], row["team_sos_net_season"]
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare read-only Opponent Difficulty / SoS candidates"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    return parser.parse_args()


def _blend(recent: Optional[float], season: Optional[float]) -> Optional[float]:
    if recent is None or season is None:
        return None
    return round(0.6 * recent + 0.4 * season, 4)


def _pearson(left: list[float], right: list[float]) -> Optional[float]:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_sum = sum((x - left_mean) ** 2 for x in left)
    right_sum = sum((y - right_mean) ** 2 for y in right)
    denominator = (left_sum * right_sum) ** 0.5
    return round(numerator / denominator, 4) if denominator else None


def _eligible_snapshots(db, args: argparse.Namespace) -> dict:
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
    game_teams = defaultdict(set)
    for snapshot in selected.values():
        game_teams[str(snapshot.game_id)].add(snapshot.team_id)
    paired_games = {
        game_id for game_id, teams in game_teams.items() if len(teams) == 2
    } & environment_games
    return {
        key: snapshot
        for key, snapshot in selected.items()
        if str(snapshot.game_id) in paired_games
    }


def _candidate_summary(rows: list[dict], candidate_name: str) -> dict:
    values = [
        (row[candidate_name], row)
        for row in rows
        if row[candidate_name] is not None
    ]
    outcome_rows = [
        (value, row)
        for value, row in values
        if row["won"] is not None and row["point_diff"] is not None
    ]
    scores = [value for value, _ in outcome_rows]
    wins = [float(row["won"]) for _, row in outcome_rows]
    point_diffs = [float(row["point_diff"]) for _, row in outcome_rows]
    paired_differences = []
    winner_higher = winner_lower = tied = 0
    rows_by_game = defaultdict(list)
    for value, row in values:
        rows_by_game[row["game_id"]].append((value, row))
    for game_rows in rows_by_game.values():
        if len(game_rows) != 2 or any(row["won"] is None for _, row in game_rows):
            continue
        winner_value = next(value for value, row in game_rows if row["won"] == 1)
        loser_value = next(value for value, row in game_rows if row["won"] == 0)
        difference = round(winner_value - loser_value, 4)
        paired_differences.append(difference)
        if difference > 0:
            winner_higher += 1
        elif difference < 0:
            winner_lower += 1
        else:
            tied += 1

    return {
        "available_rows": len(values),
        "null_rows": len(rows) - len(values),
        "outcome_rows": len(outcome_rows),
        "value_min": min(scores) if scores else None,
        "value_max": max(scores) if scores else None,
        "value_mean": round(sum(scores) / len(scores), 4) if scores else None,
        "win_correlation": _pearson(scores, wins),
        "point_diff_correlation": _pearson(scores, point_diffs),
        "winner_minus_loser_mean": (
            round(sum(paired_differences) / len(paired_differences), 4)
            if paired_differences
            else None
        ),
        "winner_higher_lower_tied": {
            "higher": winner_higher,
            "lower": winner_lower,
            "tied": tied,
        },
    }


def run_experiment(args: argparse.Namespace) -> dict:
    db = SessionLocal()
    try:
        snapshots = _eligible_snapshots(db, args)
        outcomes = {
            (str(row.game_id), row.team_id): row
            for row in db.query(TeamGameStatsORM).filter(
                TeamGameStatsORM.season == args.season,
                TeamGameStatsORM.game_id.in_({key[0] for key in snapshots}),
            ).all()
        }
        rows = []
        for key, snapshot in snapshots.items():
            opponent = snapshots.get((key[0], snapshot.opponent_team_id))
            outcome = outcomes.get(key)
            opponent_outcome = (
                outcomes.get((key[0], outcome.opponent_team_id)) if outcome else None
            )
            rows.append(
                {
                    "game_id": key[0],
                    "team_id": key[1],
                    "opponent_net_rtg_lastn": (
                        opponent.net_rtg_lastn if opponent else None
                    ),
                    "opponent_net_rtg_season": (
                        opponent.net_rtg_season if opponent else None
                    ),
                    "team_sos_net_lastn": snapshot.sos_net_lastn,
                    "team_sos_net_season": snapshot.sos_net_season,
                    "won": (
                        1 if outcome.wl == "W" else 0 if outcome.wl == "L" else None
                    )
                    if outcome
                    else None,
                    "point_diff": (
                        outcome.pts - opponent_outcome.pts
                        if outcome
                        and opponent_outcome
                        and outcome.pts is not None
                        and opponent_outcome.pts is not None
                        else None
                    ),
                }
            )
        for row in rows:
            for candidate_name, candidate_fn in CANDIDATES.items():
                row[candidate_name] = candidate_fn(row)

        return {
            "mode": "read-only-experiment",
            "research_track": "opponent_difficulty_strength_of_schedule",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "eligible_rows": len(rows),
            "outcome_rows": sum(row["won"] is not None for row in rows),
            "candidates": {
                name: _candidate_summary(rows, name) for name in CANDIDATES
            },
            "blend_note": "60% recent plus 40% season is a sensitivity candidate, not an approved weight",
            "writes_performed": False,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_experiment(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
