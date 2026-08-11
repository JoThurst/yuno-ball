"""Generate a read-only Program C player-game coverage inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.services.player_game_fact_coverage_service import (
    build_player_game_fact_coverage_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--max-batch-size", type=int, default=25)
    parser.add_argument(
        "--summary",
        action="store_true",
        help="omit the per-game inventory and print only coverage/batch totals",
    )
    args = parser.parse_args()

    with get_db_context() as db:
        report = build_player_game_fact_coverage_report(
            db,
            season=args.season,
            season_type=args.season_type,
            max_batch_size=args.max_batch_size,
        )
    if args.summary:
        batch_count = len(report["traditional_backfill_batches"])
        report = {
            key: value
            for key, value in report.items()
            if key not in {"games", "traditional_backfill_batches", "advanced_backfill_batches"}
        }
        report["traditional_batch_count"] = batch_count
        report["advanced_batch_count"] = batch_count
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
