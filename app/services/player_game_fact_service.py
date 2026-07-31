"""Validation and replay-safe registration for traditional player-game facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Mapping
import uuid

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import PlayerGameFactRevisionORM


PARSER_VERSION = "boxscore-traditional-v3-fact-v2"
UTC = timezone.utc
_MINUTES_PATTERN = re.compile(r"^(?:\d{1,3}:)?\d{2}:\d{2}$|^\d{1,3}:\d{2}$")


class PlayerGameFactConflict(ValueError):
    """Raised when an immutable source row is replayed with changed facts."""


class PlayerGameFactContractError(ValueError):
    """Raised when a traditional player-game fact violates its contract."""


@dataclass(frozen=True)
class PlayerGameFactRegistration:
    revision_id: str
    created: bool


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PlayerGameFactContractError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def validate_player_game_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "source_name",
        "source_row_key",
        "parser_version",
        "source_game_id",
        "source_player_id",
        "source_team_id",
        "source_row_sha256",
        "source_run_id",
        "game_date",
        "season",
        "season_type",
        "completeness_status",
        "participation_status",
        "retrieved_at",
        "data_available_at",
    )
    missing = [field for field in required if fact.get(field) in (None, "")]
    if missing:
        raise PlayerGameFactContractError(f"Missing player-game fact fields: {', '.join(missing)}")
    if fact["completeness_status"] not in {"complete", "partial"}:
        raise PlayerGameFactContractError("Unsupported completeness_status")
    if fact["participation_status"] not in {"played", "did_not_play", "unknown"}:
        raise PlayerGameFactContractError("Unsupported participation_status")
    if fact.get("starter_status", "unknown") not in {"starter", "bench", "unknown"}:
        raise PlayerGameFactContractError("Unsupported starter_status")
    source_hash = fact["source_row_sha256"]
    if len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
        raise PlayerGameFactContractError("source_row_sha256 must be a SHA-256 hex string")
    if fact.get("minutes") not in (None, "") and not _MINUTES_PATTERN.match(str(fact["minutes"])):
        raise PlayerGameFactContractError("minutes must use MM:SS or HH:MM:SS format")
    for field in (
        "field_goals_made", "field_goals_attempted", "three_pointers_made",
        "three_pointers_attempted", "free_throws_made", "free_throws_attempted",
        "rebounds_offensive", "rebounds_defensive", "rebounds_total", "assists",
        "steals", "blocks", "turnovers", "fouls_personal", "points",
    ):
        if fact.get(field) is not None and fact[field] < 0:
            raise PlayerGameFactContractError(f"{field} cannot be negative")
    normalized = dict(fact)
    normalized["starter_status"] = fact.get("starter_status", "unknown")
    normalized["retrieved_at"] = _aware(fact["retrieved_at"], "retrieved_at")
    normalized["data_available_at"] = _aware(fact["data_available_at"], "data_available_at")
    return normalized


def register_player_game_fact_revision(
    fact: Mapping[str, Any],
    *,
    db: Session,
) -> PlayerGameFactRegistration:
    """Register one immutable source revision; caller owns the transaction."""
    values = validate_player_game_fact(fact)
    existing = (
        db.query(PlayerGameFactRevisionORM)
        .filter_by(
            source_name=values["source_name"],
            source_row_key=values["source_row_key"],
            parser_version=values["parser_version"],
        )
        .one_or_none()
    )
    immutable_fields = (
        "source_game_id", "source_player_id", "source_team_id", "canonical_game_id",
        "canonical_player_id", "canonical_team_id", "source_row_sha256", "game_date",
        "season", "season_type", "completeness_status", "participation_status",
        "starter_status",
    ) + tuple(
        field for field in (
            "minutes", "field_goals_made", "field_goals_attempted", "field_goals_percentage",
            "three_pointers_made", "three_pointers_attempted", "three_pointers_percentage",
            "free_throws_made", "free_throws_attempted", "free_throws_percentage",
            "rebounds_offensive", "rebounds_defensive", "rebounds_total", "assists", "steals",
            "blocks", "turnovers", "fouls_personal", "points", "plus_minus_points",
        )
    )
    if existing is not None:
        # The source-row hash covers the raw row; retrieval/data-availability
        # timestamps and database numeric coercions may legitimately differ
        # across replays of the same source evidence.
        if existing.source_row_sha256 == values["source_row_sha256"]:
            return PlayerGameFactRegistration(existing.revision_id, False)
        for field in immutable_fields:
            if getattr(existing, field) != values.get(field):
                raise PlayerGameFactConflict(f"Existing revision conflicts on {field}")
        return PlayerGameFactRegistration(existing.revision_id, False)

    revision_id = str(values.pop("revision_id", None) or uuid.uuid4())
    db.add(PlayerGameFactRevisionORM(revision_id=revision_id, **values))
    db.flush()
    return PlayerGameFactRegistration(revision_id, True)
