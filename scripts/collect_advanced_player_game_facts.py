"""Run bounded Program C4 Advanced V3 collection."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.advanced_boxscore_v3_adapter import (
    AdvancedBoxScoreV3Adapter,
    transform_advanced_payload,
)
from app.services.player_game_fact_collection_service import (
    resolve_completed_game_specs,
    validate_game_bound,
)


PILOT_GAME_ID = "0022500879"


def collect(specs, *, run_id, max_games):
    validate_game_bound([spec.game_id for spec in specs], max_games=max_games)
    adapter = AdvancedBoxScoreV3Adapter()
    facts = []
    games = []
    for index, spec in enumerate(specs, start=1):
        print(f"[{index}/{len(specs)}] Advanced V3 {spec.game_id}", file=sys.stderr, flush=True)
        payload = adapter.fetch_game(spec.game_id)
        game_facts = transform_advanced_payload(
            payload,
            game_id=spec.game_id,
            game_date=spec.game_date,
            season=spec.season,
            season_type=spec.season_type,
            run_id=run_id,
            retrieved_at=datetime.now(timezone.utc),
        )
        if not game_facts:
            raise ValueError(f"Advanced V3 returned zero player rows for {spec.game_id}")
        team_ids = {int(fact["source_team_id"]) for fact in game_facts}
        if team_ids != set(spec.team_ids):
            raise ValueError(f"Advanced V3 team identity mismatch for {spec.game_id}")
        facts.extend(game_facts)
        games.append(
            {
                "game_id": spec.game_id,
                "game_date": spec.game_date.isoformat(),
                "player_rows": len(game_facts),
                "dnp_rows": sum(
                    fact["participation_status"] == "did_not_play"
                    for fact in game_facts
                ),
                "unknown_participation_rows": sum(
                    fact["participation_status"] == "unknown"
                    for fact in game_facts
                ),
                "response_sha256": game_facts[0]["raw_payload"]["response_sha256"],
            }
        )
    keys = {
        (
            fact["canonical_game_id"],
            fact["canonical_player_id"],
            fact["canonical_team_id"],
        )
        for fact in facts
    }
    if len(keys) != len(facts):
        raise ValueError("Advanced V3 batch contains duplicate canonical rows")
    return facts, games


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-id", action="append", dest="game_ids")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--max-games", type=int, default=1)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    from app.database import get_db_context

    game_ids = validate_game_bound(
        args.game_ids or [PILOT_GAME_ID],
        max_games=args.max_games,
    )
    with get_db_context() as db:
        specs = resolve_completed_game_specs(
            db,
            game_ids,
            season=args.season,
            season_type=args.season_type,
        )
        from app.services.player_game_fact_promotion_service import (
            load_player_game_predecessors,
        )
        predecessors = load_player_game_predecessors(
            db, game_ids, family="advanced"
        )
    run_id = str(uuid.uuid4())
    facts, games = collect(specs, run_id=run_id, max_games=args.max_games)
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
        print(json.dumps(result, sort_keys=True))
        return 0

    from app.services.ingestion_run_service import IngestionRunTracker
    from app.services.player_game_advanced_fact_service import publish_advanced_facts
    from app.services.player_game_fact_promotion_service import (
        attach_player_game_predecessors,
    )

    with IngestionRunTracker(
        run_type="program_c4_advanced_bounded",
        source="nba_boxscore_advanced_v3",
        season=args.season,
        target_date=min(spec.game_date for spec in specs),
        season_type=args.season_type,
        provider="nba_api",
        details={"game_ids": game_ids, "max_games": args.max_games},
    ) as tracker:
        for fact in facts:
            fact["source_run_id"] = tracker.run_id
        attach_player_game_predecessors(
            facts, predecessors, publication_key=tracker.run_id
        )
        with get_db_context() as db:
            counts = publish_advanced_facts(facts, db=db)
        result["run_id"] = tracker.run_id
        result["counts"] = counts
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=len(facts),
            rows_written=(
                counts["revisions_created"]
                + counts["facts_created"]
                + counts["facts_updated"]
            ),
            details=result,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
