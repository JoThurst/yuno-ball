"""Run a read-only, pregame-safe scaling experiment for Program E.

Each target row is compared with a same-season reference distribution built
only from strictly earlier feature cutoffs. The script does not write metric
values, choose production thresholds, or create a persistent 0-100 field.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from math import isfinite
from pathlib import Path
from statistics import median
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.services.metric_research_service import calculate_pregame_percentile


MINIMUM_REFERENCE_SIZE = 20

FIELD_SOURCES = {
    "target_opponent_net_rtg_season": lambda row, opponent: (
        opponent.net_rtg_season if opponent else None
    ),
    "target_opponent_net_rtg_lastn": lambda row, opponent: (
        opponent.net_rtg_lastn if opponent else None
    ),
    "team_sos_net_season": lambda row, opponent: row.sos_net_season,
    "team_sos_net_lastn": lambda row, opponent: row.sos_net_lastn,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare raw and point-in-time percentile Opponent Difficulty / SoS presentations"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--minimum-reference-size", type=int, default=MINIMUM_REFERENCE_SIZE)
    return parser.parse_args()


def _aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _selected_complete_snapshots(db, args: argparse.Namespace) -> dict:
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


def _is_pregame_safe(team_rows: list[object]) -> bool:
    if len(team_rows) != 2:
        return False
    cutoffs = {snapshot.feature_as_of for snapshot in team_rows}
    versions = {snapshot.calculation_version for snapshot in team_rows}
    if len(cutoffs) != 1 or len(versions) != 1:
        return False
    for snapshot in team_rows:
        cutoff = _aware_utc(snapshot.feature_as_of)
        tipoff = _aware_utc(snapshot.scheduled_tipoff)
        available = _aware_utc(snapshot.data_available_at)
        if cutoff is None or tipoff is None or available is None:
            return False
        if cutoff >= tipoff or available > cutoff:
            return False
    return True


def _eligible_rows(db, args: argparse.Namespace) -> tuple[list[object], int]:
    selected = _selected_complete_snapshots(db, args)
    rows_by_game = defaultdict(list)
    for snapshot in selected.values():
        rows_by_game[str(snapshot.game_id)].append(snapshot)
    safe_games = {
        game_id
        for game_id, team_rows in rows_by_game.items()
        if _is_pregame_safe(team_rows)
    }
    target_games = {
        game_id
        for game_id in safe_games
        if any(
            (
                args.start_date is None
                or snapshot.game_date >= args.start_date
            )
            and (
                args.end_date is None
                or snapshot.game_date <= args.end_date
            )
            for snapshot in rows_by_game[game_id]
        )
    }
    return [
        snapshot
        for (game_id, _), snapshot in selected.items()
        if game_id in safe_games
    ], len(target_games)


def _field_value(field_name: str, row, opponent) -> Optional[float]:
    value = FIELD_SOURCES[field_name](row, opponent)
    return float(value) if value is not None and isfinite(value) else None


def _target_snapshot(snapshot, args: argparse.Namespace) -> bool:
    if args.start_date is not None and snapshot.game_date < args.start_date:
        return False
    if args.end_date is not None and snapshot.game_date > args.end_date:
        return False
    return True


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


def _candidate_summary(evaluations: list[dict], field_name: str) -> dict:
    rows = [row for row in evaluations if row["field"] == field_name]
    complete = [row for row in rows if row["completeness_status"] == "complete"]
    partial_counts = Counter(
        reason
        for row in rows
        if row["completeness_status"] != "complete"
        for reason in row["missing_inputs"]
    )
    reference_sizes = [row["reference_size"] for row in rows]
    percentiles = [row["percentile"] for row in complete]
    ranks = [row["rank"] for row in complete]
    raw_values = [row["value"] for row in complete]
    outcome_rows = [
        row
        for row in complete
        if row["won"] is not None and row["point_diff"] is not None
    ]
    raw_outcomes = [row["value"] for row in outcome_rows]
    percentile_outcomes = [row["percentile"] for row in outcome_rows]
    wins = [float(row["won"]) for row in outcome_rows]
    point_diffs = [float(row["point_diff"]) for row in outcome_rows]
    return {
        "target_rows": len(rows),
        "scaled_rows": len(complete),
        "withheld_rows": len(rows) - len(complete),
        "withheld_reasons": dict(sorted(partial_counts.items())),
        "reference_size_min": min(reference_sizes) if reference_sizes else None,
        "reference_size_median": median(reference_sizes) if reference_sizes else None,
        "reference_size_max": max(reference_sizes) if reference_sizes else None,
        "percentile_min": min(percentiles) if percentiles else None,
        "percentile_max": max(percentiles) if percentiles else None,
        "percentile_mean": round(sum(percentiles) / len(percentiles), 4) if percentiles else None,
        "rank_min": min(ranks) if ranks else None,
        "rank_max": max(ranks) if ranks else None,
        "raw_value_min": min(raw_values) if raw_values else None,
        "raw_value_max": max(raw_values) if raw_values else None,
        "raw_value_mean": round(sum(raw_values) / len(raw_values), 4) if raw_values else None,
        "outcome_rows": len(outcome_rows),
        "raw_win_correlation": _pearson(raw_outcomes, wins),
        "percentile_win_correlation": _pearson(percentile_outcomes, wins),
        "raw_point_diff_correlation": _pearson(raw_outcomes, point_diffs),
        "percentile_point_diff_correlation": _pearson(percentile_outcomes, point_diffs),
        "raw_percentile_order_correlation": _pearson(raw_values, percentiles),
    }


def run_experiment(args: argparse.Namespace) -> dict:
    if args.minimum_reference_size < 2:
        raise ValueError("--minimum-reference-size must be at least 2")
    db = SessionLocal()
    try:
        all_rows, safe_game_count = _eligible_rows(db, args)
        rows_by_game = defaultdict(list)
        for snapshot in all_rows:
            rows_by_game[str(snapshot.game_id)].append(snapshot)
        target_rows = [snapshot for snapshot in all_rows if _target_snapshot(snapshot, args)]
        target_game_ids = {str(snapshot.game_id) for snapshot in target_rows}
        outcomes = {
            (str(row.game_id), row.team_id): row
            for row in db.query(TeamGameStatsORM)
            .filter(
                TeamGameStatsORM.season == args.season,
                TeamGameStatsORM.game_id.in_(target_game_ids),
            )
            .all()
        }

        evaluations = []
        reference_values = {field_name: [] for field_name in FIELD_SOURCES}
        cutoff_groups = defaultdict(list)
        for snapshot in all_rows:
            cutoff_groups[_aware_utc(snapshot.feature_as_of)].append(snapshot)

        for cutoff in sorted(cutoff_groups):
            group = cutoff_groups[cutoff]
            for snapshot in group:
                game_id = str(snapshot.game_id)
                if game_id not in target_game_ids:
                    continue
                opponent = next(
                    (
                        candidate
                        for candidate in rows_by_game[game_id]
                        if candidate.team_id == snapshot.opponent_team_id
                    ),
                    None,
                )
                outcome = outcomes.get((game_id, snapshot.team_id))
                opponent_outcome = outcomes.get((game_id, snapshot.opponent_team_id))
                won = (
                    1 if outcome.wl == "W" else 0 if outcome.wl == "L" else None
                ) if outcome else None
                point_diff = (
                    outcome.pts - opponent_outcome.pts
                    if outcome
                    and opponent_outcome
                    and outcome.pts is not None
                    and opponent_outcome.pts is not None
                    else None
                )
                for field_name in FIELD_SOURCES:
                    result = calculate_pregame_percentile(
                        _field_value(field_name, snapshot, opponent),
                        reference_values[field_name],
                        minimum_reference_size=args.minimum_reference_size,
                    )
                    evaluations.append(
                        {
                            "game_id": game_id,
                            "team_id": snapshot.team_id,
                            "feature_as_of": cutoff.isoformat(),
                            "field": field_name,
                            "won": won,
                            "point_diff": point_diff,
                            **result.as_dict(),
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
                for field_name in FIELD_SOURCES:
                    value = _field_value(field_name, snapshot, opponent)
                    if value is not None:
                        reference_values[field_name].append(value)

        return {
            "mode": "read-only-scaling-experiment",
            "research_track": "opponent_difficulty_strength_of_schedule",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "reference_scope": "same-season eligible team rows with strictly earlier feature_as_of",
            "minimum_reference_size": args.minimum_reference_size,
            "safe_source_rows": len(all_rows),
            "safe_source_games": safe_game_count,
            "target_games": len(target_game_ids),
            "target_rows": len(target_rows),
            "candidates": {
                field_name: _candidate_summary(evaluations, field_name)
                for field_name in FIELD_SOURCES
            },
            "method": {
                "percentile": "midrank empirical percentile = 100 * (prior values below + 0.5 * prior ties) / prior reference size",
                "same_cutoff_policy": "target and same-cutoff rows are excluded before reference values are added",
                "raw_units_preserved": True,
            },
            "writes_performed": False,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_experiment(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
