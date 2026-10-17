"""Dry-run or apply narrowly scoped repairs for malformed canonical game pairs."""

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


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument(
        "--season-type",
        choices=("Pre Season", "Regular Season", "NBA Cup", "Play-In", "Playoffs"),
        default="Regular Season",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        from app.database import engine
        from app.services.ingestion_run_service import IngestionRunTracker, PIPELINE_LOCK_NAME
        from app.services.schedule_coverage_repair_service import (
            apply_schedule_integrity_repair_plan,
            build_schedule_integrity_repair_plan,
            load_existing_schedule_rows,
        )
        from app.utils.fetch.schedule_fetcher import ScheduleFetcher
        from app.utils.season_utils import normalize_season

        season = normalize_season(args.season)
        start_date, end_date = _date(args.from_date), _date(args.to_date)
        source_rows = ScheduleFetcher().fetch_schedule_entries(
            season, source="stats_api", start_date=start_date, end_date=end_date,
            season_types=[args.season_type],
        )
        with engine.connect() as connection:
            existing_rows, _ = load_existing_schedule_rows(
                connection, season=season, season_types=[args.season_type]
            )
            plan = build_schedule_integrity_repair_plan(source_rows, existing_rows)
        output = {
            "mode": "dry-run",
            "database_write": False,
            "season": season,
            "from_date": start_date.isoformat(),
            "to_date": end_date.isoformat(),
            "source_games": plan.source_games,
            "repair_games": plan.repair_games,
            "repair_rows": len(plan.repair_rows),
            "conflicts": list(plan.conflicts),
        }
        if args.apply:
            details = {"scope": "malformed_canonical_schedule_pair_repair", "season_type": args.season_type, **output}
            with IngestionRunTracker(
                run_type="canonical_schedule_integrity_repair", source="nba",
                season=season,
                season_type=(None if args.season_type == "NBA Cup" else args.season_type),
                target_date=None,
                provider="stats.nba.com/ScheduleLeagueV2",
                calculation_version="schedule-integrity-v1", details=details,
                lock_name=PIPELINE_LOCK_NAME,
            ) as tracker:
                with engine.begin() as connection:
                    existing_rows, _ = load_existing_schedule_rows(
                        connection, season=season, season_types=[args.season_type]
                    )
                    locked_plan = build_schedule_integrity_repair_plan(source_rows, existing_rows)
                    written = apply_schedule_integrity_repair_plan(
                        connection, locked_plan, source_run_id=tracker.run_id
                    )
                    check = connection.execute(
                        __import__("sqlalchemy").text(
                            """SELECT game_id, COUNT(*) AS rows,
                                      COUNT(*) FILTER (WHERE home_or_away='H') AS home_rows,
                                      COUNT(*) FILTER (WHERE home_or_away='A') AS away_rows
                               FROM game_schedule
                               WHERE game_id = ANY(CAST(:game_ids AS varchar[]))
                               GROUP BY game_id"""
                        ),
                        {"game_ids": sorted({str(r["game_id"]) for r in locked_plan.repair_rows})},
                    ).mappings().all()
                    if any(int(r["rows"]) != 2 or int(r["home_rows"]) != 1 or int(r["away_rows"]) != 1 for r in check):
                        raise ValueError("Repaired schedule pairs failed reciprocal validation")
                tracker.finish("success", validation_status="passed", rows_read=len(source_rows), rows_written=written)
            output.update({"mode": "apply", "database_write": True, "run_id": tracker.run_id, "rows_written": written})
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(f"Malformed schedule repair failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
