"""Bounded materialization of Program H1 role history and pregame bands."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM
from app.services.ingestion_run_service import IngestionRunTracker
from app.services.player_role_baseline_service import (
    build_pregame_role_baseline,
    build_role_history_observation,
    publish_role_baselines,
    publish_role_history,
    role_history_records_from_facts,
)


def _scheduled_tipoff(row: GameScheduleORM) -> datetime | None:
    if row.game_date_precision != "exact" or row.game_date is None:
        return None
    value = row.game_date
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_records(
    *,
    facts: list[PlayerGameFactORM],
    schedules: list[GameScheduleORM],
    season: str,
    season_type: str,
    source_run_id: str,
    window_size: int,
    max_target_games: int,
) -> tuple[list[dict], list[dict]]:
    history_records = role_history_records_from_facts(facts)
    history = [build_role_history_observation(fact) for fact in facts]
    players_by_team: dict[int, set[int]] = defaultdict(set)
    for row in history:
        players_by_team[row.canonical_team_id].add(row.canonical_player_id)

    targets = sorted(
        [row for row in schedules if _scheduled_tipoff(row) is not None],
        key=lambda row: (row.game_date, str(row.game_id), int(row.team_id)),
    )
    baseline_records: list[dict] = []
    for schedule in targets[:max_target_games]:
        tipoff = _scheduled_tipoff(schedule)
        assert tipoff is not None
        target_date = schedule.game_date.date()
        for player_id in sorted(players_by_team.get(int(schedule.team_id), ())):
            baseline_records.append(
                build_pregame_role_baseline(
                    history,
                    canonical_game_id=str(schedule.game_id),
                    canonical_player_id=player_id,
                    canonical_team_id=int(schedule.team_id),
                    target_game_date=target_date,
                    season=season,
                    season_type=season_type,
                    feature_as_of=tipoff,
                    scheduled_tipoff=tipoff,
                    source_run_id=source_run_id,
                    window_size=window_size,
                )
            )
    return history_records, baseline_records


def _materialize(args, *, source_run_id: str) -> dict:
    with get_db_context() as db:
        facts = (
            db.query(PlayerGameFactORM)
            .filter(
                PlayerGameFactORM.season == args.season,
                PlayerGameFactORM.season_type == args.season_type,
            )
            .all()
        )
        schedules = (
            db.query(GameScheduleORM)
            .filter(
                GameScheduleORM.season == args.season,
                GameScheduleORM.season_type == args.season_type,
            )
            .order_by(GameScheduleORM.game_date, GameScheduleORM.game_id, GameScheduleORM.team_id)
            .all()
        )
        history_records, baseline_records = build_records(
            facts=facts,
            schedules=schedules,
            season=args.season,
            season_type=args.season_type,
            source_run_id=source_run_id,
            window_size=args.window_size,
            max_target_games=args.max_target_games,
        )
        result = {
            "season": args.season,
            "season_type": args.season_type,
            "fact_rows_read": len(facts),
            "exact_target_team_rows_considered": min(
                args.max_target_games,
                sum(_scheduled_tipoff(row) is not None for row in schedules),
            ),
            "role_history_rows": len(history_records),
            "baseline_rows": len(baseline_records),
            "dry_run": args.dry_run,
        }
        if not args.dry_run:
            result["role_history_rows_written"] = publish_role_history(history_records, db=db)
            result["baseline_rows_written"] = publish_role_baselines(baseline_records, db=db)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--run-id", help="Existing ingestion run used for replay lineage")
    parser.add_argument("--window-size", type=int, default=10)
    parser.add_argument("--max-target-games", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.window_size < 1 or args.max_target_games < 1:
        parser.error("--window-size and --max-target-games must be positive")

    if args.dry_run or args.run_id:
        print(_materialize(args, source_run_id=args.run_id or "dry-run"))
        return 0

    with IngestionRunTracker(
        run_type="player_role_baseline_materialization",
        source="derived",
        season=args.season,
        target_date=None,
        season_type=args.season_type,
        provider="yunoball",
        calculation_version="role-baseline-v1",
        details={
            "window_size": args.window_size,
            "max_target_games": args.max_target_games,
            "timing_policy": "strict_source",
        },
    ) as tracker:
        result = _materialize(args, source_run_id=tracker.run_id)
        tracker.finish(
            "success",
            validation_status="not_run",
            rows_read=result["fact_rows_read"],
            rows_written=result["role_history_rows_written"] + result["baseline_rows_written"],
            details=result,
        )
        print({**result, "run_id": tracker.run_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
