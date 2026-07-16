"""CLI safety tests for the bounded official injury-report collector."""

from datetime import date, datetime, timezone
import hashlib
import json
from zoneinfo import ZoneInfo

import scripts.collect_official_injury_reports as collector
from app.utils.fetch.official_injury_report_provider import (
    DiscoveredInjuryReport,
    DownloadedInjuryReport,
)


def _downloaded_report():
    content = b"%PDF-1.7\nfixture"
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
            tzinfo=ZoneInfo("America/New_York"),
        ),
    )
    return DownloadedInjuryReport(
        discovered=discovered,
        content=content,
        retrieved_at=datetime(2026, 4, 12, 20, 2, tzinfo=timezone.utc),
        raw_sha256=hashlib.sha256(content).hexdigest(),
        media_type="application/pdf",
        http_etag=None,
        http_last_modified=None,
    )


class FakeProvider:
    def __init__(self, *, page_url, timeout_seconds, download_transport):
        assert timeout_seconds == 45
        assert download_transport == "auto"
        self.report = _downloaded_report()

    def discover(self, *, report_date):
        assert report_date == date(2026, 4, 12)
        return [self.report.discovered]

    def download(self, report):
        assert report == self.report.discovered
        return self.report


class FailingDownloadProvider(FakeProvider):
    def download(self, report):
        raise RuntimeError("fixture download failure")


def test_dry_run_downloads_and_hashes_without_archive_or_persistence(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(collector, "OfficialInjuryReportProvider", FakeProvider)
    monkeypatch.delenv("YUNOBALL_INJURY_REPORT_ARCHIVE_DIR", raising=False)

    exit_code = collector.main(
        [
            "--season",
            "2025-26",
            "--report-date",
            "2026-04-12",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["database_write"] is False
    assert output["file_write"] is False
    assert output["downloaded_count"] == 1
    assert output["documents"][0]["raw_sha256"] == _downloaded_report().raw_sha256


def test_apply_requires_explicit_durable_archive(monkeypatch, capsys):
    monkeypatch.setattr(collector, "OfficialInjuryReportProvider", FakeProvider)
    monkeypatch.delenv("YUNOBALL_INJURY_REPORT_ARCHIVE_DIR", raising=False)

    exit_code = collector.main(
        [
            "--season",
            "2025-26",
            "--report-date",
            "2026-04-12",
            "--apply",
        ]
    )

    assert exit_code == 1
    assert "archive-root" in capsys.readouterr().err


def test_dry_run_exits_nonzero_when_a_discovered_document_fails(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        collector,
        "OfficialInjuryReportProvider",
        FailingDownloadProvider,
    )

    exit_code = collector.main(
        [
            "--season",
            "2025-26",
            "--report-date",
            "2026-04-12",
            "--dry-run",
        ]
    )

    assert exit_code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["failure_count"] == 1
    assert output["database_write"] is False
    assert output["file_write"] is False


def test_document_bound_is_enforced_before_provider_creation(capsys):
    exit_code = collector.main(
        [
            "--season",
            "2025-26",
            "--report-date",
            "2026-04-12",
            "--max-documents",
            "97",
            "--dry-run",
        ]
    )

    assert exit_code == 1
    assert "between 1 and 96" in capsys.readouterr().err


def test_retry_interval_is_bounded_before_provider_creation(capsys):
    exit_code = collector.main(
        [
            "--season", "2025-26",
            "--report-date", "2026-04-12",
            "--retry-interval-hours", "0",
            "--dry-run",
        ]
    )

    assert exit_code == 1
    assert "between 1 and 24" in capsys.readouterr().err


def test_freshness_threshold_is_bounded_before_provider_creation(capsys):
    exit_code = collector.main(
        [
            "--season", "2025-26",
            "--report-date", "2026-04-12",
            "--freshness-threshold-hours", "49",
            "--dry-run",
        ]
    )

    assert exit_code == 1
    assert "between 1 and 48" in capsys.readouterr().err
