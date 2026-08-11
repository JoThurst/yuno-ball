"""Generate a bounded read-only Program C reconciliation report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.models.ingestion_run_sqlalchemy import IngestionRunORM
from app.services.player_game_fact_reconciliation_service import (
    build_reconciliation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--game-id", action="append", dest="game_ids")
    selector.add_argument("--run-id", help="use the exact game manifest stored by an ingestion run")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--max-games", type=int, required=True)
    args = parser.parse_args()
    with get_db_context() as db:
        game_ids = args.game_ids
        if args.run_id:
            run = db.get(IngestionRunORM, args.run_id)
            if run is None:
                parser.error(f"Unknown ingestion run: {args.run_id}")
            game_ids = (run.details or {}).get("game_ids")
            if not isinstance(game_ids, list) or not game_ids:
                parser.error("The ingestion run does not contain a game_ids manifest")
        report = build_reconciliation_report(
            db,
            season=args.season,
            game_ids=game_ids,
            max_games=args.max_games,
        )
    print(json.dumps(report, default=str, sort_keys=True, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
