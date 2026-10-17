"""Immutable manifests for externally supplied source artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.database import Base
from app.models.ingestion_run_sqlalchemy import JSON_DOCUMENT, utc_now


class ExternalDatasetImportORM(Base):
    """One immutable registration of a source file and transformation version."""

    __tablename__ = "external_dataset_imports"
    __table_args__ = (
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_external_dataset_import_sha256",
        ),
        CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_external_dataset_import_file_size",
        ),
        CheckConstraint(
            "source_row_count IS NULL OR source_row_count >= 0",
            name="ck_external_dataset_import_row_count",
        ),
        CheckConstraint(
            "downloaded_at_precision IN ('exact', 'file_mtime', 'unknown')",
            name="ck_external_dataset_import_download_precision",
        ),
        CheckConstraint(
            "(downloaded_at IS NULL AND downloaded_at_precision = 'unknown') OR "
            "(downloaded_at IS NOT NULL AND downloaded_at_precision IN "
            "('exact', 'file_mtime'))",
            name="ck_external_dataset_import_download_value",
        ),
        CheckConstraint(
            "license_status IN "
            "('unknown', 'needs_review', 'approved_internal', "
            "'approved_public', 'rejected')",
            name="ck_external_dataset_import_license_status",
        ),
        CheckConstraint(
            "commercial_use_status IN ('unknown', 'permitted', 'prohibited')",
            name="ck_external_dataset_import_commercial_status",
        ),
        CheckConstraint(
            "validation_status IN ('registered', 'profiled', 'failed', 'rejected')",
            name="ck_external_dataset_import_validation_status",
        ),
        UniqueConstraint(
            "source_name",
            "dataset_name",
            "dataset_version",
            "sha256",
            "transformation_version",
            name="uq_external_dataset_import_artifact",
        ),
        Index("idx_external_dataset_import_sha256", "sha256"),
        Index(
            "idx_external_dataset_import_source_status",
            "source_name",
            "validation_status",
        ),
    )

    import_id = Column(String(36), primary_key=True)
    source_name = Column(String(64), nullable=False)
    dataset_name = Column(String(128), nullable=False)
    dataset_version = Column(String(128), nullable=False)
    source_url = Column(Text, nullable=True)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    media_type = Column(String(128), nullable=True)
    downloaded_at = Column(DateTime(timezone=True), nullable=True)
    downloaded_at_precision = Column(String(16), nullable=False)
    storage_locator = Column(Text, nullable=False)
    license_identifier = Column(String(255), nullable=True)
    license_status = Column(String(32), nullable=False)
    commercial_use_status = Column(String(32), nullable=False)
    transformation_version = Column(String(64), nullable=False)
    source_run_id = Column(
        String(36),
        ForeignKey("ingestion_runs.run_id"),
        nullable=False,
    )
    source_row_count = Column(BigInteger, nullable=True)
    validation_status = Column(String(32), nullable=False)
    manifest_details = Column(JSON_DOCUMENT, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return a named serialization suitable for logs and CLI output."""
        return {
            "import_id": self.import_id,
            "source_name": self.source_name,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "source_url": self.source_url,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
            "media_type": self.media_type,
            "downloaded_at": (
                self.downloaded_at.isoformat() if self.downloaded_at else None
            ),
            "downloaded_at_precision": self.downloaded_at_precision,
            "storage_locator": self.storage_locator,
            "license_identifier": self.license_identifier,
            "license_status": self.license_status,
            "commercial_use_status": self.commercial_use_status,
            "transformation_version": self.transformation_version,
            "source_run_id": self.source_run_id,
            "source_row_count": self.source_row_count,
            "validation_status": self.validation_status,
            "manifest_details": self.manifest_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
