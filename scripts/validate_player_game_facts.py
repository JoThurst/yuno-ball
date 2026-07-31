"""Generate a bounded read-only Program C reconciliation report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.services.player_game_fact_reconciliation_service import (
    build_reconciliation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", action="append", required=True, dest="game_ids")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--max-games", type=int, required=True)
    args = parser.parse_args()
    with get_db_context() as db:
        report = build_reconciliation_report(
            db,
            season=args.season,
            game_ids=args.game_ids,
            max_games=args.max_games,
        )
    print(json.dumps(report, default=str, sort_keys=True, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
