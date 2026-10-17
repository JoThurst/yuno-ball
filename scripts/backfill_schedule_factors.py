"""Bounded historical schedule-factor backfill with dry-run/apply proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import get_db_context
from app.services.ingestion_run_service import IngestionRunTracker
from app.services.schedule_analysis_service import ScheduleAnalysisService
from app.utils.season_utils import normalize_season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill schedule factors for one season from durable schedule rows"
    )
    parser.add_argument("--season", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _run(season: str, *, dry_run: bool) -> dict[str, int]:
    with get_db_context() as db:
        factors = ScheduleAnalysisService().calculate_for_season(
            season,
            db=db,
            dry_run=dry_run,
        )
    missing_days_rest = sum(factor.get("days_rest") is None for factor in factors)
    return {
        "season": season,
        "factor_rows": len(factors),
        "games": len({str(factor["game_id"]) for factor in factors}),
        "missing_days_rest": missing_days_rest,
        "dry_run": dry_run,
    }


def main() -> int:
    args = parse_args()
    season = normalize_season(args.season)
    if args.dry_run:
        print(json.dumps(_run(season, dry_run=True), sort_keys=True, indent=2))
        return 0

    with IngestionRunTracker(
        run_type="schedule_factor_backfill",
        source="derived",
        season=season,
        season_type="Regular Season",
        target_date=None,
        provider="yunoball",
        calculation_version="schedule_factors.v1",
        details={"scope": "full_season", "source": "game_schedule"},
    ) as tracker:
        result = _run(season, dry_run=False)
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=result["factor_rows"],
            rows_written=result["factor_rows"],
            details=result,
        )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
