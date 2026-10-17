"""Collect bounded starter evidence with dry-run/apply modes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import sys
import time
import uuid
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.services.player_game_starter_evidence_service import publish_starter_evidence
from app.services.starter_evidence_fetch_service import (
    StarterEvidenceFetch,
    fetch_starter_evidence,
)


MAX_GAMES = 25


@dataclass(frozen=True)
class CollectionResult:
    evidence: list[dict]
    fetches: list[StarterEvidenceFetch]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect bounded Traditional V2 starter evidence"
    )
    parser.add_argument("--game-id", action="append", dest="game_ids", required=True)
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument(
        "--source",
        choices=("traditional_v2", "live_boxscore"),
        default="traditional_v2",
        help="Starter source; live_boxscore is the preferred forward path",
    )
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _schedule_rows(db, game_ids: list[str], season: str, season_type: str) -> dict[tuple[str, int], dict]:
    rows = db.execute(
        text(
            """
            select game_id, team_id, game_date, season, season_type
            from game_schedule
            where game_id = any(:game_ids)
              and season = :season
              and season_type = :season_type
            """
        ),
        {"game_ids": game_ids, "season": season, "season_type": season_type},
    )
    return {(str(row.game_id), int(row.team_id)): dict(row._mapping) for row in rows}


def _collect(
    game_ids: list[str],
    season: str,
    season_type: str,
    pause_seconds: float,
    source: str,
) -> CollectionResult:
    with get_db_context() as db:
        schedules = _schedule_rows(db, game_ids, season, season_type)
    collected = []
    fetches = []
    for index, game_id in enumerate(game_ids):
        retrieved_at = datetime.now(timezone.utc)
        fetched = fetch_starter_evidence(
            game_id=game_id,
            season=season,
            season_type=season_type,
            run_id="dry-run",
            retrieved_at=retrieved_at,
            preferred_source=source,
        )
        fetches.append(fetched)
        rows = fetched.rows
        if not rows:
            raise ValueError(f"No starter evidence rows returned for {game_id}")
        for row in rows:
            schedule = schedules.get((game_id, int(row["source_team_id"])))
            if schedule is None:
                raise ValueError(
                    f"Missing exact schedule identity for {game_id}/{row['source_team_id']}"
                )
            row["game_date"] = schedule["game_date"].date()
            row["canonical_game_id"] = game_id
            row["canonical_team_id"] = int(row["source_team_id"])
            row["canonical_player_id"] = int(row["source_player_id"])
        collected.extend(rows)
        if index < len(game_ids) - 1 and pause_seconds:
            time.sleep(pause_seconds)
    return CollectionResult(evidence=collected, fetches=fetches)


def main() -> int:
    args = parse_args()
    if not 1 <= len(args.game_ids) <= MAX_GAMES:
        raise ValueError(f"provide between 1 and {MAX_GAMES} game IDs")
    if args.pause_seconds < 0:
        raise ValueError("pause seconds must not be negative")
    game_ids = [str(game_id) for game_id in args.game_ids]
    collection = _collect(
        game_ids, args.season, args.season_type, args.pause_seconds, args.source
    )
    evidence = collection.evidence
    fetches = collection.fetches
    effective_sources = sorted({fetch.source_name for fetch in fetches})
    fallback_reasons = [
        fetch.fallback_reason for fetch in fetches if fetch.fallback_reason
    ]
    result = {
        "mode": "dry-run" if args.dry_run else "apply",
        "preferred_source": args.source,
        "effective_sources": effective_sources,
        "season": args.season,
        "season_type": args.season_type,
        "game_ids": game_ids,
        "game_count": len(game_ids),
        "evidence_rows": len(evidence),
        "starter_rows": sum(row["starter_status"] == "starter" for row in evidence),
        "unknown_rows": sum(row["starter_status"] == "unknown" for row in evidence),
        "fallback_count": len(fallback_reasons),
        "fallback_reasons": fallback_reasons,
        "writes_performed": False,
    }
    if args.dry_run:
        print(json.dumps(result, default=str, sort_keys=True))
        return 0

    from app.services.ingestion_run_service import IngestionRunTracker

    with IngestionRunTracker(
        run_type="program_e_starter_evidence_bounded",
        source=effective_sources[0],
        season=args.season,
        target_date=min(row["game_date"] for row in evidence),
        season_type=args.season_type,
        provider="nba_api",
        calculation_version=fetches[0].parser_version,
        details={
            "game_ids": game_ids,
            "max_games": MAX_GAMES,
            "preferred_source": args.source,
            "effective_sources": effective_sources,
            "fallback_reasons": fallback_reasons,
        },
    ) as tracker:
        for row in evidence:
            row["source_run_id"] = tracker.run_id
        with get_db_context() as db:
            counts = publish_starter_evidence(evidence, db=db)
        result["run_id"] = tracker.run_id
        result["counts"] = counts
        result["writes_performed"] = counts["evidence_created"] > 0
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=len(evidence),
            rows_written=counts["evidence_created"],
            details=result,
        )
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
