"""Validation and idempotent registration for append-only market observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import uuid

from sqlalchemy.orm import Session

from app.models.market_observation_sqlalchemy import (
    MarketObservationHeaderORM,
    MarketObservationSelectionORM,
)


UTC = timezone.utc
MARKET_OBSERVATION_PARSER_VERSION = "market-observation-contract-v1"
MARKET_TYPES = frozenset({"moneyline", "spread", "total"})
SNAPSHOT_TYPES = frozenset({"historical_static", "forward"})
TIMING_PRECISIONS = frozenset({"unknown", "date", "minute", "second"})
SELECTION_KEYS = frozenset({"home", "away", "over", "under"})
PAIR_STATUSES = frozenset({"inverse", "selection_specific", "not_applicable", "unknown"})


class MarketObservationConflict(ValueError):
    """Raised when a source key is replayed with different immutable values."""


class MarketObservationContractError(ValueError):
    """Raised when a market observation violates its source/timing contract."""


@dataclass(frozen=True)
class MarketObservationRegistration:
    observation_id: str
    header_created: bool
    selections_created: int


def _aware(value: datetime | None, field: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarketObservationContractError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def validate_market_observation(
    header: Mapping[str, Any],
    selections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate and normalize one immutable header plus its selections."""
    required = (
        "source_name",
        "source_observation_key",
        "parser_version",
        "snapshot_type",
        "timing_precision",
        "market_type",
        "source_run_id",
        "source_game_id",
        "canonical_game_id",
        "source_row_sha256",
        "game_date",
        "season",
        "season_type",
        "home_team_id",
        "away_team_id",
        "sportsbook_id",
        "retrieved_at",
        "data_available_at",
    )
    missing = [field for field in required if not header.get(field)]
    if missing:
        raise MarketObservationContractError(
            f"Missing market observation fields: {', '.join(missing)}"
        )
    if header["market_type"] not in MARKET_TYPES:
        raise MarketObservationContractError("Unsupported market_type")
    if header["snapshot_type"] not in SNAPSHOT_TYPES:
        raise MarketObservationContractError("Unsupported snapshot_type")
    if header["timing_precision"] not in TIMING_PRECISIONS:
        raise MarketObservationContractError("Unsupported timing_precision")
    if header["home_team_id"] == header["away_team_id"]:
        raise MarketObservationContractError("home_team_id and away_team_id must differ")
    if header["snapshot_type"] == "historical_static":
        if header["timing_precision"] != "unknown":
            raise MarketObservationContractError(
                "historical_static observations require unknown timing_precision"
            )
        if not header.get("source_import_id"):
            raise MarketObservationContractError(
                "historical_static observations require source_import_id"
            )
    if header["snapshot_type"] == "forward":
        if header["timing_precision"] == "unknown":
            raise MarketObservationContractError(
                "forward observations require declared timing precision"
            )
        if not any(header.get(field) for field in ("observed_at", "provider_updated_at")):
            raise MarketObservationContractError(
                "forward observations require observed_at or provider_updated_at"
            )
    source_row_sha256 = header["source_row_sha256"]
    if (
        len(source_row_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_row_sha256)
    ):
        raise MarketObservationContractError("source_row_sha256 must be a SHA-256 hex string")
    if not selections:
        raise MarketObservationContractError("At least one market selection is required")
    keys = [selection.get("selection_key") for selection in selections]
    if any(key not in SELECTION_KEYS for key in keys) or len(set(keys)) != len(keys):
        raise MarketObservationContractError("Selections must have unique supported keys")
    for selection in selections:
        if selection.get("pair_status") not in PAIR_STATUSES:
            raise MarketObservationContractError("Unsupported selection pair_status")
        if not selection.get("selection_label"):
            raise MarketObservationContractError("selection_label is required")

    normalized = dict(header)
    for field in (
        "source_published_at",
        "provider_updated_at",
        "observed_at",
        "retrieved_at",
        "data_available_at",
    ):
        normalized[field] = _aware(header.get(field), field)
    return normalized


def register_market_observation(
    header: Mapping[str, Any],
    selections: Sequence[Mapping[str, Any]],
    *,
    db: Session,
) -> MarketObservationRegistration:
    """Register one observation without overwriting an existing source key.

    The caller owns the surrounding transaction. Header and selection inserts
    are flushed together so a later selection failure rolls back atomically.
    """
    values = validate_market_observation(header, selections)
    parser_version = values["parser_version"]
    existing = (
        db.query(MarketObservationHeaderORM)
        .filter_by(
            source_name=values["source_name"],
            source_observation_key=values["source_observation_key"],
            parser_version=parser_version,
        )
        .one_or_none()
    )
    if existing is not None:
        immutable_fields = (
            "snapshot_type",
            "timing_precision",
            "market_type",
            "source_import_id",
            "source_run_id",
            "source_game_id",
            "canonical_game_id",
            "source_row_sha256",
            "game_date",
            "season",
            "season_type",
            "home_team_id",
            "away_team_id",
            "sportsbook_id",
            "source_published_at",
            "provider_updated_at",
            "observed_at",
            "retrieved_at",
            "data_available_at",
        )
        for field in immutable_fields:
            if getattr(existing, field) != values.get(field):
                raise MarketObservationConflict(
                    f"Existing market observation conflicts on {field}"
                )
        existing_keys = {
            row.selection_key
            for row in db.query(MarketObservationSelectionORM)
            .filter_by(observation_id=existing.observation_id)
            .all()
        }
        incoming_keys = {selection["selection_key"] for selection in selections}
        if existing_keys != incoming_keys:
            raise MarketObservationConflict("Existing market selections differ")
        return MarketObservationRegistration(existing.observation_id, False, 0)

    observation_id = str(values.get("observation_id") or uuid.uuid4())
    row_values = {
        **values,
        "observation_id": observation_id,
        "parser_version": parser_version or MARKET_OBSERVATION_PARSER_VERSION,
    }
    db.add(MarketObservationHeaderORM(**row_values))
    for selection in selections:
        db.add(
            MarketObservationSelectionORM(
                selection_id=str(selection.get("selection_id") or uuid.uuid4()),
                observation_id=observation_id,
                selection_key=selection["selection_key"],
                selection_label=selection["selection_label"],
                selection_team_id=selection.get("selection_team_id"),
                line_value=selection.get("line_value"),
                price_american=selection.get("price_american"),
                price_decimal=selection.get("price_decimal"),
                pair_status=selection["pair_status"],
                raw_selection=selection.get("raw_selection"),
            )
        )
    db.flush()
    return MarketObservationRegistration(observation_id, True, len(selections))
