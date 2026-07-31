"""Validation and transactional publication for Advanced V3 facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameAdvancedFactRevisionORM,
    PlayerGameFactORM,
    advanced_fact_values_from_revision,
)
from app.services.player_game_fact_ingestion_service import validate_schedule_identity


@dataclass(frozen=True)
class AdvancedRegistration:
    revision_id: str
    created: bool


def validate_advanced_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "source_name", "source_row_key", "parser_version", "source_game_id",
        "source_player_id", "source_team_id", "source_row_sha256", "source_run_id",
        "game_date", "season", "season_type", "completeness_status",
        "participation_status", "retrieved_at", "data_available_at",
    )
    missing = [field for field in required if fact.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing advanced fact fields: {', '.join(missing)}")
    if fact["completeness_status"] not in {"complete", "partial"}:
        raise ValueError("Unsupported completeness_status")
    if fact["participation_status"] not in {"played", "did_not_play", "unknown"}:
        raise ValueError("Unsupported participation_status")
    source_hash = fact["source_row_sha256"]
    if len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
        raise ValueError("source_row_sha256 must be a SHA-256 hex string")
    normalized = dict(fact)
    for field in ("retrieved_at", "data_available_at"):
        value = fact[field]
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware")
        normalized[field] = value.astimezone(timezone.utc)
    return normalized


def register_advanced_revision(
    fact: Mapping[str, Any],
    *,
    db: Session,
) -> AdvancedRegistration:
    values = validate_advanced_fact(fact)
    existing = (
        db.query(PlayerGameAdvancedFactRevisionORM)
        .filter_by(
            source_name=values["source_name"],
            source_row_key=values["source_row_key"],
            parser_version=values["parser_version"],
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.source_row_sha256 == values["source_row_sha256"]:
            return AdvancedRegistration(existing.revision_id, False)
        raise ValueError("Existing Advanced V3 revision conflicts with source hash")
    revision_id = str(values.pop("revision_id", None) or uuid.uuid4())
    db.add(PlayerGameAdvancedFactRevisionORM(revision_id=revision_id, **values))
    db.flush()
    return AdvancedRegistration(revision_id, True)


def validate_traditional_identity_set(
    facts: list[Mapping[str, Any]],
    *,
    db: Session,
) -> None:
    game_ids = sorted({str(fact["canonical_game_id"]) for fact in facts})
    traditional = (
        db.query(
            PlayerGameFactORM.canonical_game_id,
            PlayerGameFactORM.canonical_player_id,
            PlayerGameFactORM.canonical_team_id,
        )
        .filter(PlayerGameFactORM.canonical_game_id.in_(game_ids))
        .all()
    )
    expected = {
        (str(row.canonical_game_id), int(row.canonical_player_id), int(row.canonical_team_id))
        for row in traditional
    }
    incoming = {
        (
            str(fact["canonical_game_id"]),
            int(fact["canonical_player_id"]),
            int(fact["canonical_team_id"]),
        )
        for fact in facts
    }
    if expected != incoming:
        missing = sorted(expected - incoming)[:10]
        unexpected = sorted(incoming - expected)[:10]
        raise ValueError(
            "Advanced/traditional player identity mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )


def publish_advanced_facts(
    facts: list[Mapping[str, Any]],
    *,
    db: Session,
) -> dict[str, int]:
    if not facts:
        return {"revisions_created": 0, "facts_created": 0, "facts_updated": 0, "facts_unchanged": 0}
    validate_schedule_identity(facts, db=db)
    validate_traditional_identity_set(facts, db=db)
    counts = {"revisions_created": 0, "facts_created": 0, "facts_updated": 0, "facts_unchanged": 0}
    for fact in facts:
        registration = register_advanced_revision(fact, db=db)
        counts["revisions_created"] += int(registration.created)
        revision = db.get(PlayerGameAdvancedFactRevisionORM, registration.revision_id)
        existing = (
            db.query(PlayerGameAdvancedFactORM)
            .filter_by(
                canonical_game_id=fact["canonical_game_id"],
                canonical_player_id=fact["canonical_player_id"],
                canonical_team_id=fact["canonical_team_id"],
            )
            .one_or_none()
        )
        if (
            existing is not None
            and existing.source_row_sha256 == fact["source_row_sha256"]
            and existing.parser_version == fact["parser_version"]
        ):
            counts["facts_unchanged"] += 1
            continue
        values = {
            "fact_id": str(uuid.uuid4()),
            "revision_id": revision.revision_id,
            "canonical_game_id": revision.canonical_game_id,
            "canonical_player_id": revision.canonical_player_id,
            "canonical_team_id": revision.canonical_team_id,
            "game_date": revision.game_date,
            "season": revision.season,
            "season_type": revision.season_type,
            "completeness_status": revision.completeness_status,
            "participation_status": revision.participation_status,
            "source_name": revision.source_name,
            "parser_version": revision.parser_version,
            "source_row_sha256": revision.source_row_sha256,
            "source_run_id": revision.source_run_id,
            "data_available_at": revision.data_available_at,
            "selected_at": datetime.now(timezone.utc),
            **advanced_fact_values_from_revision(revision),
        }
        if existing is None:
            db.add(PlayerGameAdvancedFactORM(**values))
            counts["facts_created"] += 1
        else:
            for field, value in values.items():
                if field != "fact_id":
                    setattr(existing, field, value)
            counts["facts_updated"] += 1
    db.flush()
    return counts
