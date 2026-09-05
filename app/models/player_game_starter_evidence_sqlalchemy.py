"""Immutable source evidence for player-game starter positions."""

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
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.ingestion_run_sqlalchemy import utc_now


class PlayerGameStarterEvidenceORM(Base):
    """One immutable starter-position source row for one player-game-team."""

    __tablename__ = "player_game_starter_evidence"
    __table_args__ = (
        CheckConstraint(
            "starter_status IN ('starter', 'unknown')",
            name="ck_player_game_starter_evidence_status",
        ),
        CheckConstraint(
            "source_row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_starter_evidence_row_sha256",
        ),
        CheckConstraint(
            "source_response_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_starter_evidence_response_sha256",
        ),
        UniqueConstraint(
            "source_name",
            "source_row_key",
            "parser_version",
            name="uq_player_game_starter_evidence_source_row",
        ),
        ForeignKeyConstraint(
            ["canonical_game_id", "canonical_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_player_game_starter_evidence_schedule",
        ),
        Index("idx_player_game_starter_evidence_game", "canonical_game_id"),
        Index("idx_player_game_starter_evidence_player", "canonical_player_id"),
        Index("idx_player_game_starter_evidence_date", "game_date"),
        Index("idx_player_game_starter_evidence_run", "source_run_id"),
    )

    evidence_id = Column(String(36), primary_key=True)
    source_name = Column(String(64), nullable=False)
    source_row_key = Column(String(255), nullable=False)
    parser_version = Column(String(64), nullable=False)
    source_game_id = Column(String(32), nullable=False)
    source_player_id = Column(BigInteger, nullable=False)
    source_team_id = Column(Integer, nullable=False)
    canonical_game_id = Column(String(32), nullable=True)
    canonical_player_id = Column(BigInteger, ForeignKey("players.player_id"), nullable=True)
    canonical_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=True)
    game_date = Column(Date, nullable=False)
    season = Column(String(7), nullable=False)
    season_type = Column(String(32), nullable=False)
    starter_status = Column(String(16), nullable=False)
    start_position = Column(String(8), nullable=True)
    source_row_sha256 = Column(String(64), nullable=False)
    source_response_sha256 = Column(String(64), nullable=False)
    source_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
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
            "evidence_id": self.evidence_id,
            "source_name": self.source_name,
            "source_row_key": self.source_row_key,
            "parser_version": self.parser_version,
            "source_game_id": self.source_game_id,
            "source_player_id": self.source_player_id,
            "source_team_id": self.source_team_id,
            "canonical_game_id": self.canonical_game_id,
            "canonical_player_id": self.canonical_player_id,
            "canonical_team_id": self.canonical_team_id,
            "game_date": self.game_date.isoformat(),
            "season": self.season,
            "season_type": self.season_type,
            "starter_status": self.starter_status,
            "start_position": self.start_position,
            "source_row_sha256": self.source_row_sha256,
            "source_response_sha256": self.source_response_sha256,
            "source_run_id": self.source_run_id,
            "retrieved_at": self.retrieved_at.isoformat(),
            "data_available_at": self.data_available_at.isoformat(),
            "raw_payload": self.raw_payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
