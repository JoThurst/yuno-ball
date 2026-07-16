"""Persistence contract for immutable external dataset manifests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import uuid
from typing import Any, Dict, Mapping, Optional

from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.external_dataset_import_sqlalchemy import ExternalDatasetImportORM


EXTERNAL_MANIFEST_LOCK_NAME = "yunoball:external_dataset_manifest"
MANIFEST_TRANSFORMATION_VERSION = "external-manifest-v1"

DOWNLOAD_PRECISIONS = {"exact", "file_mtime", "unknown"}
LICENSE_STATUSES = {
    "unknown",
    "needs_review",
    "approved_internal",
    "approved_public",
    "rejected",
}
COMMERCIAL_USE_STATUSES = {"unknown", "permitted", "prohibited"}
VALIDATION_STATUSES = {"registered", "profiled", "failed", "rejected"}

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_TEXT_LENGTHS = {
    "source_name": 64,
    "dataset_name": 128,
    "dataset_version": 128,
    "file_name": 255,
    "sha256": 64,
    "storage_locator": None,
    "transformation_version": 64,
    "source_run_id": 36,
}
_OPTIONAL_TEXT_LENGTHS = {
    "source_url": None,
    "media_type": 128,
    "license_identifier": 255,
}
_IDENTITY_FIELDS = (
    "source_name",
    "dataset_name",
    "dataset_version",
    "sha256",
    "transformation_version",
)
_IMMUTABLE_FIELDS = (
    "source_url",
    "file_name",
    "file_size_bytes",
    "media_type",
    "downloaded_at",
    "downloaded_at_precision",
    "storage_locator",
    "license_identifier",
    "license_status",
    "commercial_use_status",
    "source_row_count",
    "validation_status",
    "manifest_details",
)


class ExternalDatasetManifestConflict(ValueError):
    """Raised when a natural-key rerun supplies different immutable metadata."""


@dataclass(frozen=True)
class ManifestRegistrationResult:
    """Named result for an external manifest registration attempt."""

    import_id: str
    created: bool
    manifest: ExternalDatasetImportORM


def _normalize_text(
    values: Mapping[str, Any],
    field: str,
    *,
    required: bool,
    max_length: Optional[int],
) -> Optional[str]:
    raw = values.get(field)
    if raw is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    normalized = str(raw).strip()
    if not normalized:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if max_length is not None and len(normalized) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    return normalized


def _normalize_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError("downloaded_at must be a datetime or None")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("downloaded_at must include timezone information")
    return value.astimezone(timezone.utc)


def normalize_manifest_values(values: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a candidate manifest before database access."""
    normalized: Dict[str, Any] = {}
    for field, max_length in _REQUIRED_TEXT_LENGTHS.items():
        normalized[field] = _normalize_text(
            values,
            field,
            required=True,
            max_length=max_length,
        )
    for field, max_length in _OPTIONAL_TEXT_LENGTHS.items():
        normalized[field] = _normalize_text(
            values,
            field,
            required=False,
            max_length=max_length,
        )

    normalized["sha256"] = normalized["sha256"].lower()
    if not _SHA256_PATTERN.fullmatch(normalized["sha256"]):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")

    try:
        uuid.UUID(normalized["source_run_id"])
    except ValueError as exc:
        raise ValueError("source_run_id must be a UUID") from exc

    file_size_bytes = values.get("file_size_bytes")
    if isinstance(file_size_bytes, bool) or not isinstance(file_size_bytes, int):
        raise ValueError("file_size_bytes must be an integer")
    if file_size_bytes < 0:
        raise ValueError("file_size_bytes must be non-negative")
    normalized["file_size_bytes"] = file_size_bytes

    source_row_count = values.get("source_row_count")
    if source_row_count is not None:
        if isinstance(source_row_count, bool) or not isinstance(source_row_count, int):
            raise ValueError("source_row_count must be an integer or None")
        if source_row_count < 0:
            raise ValueError("source_row_count must be non-negative")
    normalized["source_row_count"] = source_row_count

    normalized["downloaded_at"] = _normalize_datetime(values.get("downloaded_at"))
    downloaded_at_precision = str(values.get("downloaded_at_precision", "")).strip()
    if downloaded_at_precision not in DOWNLOAD_PRECISIONS:
        raise ValueError(f"Invalid downloaded_at_precision: {downloaded_at_precision}")
    if normalized["downloaded_at"] is None and downloaded_at_precision != "unknown":
        raise ValueError("downloaded_at_precision must be unknown without downloaded_at")
    if normalized["downloaded_at"] is not None and downloaded_at_precision == "unknown":
        raise ValueError("downloaded_at_precision cannot be unknown with downloaded_at")
    normalized["downloaded_at_precision"] = downloaded_at_precision

    for field, allowed in (
        ("license_status", LICENSE_STATUSES),
        ("commercial_use_status", COMMERCIAL_USE_STATUSES),
        ("validation_status", VALIDATION_STATUSES),
    ):
        value = str(values.get(field, "")).strip()
        if value not in allowed:
            raise ValueError(f"Invalid {field}: {value}")
        normalized[field] = value

    manifest_details = values.get("manifest_details")
    if manifest_details is not None and not isinstance(manifest_details, dict):
        raise ValueError("manifest_details must be a dictionary or None")
    normalized["manifest_details"] = manifest_details
    return normalized


def _comparable(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return value


def _register(
    db: Session,
    normalized: Mapping[str, Any],
) -> ManifestRegistrationResult:
    identity = {field: normalized[field] for field in _IDENTITY_FIELDS}
    existing = (
        db.query(ExternalDatasetImportORM)
        .filter_by(**identity)
        .one_or_none()
    )
    if existing is not None:
        conflicts = [
            field
            for field in _IMMUTABLE_FIELDS
            if _comparable(getattr(existing, field))
            != _comparable(normalized.get(field))
        ]
        if conflicts:
            raise ExternalDatasetManifestConflict(
                "Existing manifest has different immutable metadata: "
                + ", ".join(conflicts)
            )
        return ManifestRegistrationResult(
            import_id=existing.import_id,
            created=False,
            manifest=existing,
        )

    manifest = ExternalDatasetImportORM(
        import_id=str(uuid.uuid4()),
        **normalized,
    )
    db.add(manifest)
    db.flush()
    return ManifestRegistrationResult(
        import_id=manifest.import_id,
        created=True,
        manifest=manifest,
    )


def register_external_dataset_import(
    values: Mapping[str, Any],
    *,
    db: Optional[Session] = None,
) -> ManifestRegistrationResult:
    """Register one source artifact idempotently at its immutable natural key."""
    normalized = normalize_manifest_values(values)
    if db is not None:
        return _register(db, normalized)

    with get_db_context() as session:
        return _register(session, normalized)
