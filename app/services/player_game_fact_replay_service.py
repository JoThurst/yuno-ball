"""Database-only idempotency replay for published C7 player-game facts."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameAdvancedFactRevisionORM,
    PlayerGameFactORM,
    PlayerGameFactRevisionORM,
)
from app.services.player_game_advanced_fact_service import publish_advanced_facts
from app.services.player_game_fact_ingestion_service import publish_player_game_facts


def _revision_values(revision: Any) -> dict[str, Any]:
    return {
        column.name: getattr(revision, column.name)
        for column in revision.__table__.columns
    }


def replay_published_player_game_facts(
    db: Session,
    *,
    game_ids: list[str],
) -> dict[str, dict[str, int]]:
    """Replay canonical source revisions without contacting an external provider."""
    traditional_rows = (
        db.query(PlayerGameFactORM)
        .filter(PlayerGameFactORM.canonical_game_id.in_(game_ids))
        .all()
    )
    advanced_rows = (
        db.query(PlayerGameAdvancedFactORM)
        .filter(PlayerGameAdvancedFactORM.canonical_game_id.in_(game_ids))
        .all()
    )
    traditional_facts = [
        _revision_values(db.get(PlayerGameFactRevisionORM, row.revision_id))
        for row in traditional_rows
    ]
    advanced_facts = [
        _revision_values(db.get(PlayerGameAdvancedFactRevisionORM, row.revision_id))
        for row in advanced_rows
    ]
    if {str(row.canonical_game_id) for row in traditional_rows} != set(game_ids):
        raise ValueError("Database replay is missing Traditional coverage for the manifest")
    if {str(row.canonical_game_id) for row in advanced_rows} != set(game_ids):
        raise ValueError("Database replay is missing Advanced coverage for the manifest")

    return {
        "traditional_counts": publish_player_game_facts(traditional_facts, db=db),
        "advanced_counts": publish_advanced_facts(advanced_facts, db=db),
    }
