"""Dry-run or apply a bounded season-aware canonical schedule repair."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _date(value: str, option: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{option} must use YYYY-MM-DD") from exc


def _source_rows(args):
    from app.utils.fetch.schedule_fetcher import ScheduleFetcher

    return ScheduleFetcher().fetch_schedule_entries(
        args.season,
        source=args.source,
        start_date=args.start_date,
        end_date=args.end_date,
        season_types=args.season_types,
    )


def _database_plan(args, source_rows):
    from sqlalchemy import text

    from app.database import engine
    from app.services.schedule_coverage_repair_service import (
        build_schedule_coverage_plan,
        load_existing_schedule_rows,
    )

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            existing_rows, team_ids = load_existing_schedule_rows(
                connection,
                season=args.season,
                season_types=args.season_types,
            )
            plan = build_schedule_coverage_plan(source_rows, existing_rows, team_ids)
        finally:
            transaction.rollback()
    return plan


def _plan_payload(args, plan):
    return {
        "mode": "dry-run",
        "database_write": False,
        "source_fetch": True,
        "source": args.source,
        "season": args.season,
        "season_types": args.season_types,
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "source_games": plan.source_games,
        "already_matched_games": plan.already_matched_games,
        "candidate_games": plan.candidate_games,
        "candidate_rows": len(plan.candidate_rows),
        "conflict_count": len(plan.conflicts),
        "conflict_samples": list(plan.conflicts[:20]),
    }


def _apply(args, source_rows, plan):
    from app.database import engine
    from app.services.ingestion_run_service import (
        IngestionRunTracker,
        PIPELINE_LOCK_NAME,
    )
    from app.services.schedule_coverage_repair_service import (
        apply_schedule_coverage_plan,
        build_schedule_coverage_plan,
        load_existing_schedule_rows,
    )
    from sqlalchemy import text

    details = {
        "scope": "bounded_canonical_schedule_coverage",
        "source": args.source,
        "season": args.season,
        "season_types": args.season_types,
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "identity_policy": "exact_game_id_and_reciprocal_teams",
    }
    with IngestionRunTracker(
        run_type="canonical_schedule_coverage_repair",
        source="nba",
        season=args.season,
        season_type=None,
        target_date=None,
        provider=(
            "stats.nba.com/ScheduleLeagueV2"
            if args.source == "stats_api"
            else "cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
        ),
        calculation_version="schedule-coverage-v1",
        details=details,
        lock_name=PIPELINE_LOCK_NAME,
    ) as tracker:
        with engine.begin() as connection:
            existing_rows, team_ids = load_existing_schedule_rows(
                connection,
                season=args.season,
                season_types=args.season_types,
            )
            locked_plan = build_schedule_coverage_plan(
                source_rows,
                existing_rows,
                team_ids,
            )
            written = apply_schedule_coverage_plan(
                connection,
                locked_plan,
                source_run_id=tracker.run_id,
            )
            if written:
                game_ids = sorted({str(row["game_id"]) for row in locked_plan.candidate_rows})
                persisted = connection.execute(
                    text(
                        """
                        SELECT game_id, count(*) AS row_count
                        FROM game_schedule
                        WHERE game_id = ANY(CAST(:game_ids AS varchar[]))
                        GROUP BY game_id
                        """
                    ),
                    {"game_ids": game_ids},
                ).mappings().all()
                if len(persisted) != len(game_ids) or any(
                    int(row["row_count"]) != 2 for row in persisted
                ):
                    raise ValueError("Post-insert schedule validation did not produce two rows per game")
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=locked_plan.source_games * 2,
            rows_written=written,
            details={
                **details,
                "already_matched_games": locked_plan.already_matched_games,
                "promoted_games": locked_plan.candidate_games,
                "inserted_schedule_rows": written,
            },
        )
    return {
        "mode": "apply",
        "database_write": True,
        "source_fetch": True,
        "run_id": tracker.run_id,
        "source": args.source,
        "season": args.season,
        "source_games": plan.source_games,
        "already_matched_games": plan.already_matched_games,
        "candidate_games": plan.candidate_games,
        "inserted_schedule_rows": written,
        "conflict_count": len(plan.conflicts),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repair bounded canonical schedule coverage from an explicit-season source"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument(
        "--season-type",
        dest="season_types",
        action="append",
        choices=("Play-In", "Playoffs", "Regular Season", "NBA Cup"),
        help="Repeat to include multiple types; defaults to Play-In and Playoffs",
    )
    parser.add_argument(
        "--source",
        choices=("stats_api", "cdn"),
        default="stats_api",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from app.utils.season_utils import normalize_season

        args.season = normalize_season(args.season)
        args.start_date = _date(args.from_date, "--from-date")
        args.end_date = _date(args.to_date, "--to-date")
        if args.end_date < args.start_date:
            raise ValueError("--to-date cannot precede --from-date")
        args.season_types = args.season_types or ["Play-In", "Playoffs"]
        source_rows = _source_rows(args)
        plan = _database_plan(args, source_rows)
        if args.dry_run:
            output = _plan_payload(args, plan)
        else:
            output = _apply(args, source_rows, plan)
    except Exception as exc:
        print(f"Schedule coverage repair failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
