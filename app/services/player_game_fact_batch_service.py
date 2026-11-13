"""Fetch and validate one deterministic Traditional/Advanced C7 batch."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import sys
from typing import Any, Callable, Mapping, Sequence

from app.services.advanced_boxscore_v3_adapter import (
    AdvancedBoxScoreV3Adapter,
    response_sha256,
    transform_advanced_payload,
)
from app.services.player_game_fact_collection_service import (
    CompletedGameSpec,
    collect_traditional_games,
)


def _advanced_games(
    specs: Sequence[CompletedGameSpec],
    *,
    run_id: str,
    adapter: AdvancedBoxScoreV3Adapter | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    adapter = adapter or AdvancedBoxScoreV3Adapter()
    facts: list[dict[str, Any]] = []
    games: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        print(
            f"[{index}/{len(specs)}] Advanced V3 {spec.game_id}",
            file=sys.stderr,
            flush=True,
        )
        payload = adapter.fetch_game(spec.game_id)
        retrieved_at = datetime.now(timezone.utc)
        if progress_callback:
            progress_callback(
                {
                    "game_id": spec.game_id,
                    "response_sha256": response_sha256(payload),
                    "retrieved_at": retrieved_at.isoformat(),
                }
            )
        game_facts = transform_advanced_payload(
            payload,
            game_id=spec.game_id,
            game_date=spec.game_date,
            season=spec.season,
            season_type=spec.season_type,
            run_id=run_id,
            retrieved_at=retrieved_at,
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
                "retrieved_at": game_facts[0]["retrieved_at"].isoformat(),
            }
        )
    rows_by_key: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        key = (
            str(fact["canonical_game_id"]),
            int(fact["canonical_player_id"]),
            int(fact["canonical_team_id"]),
        )
        rows_by_key[key].append(fact)
    duplicates = {
        key: rows
        for key, rows in rows_by_key.items()
        if len(rows) > 1
    }
    if duplicates:
        sample = [
            {
                "key": key,
                "rows": [
                    {
                        "minutes": row.get("minutes"),
                        "participation_status": row.get("participation_status"),
                        "source_row_sha256": row.get("source_row_sha256"),
                    }
                    for row in rows
                ],
            }
            for key, rows in list(duplicates.items())[:10]
        ]
        raise ValueError(
            "Advanced V3 batch contains duplicate canonical rows: "
            f"duplicate_keys={sample}"
        )
    return facts, games


def validate_batch_identity(
    traditional_facts: Sequence[Mapping[str, Any]],
    advanced_facts: Sequence[Mapping[str, Any]],
) -> None:
    """Require Advanced and Traditional to expose the exact same player grain."""
    traditional = {
        (
            str(fact["canonical_game_id"]),
            int(fact["canonical_player_id"]),
            int(fact["canonical_team_id"]),
        )
        for fact in traditional_facts
    }
    advanced = {
        (
            str(fact["canonical_game_id"]),
            int(fact["canonical_player_id"]),
            int(fact["canonical_team_id"]),
        )
        for fact in advanced_facts
    }
    if traditional != advanced:
        raise ValueError(
            "Advanced/Traditional batch identity mismatch: "
            f"traditional_only={sorted(traditional - advanced)[:10]}, "
            f"advanced_only={sorted(advanced - traditional)[:10]}"
        )


def collect_player_game_batch(
    specs: Sequence[CompletedGameSpec],
    *,
    run_id: str,
    max_games: int,
    progress_callback: Callable[[str, list[dict[str, Any]]], None] | None = None,
) -> dict[str, Any]:
    """Fetch Traditional then Advanced and validate both before publication."""
    traditional_facts, traditional_games = collect_traditional_games(
        specs,
        run_id=run_id,
        max_games=max_games,
        progress_callback=(
            (lambda game: progress_callback("traditional", [game]))
            if progress_callback
            else None
        ),
    )
    advanced_facts, advanced_games = _advanced_games(
        specs,
        run_id=run_id,
        progress_callback=(
            (lambda game: progress_callback("advanced", [game]))
            if progress_callback
            else None
        ),
    )
    validate_batch_identity(traditional_facts, advanced_facts)
    return {
        "traditional_facts": traditional_facts,
        "advanced_facts": advanced_facts,
        "traditional_games": traditional_games,
        "advanced_games": advanced_games,
    }
