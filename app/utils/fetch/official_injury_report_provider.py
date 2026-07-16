"""Provider boundary for official NBA injury-report pages and PDF revisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import os
import re
import shutil
import subprocess
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
CURL_TIMEOUT_EXIT_CODE = 28
DOWNLOAD_TRANSPORTS = {"auto", "requests", "curl"}

_REPORT_FILE_PATTERN = re.compile(
    r"^Injury-Report_(?P<date>\d{4}-\d{2}-\d{2})_"
    r"(?P<hour>\d{2})_(?P<minute>\d{2})(?P<meridiem>AM|PM)\.pdf$",
    re.IGNORECASE,
)


class OfficialInjuryReportProviderError(RuntimeError):
    """Raised when discovery or retrieval violates the official-source contract."""


class OfficialInjuryReportNotFound(OfficialInjuryReportProviderError):
    """Raised when an allowlisted candidate URL is confirmed absent (HTTP 404)."""


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


def parse_official_injury_report_url(
    raw_url: str,
) -> Optional[DiscoveredInjuryReport]:
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


def official_injury_report_url(published_at: datetime) -> str:
    """Build one canonical official CDN candidate from an Eastern timestamp."""
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ValueError("published_at must include timezone information")
    eastern = published_at.astimezone(ZoneInfo("America/New_York"))
    return (
        f"https://{OFFICIAL_DOCUMENT_HOST}{OFFICIAL_DOCUMENT_PATH_PREFIX}"
        f"Injury-Report_{eastern:%Y-%m-%d_%I_%M%p}.pdf"
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
        download_transport: str = "auto",
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        parsed_page = urlparse(page_url)
        if parsed_page.scheme.casefold() != "https" or (
            parsed_page.hostname or ""
        ).casefold() != OFFICIAL_PAGE_HOST:
            raise ValueError("page_url must use the official.nba.com HTTPS host")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if download_transport not in DOWNLOAD_TRANSPORTS:
            raise ValueError(
                f"download_transport must be one of {sorted(DOWNLOAD_TRANSPORTS)}"
            )
        self.page_url = page_url
        self.timeout_seconds = timeout_seconds
        self.download_transport = download_transport
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
            report = parse_official_injury_report_url(absolute_url)
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
        validated = parse_official_injury_report_url(report.source_url)
        if validated != report:
            raise OfficialInjuryReportProviderError(
                "Report URL or filename timestamp is outside the official contract"
            )
        retrieval_started_at = self._now()
        if (
            retrieval_started_at.tzinfo is None
            or retrieval_started_at.utcoffset() is None
        ):
            raise OfficialInjuryReportProviderError(
                "Provider clock must return a timezone-aware retrieval timestamp"
            )
        retrieval_url = f"{report.source_url}?yunoball_download=1"
        response = None
        if self.download_transport == "curl":
            content = self._download_with_curl(
                report,
                retrieval_url=retrieval_url,
                primary_error=OfficialInjuryReportProviderError(
                    "curl transport explicitly selected"
                ),
            )
            http_etag = None
            http_last_modified = None
            declared_length = None
        else:
            try:
                response = self._session.get(
                    retrieval_url,
                    **self._request_kwargs(accept="application/pdf"),
                )
                response.raise_for_status()
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    raise OfficialInjuryReportNotFound(
                        f"Official injury-report candidate was not found: "
                        f"{report.source_url}"
                    ) from exc
                if self.download_transport == "requests":
                    raise OfficialInjuryReportProviderError(
                        f"Official injury-report download failed for "
                        f"{report.source_url}: {exc}"
                    ) from exc
                content = self._download_with_curl(
                    report,
                    retrieval_url=retrieval_url,
                    primary_error=exc,
                )
                http_etag = None
                http_last_modified = None
                declared_length = None
            except requests.RequestException as exc:
                if self.download_transport == "requests":
                    raise OfficialInjuryReportProviderError(
                        f"Official injury-report download failed for "
                        f"{report.source_url}: {exc}"
                    ) from exc
                content = self._download_with_curl(
                    report,
                    retrieval_url=retrieval_url,
                    primary_error=exc,
                )
                http_etag = None
                http_last_modified = None
                declared_length = None
            else:
                content = bytes(response.content)
                http_etag = response.headers.get("ETag")
                http_last_modified = _parse_http_datetime(
                    response.headers.get("Last-Modified")
                )
                declared_length = response.headers.get("Content-Length")

        if not content.startswith(b"%PDF-"):
            raise OfficialInjuryReportProviderError(
                f"Official report is not a PDF: {report.source_url}"
            )
        if len(content) > MAX_DOCUMENT_BYTES:
            raise OfficialInjuryReportProviderError(
                f"Official report exceeds {MAX_DOCUMENT_BYTES} bytes"
            )
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
        return DownloadedInjuryReport(
            discovered=report,
            content=content,
            retrieved_at=retrieved_at.astimezone(timezone.utc),
            raw_sha256=hashlib.sha256(content).hexdigest(),
            media_type="application/pdf",
            http_etag=http_etag,
            http_last_modified=http_last_modified,
        )

    def _download_with_curl(
        self,
        report: DiscoveredInjuryReport,
        *,
        retrieval_url: str,
        primary_error: BaseException,
    ) -> bytes:
        """Use the system curl client when requests cannot read the NBA CDN."""
        curl = shutil.which("curl") or shutil.which("curl.exe")
        if not curl:
            raise OfficialInjuryReportProviderError(
                f"Official injury-report download failed for {report.source_url}: "
                f"{primary_error}; curl fallback is unavailable"
            ) from primary_error
        command = [
            curl,
            "--ipv4",
            "--http1.1",
            "--location",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            str(self.timeout_seconds),
            "--connect-timeout",
            str(min(self.timeout_seconds, 10)),
            "--retry",
            "3",
            "--retry-all-errors",
            "--retry-delay",
            "1",
            "--max-filesize",
            str(MAX_DOCUMENT_BYTES),
            "--header",
            f"Referer: {self.page_url}",
            "--header",
            "Accept: application/pdf",
            "--header",
            "User-Agent: Mozilla/5.0 (compatible; YunoBall/1.0; +https://yunoball.xyz/)",
            "--write-out",
            "\nYUNOBALL_HTTP_STATUS:%{http_code}",
            retrieval_url,
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                timeout=(self.timeout_seconds * 4) + 10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OfficialInjuryReportProviderError(
                f"Official injury-report curl fallback failed for "
                f"{report.source_url}: {exc}"
            ) from exc
        marker = b"\nYUNOBALL_HTTP_STATUS:"
        content, separator, status_bytes = completed.stdout.rpartition(marker)
        http_status = (
            status_bytes.decode("ascii", errors="ignore").strip()
            if separator
            else ""
        )
        if http_status == "404":
            raise OfficialInjuryReportNotFound(
                f"Official injury-report candidate was not found: {report.source_url}"
            ) from primary_error
        if completed.returncode != 0:
            error = completed.stderr.decode("utf-8", errors="replace").strip()
            label = (
                "timed out"
                if completed.returncode == CURL_TIMEOUT_EXIT_CODE
                else f"exited {completed.returncode}"
            )
            raise OfficialInjuryReportProviderError(
                f"Official injury-report curl fallback {label} for "
                f"{report.source_url}: {error[:500]}"
            ) from primary_error
        if not separator:
            raise OfficialInjuryReportProviderError(
                f"Official injury-report curl fallback returned no HTTP status for "
                f"{report.source_url}"
            )
        return bytes(content)
