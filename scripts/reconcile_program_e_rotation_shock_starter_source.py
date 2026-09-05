"""Reconcile a bounded V2 starter source trial to canonical facts without writes."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.utils.fetch.api_utils import create_api_endpoint
from scripts.probe_program_e_rotation_shock_starter_source import _player_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile BoxScoreTraditionalV2 starter fields without persistence"
    )
    parser.add_argument("--game-id", action="append", required=True)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    return parser.parse_args()


def _canonical_rows(db, game_id: str) -> dict[tuple[int, int], dict[str, Any]]:
    rows = db.execute(
        text(
            """
            select canonical_player_id, canonical_team_id, starter_status,
                   participation_status, completeness_status
            from player_game_facts
            where canonical_game_id = :game_id
            """
        ),
        {"game_id": game_id},
    )
    return {
        (int(row.canonical_player_id), int(row.canonical_team_id)): dict(row._mapping)
        for row in rows
    }


def reconcile_game(db, game_id: str) -> dict[str, Any]:
    from nba_api.stats.endpoints import boxscoretraditionalv2

    endpoint = create_api_endpoint(boxscoretraditionalv2.BoxScoreTraditionalV2, game_id=game_id)
    rows = _player_rows(endpoint.get_dict())
    canonical = _canonical_rows(db, str(game_id))
    player_rows = [
        row for row in rows
        if row.get("PLAYER_ID") is not None and row.get("TEAM_ID") is not None
    ]
    starter_rows = [row for row in player_rows if row.get("START_POSITION") not in (None, "")]
    matches = []
    missing_canonical = []
    candidate_updates = []
    for row in starter_rows:
        key = (int(row["PLAYER_ID"]), int(row["TEAM_ID"]))
        canonical_row = canonical.get(key)
        if canonical_row is None:
            missing_canonical.append(key)
            continue
        matches.append(key)
        if canonical_row["starter_status"] == "unknown":
            candidate_updates.append(
                {
                    "player_id": key[0],
                    "team_id": key[1],
                    "start_position": str(row["START_POSITION"]),
                    "canonical_starter_status": canonical_row["starter_status"],
                }
            )
    return {
        "game_id": str(game_id),
        "source_player_rows": len(player_rows),
        "source_starter_rows": len(starter_rows),
        "source_starter_position_counts": dict(sorted(
            Counter(str(row["START_POSITION"]) for row in starter_rows).items()
        )),
        "canonical_player_fact_rows": len(canonical),
        "starter_rows_matching_canonical_grain": len(matches),
        "starter_rows_missing_canonical_grain": len(missing_canonical),
        "candidate_unknown_starter_updates": len(candidate_updates),
        "candidate_update_sample": candidate_updates[:10],
    }


def main() -> int:
    args = parse_args()
    if not 1 <= len(args.game_id) <= 25:
        raise ValueError("provide between 1 and 25 game IDs")
    if args.pause_seconds < 0:
        raise ValueError("pause seconds must not be negative")

    results = []
    errors = []
    with engine.connect() as db:
        for index, game_id in enumerate(args.game_id):
            try:
                results.append(reconcile_game(db, game_id))
            except Exception as exc:  # noqa: BLE001 - report bounded source failures
                errors.append(
                    {
                        "game_id": str(game_id),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if index < len(args.game_id) - 1 and args.pause_seconds:
                import time

                time.sleep(args.pause_seconds)

    print(json.dumps({
        "mode": "read-only-source-reconciliation",
        "source": "BoxScoreTraditionalV2",
        "results": results,
        "errors": errors,
        "writes_performed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
