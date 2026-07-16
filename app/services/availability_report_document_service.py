"""Durable persistence for immutable official availability-report documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
    AvailabilityReportDownloadAttemptORM,
)
from app.utils.fetch.official_injury_report_provider import (
    DiscoveredInjuryReport,
    DownloadedInjuryReport,
)


AVAILABILITY_DOCUMENT_LOCK_NAME = "yunoball:official_injury_report_documents"
AVAILABILITY_DOCUMENT_SOURCE = "official_nba"
AVAILABILITY_DOCUMENT_COLLECTOR_VERSION = "official-injury-documents-v1"
DEFAULT_DOWNLOAD_RETRY_INTERVAL = timedelta(hours=2)

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


@dataclass(frozen=True)
class AvailabilityDownloadQueueSummary:
    pending_count: int
    due_count: int
    overdue_count: int
    oldest_pending_published_at: Optional[datetime]


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


def upsert_discovered_downloads(
    reports: Iterable[DiscoveredInjuryReport],
    *,
    source_run_id: str,
    discovered_at: datetime,
    db: Session,
) -> int:
    """Persist newly discovered URLs and refresh discovery time idempotently."""
    observed_at = _aware_utc(discovered_at, "discovered_at")
    created = 0
    for report in reports:
        existing = db.query(AvailabilityReportDownloadAttemptORM).filter_by(
            source_name=AVAILABILITY_DOCUMENT_SOURCE,
            source_url=report.source_url,
        ).one_or_none()
        published_at = _aware_utc(report.report_published_at, "report_published_at")
        if existing is None:
            db.add(AvailabilityReportDownloadAttemptORM(
                download_attempt_id=str(uuid.uuid4()),
                source_name=AVAILABILITY_DOCUMENT_SOURCE,
                source_url=report.source_url,
                file_name=report.file_name,
                report_published_at=published_at,
                report_date=report.report_date,
                status="pending",
                attempt_count=0,
                first_discovered_at=observed_at,
                last_discovered_at=observed_at,
                next_retry_at=observed_at,
                first_discovered_run_id=source_run_id,
                updated_at=observed_at,
            ))
            created += 1
        else:
            if (existing.file_name, _comparable(existing.report_published_at), existing.report_date) != (
                report.file_name, published_at, report.report_date
            ):
                raise AvailabilityReportDocumentConflict(
                    f"Discovered URL changed immutable filename metadata: {report.source_url}"
                )
            existing.last_discovered_at = observed_at
            existing.updated_at = observed_at
    db.flush()
    return created


def select_due_downloads(
    *, report_date: date, attempted_at: datetime, limit: int, db: Session
) -> Sequence[AvailabilityReportDownloadAttemptORM]:
    """Select unresolved URLs whose retry window is due, oldest first."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    now = _aware_utc(attempted_at, "attempted_at")
    return tuple(
        db.query(AvailabilityReportDownloadAttemptORM)
        .filter(
            AvailabilityReportDownloadAttemptORM.report_date == report_date,
            AvailabilityReportDownloadAttemptORM.status == "pending",
            AvailabilityReportDownloadAttemptORM.next_retry_at <= now,
        )
        .order_by(
            AvailabilityReportDownloadAttemptORM.report_published_at,
            AvailabilityReportDownloadAttemptORM.source_url,
        )
        .limit(limit)
        .all()
    )


def summarize_download_queue(
    *,
    report_date: date,
    observed_at: datetime,
    freshness_threshold: timedelta,
    db: Session,
) -> AvailabilityDownloadQueueSummary:
    """Return monitoring counts for unresolved documents on one report date."""
    now = _aware_utc(observed_at, "observed_at")
    if freshness_threshold <= timedelta(0):
        raise ValueError("freshness_threshold must be positive")
    pending = db.query(AvailabilityReportDownloadAttemptORM).filter(
        AvailabilityReportDownloadAttemptORM.report_date == report_date,
        AvailabilityReportDownloadAttemptORM.status == "pending",
    ).all()
    published = [
        _aware_utc(item.report_published_at, "report_published_at") for item in pending
    ]
    return AvailabilityDownloadQueueSummary(
        pending_count=len(pending),
        due_count=sum(
            1 for item in pending
            if item.next_retry_at is not None
            and _aware_utc(item.next_retry_at, "next_retry_at") <= now
        ),
        overdue_count=sum(1 for value in published if value + freshness_threshold <= now),
        oldest_pending_published_at=min(published) if published else None,
    )


def discovered_report_from_attempt(
    attempt: AvailabilityReportDownloadAttemptORM,
) -> DiscoveredInjuryReport:
    return DiscoveredInjuryReport(
        source_url=attempt.source_url,
        file_name=attempt.file_name,
        report_date=attempt.report_date,
        report_published_at=_aware_utc(attempt.report_published_at, "report_published_at"),
    )


def record_download_failure(
    source_url: str,
    *, source_run_id: str,
    attempted_at: datetime,
    error: BaseException,
    retry_interval: timedelta = DEFAULT_DOWNLOAD_RETRY_INTERVAL,
    db: Session,
) -> None:
    """Advance one failed URL while retaining it for a later scheduled run."""
    now = _aware_utc(attempted_at, "attempted_at")
    if retry_interval <= timedelta(0):
        raise ValueError("retry_interval must be positive")
    attempt = db.query(AvailabilityReportDownloadAttemptORM).filter_by(
        source_name=AVAILABILITY_DOCUMENT_SOURCE, source_url=source_url
    ).one()
    if attempt.status != "pending":
        return
    attempt.attempt_count += 1
    attempt.last_attempt_at = now
    attempt.next_retry_at = now + retry_interval
    attempt.last_error_class = type(error).__name__[:128]
    attempt.last_error_summary = str(error)[:2000]
    attempt.last_attempt_run_id = source_run_id
    attempt.updated_at = now


def persist_downloaded_report_and_mark_success(
    report: DownloadedInjuryReport,
    *, archive_root: str | Path,
    source_run_id: str,
    db: Session,
) -> AvailabilityReportDocumentResult:
    """Store/register a PDF and close its queue row in the caller transaction."""
    path = store_raw_document_atomically(archive_root, report)
    result = register_availability_report_document(
        report, storage_locator=str(path), source_run_id=source_run_id, db=db
    )
    attempt = db.query(AvailabilityReportDownloadAttemptORM).filter_by(
        source_name=AVAILABILITY_DOCUMENT_SOURCE,
        source_url=report.discovered.source_url,
    ).one()
    attempt.status = "succeeded"
    attempt.attempt_count += 1
    attempt.last_attempt_at = report.retrieved_at
    attempt.next_retry_at = None
    attempt.last_error_class = None
    attempt.last_error_summary = None
    attempt.last_attempt_run_id = source_run_id
    attempt.document_id = result.document_id
    attempt.updated_at = report.retrieved_at
    db.flush()
    return result
