"""ORM models for source-preserving official availability observations."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.database import Base
from app.models.ingestion_run_sqlalchemy import utc_now


_SOURCE_LINEAGE_CHECKS = (
    CheckConstraint(
        "source_name = 'official_nba'",
        name="ck_availability_observation_source",
    ),
    CheckConstraint(
        "raw_sha256 ~ '^[0-9a-f]{64}$'",
        name="ck_availability_observation_sha256",
    ),
    CheckConstraint(
        "source_time_precision IN ('hour', 'minute')",
        name="ck_availability_observation_time_precision",
    ),
)


class AvailabilityObservationORM(Base):
    """One player status in one official report/game/team context."""

    __tablename__ = "availability_observations"
    __table_args__ = (
        *_SOURCE_LINEAGE_CHECKS,
        CheckConstraint(
            "status IN ('Available', 'Probable', 'Questionable', 'Doubtful', 'Out')",
            name="ck_availability_observation_status",
        ),
        UniqueConstraint(
            "report_document_id",
            "parser_version",
            "source_row_key",
            name="uq_availability_observation_parse_row",
        ),
        Index("idx_availability_observation_game", "game_id"),
        Index("idx_availability_observation_team_date", "team_id", "game_date"),
        Index(
            "idx_availability_observation_report_time",
            "report_published_at",
        ),
        Index("idx_availability_observation_player", "player_id"),
    )

    observation_id = Column(String(36), primary_key=True)
    report_document_id = Column(
        String(36),
        ForeignKey("availability_report_documents.document_id"),
        nullable=False,
    )
    source_name = Column(String(64), nullable=False)
    source_url = Column(Text, nullable=False)
    raw_sha256 = Column(String(64), nullable=False)
    report_published_at = Column(DateTime(timezone=True), nullable=False)
    source_time_precision = Column(String(16), nullable=False)
    parser_version = Column(String(64), nullable=False)
    source_row_key = Column(String(64), nullable=False)

    game_id = Column(String(32), nullable=True)
    game_date = Column(Date, nullable=False)
    reported_game_time_text = Column(String(32), nullable=True)
    scheduled_tipoff = Column(DateTime(timezone=True), nullable=True)
    matchup_text = Column(Text, nullable=False)
    team_id = Column(Integer, nullable=True)
    player_id = Column(Integer, nullable=True)
    reported_team_name = Column(Text, nullable=False)
    reported_player_name = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)
    raw_reason = Column(Text, nullable=True)
    reason_category = Column(Text, nullable=True)
    reason_detail = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return a named payload without silently converting missing IDs."""
        return {
            "observation_id": self.observation_id,
            "report_document_id": self.report_document_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "raw_sha256": self.raw_sha256,
            "report_published_at": self.report_published_at.isoformat(),
            "source_time_precision": self.source_time_precision,
            "parser_version": self.parser_version,
            "source_row_key": self.source_row_key,
            "game_id": self.game_id,
            "game_date": self.game_date.isoformat(),
            "reported_game_time": self.reported_game_time_text,
            "scheduled_tipoff": (
                self.scheduled_tipoff.isoformat()
                if self.scheduled_tipoff
                else None
            ),
            "matchup": self.matchup_text,
            "team_id": self.team_id,
            "player_id": self.player_id,
            "reported_team_name": self.reported_team_name,
            "reported_player_name": self.reported_player_name,
            "status": self.status,
            "raw_reason": self.raw_reason,
            "reason_category": self.reason_category,
            "reason_detail": self.reason_detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TeamReportSubmissionStatusORM(Base):
    """One explicit team submission state in one official report."""

    __tablename__ = "team_report_submission_status"
    __table_args__ = (
        *_SOURCE_LINEAGE_CHECKS,
        CheckConstraint(
            "submission_status = 'NOT YET SUBMITTED'",
            name="ck_team_report_submission_status_value",
        ),
        UniqueConstraint(
            "report_document_id",
            "parser_version",
            "source_row_key",
            name="uq_team_report_submission_parse_row",
        ),
        Index("idx_team_report_submission_game", "game_id"),
        Index("idx_team_report_submission_report_time", "report_published_at"),
    )

    submission_id = Column(String(36), primary_key=True)
    report_document_id = Column(
        String(36),
        ForeignKey("availability_report_documents.document_id"),
        nullable=False,
    )
    source_name = Column(String(64), nullable=False)
    source_url = Column(Text, nullable=False)
    raw_sha256 = Column(String(64), nullable=False)
    report_published_at = Column(DateTime(timezone=True), nullable=False)
    source_time_precision = Column(String(16), nullable=False)
    parser_version = Column(String(64), nullable=False)
    source_row_key = Column(String(64), nullable=False)

    game_id = Column(String(32), nullable=True)
    game_date = Column(Date, nullable=False)
    reported_game_time_text = Column(String(32), nullable=True)
    scheduled_tipoff = Column(DateTime(timezone=True), nullable=True)
    matchup_text = Column(Text, nullable=False)
    team_id = Column(Integer, nullable=True)
    reported_team_name = Column(Text, nullable=False)
    submission_status = Column(String(32), nullable=False)
    raw_text = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "report_document_id": self.report_document_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "raw_sha256": self.raw_sha256,
            "report_published_at": self.report_published_at.isoformat(),
            "source_time_precision": self.source_time_precision,
            "parser_version": self.parser_version,
            "source_row_key": self.source_row_key,
            "game_id": self.game_id,
            "game_date": self.game_date.isoformat(),
            "reported_game_time": self.reported_game_time_text,
            "scheduled_tipoff": (
                self.scheduled_tipoff.isoformat()
                if self.scheduled_tipoff
                else None
            ),
            "matchup": self.matchup_text,
            "team_id": self.team_id,
            "reported_team_name": self.reported_team_name,
            "submission_status": self.submission_status,
            "raw_text": self.raw_text,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
