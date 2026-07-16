"""Durable persistence for immutable official availability-report documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import uuid
from typing import Iterable, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.availability_report_document_sqlalchemy import (
    AvailabilityReportDocumentORM,
)
from app.utils.fetch.official_injury_report_provider import DownloadedInjuryReport


AVAILABILITY_DOCUMENT_LOCK_NAME = "yunoball:official_injury_report_documents"
AVAILABILITY_DOCUMENT_SOURCE = "official_nba"
AVAILABILITY_DOCUMENT_COLLECTOR_VERSION = "official-injury-documents-v1"

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class AvailabilityReportDocumentConflict(ValueError):
    """Raised when an exact revision rerun changes immutable metadata."""


@dataclass(frozen=True)
class AvailabilityReportDocumentResult:
    """Named result for one persisted or previously known document revision."""

    document_id: str
    created: bool
    document: AvailabilityReportDocumentORM


@dataclass(frozen=True)
class AvailabilityReportDocumentBatchResult:
    """Named result for one transactionally registered document batch."""

    results: Sequence[AvailabilityReportDocumentResult]

    @property
    def rows_written(self) -> int:
        return sum(1 for result in self.results if result.created)


def validate_archive_root(
    archive_root: str | Path,
    *,
    repository_root: Optional[str | Path] = None,
) -> Path:
    """Require a durable root outside the repository and temporary archive."""
    raw = str(archive_root).strip()
    if not raw:
        raise ValueError("A durable archive root is required")
    root = Path(raw).expanduser().resolve()
    repo = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    try:
        root.relative_to(repo)
    except ValueError:
        pass
    else:
        raise ValueError("The injury-report archive root must be outside the repository")
    comparable = root.as_posix().casefold()
    if "datasource/archive" in comparable:
        raise ValueError("dataSource/archive is temporary and cannot be durable storage")
    return root


def document_storage_path(
    archive_root: str | Path,
    report: DownloadedInjuryReport,
) -> Path:
    """Build a deterministic content-addressed raw-document path."""
    root = validate_archive_root(archive_root)
    published = report.discovered.report_published_at
    stem = Path(report.discovered.file_name).stem
    return (
        root
        / "official_nba_injury_reports"
        / f"{published.year:04d}"
        / f"{published.month:02d}"
        / f"{published.day:02d}"
        / f"{stem}_{report.raw_sha256[:16]}.pdf"
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def store_raw_document_atomically(
    archive_root: str | Path,
    report: DownloadedInjuryReport,
) -> Path:
    """Write one immutable PDF safely; verify an existing content-addressed file."""
    if not _SHA256_PATTERN.fullmatch(report.raw_sha256):
        raise ValueError("raw_sha256 must be 64 lowercase hexadecimal characters")
    if hashlib.sha256(report.content).hexdigest() != report.raw_sha256:
        raise ValueError("Downloaded bytes do not match raw_sha256")
    target = document_storage_path(archive_root, report)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size != report.file_size_bytes or _hash_file(target) != report.raw_sha256:
            raise AvailabilityReportDocumentConflict(
                f"Existing raw document does not match expected bytes: {target}"
            )
        return target

    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(report.content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def _aware_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include timezone information")
    return value.astimezone(timezone.utc)


def _comparable(value):
    if isinstance(value, datetime):
        return _aware_utc(value, "timestamp")
    return value


def register_availability_report_document(
    report: DownloadedInjuryReport,
    *,
    storage_locator: str,
    source_run_id: str,
    db: Session,
) -> AvailabilityReportDocumentResult:
    """Register one exact document revision idempotently in the caller transaction."""
    try:
        uuid.UUID(source_run_id)
    except ValueError as exc:
        raise ValueError("source_run_id must be a UUID") from exc
    if not storage_locator.strip():
        raise ValueError("storage_locator is required")
    if not report.content.startswith(b"%PDF-"):
        raise ValueError("Only validated PDF content can be registered")
    if hashlib.sha256(report.content).hexdigest() != report.raw_sha256:
        raise ValueError("Downloaded bytes do not match raw_sha256")
    report_published_at = _aware_utc(
        report.discovered.report_published_at,
        "report_published_at",
    )
    retrieved_at = _aware_utc(report.retrieved_at, "retrieved_at")
    if retrieved_at < report_published_at:
        raise ValueError("retrieved_at cannot precede report_published_at")
    http_last_modified = (
        _aware_utc(report.http_last_modified, "http_last_modified")
        if report.http_last_modified
        else None
    )
    identity = {
        "source_name": AVAILABILITY_DOCUMENT_SOURCE,
        "source_url": report.discovered.source_url,
        "raw_sha256": report.raw_sha256,
    }
    values = {
        **identity,
        "report_published_at": report_published_at,
        "report_date": report.discovered.report_date,
        "source_time_precision": "minute",
        "retrieved_at": retrieved_at,
        "file_name": report.discovered.file_name,
        "file_size_bytes": report.file_size_bytes,
        "media_type": report.media_type,
        "raw_storage_locator": storage_locator.strip(),
        "http_etag": report.http_etag,
        "http_last_modified": http_last_modified,
        "collector_version": AVAILABILITY_DOCUMENT_COLLECTOR_VERSION,
        "completeness_status": "complete",
        "parser_version": None,
        "parse_status": "not_parsed",
        "parse_error_summary": None,
        "source_run_id": source_run_id,
    }
    existing = (
        db.query(AvailabilityReportDocumentORM)
        .filter_by(**identity)
        .one_or_none()
    )
    if existing is not None:
        # A later poll may retrieve byte-identical content under new HTTP metadata.
        # Preserve the first-seen observation instead of treating that rerun as a
        # conflicting document revision.
        observation_fields = {
            "retrieved_at",
            "http_etag",
            "http_last_modified",
            "source_run_id",
        }
        immutable_fields = tuple(
            values.keys() - identity.keys() - observation_fields
        )
        conflicts = [
            field
            for field in immutable_fields
            if _comparable(getattr(existing, field)) != _comparable(values[field])
        ]
        if conflicts:
            raise AvailabilityReportDocumentConflict(
                "Existing document revision has different immutable metadata: "
                + ", ".join(sorted(conflicts))
            )
        return AvailabilityReportDocumentResult(
            document_id=existing.document_id,
            created=False,
            document=existing,
        )

    document = AvailabilityReportDocumentORM(
        document_id=str(uuid.uuid4()),
        **values,
    )
    db.add(document)
    db.flush()
    return AvailabilityReportDocumentResult(
        document_id=document.document_id,
        created=True,
        document=document,
    )


def persist_downloaded_report_batch(
    reports: Iterable[DownloadedInjuryReport],
    *,
    archive_root: str | Path,
    source_run_id: str,
    db: Optional[Session] = None,
) -> AvailabilityReportDocumentBatchResult:
    """Store raw files, then register all metadata rows in one DB transaction."""
    report_list = list(reports)
    stored = [
        (report, store_raw_document_atomically(archive_root, report))
        for report in report_list
    ]

    def register_all(session: Session) -> AvailabilityReportDocumentBatchResult:
        results: List[AvailabilityReportDocumentResult] = []
        for report, path in stored:
            results.append(
                register_availability_report_document(
                    report,
                    storage_locator=str(path),
                    source_run_id=source_run_id,
                    db=session,
                )
            )
        return AvailabilityReportDocumentBatchResult(results=tuple(results))

    if db is not None:
        return register_all(db)
    with SessionLocal.begin() as session:
        return register_all(session)
