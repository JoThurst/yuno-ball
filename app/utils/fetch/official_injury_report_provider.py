"""Provider boundary for official NBA injury-report pages and PDF revisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import os
import re
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


OFFICIAL_PAGE_HOST = "official.nba.com"
OFFICIAL_DOCUMENT_HOST = "ak-static.cms.nba.com"
OFFICIAL_DOCUMENT_PATH_PREFIX = "/referee/injury/"
DEFAULT_TIMEOUT_SECONDS = 45
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024

_REPORT_FILE_PATTERN = re.compile(
    r"^Injury-Report_(?P<date>\d{4}-\d{2}-\d{2})_"
    r"(?P<hour>\d{2})_(?P<minute>\d{2})(?P<meridiem>AM|PM)\.pdf$",
    re.IGNORECASE,
)


class OfficialInjuryReportProviderError(RuntimeError):
    """Raised when discovery or retrieval violates the official-source contract."""


@dataclass(frozen=True)
class DiscoveredInjuryReport:
    """One official report link with filename-derived publication semantics."""

    source_url: str
    file_name: str
    report_date: date
    report_published_at: datetime


@dataclass(frozen=True)
class DownloadedInjuryReport:
    """One validated official PDF revision held in memory before persistence."""

    discovered: DiscoveredInjuryReport
    content: bytes
    retrieved_at: datetime
    raw_sha256: str
    media_type: str
    http_etag: Optional[str]
    http_last_modified: Optional[datetime]

    @property
    def file_size_bytes(self) -> int:
        return len(self.content)


def official_injury_report_page_url(season: str) -> str:
    """Build the official season page without embedding a fixed season."""
    return f"https://{OFFICIAL_PAGE_HOST}/nba-injury-report-{season}-season/"


def _parse_report_url(raw_url: str) -> Optional[DiscoveredInjuryReport]:
    parsed = urlparse(raw_url)
    if parsed.scheme.casefold() != "https":
        return None
    if (parsed.hostname or "").casefold() != OFFICIAL_DOCUMENT_HOST:
        return None
    if not parsed.path.startswith(OFFICIAL_DOCUMENT_PATH_PREFIX):
        return None
    file_name = parsed.path.rsplit("/", 1)[-1]
    match = _REPORT_FILE_PATTERN.fullmatch(file_name)
    if match is None:
        return None
    try:
        report_date = date.fromisoformat(match.group("date"))
        published = datetime.strptime(
            (
                f"{match.group('date')} {match.group('hour')}:"
                f"{match.group('minute')}{match.group('meridiem').upper()}"
            ),
            "%Y-%m-%d %I:%M%p",
        ).replace(tzinfo=ZoneInfo("America/New_York"))
    except ValueError:
        return None
    return DiscoveredInjuryReport(
        source_url=raw_url,
        file_name=file_name,
        report_date=report_date,
        report_published_at=published,
    )


def _parse_http_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class OfficialInjuryReportProvider:
    """Discover and retrieve official PDFs behind one injectable HTTP boundary."""

    def __init__(
        self,
        *,
        page_url: str,
        session: Optional[requests.Session] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        parsed_page = urlparse(page_url)
        if parsed_page.scheme.casefold() != "https" or (
            parsed_page.hostname or ""
        ).casefold() != OFFICIAL_PAGE_HOST:
            raise ValueError("page_url must use the official.nba.com HTTPS host")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.page_url = page_url
        self.timeout_seconds = timeout_seconds
        self._now = now
        self._session = session or self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=2,
            connect=2,
            read=2,
            status=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        return session

    def _request_kwargs(self, *, accept: str) -> Dict[str, object]:
        kwargs: Dict[str, object] = {
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; YunoBall/1.0; "
                    "+https://yunoball.xyz/)"
                ),
                "Accept": accept,
                "Referer": self.page_url,
            },
            "timeout": self.timeout_seconds,
        }
        force_proxy = os.getenv("FORCE_PROXY", "").casefold() == "true"
        force_local = os.getenv("FORCE_LOCAL", "").casefold() == "true"
        if force_proxy and not force_local:
            from app.utils.fetch.api_utils import get_proxy_manager

            proxy = get_proxy_manager().get_healthy_proxy()
            if proxy:
                kwargs["proxies"] = {"http": proxy, "https": proxy}
        return kwargs

    def discover(
        self,
        *,
        report_date: Optional[date] = None,
    ) -> List[DiscoveredInjuryReport]:
        """Return unique allowlisted report links, optionally for one ET date."""
        try:
            response = self._session.get(
                self.page_url,
                **self._request_kwargs(accept="text/html,application/xhtml+xml"),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OfficialInjuryReportProviderError(
                f"Official injury-report discovery failed: {exc}"
            ) from exc

        content_type = response.headers.get("Content-Type", "").casefold()
        if content_type and "html" not in content_type:
            raise OfficialInjuryReportProviderError(
                f"Official injury-report page returned {content_type!r}, not HTML"
            )

        discovered: Dict[str, DiscoveredInjuryReport] = {}
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            absolute_url = urljoin(self.page_url, anchor["href"])
            report = _parse_report_url(absolute_url)
            if report is None:
                continue
            if report_date is not None and report.report_date != report_date:
                continue
            discovered[report.source_url] = report
        return sorted(
            discovered.values(),
            key=lambda item: (item.report_published_at, item.source_url),
        )

    def download(self, report: DiscoveredInjuryReport) -> DownloadedInjuryReport:
        """Retrieve and validate one allowlisted PDF without persisting it."""
        validated = _parse_report_url(report.source_url)
        if validated != report:
            raise OfficialInjuryReportProviderError(
                "Report URL or filename timestamp is outside the official contract"
            )
        try:
            response = self._session.get(
                report.source_url,
                **self._request_kwargs(accept="application/pdf"),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OfficialInjuryReportProviderError(
                f"Official injury-report download failed for {report.source_url}: {exc}"
            ) from exc

        content = bytes(response.content)
        if not content.startswith(b"%PDF-"):
            raise OfficialInjuryReportProviderError(
                f"Official report is not a PDF: {report.source_url}"
            )
        if len(content) > MAX_DOCUMENT_BYTES:
            raise OfficialInjuryReportProviderError(
                f"Official report exceeds {MAX_DOCUMENT_BYTES} bytes"
            )
        declared_length = response.headers.get("Content-Length")
        if declared_length:
            try:
                if int(declared_length) != len(content):
                    raise OfficialInjuryReportProviderError(
                        "Official report Content-Length does not match downloaded bytes"
                    )
            except ValueError as exc:
                raise OfficialInjuryReportProviderError(
                    "Official report returned an invalid Content-Length"
                ) from exc

        retrieved_at = self._now()
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise OfficialInjuryReportProviderError(
                "Provider clock must return a timezone-aware retrieval timestamp"
            )
        return DownloadedInjuryReport(
            discovered=report,
            content=content,
            retrieved_at=retrieved_at.astimezone(timezone.utc),
            raw_sha256=hashlib.sha256(content).hexdigest(),
            media_type="application/pdf",
            http_etag=response.headers.get("ETag"),
            http_last_modified=_parse_http_datetime(
                response.headers.get("Last-Modified")
            ),
        )
