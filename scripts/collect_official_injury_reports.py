"""Collect bounded official NBA injury-report PDF revisions."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
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
    discovered_report_from_attempt,
    persist_downloaded_report_and_mark_success,
    record_download_failure,
    select_due_downloads,
    summarize_download_queue,
    upsert_discovered_downloads,
    validate_archive_root,
)
from app.database import SessionLocal  # noqa: E402
from app.utils.fetch.official_injury_report_provider import (  # noqa: E402
    OfficialInjuryReportProvider,
    official_injury_report_page_url,
)
from app.utils.season_utils import get_current_season, normalize_season  # noqa: E402


MAX_ALLOWED_DOCUMENTS = 96
MAX_LOOKBACK_DAYS = 7


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


def build_report_dates(report_date: date, lookback_days: int) -> list[date]:
    """Return oldest-to-newest dates for a bounded workstation catch-up run."""
    if not 0 <= lookback_days <= MAX_LOOKBACK_DAYS:
        raise ValueError(
            f"lookback_days must be between 0 and {MAX_LOOKBACK_DAYS}"
        )
    return [
        report_date - timedelta(days=offset)
        for offset in range(lookback_days, -1, -1)
    ]


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
    report_dates: Sequence[date],
    max_documents: int,
    published_at_or_before: Optional[datetime] = None,
) -> tuple[list, list[Dict[str, str]], int]:
    downloaded = []
    failures: list[Dict[str, str]] = []
    discovered_count = 0
    for report_date in report_dates:
        discovered = provider.discover(report_date=report_date)
        eligible = [
            report
            for report in discovered
            if published_at_or_before is None
            or report.report_published_at <= published_at_or_before
        ]
        selected = eligible[-max_documents:]
        discovered_count += len(discovered)
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
    return downloaded, failures, discovered_count


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
        "--retry-interval-hours",
        type=int,
        default=2,
        help="Hours before a failed URL becomes eligible again (1-24; default 2)",
    )
    parser.add_argument(
        "--freshness-threshold-hours",
        type=int,
        default=4,
        help="Age at which a pending report emits an alert (1-48; default 4)",
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
        "--lookback-days",
        type=int,
        default=0,
        help=(
            "Also inspect this many prior Eastern report dates "
            f"(0-{MAX_LOOKBACK_DAYS}; default 0)"
        ),
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
    if not 1 <= args.retry_interval_hours <= 24:
        raise ValueError("--retry-interval-hours must be between 1 and 24")
    if not 1 <= args.freshness_threshold_hours <= 48:
        raise ValueError("--freshness-threshold-hours must be between 1 and 48")
    if not 0 <= args.lookback_days <= MAX_LOOKBACK_DAYS:
        raise ValueError(
            f"--lookback-days must be between 0 and {MAX_LOOKBACK_DAYS}"
        )
    season = normalize_season(args.season or get_current_season())
    report_date = _parse_report_date(args.report_date)
    page_url = args.page_url or official_injury_report_page_url(season)
    return season, report_date, page_url


def _dry_run(
    provider: OfficialInjuryReportProvider,
    *,
    season: str,
    report_date: date,
    lookback_days: int,
    page_url: str,
    max_documents: int,
    published_at_or_before: Optional[datetime],
) -> Dict[str, object]:
    downloaded, failures, discovered_count = _collect(
        provider,
        report_dates=build_report_dates(report_date, lookback_days),
        max_documents=max_documents,
        published_at_or_before=published_at_or_before,
    )
    return {
        "mode": "dry-run",
        "database_write": False,
        "file_write": False,
        "season": season,
        "report_date": report_date.isoformat(),
        "lookback_days": lookback_days,
        "report_dates": [
            item.isoformat() for item in build_report_dates(report_date, lookback_days)
        ],
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
    lookback_days: int,
    page_url: str,
    max_documents: int,
    archive_root: Path,
    published_at_or_before: Optional[datetime],
    retry_interval_hours: int,
    freshness_threshold_hours: int,
) -> Dict[str, object]:
    from app.services.ingestion_run_service import IngestionRunTracker

    run_details = {
        "page_url": page_url,
        "report_date": report_date.isoformat(),
        "lookback_days": lookback_days,
        "report_dates": [
            item.isoformat() for item in build_report_dates(report_date, lookback_days)
        ],
        "max_documents": max_documents,
        "published_at_or_before": (
            published_at_or_before.isoformat() if published_at_or_before else None
        ),
        "archive_root": str(archive_root),
        "scope": "raw_documents_only",
        "retry_interval_hours": retry_interval_hours,
        "freshness_threshold_hours": freshness_threshold_hours,
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
        report_dates = build_report_dates(report_date, lookback_days)
        attempted_at = datetime.now(timezone.utc)
        discovered_count = 0
        queued_count = 0
        due_reports = []
        with SessionLocal.begin() as db:
            for discovery_date in report_dates:
                discovered = provider.discover(report_date=discovery_date)
                eligible = [
                    report for report in discovered
                    if published_at_or_before is None
                    or report.report_published_at <= published_at_or_before
                ]
                discovered_count += len(discovered)
                queued_count += upsert_discovered_downloads(
                    eligible,
                    source_run_id=tracker.run_id,
                    discovered_at=attempted_at,
                    db=db,
                )
                due = select_due_downloads(
                    report_date=discovery_date,
                    attempted_at=attempted_at,
                    limit=max_documents,
                    db=db,
                )
                due_reports.extend(discovered_report_from_attempt(item) for item in due)

        downloaded = []
        failures: list[Dict[str, str]] = []
        rows_written = 0
        document_ids = []
        for report in due_reports:
            try:
                downloaded_report = provider.download(report)
                with SessionLocal.begin() as db:
                    result = persist_downloaded_report_and_mark_success(
                        downloaded_report,
                        archive_root=archive_root,
                        source_run_id=tracker.run_id,
                        db=db,
                    )
                downloaded.append(downloaded_report)
                rows_written += int(result.created)
                document_ids.append(result.document_id)
            except Exception as exc:
                with SessionLocal.begin() as db:
                    record_download_failure(
                        report.source_url,
                        source_run_id=tracker.run_id,
                        attempted_at=datetime.now(timezone.utc),
                        error=exc,
                        retry_interval=timedelta(hours=retry_interval_hours),
                        db=db,
                    )
                failures.append({
                    "source_url": report.source_url,
                    "error_class": type(exc).__name__,
                    "error_summary": str(exc)[:500],
                })
        with SessionLocal.begin() as db:
            queue_summaries = [
                summarize_download_queue(
                    report_date=discovery_date,
                    observed_at=datetime.now(timezone.utc),
                    freshness_threshold=timedelta(hours=freshness_threshold_hours),
                    db=db,
                )
                for discovery_date in report_dates
            ]
        queue_summary = type(queue_summaries[0])(
            pending_count=sum(item.pending_count for item in queue_summaries),
            due_count=sum(item.due_count for item in queue_summaries),
            overdue_count=sum(item.overdue_count for item in queue_summaries),
            oldest_pending_published_at=min(
                (
                    item.oldest_pending_published_at
                    for item in queue_summaries
                    if item.oldest_pending_published_at is not None
                ),
                default=None,
            ),
        )
        terminal_status = "partial" if failures or queue_summary.overdue_count else "success"
        validation_status = "failed" if terminal_status == "partial" else "passed"
        finish_details = {
            **run_details,
            "discovered_count": discovered_count,
            "downloaded_count": len(downloaded),
            "newly_queued_count": queued_count,
            "due_count": len(due_reports),
            "failure_count": len(failures),
            "pending_count": queue_summary.pending_count,
            "pending_due_count": queue_summary.due_count,
            "overdue_count": queue_summary.overdue_count,
            "oldest_pending_published_at": (
                queue_summary.oldest_pending_published_at.isoformat()
                if queue_summary.oldest_pending_published_at else None
            ),
            "failures": failures,
            "document_ids": document_ids,
        }
        tracker.finish(
            terminal_status,
            validation_status=validation_status,
            rows_read=discovered_count,
            rows_written=rows_written,
            details=finish_details,
        )
    return {
        "mode": "apply",
        "run_id": tracker.run_id,
        "status": terminal_status,
        "season": season,
        "report_date": report_date.isoformat(),
        "lookback_days": lookback_days,
        "report_dates": [item.isoformat() for item in report_dates],
        "page_url": page_url,
        "archive_root": str(archive_root),
        "discovered_count": discovered_count,
        "downloaded_count": len(downloaded),
        "newly_queued_count": queued_count,
        "due_count": len(due_reports),
        "rows_written": rows_written,
        "failure_count": len(failures),
        "pending_count": queue_summary.pending_count,
        "pending_due_count": queue_summary.due_count,
        "overdue_count": queue_summary.overdue_count,
        "oldest_pending_published_at": (
            queue_summary.oldest_pending_published_at.isoformat()
            if queue_summary.oldest_pending_published_at else None
        ),
        "failures": failures,
        "document_ids": document_ids,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        season, report_date, page_url = _validate_args(args)
        lookback_days = args.lookback_days
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
                lookback_days=lookback_days,
                page_url=page_url,
                max_documents=args.max_documents,
                published_at_or_before=published_at_or_before,
            )
        else:
            output = _apply(
                provider,
                season=season,
                report_date=report_date,
                lookback_days=lookback_days,
                page_url=page_url,
                max_documents=args.max_documents,
                archive_root=_archive_root(args),
                published_at_or_before=published_at_or_before,
                retry_interval_hours=args.retry_interval_hours,
                freshness_threshold_hours=args.freshness_threshold_hours,
            )
    except Exception as exc:
        print(f"Official injury-report collection failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1

    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 1 if output.get("failure_count") or output.get("overdue_count") else 0


if __name__ == "__main__":
    raise SystemExit(main())
