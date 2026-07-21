"""Contract tests for official injury-report discovery and retrieval."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from app.utils.fetch.official_injury_report_provider import (
    OfficialInjuryReportProvider,
    OfficialInjuryReportNotFound,
    OfficialInjuryReportProviderError,
    official_injury_report_url,
    parse_official_injury_report_url,
)


PAGE_URL = "https://official.nba.com/nba-injury-report-2025-26-season/"
REPORT_URL = (
    "https://ak-static.cms.nba.com/referee/injury/"
    "Injury-Report_2026-04-12_04_00PM.pdf"
)


class FakeResponse:
    def __init__(self, *, text="", content=b"", headers=None, status_code=200):
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_discovery_allowlists_host_path_and_parses_exact_eastern_timestamp():
    html = f"""
    <a href="{REPORT_URL}">valid</a>
    <a href="{REPORT_URL}">duplicate</a>
    <a href="https://evil.example/referee/injury/Injury-Report_2026-04-12_04_15PM.pdf">bad host</a>
    <a href="https://ak-static.cms.nba.com/referee/wnba_injury/Injury-Report_2026-04-12_04_30PM.pdf">bad path</a>
    <a href="https://ak-static.cms.nba.com/referee/injury/not-a-report.pdf">bad name</a>
    """
    session = FakeSession(
        [FakeResponse(text=html, headers={"Content-Type": "text/html"})]
    )
    provider = OfficialInjuryReportProvider(page_url=PAGE_URL, session=session)

    reports = provider.discover(report_date=date(2026, 4, 12))

    assert len(reports) == 1
    assert reports[0].source_url == REPORT_URL
    assert reports[0].report_date == date(2026, 4, 12)
    assert reports[0].report_published_at.isoformat() == "2026-04-12T16:00:00-04:00"


def test_download_hashes_valid_pdf_and_preserves_http_provenance():
    html = f'<a href="{REPORT_URL}">valid</a>'
    content = b"%PDF-1.7\nfixture"
    session = FakeSession(
        [
            FakeResponse(text=html, headers={"Content-Type": "text/html"}),
            FakeResponse(
                content=content,
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Length": str(len(content)),
                    "ETag": '"fixture-etag"',
                    "Last-Modified": "Sun, 12 Apr 2026 20:01:00 GMT",
                },
            ),
        ]
    )
    provider = OfficialInjuryReportProvider(
        page_url=PAGE_URL,
        session=session,
        now=lambda: datetime(2026, 4, 12, 20, 2, tzinfo=timezone.utc),
    )
    report = provider.discover()[0]

    downloaded = provider.download(report)

    assert downloaded.content == content
    assert downloaded.file_size_bytes == len(content)
    assert downloaded.raw_sha256 == (
        "f581fc87f30296eff11777c3ce1b9a8b7077071ad8abedfcba317fef0c807224"
    )
    assert downloaded.http_etag == '"fixture-etag"'
    assert downloaded.http_last_modified == datetime(
        2026, 4, 12, 20, 1, tzinfo=timezone.utc
    )
    assert session.calls[1][1]["headers"] == {"Accept": "application/pdf"}


def test_download_rejects_non_pdf_content():
    html = f'<a href="{REPORT_URL}">valid</a>'
    session = FakeSession(
        [
            FakeResponse(text=html, headers={"Content-Type": "text/html"}),
            FakeResponse(content=b"<html>blocked</html>"),
        ]
    )
    provider = OfficialInjuryReportProvider(page_url=PAGE_URL, session=session)
    report = provider.discover()[0]

    with pytest.raises(OfficialInjuryReportProviderError, match="not a PDF"):
        provider.download(report)


def test_download_uses_bounded_curl_fallback_after_requests_timeout(monkeypatch):
    html = f'<a href="{REPORT_URL}">valid</a>'
    content = b"%PDF-1.7\ncurl-fixture"
    session = FakeSession(
        [
            FakeResponse(text=html, headers={"Content-Type": "text/html"}),
            requests.Timeout("cdn timeout"),
        ]
    )
    provider = OfficialInjuryReportProvider(
        page_url=PAGE_URL,
        session=session,
        timeout_seconds=17,
        now=lambda: datetime(2026, 4, 12, 20, 2, tzinfo=timezone.utc),
    )
    report = provider.discover()[0]
    monkeypatch.setattr(
        "app.utils.fetch.official_injury_report_provider.shutil.which",
        lambda name: "C:/Windows/System32/curl.exe",
    )
    run = MagicMock(
        return_value=SimpleNamespace(
            returncode=0,
            stdout=content + b"\nYUNOBALL_HTTP_STATUS:200",
            stderr=b"",
        )
    )
    monkeypatch.setattr(
        "app.utils.fetch.official_injury_report_provider.subprocess.run",
        run,
    )

    downloaded = provider.download(report)

    assert downloaded.content == content
    assert downloaded.http_etag is None
    assert downloaded.http_last_modified is None
    command = run.call_args.args[0]
    assert command[command.index("--max-time") + 1] == "17"
    assert "--ipv4" in command
    assert "--http1.1" in command
    assert command[command.index("--connect-timeout") + 1] == "10"
    assert command[command.index("--retry") + 1] == "3"
    assert "--retry-all-errors" in command
    assert command[command.index("--max-filesize") + 1] == str(25 * 1024 * 1024)
    assert command[-1] == REPORT_URL
    assert run.call_args.kwargs["timeout"] == 78


def test_curl_uses_approved_proxy_only_when_explicitly_enabled(monkeypatch):
    content = b"%PDF-1.7\nproxy-fixture"
    report = parse_official_injury_report_url(REPORT_URL)
    provider = OfficialInjuryReportProvider(
        page_url=PAGE_URL,
        download_transport="curl",
        curl_retries=0,
    )
    monkeypatch.setenv("FORCE_PROXY", "true")
    monkeypatch.delenv("FORCE_LOCAL", raising=False)
    manager = MagicMock()
    manager.get_healthy_proxy.return_value = "http://user:secret@proxy.test:7000"
    monkeypatch.setattr(
        "app.utils.fetch.api_utils.get_proxy_manager", lambda: manager
    )
    monkeypatch.setattr(
        "app.utils.fetch.official_injury_report_provider.shutil.which",
        lambda name: "C:/Windows/System32/curl.exe",
    )
    run = MagicMock(return_value=SimpleNamespace(
        returncode=0,
        stdout=content + b"\nYUNOBALL_HTTP_STATUS:200",
        stderr=b"",
    ))
    monkeypatch.setattr(
        "app.utils.fetch.official_injury_report_provider.subprocess.run", run
    )

    downloaded = provider.download(report)

    command = run.call_args.args[0]
    assert downloaded.content == content
    assert command[command.index("--proxy") + 1] == "http://user:secret@proxy.test:7000"
    assert command[command.index("--retry") + 1] == "0"


def test_discovery_wraps_source_outage():
    provider = OfficialInjuryReportProvider(
        page_url=PAGE_URL,
        session=FakeSession([requests.Timeout("source unavailable")]),
    )

    with pytest.raises(OfficialInjuryReportProviderError, match="discovery failed"):
        provider.discover()


def test_page_url_must_remain_on_official_host():
    with pytest.raises(ValueError, match="official.nba.com"):
        OfficialInjuryReportProvider(page_url="https://example.test/injuries")


def test_canonical_candidate_url_round_trips_filename_timestamp():
    published = datetime(2026, 3, 3, 16, 30, tzinfo=timezone.utc).astimezone(
        __import__("zoneinfo").ZoneInfo("America/New_York")
    )
    url = official_injury_report_url(published)

    report = parse_official_injury_report_url(url)

    assert url.endswith("Injury-Report_2026-03-03_11_30AM.pdf")
    assert report is not None
    assert report.report_published_at == published


def test_legacy_hourly_filename_preserves_hour_precision():
    url = (
        "https://ak-static.cms.nba.com/referee/injury/"
        "Injury-Report_2024-01-15_05PM.pdf"
    )

    report = parse_official_injury_report_url(url)

    assert report is not None
    assert report.source_time_precision == "hour"
    assert report.report_published_at.isoformat() == "2024-01-15T17:00:00-05:00"
    assert official_injury_report_url(datetime(2024, 1, 15, 22, 30, tzinfo=timezone.utc)) == url


def test_filename_transition_gap_fails_closed():
    with pytest.raises(ValueError, match="No official report filename format"):
        official_injury_report_url(datetime(2025, 12, 19, 20, 45, tzinfo=timezone.utc))


def test_confirmed_candidate_404_is_not_a_transient_download_failure():
    report = parse_official_injury_report_url(REPORT_URL)
    provider = OfficialInjuryReportProvider(
        page_url=PAGE_URL,
        session=FakeSession([FakeResponse(status_code=404)]),
        download_transport="requests",
    )

    with pytest.raises(OfficialInjuryReportNotFound):
        provider.download(report)
