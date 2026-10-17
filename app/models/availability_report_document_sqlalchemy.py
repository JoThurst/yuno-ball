"""Immutable official availability-report document observations."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.database import Base
from app.models.ingestion_run_sqlalchemy import utc_now


class AvailabilityReportDocumentORM(Base):
    """One retrieved byte revision of an official availability report."""

    __tablename__ = "availability_report_documents"
    __table_args__ = (
        CheckConstraint(
            "source_name = 'official_nba'",
            name="ck_availability_report_document_source",
        ),
        CheckConstraint(
            "raw_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_availability_report_document_sha256",
        ),
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_availability_report_document_file_size",
        ),
        CheckConstraint(
            "media_type = 'application/pdf'",
            name="ck_availability_report_document_media_type",
        ),
        CheckConstraint(
            "source_time_precision IN ('hour', 'minute')",
            name="ck_availability_report_document_time_precision",
        ),
        CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_availability_report_document_completeness",
        ),
        CheckConstraint(
            "parse_status IN ('not_parsed', 'parsed', 'partial', 'failed')",
            name="ck_availability_report_document_parse_status",
        ),
        CheckConstraint(
            "(parse_status = 'not_parsed' AND parser_version IS NULL AND "
            "parse_error_summary IS NULL) OR "
            "(parse_status IN ('parsed', 'partial') AND parser_version IS NOT NULL) OR "
            "(parse_status = 'failed' AND parser_version IS NOT NULL AND "
            "parse_error_summary IS NOT NULL)",
            name="ck_availability_report_document_parse_lineage",
        ),
        UniqueConstraint(
            "source_name",
            "source_url",
            "raw_sha256",
            name="uq_availability_report_document_revision",
        ),
        Index(
            "idx_availability_report_document_published",
            "report_published_at",
        ),
        Index("idx_availability_report_document_sha256", "raw_sha256"),
        Index("idx_availability_report_document_source_run", "source_run_id"),
    )

    document_id = Column(String(36), primary_key=True)
    source_name = Column(String(64), nullable=False)
    source_url = Column(Text, nullable=False)
    report_published_at = Column(DateTime(timezone=True), nullable=False)
    printed_report_published_at = Column(DateTime(timezone=True), nullable=True)
    report_date = Column(Date, nullable=False)
    source_time_precision = Column(String(16), nullable=False)  # hour for legacy filenames; minute for newer PDFs
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    raw_sha256 = Column(String(64), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    media_type = Column(String(128), nullable=False)
    raw_storage_locator = Column(Text, nullable=False)
    http_etag = Column(Text, nullable=True)
    http_last_modified = Column(DateTime(timezone=True), nullable=True)
    collector_version = Column(String(64), nullable=False)
    completeness_status = Column(String(16), nullable=False)
    parser_version = Column(String(64), nullable=True)
    parse_status = Column(String(16), nullable=False)
    parse_error_summary = Column(Text, nullable=True)
    source_run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return a named, serialization-safe metadata payload."""
        return {
            "document_id": self.document_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "report_published_at": self.report_published_at.isoformat(),
            "printed_report_published_at": (
                self.printed_report_published_at.isoformat()
                if self.printed_report_published_at
                else None
            ),
            "report_date": self.report_date.isoformat(),
            "source_time_precision": self.source_time_precision,
            "retrieved_at": self.retrieved_at.isoformat(),
            "raw_sha256": self.raw_sha256,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "media_type": self.media_type,
            "raw_storage_locator": self.raw_storage_locator,
            "http_etag": self.http_etag,
            "http_last_modified": (
                self.http_last_modified.isoformat()
                if self.http_last_modified
                else None
            ),
            "collector_version": self.collector_version,
            "completeness_status": self.completeness_status,
            "parser_version": self.parser_version,
            "parse_status": self.parse_status,
            "parse_error_summary": self.parse_error_summary,
            "source_run_id": self.source_run_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AvailabilityReportDownloadAttemptORM(Base):
    """Durable retry state for one discovered official report URL."""

    __tablename__ = "availability_report_download_attempts"
    __table_args__ = (
        CheckConstraint("source_name = 'official_nba'", name="ck_availability_download_source"),
        CheckConstraint(
            "source_time_precision IN ('hour', 'minute')",
            name="ck_availability_download_time_precision",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'not_found')",
            name="ck_availability_download_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_availability_download_attempt_count"),
        CheckConstraint(
            "(status = 'pending' AND document_id IS NULL) OR "
            "(status = 'succeeded' AND document_id IS NOT NULL AND "
            "last_error_class IS NULL AND last_error_summary IS NULL AND next_retry_at IS NULL) OR "
            "(status = 'not_found' AND document_id IS NULL AND next_retry_at IS NULL AND "
            "last_error_class IS NOT NULL AND last_error_summary IS NOT NULL)",
            name="ck_availability_download_terminal_state",
        ),
        UniqueConstraint("source_name", "source_url", name="uq_availability_download_source_url"),
        Index("idx_availability_download_due", "status", "next_retry_at"),
        Index("idx_availability_download_report_date", "report_date"),
    )

    download_attempt_id = Column(String(36), primary_key=True)
    source_name = Column(String(64), nullable=False)
    source_url = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=False)
    report_published_at = Column(DateTime(timezone=True), nullable=False)
    report_date = Column(Date, nullable=False)
    source_time_precision = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False)
    attempt_count = Column(BigInteger, nullable=False, default=0, server_default="0")
    first_discovered_at = Column(DateTime(timezone=True), nullable=False)
    last_discovered_at = Column(DateTime(timezone=True), nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    last_error_class = Column(String(128), nullable=True)
    last_error_summary = Column(Text, nullable=True)
    first_discovered_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=False)
    last_attempt_run_id = Column(String(36), ForeignKey("ingestion_runs.run_id"), nullable=True)
    document_id = Column(String(36), ForeignKey("availability_report_documents.document_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now())
