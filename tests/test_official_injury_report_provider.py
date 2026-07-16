"""Contract tests for official injury-report discovery and retrieval."""

from datetime import date, datetime, timezone

import pytest
import requests

from app.utils.fetch.official_injury_report_provider import (
    OfficialInjuryReportProvider,
    OfficialInjuryReportProviderError,
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
            raise requests.HTTPError(f"HTTP {self.status_code}")


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
