"""Project explicit starter evidence onto bounded canonical facts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.services.player_game_starter_projection_service import project_starter_evidence


MAX_GAMES = 25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project bounded starter evidence onto canonical facts"
    )
    parser.add_argument("--game-id", action="append", dest="game_ids", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _load_rows(db, game_ids: list[str], season: str, season_type: str) -> list[dict]:
    rows = db.execute(
        text(
            """
            select evidence_id, canonical_game_id, canonical_player_id,
                   canonical_team_id, starter_status, start_position
            from player_game_starter_evidence
            where canonical_game_id = any(:game_ids)
              and season = :season
              and season_type = :season_type
            order by canonical_game_id, canonical_player_id
            """
        ),
        {"game_ids": game_ids, "season": season, "season_type": season_type},
    )
    result = []
    for row in rows:
        value = dict(row._mapping)
        result.append(value)
    return result


def main() -> int:
    args = parse_args()
    if not 1 <= len(args.game_ids) <= MAX_GAMES:
        raise ValueError(f"provide between 1 and {MAX_GAMES} game IDs")
    with get_db_context() as db:
        evidence = _load_rows(db, args.game_ids, args.season, args.season_type)
        result = {
            "mode": "dry-run" if args.dry_run else "apply",
            "season": args.season,
            "season_type": args.season_type,
            "game_ids": args.game_ids,
            "game_count": len(args.game_ids),
            "evidence_rows": len(evidence),
            "starter_rows": sum(row["starter_status"] == "starter" for row in evidence),
            "writes_performed": False,
        }
        if args.dry_run:
            counts = project_starter_evidence(evidence, db=db)
            db.rollback()
            result["counts"] = counts
            print(json.dumps(result, default=str, sort_keys=True))
            return 0
        from app.services.ingestion_run_service import IngestionRunTracker

        target_date = datetime.now(timezone.utc).date()
        with IngestionRunTracker(
            run_type="program_e_starter_projection_bounded",
            source="player_game_starter_evidence",
            season=args.season,
            target_date=target_date,
            season_type=args.season_type,
            provider="local_database",
            calculation_version="starter-evidence-projection-v1",
            details={"game_ids": args.game_ids, "max_games": MAX_GAMES},
        ) as tracker:
            counts = project_starter_evidence(evidence, db=db)
            result["run_id"] = tracker.run_id
            result["counts"] = counts
            result["writes_performed"] = counts["facts_updated"] > 0
            tracker.finish(
                "success",
                validation_status="passed",
                rows_read=len(evidence),
                rows_written=counts["facts_updated"],
                details=result,
            )
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
