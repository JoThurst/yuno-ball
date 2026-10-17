"""Transactional publication for the bounded Traditional V3 pilot."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import (
    PlayerGameFactORM,
    PlayerGameFactRevisionORM,
    fact_values_from_revision,
)
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.services.player_game_fact_service import register_player_game_fact_revision


def validate_schedule_identity(facts: Iterable[Mapping[str, Any]], *, db: Session) -> None:
    """Require each fact's game/team/date/season/type to match exact schedule rows."""
    seen: set[tuple[str, int]] = set()
    for fact in facts:
        key = (str(fact["canonical_game_id"]), int(fact["canonical_team_id"]))
        if key in seen:
            continue
        seen.add(key)
        row = db.query(GameScheduleORM).filter_by(game_id=key[0], team_id=key[1]).one_or_none()
        if row is None:
            raise ValueError(f"Missing exact schedule identity for game/team {key}")
        if row.season != fact["season"] or row.season_type != fact["season_type"]:
            raise ValueError(f"Schedule season identity mismatch for {key}")
        scheduled_date = row.game_date.date() if hasattr(row.game_date, "date") else row.game_date
        if scheduled_date != fact["game_date"]:
            raise ValueError(f"Schedule date identity mismatch for {key}")
        if row.opponent_team_id == key[1] or row.opponent_team_id is None:
            raise ValueError(f"Schedule opponent identity is invalid for {key}")


def publish_player_game_facts(facts: list[Mapping[str, Any]], *, db: Session) -> dict[str, int]:
    """Register immutable revisions and update the canonical projection atomically."""
    if not facts:
        return {"revisions_created": 0, "facts_created": 0, "facts_updated": 0, "facts_unchanged": 0}
    validate_schedule_identity(facts, db=db)
    counts = {"revisions_created": 0, "facts_created": 0, "facts_updated": 0, "facts_unchanged": 0}
    for fact in facts:
        registration = register_player_game_fact_revision(fact, db=db)
        counts["revisions_created"] += int(registration.created)
        revision = db.get(PlayerGameFactRevisionORM, registration.revision_id)
        if revision is None:
            raise ValueError(f"Registered revision {registration.revision_id} was not flushed")
        existing = db.query(PlayerGameFactORM).filter_by(
            canonical_game_id=fact["canonical_game_id"], canonical_player_id=fact["canonical_player_id"],
            canonical_team_id=fact["canonical_team_id"],
        ).one_or_none()
        if existing is not None and existing.source_row_sha256 == fact["source_row_sha256"] and existing.parser_version == fact["parser_version"]:
            counts["facts_unchanged"] += 1
            continue
        values = {
            "fact_id": str(uuid.uuid4()), "revision_id": revision.revision_id,
            "canonical_game_id": revision.canonical_game_id, "canonical_player_id": revision.canonical_player_id,
            "canonical_team_id": revision.canonical_team_id, "game_date": revision.game_date,
            "season": revision.season, "season_type": revision.season_type,
            "completeness_status": revision.completeness_status, "participation_status": revision.participation_status,
            "starter_status": revision.starter_status, "source_name": revision.source_name,
            "parser_version": revision.parser_version, "source_row_sha256": revision.source_row_sha256,
            "source_run_id": revision.source_run_id, "data_available_at": revision.data_available_at,
            "selected_at": datetime.now(timezone.utc), **fact_values_from_revision(revision),
        }
        if existing is None:
            db.add(PlayerGameFactORM(**values))
            counts["facts_created"] += 1
        else:
            for field, value in values.items():
                if field != "fact_id":
                    setattr(existing, field, value)
            counts["facts_updated"] += 1
    db.flush()
    return counts
