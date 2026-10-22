"""Shared optimistic-concurrency inputs for player-game publication."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameFactORM,
)


PlayerGameGrain = tuple[str, int, int]


def load_player_game_predecessors(
    db: Session,
    game_ids: Sequence[str],
    *,
    family: str,
) -> dict[PlayerGameGrain, str]:
    """Snapshot selected revisions before an external collection starts."""
    model = {
        "traditional": PlayerGameFactORM,
        "advanced": PlayerGameAdvancedFactORM,
    }.get(family)
    if model is None:
        raise ValueError(f"Unsupported player-game fact family: {family}")
    # Small pure-service tests use minimal database doubles. Real SQLAlchemy
    # sessions always expose query(); no predecessor exists in those doubles.
    if not hasattr(db, "query"):
        return {}
    normalized_ids = [str(game_id) for game_id in game_ids]
    rows = (
        db.query(model)
        .filter(model.canonical_game_id.in_(normalized_ids))
        .all()
    )
    return {
        (
            str(row.canonical_game_id),
            int(row.canonical_player_id),
            int(row.canonical_team_id),
        ): str(row.revision_id)
        for row in rows
    }


def attach_player_game_predecessors(
    facts: Sequence[MutableMapping[str, Any]],
    predecessors: Mapping[PlayerGameGrain, str],
    *,
    publication_key: str,
) -> None:
    """Attach the pre-collection selection and one idempotent publication key."""
    if not publication_key:
        raise ValueError("Player-game publication requires a publication key")
    for fact in facts:
        grain = (
            str(fact["canonical_game_id"]),
            int(fact["canonical_player_id"]),
            int(fact["canonical_team_id"]),
        )
        fact["expected_previous_revision_id"] = predecessors.get(grain)
        fact["publication_key"] = str(publication_key)
