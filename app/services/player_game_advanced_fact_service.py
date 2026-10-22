"""Validation and transactional publication for Advanced V3 facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
import hashlib
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameAdvancedFactPromotionORM,
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
    response_hash = fact.get("source_response_sha256")
    if response_hash is None and isinstance(fact.get("raw_payload"), Mapping):
        response_hash = fact["raw_payload"].get("response_sha256")
    if response_hash is not None and (len(response_hash) != 64 or any(c not in "0123456789abcdef" for c in response_hash)):
        raise ValueError("source_response_sha256 must be a SHA-256 hex string")
    normalized["source_response_sha256"] = response_hash
    normalized["data_available_at_basis"] = fact.get("data_available_at_basis", "retrieved_proxy")
    if normalized["data_available_at_basis"] not in {"provider_published", "retrieved_proxy", "legacy_unspecified"}:
        raise ValueError("Unsupported data_available_at_basis")
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
            source_row_sha256=values["source_row_sha256"],
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.source_row_sha256 == values["source_row_sha256"]:
            for field, value in values.items():
                if field not in {
                    "source_run_id",
                    "retrieved_at",
                    "data_available_at",
                    "data_available_at_basis",
                    "raw_payload",
                    "source_response_sha256",
                } and getattr(existing, field, value) != value:
                    raise ValueError(f"Existing Advanced V3 revision conflicts on {field}")
            return AdvancedRegistration(existing.revision_id, False)
    revision_id = str(values.pop("revision_id", None) or uuid.uuid4())
    values.pop("expected_previous_revision_id", None)
    values.pop("publication_key", None)
    try:
        with db.begin_nested():
            db.add(PlayerGameAdvancedFactRevisionORM(revision_id=revision_id, **values))
            db.flush()
    except IntegrityError:
        existing = (
            db.query(PlayerGameAdvancedFactRevisionORM)
            .filter_by(
                source_name=values["source_name"],
                source_row_key=values["source_row_key"],
                parser_version=values["parser_version"],
                source_row_sha256=values["source_row_sha256"],
            )
            .one_or_none()
        )
        if existing is None:
            raise
        for field, value in values.items():
            if field not in {
                "source_run_id",
                "retrieved_at",
                "data_available_at",
                "data_available_at_basis",
                "raw_payload",
                "source_response_sha256",
            } and getattr(existing, field, value) != value:
                raise ValueError(f"Concurrent Advanced V3 revision conflicts on {field}")
        return AdvancedRegistration(existing.revision_id, False)
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
        grain_lock = "advanced|{}|{}|{}".format(fact["canonical_game_id"], fact["canonical_player_id"], fact["canonical_team_id"])
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:grain_lock))"), {"grain_lock": grain_lock})
        existing = (
            db.query(PlayerGameAdvancedFactORM)
            .filter_by(
                canonical_game_id=fact["canonical_game_id"],
                canonical_player_id=fact["canonical_player_id"],
                canonical_team_id=fact["canonical_team_id"],
            )
            .with_for_update().one_or_none()
        )
        if existing is not None and existing.revision_id == revision.revision_id:
            counts["facts_unchanged"] += 1
            continue
        if existing is not None:
            previous_revision = db.get(
                PlayerGameAdvancedFactRevisionORM, existing.revision_id
            )
            if previous_revision is None:
                raise ValueError("Advanced projection lacks its selected revision")
            identity_fields = (
                "source_name",
                "source_row_key",
                "parser_version",
                "canonical_game_id",
                "canonical_player_id",
                "canonical_team_id",
                "season",
                "season_type",
            )
            if any(
                getattr(previous_revision, field) != getattr(revision, field)
                for field in identity_fields
            ):
                raise ValueError(
                    "Advanced correction changed source or canonical identity"
                )
        if (
            existing is not None
            and "expected_previous_revision_id" not in fact
        ):
            raise ValueError("Advanced correction requires the pre-collection expected predecessor")
        if "expected_previous_revision_id" in fact:
            expected = fact["expected_previous_revision_id"]
            actual = existing.revision_id if existing else None
            if actual != expected:
                raise ValueError(
                    f"Stale Advanced correction predecessor for {fact['canonical_game_id']}/"
                    f"{fact['canonical_player_id']}/{fact['canonical_team_id']}: expected {expected}, found {actual}"
                )
        previous_revision_id = existing.revision_id if existing else None
        reason = "initial" if existing is None else "correction"
        if existing is not None and db.query(PlayerGameAdvancedFactPromotionORM).filter_by(
            canonical_game_id=fact["canonical_game_id"], canonical_player_id=fact["canonical_player_id"],
            canonical_team_id=fact["canonical_team_id"], selected_revision_id=revision.revision_id,
        ).first():
            reason = "reversion"
        publication_key = str(fact.get("publication_key") or fact["source_run_id"])
        promotion_key = hashlib.sha256("|".join(("advanced", str(fact["canonical_game_id"]), str(fact["canonical_player_id"]),
            str(fact["canonical_team_id"]), previous_revision_id or "", revision.revision_id, publication_key)).encode()).hexdigest()
        db.add(PlayerGameAdvancedFactPromotionORM(
            promotion_id=str(uuid.uuid4()), promotion_key=promotion_key,
            canonical_game_id=fact["canonical_game_id"], canonical_player_id=fact["canonical_player_id"],
            canonical_team_id=fact["canonical_team_id"], previous_revision_id=previous_revision_id,
            selected_revision_id=revision.revision_id, source_run_id=fact["source_run_id"],
            publication_key=publication_key, reason=reason, selected_at=datetime.now(timezone.utc),
        ))
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
