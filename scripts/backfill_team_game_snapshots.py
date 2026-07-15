"""Bounded, resumable backfill for Phase 3 team/game snapshots."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from app.database import get_db_context
from app.models.team_analytics_snapshot_sqlalchemy import TEAM_SNAPSHOT_CALCULATION_VERSION
from app.services.ingestion_run_service import IngestionRunTracker
from app.services.team_snapshot_service import (
    DEFAULT_WINDOW_SIZE,
    SEASON_TYPE_GAME_ID_PREFIX,
    build_team_snapshot_context,
    feature_cutoff_for_slate,
    publish_team_game_snapshots,
)
from app.utils.season_utils import normalize_season, normalize_season_type


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def _slate_dates(season: str, season_type: str, start: date, end: date) -> list[date]:
    with get_db_context() as db:
        rows = db.execute(
            text(
                "SELECT DISTINCT DATE((game_date AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'America/New_York') AS slate_date "
                "FROM game_schedule "
                "WHERE season = :season "
                "AND LTRIM(game_id, '0') LIKE :game_id_prefix "
                "AND DATE((game_date AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'America/New_York') BETWEEN :start_date AND :end_date "
                "ORDER BY slate_date"
            ),
            {
                "season": season,
                "game_id_prefix": SEASON_TYPE_GAME_ID_PREFIX[season_type] + "%",
                "start_date": start,
                "end_date": end,
            },
        ).all()
    return [row.slate_date for row in rows]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill versioned team/game snapshots for scheduled NBA slate dates"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--from-date", required=True, type=_parse_date)
    parser.add_argument("--to-date", required=True, type=_parse_date)
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE)
    parser.add_argument("--team-id", type=int, help="Optionally publish only one team's feature rows")
    parser.add_argument(
        "--calculation-version",
        default=TEAM_SNAPSHOT_CALCULATION_VERSION,
    )
    parser.add_argument(
        "--resume-after",
        type=_parse_date,
        help="Skip slate dates through this date after an interrupted run",
    )
    parser.add_argument(
        "--max-dates",
        type=int,
        default=31,
        help="Safety bound on scheduled slate dates per invocation (default: 31)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _run_dates(
    slate_dates: list[date],
    *,
    season: str,
    season_type: str,
    calculation_version: str,
    source_run_id: str,
    window_size: int,
    team_id: int | None,
    dry_run: bool,
) -> dict[str, int]:
    totals = {"team_features": 0, "game_environments": 0}
    for slate_date in slate_dates:
        context = build_team_snapshot_context(
            season=season,
            season_type=season_type,
            target_date=slate_date,
            calculation_version=calculation_version,
            source_run_id=source_run_id,
        )
        counts = publish_team_game_snapshots(
            context,
            window_size=window_size,
            team_id=team_id,
            dry_run=dry_run,
        )
        for metric, count in counts.items():
            totals[metric] += count
        print(f"{slate_date}: {counts}")
    return totals


def main() -> int:
    args = parse_args()
    season = normalize_season(args.season)
    season_type = normalize_season_type(args.season_type)
    if args.from_date > args.to_date:
        raise SystemExit("--from-date must be on or before --to-date")
    if args.max_dates < 1 or args.window_size < 1:
        raise SystemExit("--max-dates and --window-size must be positive")

    slate_dates = _slate_dates(season, season_type, args.from_date, args.to_date)
    if args.resume_after:
        slate_dates = [value for value in slate_dates if value > args.resume_after]
    if len(slate_dates) > args.max_dates:
        raise SystemExit(
            f"Refusing {len(slate_dates)} slate dates; split the range or raise --max-dates explicitly"
        )
    if not slate_dates:
        print("No scheduled slate dates in the requested range.")
        return 0

    common = {
        "slate_dates": slate_dates,
        "season": season,
        "season_type": season_type,
        "calculation_version": args.calculation_version,
        "window_size": args.window_size,
        "team_id": args.team_id,
    }
    if args.dry_run:
        totals = _run_dates(source_run_id="dry-run", dry_run=True, **common)
        print(f"DRY RUN total: {totals}")
        return 0

    with IngestionRunTracker(
        run_type="team_snapshot_backfill",
        source="derived",
        season=season,
        season_type=season_type,
        target_date=slate_dates[-1],
        feature_cutoff=feature_cutoff_for_slate(slate_dates[-1]),
        provider="yunoball",
        calculation_version=args.calculation_version,
        details={
            "from_date": slate_dates[0].isoformat(),
            "to_date": slate_dates[-1].isoformat(),
            "slate_dates": len(slate_dates),
            "window_size": args.window_size,
            "team_id": args.team_id,
        },
    ) as tracker:
        totals = _run_dates(source_run_id=tracker.run_id, dry_run=False, **common)
        tracker.finish(
            "success",
            validation_status="not_run",
            rows_written=sum(totals.values()),
            details={"totals": totals, "slate_dates": len(slate_dates)},
        )
    print(f"APPLIED total: {totals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
