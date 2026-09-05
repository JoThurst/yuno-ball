"""Audit leakage-safe inputs for the Program E Opponent Difficulty / SoS track."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)


FIELD_SEMANTICS = {
    "target_opponent_net_rtg_season": "opponent snapshot net_rtg_season at the target-game cutoff",
    "target_opponent_net_rtg_lastn": "opponent snapshot net_rtg_lastn at the target-game cutoff",
    "target_opponent_net_rtg_delta": "opponent snapshot net_rtg_delta at the target-game cutoff",
    "team_sos_net_season": "team snapshot sos_net_season from prior opponents",
    "team_sos_net_lastn": "team snapshot sos_net_lastn from recent prior opponents",
    "team_sos_net_delta": "team snapshot sos_net_delta, recent SoS minus season SoS",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit read-only Opponent Difficulty / SoS input coverage"
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


def _summary(values: Iterable[Optional[float]]) -> dict:
    values_list = list(values)
    usable = [value for value in values_list if value is not None]
    return {
        "rows": len(values_list),
        "non_null": len(usable),
        "null": len(values_list) - len(usable),
        "min": min(usable) if usable else None,
        "max": max(usable) if usable else None,
        "mean": round(sum(usable) / len(usable), 4) if usable else None,
    }


def _field_value(field_name: str, snapshot, opponent) -> Optional[float]:
    if field_name.startswith("target_opponent_"):
        if opponent is None:
            return None
        source_field = field_name.removeprefix("target_opponent_")
        return getattr(opponent, source_field)
    source_field = field_name.removeprefix("team_")
    return getattr(snapshot, source_field)


def run_audit(args: argparse.Namespace) -> dict:
    db = SessionLocal()
    try:
        query = db.query(TeamGameFeatureSnapshotORM).filter(
            TeamGameFeatureSnapshotORM.season == args.season,
            TeamGameFeatureSnapshotORM.season_type == args.season_type,
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

        selected_status_counts = Counter(
            snapshot.completeness_status for snapshot in selected.values()
        )
        complete_selected = {
            key: snapshot
            for key, snapshot in selected.items()
            if snapshot.completeness_status == "complete"
        }

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
        for snapshot in complete_selected.values():
            game_teams.setdefault(str(snapshot.game_id), set()).add(snapshot.team_id)
        exactly_paired_games = {
            game_id for game_id, teams in game_teams.items() if len(teams) == 2
        }
        eligible_games = exactly_paired_games & complete_environment_games
        eligible = {
            key: snapshot
            for key, snapshot in complete_selected.items()
            if str(snapshot.game_id) in eligible_games
        }

        pair_cutoff_mismatch_games = 0
        pair_version_mismatch_games = 0
        cutoff_failures = Counter()
        for game_id in eligible_games:
            team_rows = [
                snapshot
                for (snapshot_game_id, _), snapshot in eligible.items()
                if snapshot_game_id == game_id
            ]
            feature_cutoffs = {snapshot.feature_as_of for snapshot in team_rows}
            versions = {snapshot.calculation_version for snapshot in team_rows}
            if len(feature_cutoffs) != 1:
                pair_cutoff_mismatch_games += 1
            if len(versions) != 1:
                pair_version_mismatch_games += 1
            for snapshot in team_rows:
                if snapshot.feature_as_of is None:
                    cutoff_failures["missing_feature_as_of"] += 1
                elif snapshot.scheduled_tipoff is not None and _aware_utc(
                    snapshot.feature_as_of
                ) >= _aware_utc(snapshot.scheduled_tipoff):
                    cutoff_failures["feature_as_of_not_before_tipoff"] += 1
                if snapshot.data_available_at is not None and snapshot.feature_as_of is not None:
                    if _aware_utc(snapshot.data_available_at) > _aware_utc(
                        snapshot.feature_as_of
                    ):
                        cutoff_failures["data_available_at_after_feature_as_of"] += 1

        field_values = {field: [] for field in FIELD_SEMANTICS}
        missing_opponent_rows = 0
        for key, snapshot in eligible.items():
            opponent = eligible.get((key[0], snapshot.opponent_team_id))
            if opponent is None:
                missing_opponent_rows += 1
            for field in field_values:
                field_values[field].append(_field_value(field, snapshot, opponent))

        return {
            "mode": "read-only-audit",
            "research_track": "opponent_difficulty_strength_of_schedule",
            "season": args.season,
            "season_type": args.season_type,
            "start_date": args.start_date.isoformat() if args.start_date else None,
            "end_date": args.end_date.isoformat() if args.end_date else None,
            "field_semantics": FIELD_SEMANTICS,
            "source_snapshot_rows": len(snapshots),
            "selected_snapshot_rows": len(selected),
            "selected_status_counts": dict(sorted(selected_status_counts.items())),
            "complete_selected_rows": len(complete_selected),
            "complete_environment_games": len(complete_environment_games),
            "exactly_paired_games": len(exactly_paired_games),
            "eligible_paired_environment_games": len(eligible_games),
            "eligible_rows": len(eligible),
            "excluded_selected_rows": len(complete_selected) - len(eligible),
            "missing_opponent_rows": missing_opponent_rows,
            "pair_cutoff_mismatch_games": pair_cutoff_mismatch_games,
            "pair_version_mismatch_games": pair_version_mismatch_games,
            "cutoff_failures": dict(sorted(cutoff_failures.items())),
            "field_summary": {
                field: _summary(values) for field, values in field_values.items()
            },
            "writes_performed": False,
        }
    finally:
        db.close()


def main() -> int:
    print(json.dumps(run_audit(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
