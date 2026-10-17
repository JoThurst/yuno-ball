"""Validation and idempotent publication for starter-source evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.models.player_game_starter_evidence_sqlalchemy import PlayerGameStarterEvidenceORM


UTC = timezone.utc


class StarterEvidenceConflict(ValueError):
    """Raised when an immutable starter evidence row changes on replay."""


class StarterEvidenceContractError(ValueError):
    """Raised when starter evidence violates its source contract."""


@dataclass(frozen=True)
class StarterEvidenceRegistration:
    evidence_id: str
    created: bool


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise StarterEvidenceContractError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _valid_sha(value: Any, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise StarterEvidenceContractError(f"{field} must be a SHA-256 hex string")


def validate_starter_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "source_name", "source_row_key", "parser_version", "source_game_id",
        "source_player_id", "source_team_id", "game_date", "season",
        "season_type", "starter_status", "source_row_sha256",
        "source_response_sha256", "source_run_id", "retrieved_at",
        "data_available_at",
    )
    missing = [field for field in required if evidence.get(field) in (None, "")]
    if missing:
        raise StarterEvidenceContractError(
            f"Missing starter evidence fields: {', '.join(missing)}"
        )
    if evidence["starter_status"] not in {"starter", "unknown"}:
        raise StarterEvidenceContractError("Unsupported starter_status")
    if evidence.get("starter_status") == "unknown" and evidence.get("start_position"):
        raise StarterEvidenceContractError(
            "unknown starter_status cannot have a populated start_position"
        )
    _valid_sha(evidence["source_row_sha256"], "source_row_sha256")
    _valid_sha(evidence["source_response_sha256"], "source_response_sha256")
    normalized = dict(evidence)
    normalized["retrieved_at"] = _aware(evidence["retrieved_at"], "retrieved_at")
    normalized["data_available_at"] = _aware(
        evidence["data_available_at"], "data_available_at"
    )
    return normalized


def register_starter_evidence(
    evidence: Mapping[str, Any],
    *,
    db: Session,
) -> StarterEvidenceRegistration:
    """Register one immutable source row; caller owns the transaction."""
    values = validate_starter_evidence(evidence)
    existing = (
        db.query(PlayerGameStarterEvidenceORM)
        .filter_by(
            source_name=values["source_name"],
            source_row_key=values["source_row_key"],
            parser_version=values["parser_version"],
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.source_row_sha256 == values["source_row_sha256"]:
            return StarterEvidenceRegistration(existing.evidence_id, False)
        raise StarterEvidenceConflict("Existing starter evidence conflicts on source hash")

    evidence_id = str(values.pop("evidence_id", None) or uuid.uuid4())
    db.add(PlayerGameStarterEvidenceORM(evidence_id=evidence_id, **values))
    db.flush()
    return StarterEvidenceRegistration(evidence_id, True)


def publish_starter_evidence(
    evidence_rows: list[Mapping[str, Any]],
    *,
    db: Session,
) -> dict[str, int]:
    """Publish a bounded evidence batch without updating canonical facts."""
    counts = {"evidence_created": 0, "evidence_unchanged": 0}
    for evidence in evidence_rows:
        registration = register_starter_evidence(evidence, db=db)
        counts["evidence_created" if registration.created else "evidence_unchanged"] += 1
    db.flush()
    return counts
