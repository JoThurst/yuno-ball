"""Collect bounded official NBA injury-report PDF revisions."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import sys
from typing import Dict, Optional, Sequence
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.availability_report_document_service import (  # noqa: E402
    AVAILABILITY_DOCUMENT_COLLECTOR_VERSION,
    AVAILABILITY_DOCUMENT_LOCK_NAME,
    persist_downloaded_report_batch,
    validate_archive_root,
)
from app.utils.fetch.official_injury_report_provider import (  # noqa: E402
    OfficialInjuryReportProvider,
    official_injury_report_page_url,
)
from app.utils.season_utils import get_current_season, normalize_season  # noqa: E402


MAX_ALLOWED_DOCUMENTS = 96


def _parse_report_date(raw: Optional[str]) -> date:
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError("--report-date must use YYYY-MM-DD") from exc
    return datetime.now(ZoneInfo("America/New_York")).date()


def _parse_published_at_or_before(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("--published-at-or-before must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--published-at-or-before must include a timezone")
    return parsed


def _archive_root(args: argparse.Namespace) -> Path:
    raw = args.archive_root or os.getenv("YUNOBALL_INJURY_REPORT_ARCHIVE_DIR")
    if not raw:
        raise ValueError(
            "--archive-root or YUNOBALL_INJURY_REPORT_ARCHIVE_DIR is required for --apply"
        )
    return validate_archive_root(raw)


def _collect(
    provider: OfficialInjuryReportProvider,
    *,
    report_date: date,
    max_documents: int,
    published_at_or_before: Optional[datetime] = None,
) -> tuple[list, list[Dict[str, str]], int]:
    discovered = provider.discover(report_date=report_date)
    eligible = [
        report
        for report in discovered
        if published_at_or_before is None
        or report.report_published_at <= published_at_or_before
    ]
    selected = eligible[-max_documents:]
    downloaded = []
    failures: list[Dict[str, str]] = []
    for report in selected:
        try:
            downloaded.append(provider.download(report))
        except Exception as exc:
            failures.append(
                {
                    "source_url": report.source_url,
                    "error_class": type(exc).__name__,
                    "error_summary": str(exc)[:500],
                }
            )
    return downloaded, failures, len(discovered)


def _report_metadata(report) -> Dict[str, object]:
    return {
        "source_url": report.discovered.source_url,
        "file_name": report.discovered.file_name,
        "report_published_at": report.discovered.report_published_at.isoformat(),
        "report_date": report.discovered.report_date.isoformat(),
        "retrieved_at": report.retrieved_at.isoformat(),
        "raw_sha256": report.raw_sha256,
        "file_size_bytes": report.file_size_bytes,
        "media_type": report.media_type,
        "http_etag": report.http_etag,
        "http_last_modified": (
            report.http_last_modified.isoformat()
            if report.http_last_modified
            else None
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and retain official NBA injury-report PDFs without parsing "
            "availability observations"
        )
    )
    parser.add_argument(
        "--season",
        help="Canonical NBA season; defaults through shared season selection",
    )
    parser.add_argument(
        "--report-date",
        help="Bound discovery to one Eastern report date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--max-documents",
        type=int,
        default=MAX_ALLOWED_DOCUMENTS,
        help=f"Maximum reports downloaded in one run (1-{MAX_ALLOWED_DOCUMENTS})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=45,
        help="Per-request HTTP timeout (5-120 seconds)",
    )
    parser.add_argument(
        "--download-transport",
        choices=("auto", "curl", "requests"),
        default="auto",
        help="PDF transport; curl bypasses known requests/CDN timeouts",
    )
    parser.add_argument(
        "--published-at-or-before",
        help=(
            "Only select reports at or before this timezone-aware ISO timestamp; "
            "useful for CDN propagation lag"
        ),
    )
    parser.add_argument(
        "--page-url",
        help="Official season page override; must remain on official.nba.com",
    )
    parser.add_argument(
        "--archive-root",
        help=(
            "Durable root outside the repository; may also be supplied through "
            "YUNOBALL_INJURY_REPORT_ARCHIVE_DIR"
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def _validate_args(args: argparse.Namespace) -> tuple[str, date, str]:
    if not 1 <= args.max_documents <= MAX_ALLOWED_DOCUMENTS:
        raise ValueError(
            f"--max-documents must be between 1 and {MAX_ALLOWED_DOCUMENTS}"
        )
    if not 5 <= args.timeout_seconds <= 120:
        raise ValueError("--timeout-seconds must be between 5 and 120")
    season = normalize_season(args.season or get_current_season())
    report_date = _parse_report_date(args.report_date)
    page_url = args.page_url or official_injury_report_page_url(season)
    return season, report_date, page_url


def _dry_run(
    provider: OfficialInjuryReportProvider,
    *,
    season: str,
    report_date: date,
    page_url: str,
    max_documents: int,
    published_at_or_before: Optional[datetime],
) -> Dict[str, object]:
    downloaded, failures, discovered_count = _collect(
        provider,
        report_date=report_date,
        max_documents=max_documents,
        published_at_or_before=published_at_or_before,
    )
    return {
        "mode": "dry-run",
        "database_write": False,
        "file_write": False,
        "season": season,
        "report_date": report_date.isoformat(),
        "page_url": page_url,
        "collector_version": AVAILABILITY_DOCUMENT_COLLECTOR_VERSION,
        "published_at_or_before": (
            published_at_or_before.isoformat() if published_at_or_before else None
        ),
        "discovered_count": discovered_count,
        "downloaded_count": len(downloaded),
        "failure_count": len(failures),
        "documents": [_report_metadata(report) for report in downloaded],
        "failures": failures,
    }


def _apply(
    provider: OfficialInjuryReportProvider,
    *,
    season: str,
    report_date: date,
    page_url: str,
    max_documents: int,
    archive_root: Path,
    published_at_or_before: Optional[datetime],
) -> Dict[str, object]:
    from app.services.ingestion_run_service import IngestionRunTracker

    run_details = {
        "page_url": page_url,
        "report_date": report_date.isoformat(),
        "max_documents": max_documents,
        "published_at_or_before": (
            published_at_or_before.isoformat() if published_at_or_before else None
        ),
        "archive_root": str(archive_root),
        "scope": "raw_documents_only",
    }
    with IngestionRunTracker(
        run_type="official_injury_report_documents",
        source="official_nba",
        season=season,
        target_date=report_date,
        provider="official.nba.com",
        calculation_version=AVAILABILITY_DOCUMENT_COLLECTOR_VERSION,
        details=run_details,
        lock_name=AVAILABILITY_DOCUMENT_LOCK_NAME,
    ) as tracker:
        downloaded, failures, discovered_count = _collect(
            provider,
            report_date=report_date,
            max_documents=max_documents,
            published_at_or_before=published_at_or_before,
        )
        batch = persist_downloaded_report_batch(
            downloaded,
            archive_root=archive_root,
            source_run_id=tracker.run_id,
        )
        terminal_status = "partial" if failures else "success"
        validation_status = "failed" if failures else "passed"
        finish_details = {
            **run_details,
            "discovered_count": discovered_count,
            "downloaded_count": len(downloaded),
            "failure_count": len(failures),
            "failures": failures,
            "document_ids": [result.document_id for result in batch.results],
        }
        tracker.finish(
            terminal_status,
            validation_status=validation_status,
            rows_read=discovered_count,
            rows_written=batch.rows_written,
            details=finish_details,
        )
    return {
        "mode": "apply",
        "run_id": tracker.run_id,
        "status": terminal_status,
        "season": season,
        "report_date": report_date.isoformat(),
        "page_url": page_url,
        "archive_root": str(archive_root),
        "discovered_count": discovered_count,
        "downloaded_count": len(downloaded),
        "rows_written": batch.rows_written,
        "failure_count": len(failures),
        "failures": failures,
        "documents": [result.document.to_dict() for result in batch.results],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        season, report_date, page_url = _validate_args(args)
        published_at_or_before = _parse_published_at_or_before(
            args.published_at_or_before
        )
        provider = OfficialInjuryReportProvider(
            page_url=page_url,
            timeout_seconds=args.timeout_seconds,
            download_transport=args.download_transport,
        )
        if args.dry_run:
            output = _dry_run(
                provider,
                season=season,
                report_date=report_date,
                page_url=page_url,
                max_documents=args.max_documents,
                published_at_or_before=published_at_or_before,
            )
        else:
            output = _apply(
                provider,
                season=season,
                report_date=report_date,
                page_url=page_url,
                max_documents=args.max_documents,
                archive_root=_archive_root(args),
                published_at_or_before=published_at_or_before,
            )
    except Exception as exc:
        print(f"Official injury-report collection failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1

    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 1 if output.get("failure_count") else 0


if __name__ == "__main__":
    raise SystemExit(main())
