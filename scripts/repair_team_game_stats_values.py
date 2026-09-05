"""Repair legacy TeamGameLog fields with a bounded dry-run/apply contract."""

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
from app.services.team_game_stats_repair_service import (
    apply_repair_plan,
    build_repair_plan,
)
from app.utils.season_utils import normalize_season


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repair missing TeamGameLog rebound/result fields for one season"
    )
    parser.add_argument("--season", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    season = normalize_season(args.season)

    if args.dry_run:
        with get_db_context() as db:
            plan = build_repair_plan(db, season=season)
        print(json.dumps(plan.summary(), default=str, sort_keys=True, indent=2))
        return 0 if plan.valid else 1

    with IngestionRunTracker(
        run_type="team_game_stats_value_repair",
        source="nba_team_game_log",
        season=season,
        season_type="Regular Season",
        target_date=None,
        provider="TeamGameLog",
        details={
            "repair_fields": ["oreb", "dreb", "wl", "w", "l", "w_pct"],
            "validation": [
                "existing game/date/points/rebounds identity",
                "exact reciprocal team pair",
                "one W and one L per game",
            ],
        },
    ) as tracker:
        with get_db_context() as db:
            plan = build_repair_plan(db, season=season)
            if not plan.valid:
                tracker.finish(
                    "failed",
                    validation_status="failed",
                    rows_read=plan.rows_read,
                    rows_written=0,
                    error_summary=json.dumps(plan.summary(), default=str),
                    details=plan.summary(),
                )
                print(json.dumps(plan.summary(), default=str, sort_keys=True, indent=2))
                return 1
            written = apply_repair_plan(db, plan)
            db.commit()
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=plan.rows_read,
            rows_written=written,
            details=plan.summary() | {"rows_written": written},
        )

    print(json.dumps(plan.summary() | {"rows_written": written}, default=str, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
