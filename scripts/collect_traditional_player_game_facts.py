"""Run bounded Program C Traditional V3 game collection."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.player_game_fact_collection_service import (
    collect_traditional_games,
    resolve_completed_game_specs,
    validate_game_bound,
)


GAME_ID = "0022500879"
GAME_DATE = date(2026, 3, 3)
SEASON = "2025-26"
SEASON_TYPE = "Regular Season"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", action="append", dest="game_ids")
    parser.add_argument(
        "--game-date",
        type=date.fromisoformat,
        help="Legacy single-game assertion; schedule identity remains authoritative",
    )
    parser.add_argument("--season", default=SEASON)
    parser.add_argument("--season-type", default=SEASON_TYPE)
    parser.add_argument("--max-games", type=int, default=1)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from app.database import get_db_context

    game_ids = validate_game_bound(args.game_ids or [GAME_ID], max_games=args.max_games)
    with get_db_context() as db:
        specs = resolve_completed_game_specs(
            db,
            game_ids,
            season=args.season,
            season_type=args.season_type,
        )
    if args.game_date is not None and (
        len(specs) != 1 or specs[0].game_date != args.game_date
    ):
        raise ValueError("--game-date does not match the exact schedule identity")

    run_id = str(uuid.uuid4())
    facts, games = collect_traditional_games(
        specs,
        run_id=run_id,
        max_games=args.max_games,
    )
    result = {
        "run_id": run_id,
        "mode": "dry-run" if args.dry_run else "apply",
        "season": args.season,
        "season_type": args.season_type,
        "game_count": len(games),
        "player_rows": len(facts),
        "dnp_rows": sum(
            fact["participation_status"] == "did_not_play" for fact in facts
        ),
        "games": games,
    }
    if args.dry_run:
        print(json.dumps(result, default=str, sort_keys=True))
        return 0
    from app.services.ingestion_run_service import IngestionRunTracker
    from app.services.player_game_fact_ingestion_service import publish_player_game_facts
    target_date = min(spec.game_date for spec in specs)
    with IngestionRunTracker(
        run_type="program_c3_traditional_bounded",
        source="nba_boxscore_traditional_v3",
        season=args.season,
        target_date=target_date,
        season_type=args.season_type,
        provider="nba_api",
        details={"game_ids": game_ids, "max_games": args.max_games},
    ) as tracker:
        for fact in facts:
            fact["source_run_id"] = tracker.run_id
        with get_db_context() as db:
            counts = publish_player_game_facts(facts, db=db)
        result["run_id"] = tracker.run_id
        result["counts"] = counts
        rows_written = (
            counts["revisions_created"]
            + counts["facts_created"]
            + counts["facts_updated"]
        )
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=len(facts),
            rows_written=rows_written,
            details=result,
        )
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
