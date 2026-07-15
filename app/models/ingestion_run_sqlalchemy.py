"""Durable observability records for ingestion jobs and their tasks."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


def utc_now() -> datetime:
    """Return an aware UTC timestamp for application-side defaults."""
    return datetime.now(timezone.utc)


JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class IngestionRunORM(Base):
    """One durable execution record for an ingestion or calculation command."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')",
            name="ck_ingestion_runs_status",
        ),
        CheckConstraint(
            "validation_status IN ('not_run', 'passed', 'failed', 'skipped')",
            name="ck_ingestion_runs_validation_status",
        ),
        Index("idx_ingestion_runs_started_at", "started_at"),
        Index("idx_ingestion_runs_status", "status"),
        Index("idx_ingestion_runs_season_date", "season", "target_date"),
    )

    run_id = Column(String(36), primary_key=True)
    parent_run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    )
    run_type = Column(String(64), nullable=False)
    source = Column(String(64), nullable=False, default="yunoball")
    season = Column(String(7), nullable=True)
    season_type = Column(String(32), nullable=True)
    target_date = Column(Date, nullable=True)
    feature_cutoff = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), nullable=False, default="running")
    validation_status = Column(String(16), nullable=False, default="not_run")
    started_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    finished_at = Column(DateTime(timezone=True), nullable=True)
    rows_read = Column(Integer, nullable=True)
    rows_written = Column(Integer, nullable=True)
    provider = Column(String(128), nullable=True)
    code_version = Column(String(128), nullable=True)
    calculation_version = Column(String(128), nullable=True)
    error_class = Column(String(255), nullable=True)
    error_summary = Column(Text, nullable=True)
    details = Column(JSON_DOCUMENT, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class IngestionTaskRunORM(Base):
    """One task or source step executed inside an ingestion run."""

    __tablename__ = "ingestion_task_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'skipped', 'failed')",
            name="ck_ingestion_task_runs_status",
        ),
        UniqueConstraint("run_id", "task_name", name="uq_ingestion_task_run_name"),
        Index("idx_ingestion_task_runs_run_status", "run_id", "status"),
        Index("idx_ingestion_task_runs_source", "source"),
    )

    task_run_id = Column(String(36), primary_key=True)
    run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    task_name = Column(String(128), nullable=False)
    source = Column(String(128), nullable=True)
    status = Column(String(16), nullable=False, default="running")
    started_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    finished_at = Column(DateTime(timezone=True), nullable=True)
    rows_read = Column(Integer, nullable=True)
    rows_written = Column(Integer, nullable=True)
    provider = Column(String(128), nullable=True)
    error_class = Column(String(255), nullable=True)
    error_summary = Column(Text, nullable=True)
    details = Column(JSON_DOCUMENT, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
