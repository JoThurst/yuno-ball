"""Immutable market-observation header and selection models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.ingestion_run_sqlalchemy import utc_now


class MarketObservationHeaderORM(Base):
    """One immutable source/book/game/market snapshot."""

    __tablename__ = "market_observation_headers"
    __table_args__ = (
        CheckConstraint(
            "market_type IN ('moneyline', 'spread', 'total')",
            name="ck_market_observation_market_type",
        ),
        CheckConstraint(
            "snapshot_type IN ('historical_static', 'forward')",
            name="ck_market_observation_snapshot_type",
        ),
        CheckConstraint(
            "timing_precision IN ('unknown', 'date', 'minute', 'second')",
            name="ck_market_observation_timing_precision",
        ),
        CheckConstraint(
            "source_row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_market_observation_sha256",
        ),
        CheckConstraint(
            "home_team_id <> away_team_id",
            name="ck_market_observation_distinct_teams",
        ),
        UniqueConstraint(
            "source_name",
            "source_observation_key",
            "parser_version",
            name="uq_market_observation_source_key",
        ),
        Index("idx_market_observation_game_time", "canonical_game_id", "observed_at"),
        Index("idx_market_observation_as_of", "canonical_game_id", "data_available_at"),
        Index("idx_market_observation_market", "market_type", "snapshot_type"),
        Index("idx_market_observation_source_run", "source_run_id"),
    )

    observation_id = Column(String(36), primary_key=True)
    source_name = Column(String(64), nullable=False)
    source_observation_key = Column(String(255), nullable=False)
    parser_version = Column(String(64), nullable=False)
    snapshot_type = Column(String(32), nullable=False)
    timing_precision = Column(String(16), nullable=False)
    market_type = Column(String(16), nullable=False)

    source_import_id = Column(
        String(36),
        ForeignKey("external_dataset_imports.import_id"),
        nullable=True,
    )
    source_run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id"),
        nullable=False,
    )
    source_row_number = Column(BigInteger, nullable=True)
    source_game_id = Column(String(64), nullable=False)
    canonical_game_id = Column(String(32), nullable=False)
    source_row_sha256 = Column(String(64), nullable=False)

    game_date = Column(Date, nullable=False)
    season = Column(String(10), nullable=False)
    season_type = Column(String(32), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    sportsbook_id = Column(String(64), nullable=False)
    sportsbook_name = Column(Text, nullable=True)

    source_published_at = Column(DateTime(timezone=True), nullable=True)
    provider_updated_at = Column(DateTime(timezone=True), nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    data_available_at = Column(DateTime(timezone=True), nullable=False)
    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source_name": self.source_name,
            "source_observation_key": self.source_observation_key,
            "parser_version": self.parser_version,
            "snapshot_type": self.snapshot_type,
            "timing_precision": self.timing_precision,
            "market_type": self.market_type,
            "source_import_id": self.source_import_id,
            "source_run_id": self.source_run_id,
            "source_row_number": self.source_row_number,
            "source_game_id": self.source_game_id,
            "canonical_game_id": self.canonical_game_id,
            "source_row_sha256": self.source_row_sha256,
            "game_date": self.game_date.isoformat(),
            "season": self.season,
            "season_type": self.season_type,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "sportsbook_id": self.sportsbook_id,
            "sportsbook_name": self.sportsbook_name,
            "source_published_at": _iso(self.source_published_at),
            "provider_updated_at": _iso(self.provider_updated_at),
            "observed_at": _iso(self.observed_at),
            "retrieved_at": _iso(self.retrieved_at),
            "data_available_at": _iso(self.data_available_at),
            "raw_payload": self.raw_payload,
            "created_at": _iso(self.created_at),
        }


class MarketObservationSelectionORM(Base):
    """One immutable selection within a market-observation header."""

    __tablename__ = "market_observation_selections"
    __table_args__ = (
        CheckConstraint(
            "selection_key IN ('home', 'away', 'over', 'under')",
            name="ck_market_selection_key",
        ),
        CheckConstraint(
            "pair_status IN ('inverse', 'selection_specific', 'not_applicable', 'unknown')",
            name="ck_market_selection_pair_status",
        ),
        UniqueConstraint(
            "observation_id",
            "selection_key",
            name="uq_market_selection_observation_key",
        ),
        Index("idx_market_selection_team", "selection_team_id"),
    )

    selection_id = Column(String(36), primary_key=True)
    observation_id = Column(
        String(36),
        ForeignKey("market_observation_headers.observation_id", ondelete="CASCADE"),
        nullable=False,
    )
    selection_key = Column(String(16), nullable=False)
    selection_label = Column(Text, nullable=False)
    selection_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    line_value = Column(Numeric(12, 4), nullable=True)
    price_american = Column(Integer, nullable=True)
    price_decimal = Column(Numeric(12, 6), nullable=True)
    pair_status = Column(String(24), nullable=False)
    raw_selection = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "observation_id": self.observation_id,
            "selection_key": self.selection_key,
            "selection_label": self.selection_label,
            "selection_team_id": self.selection_team_id,
            "line_value": str(self.line_value) if self.line_value is not None else None,
            "price_american": self.price_american,
            "price_decimal": (
                str(self.price_decimal) if self.price_decimal is not None else None
            ),
            "pair_status": self.pair_status,
            "raw_selection": self.raw_selection,
            "created_at": _iso(self.created_at),
        }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
