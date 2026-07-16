"""Unit tests for immutable official report-document persistence."""

from datetime import date, datetime, timedelta, timezone
import hashlib
from pathlib import Path
from unittest.mock import MagicMock
import uuid
from zoneinfo import ZoneInfo

import pytest

from app.models.availability_report_document_sqlalchemy import (
    AvailabilityReportDocumentORM,
)
from app.services.availability_report_document_service import (
    AvailabilityReportDocumentConflict,
    register_availability_report_document,
    store_raw_document_atomically,
    validate_archive_root,
)
from app.utils.fetch.official_injury_report_provider import (
    DiscoveredInjuryReport,
    DownloadedInjuryReport,
)


def _report(content=b"%PDF-1.7\nfixture", *, retrieved_at=None):
    discovered = DiscoveredInjuryReport(
        source_url=(
            "https://ak-static.cms.nba.com/referee/injury/"
            "Injury-Report_2026-04-12_04_00PM.pdf"
        ),
        file_name="Injury-Report_2026-04-12_04_00PM.pdf",
        report_date=date(2026, 4, 12),
        report_published_at=datetime(
            2026,
            4,
            12,
            16,
            0,
            tzinfo=ZoneInfo("America/New_York"),
        ),
    )
    return DownloadedInjuryReport(
        discovered=discovered,
        content=content,
        retrieved_at=retrieved_at
        or datetime(2026, 4, 12, 20, 2, tzinfo=timezone.utc),
        raw_sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/pdf",
        http_etag='"fixture"',
        http_last_modified=datetime(2026, 4, 12, 20, 1, tzinfo=timezone.utc),
    )


def _session(existing=None):
    session = MagicMock()
    session.query.return_value.filter_by.return_value.one_or_none.return_value = existing
    return session


def test_first_revision_is_registered_with_raw_source_lineage():
    report = _report()
    session = _session()
    run_id = str(uuid.uuid4())

    result = register_availability_report_document(
        report,
        storage_locator="C:/private/archive/report.pdf",
        source_run_id=run_id,
        db=session,
    )

    assert result.created is True
    assert result.document.source_name == "official_nba"
    assert result.document.report_published_at == datetime(
        2026, 4, 12, 20, 0, tzinfo=timezone.utc
    )
    assert result.document.source_time_precision == "minute"
    assert result.document.completeness_status == "complete"
    assert result.document.parse_status == "not_parsed"
    assert result.document.source_run_id == run_id
    session.add.assert_called_once_with(result.document)
    session.flush.assert_called_once_with()


def test_byte_identical_later_retrieval_is_an_idempotent_no_op():
    first = _report()
    existing = AvailabilityReportDocumentORM(
        document_id=str(uuid.uuid4()),
        source_name="official_nba",
        source_url=first.discovered.source_url,
        report_published_at=datetime(2026, 4, 12, 20, 0, tzinfo=timezone.utc),
        report_date=first.discovered.report_date,
        source_time_precision="minute",
        retrieved_at=first.retrieved_at,
        raw_sha256=first.raw_sha256,
        file_name=first.discovered.file_name,
        file_size_bytes=first.file_size_bytes,
        media_type="application/pdf",
        raw_storage_locator="C:/private/archive/report.pdf",
        http_etag='"old-etag"',
        http_last_modified=None,
        collector_version="official-injury-documents-v1",
        completeness_status="complete",
        parser_version=None,
        parse_status="not_parsed",
        parse_error_summary=None,
        source_run_id=str(uuid.uuid4()),
    )
    rerun = _report(retrieved_at=first.retrieved_at + timedelta(minutes=15))
    session = _session(existing)

    result = register_availability_report_document(
        rerun,
        storage_locator="C:/private/archive/report.pdf",
        source_run_id=str(uuid.uuid4()),
        db=session,
    )

    assert result.created is False
    assert result.document_id == existing.document_id
    assert result.document.retrieved_at == first.retrieved_at
    session.add.assert_not_called()


def test_changed_content_at_same_url_is_a_separate_revision():
    first = _report()
    changed = _report(content=b"%PDF-1.7\ncorrected")
    session = _session(existing=None)

    result = register_availability_report_document(
        changed,
        storage_locator="C:/private/archive/corrected.pdf",
        source_run_id=str(uuid.uuid4()),
        db=session,
    )

    assert result.created is True
    assert changed.raw_sha256 != first.raw_sha256


def test_exact_revision_rejects_changed_immutable_storage_locator():
    report = _report()
    existing = AvailabilityReportDocumentORM(
        document_id=str(uuid.uuid4()),
        source_name="official_nba",
        source_url=report.discovered.source_url,
        report_published_at=datetime(2026, 4, 12, 20, 0, tzinfo=timezone.utc),
        report_date=report.discovered.report_date,
        source_time_precision="minute",
        retrieved_at=report.retrieved_at,
        raw_sha256=report.raw_sha256,
        file_name=report.discovered.file_name,
        file_size_bytes=report.file_size_bytes,
        media_type="application/pdf",
        raw_storage_locator="C:/private/archive/original.pdf",
        http_etag=report.http_etag,
        http_last_modified=report.http_last_modified,
        collector_version="official-injury-documents-v1",
        completeness_status="complete",
        parser_version=None,
        parse_status="not_parsed",
        parse_error_summary=None,
        source_run_id=str(uuid.uuid4()),
    )

    with pytest.raises(AvailabilityReportDocumentConflict, match="raw_storage_locator"):
        register_availability_report_document(
            report,
            storage_locator="C:/private/archive/moved.pdf",
            source_run_id=str(uuid.uuid4()),
            db=_session(existing),
        )


def test_atomic_storage_is_content_addressed_and_rerun_safe(tmp_path):
    report = _report()

    stored = store_raw_document_atomically(tmp_path, report)
    rerun = store_raw_document_atomically(tmp_path, report)

    assert stored == rerun
    assert stored.read_bytes() == report.content
    assert report.raw_sha256[:16] in stored.name


def test_archive_root_rejects_repository_paths():
    repository_root = Path(__file__).resolve().parents[1]

    with pytest.raises(ValueError, match="outside the repository"):
        validate_archive_root(
            repository_root / "dataSource" / "archive",
            repository_root=repository_root,
        )
