"""Probe bounded official NBA injury-report CDN candidates and retain valid PDFs."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.availability_report_document_service import (  # noqa: E402
    AVAILABILITY_DOCUMENT_COLLECTOR_VERSION,
    AVAILABILITY_DOCUMENT_LOCK_NAME,
    persist_downloaded_report_and_mark_success,
    upsert_discovered_downloads,
    validate_archive_root,
)
from app.services.ingestion_run_service import IngestionRunTracker  # noqa: E402
from app.utils.fetch.official_injury_report_provider import (  # noqa: E402
    OfficialInjuryReportNotFound,
    OfficialInjuryReportProvider,
    official_injury_report_page_url,
    official_injury_report_url,
    parse_official_injury_report_url,
)
from app.utils.season_utils import get_current_season, normalize_season  # noqa: E402


MAX_DATES = 31
MAX_CANDIDATES = 1488
EASTERN = ZoneInfo("America/New_York")


def _iso_date(raw: str, option: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{option} must use YYYY-MM-DD") from exc


def _clock(raw: str, option: str) -> time:
    try:
        return time.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{option} must use HH:MM") from exc


def build_candidates(
    *, start_date: date, end_date: date, start_time: time, end_time: time,
    interval_minutes: int,
):
    """Build deterministic official filename candidates in Eastern time."""
    if end_date < start_date:
        raise ValueError("--end-date cannot precede --start-date")
    if end_time < start_time:
        raise ValueError("--end-time cannot precede --start-time")
    candidates = []
    current_date = start_date
    while current_date <= end_date:
        current = datetime.combine(current_date, start_time, tzinfo=EASTERN)
        final = datetime.combine(current_date, end_time, tzinfo=EASTERN)
        while current <= final:
            report = parse_official_injury_report_url(
                official_injury_report_url(current)
            )
            if report is None:  # defensive; generated URLs must satisfy the contract
                raise RuntimeError("Generated official injury-report URL was invalid")
            candidates.append(report)
            current += timedelta(minutes=interval_minutes)
        current_date += timedelta(days=1)
    return candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill valid official NBA injury-report PDFs from bounded CDN filename candidates"
    )
    parser.add_argument("--start-date", required=True, help="First Eastern date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Last Eastern date (YYYY-MM-DD)")
    parser.add_argument("--start-time", default="12:00", help="First Eastern candidate time (HH:MM)")
    parser.add_argument("--end-time", default="23:45", help="Last Eastern candidate time (HH:MM)")
    parser.add_argument("--interval-minutes", type=int, choices=(15, 30, 60), default=15)
    parser.add_argument("--max-dates", type=int, default=7, help=f"Safety limit (1-{MAX_DATES})")
    parser.add_argument("--season", help="Canonical NBA season; defaults through shared season selection")
    parser.add_argument("--archive-root", help="Durable root outside the repository")
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--download-transport", choices=("auto", "curl", "requests"), default="curl")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="List candidates only; no network or writes")
    mode.add_argument("--apply", action="store_true", help="Probe candidates and persist validated PDFs")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        start_date = _iso_date(args.start_date, "--start-date")
        end_date = _iso_date(args.end_date, "--end-date")
        date_count = (end_date - start_date).days + 1
        if not 1 <= args.max_dates <= MAX_DATES:
            raise ValueError(f"--max-dates must be between 1 and {MAX_DATES}")
        if date_count > args.max_dates:
            raise ValueError(
                f"Date range contains {date_count} dates; split it or raise --max-dates (maximum {MAX_DATES})"
            )
        if not 5 <= args.timeout_seconds <= 120:
            raise ValueError("--timeout-seconds must be between 5 and 120")
        season = normalize_season(args.season or get_current_season())
        candidates = build_candidates(
            start_date=start_date,
            end_date=end_date,
            start_time=_clock(args.start_time, "--start-time"),
            end_time=_clock(args.end_time, "--end-time"),
            interval_minutes=args.interval_minutes,
        )
        if len(candidates) > MAX_CANDIDATES:
            raise ValueError(f"Candidate count exceeds safety maximum {MAX_CANDIDATES}")
        if args.dry_run:
            print(json.dumps({
                "mode": "dry-run",
                "network_access": False,
                "database_write": False,
                "file_write": False,
                "season": season,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "candidate_count": len(candidates),
                "first_candidate": candidates[0].source_url if candidates else None,
                "last_candidate": candidates[-1].source_url if candidates else None,
            }, indent=2, sort_keys=True))
            return 0

        archive_root = validate_archive_root(
            args.archive_root or os.getenv("YUNOBALL_INJURY_REPORT_ARCHIVE_DIR", "")
        )
        provider = OfficialInjuryReportProvider(
            page_url=official_injury_report_page_url(season),
            timeout_seconds=args.timeout_seconds,
            download_transport=args.download_transport,
        )
        details = {
            "scope": "bounded_historical_filename_probe",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "candidate_count": len(candidates),
            "interval_minutes": args.interval_minutes,
        }
        found = []
        transient_failures = []
        not_found_count = 0
        rows_written = 0
        with IngestionRunTracker(
            run_type="official_injury_report_historical_backfill",
            source="official_nba",
            season=season,
            target_date=end_date,
            provider="ak-static.cms.nba.com",
            calculation_version=AVAILABILITY_DOCUMENT_COLLECTOR_VERSION,
            details=details,
            lock_name=AVAILABILITY_DOCUMENT_LOCK_NAME,
        ) as tracker:
            for candidate in candidates:
                try:
                    downloaded = provider.download(candidate)
                except OfficialInjuryReportNotFound:
                    not_found_count += 1
                    continue
                except Exception as exc:
                    transient_failures.append({
                        "source_url": candidate.source_url,
                        "error_class": type(exc).__name__,
                        "error_summary": str(exc)[:500],
                    })
                    continue
                with SessionLocal.begin() as db:
                    upsert_discovered_downloads(
                        [candidate], source_run_id=tracker.run_id,
                        discovered_at=datetime.now(timezone.utc), db=db,
                    )
                    result = persist_downloaded_report_and_mark_success(
                        downloaded, archive_root=archive_root,
                        source_run_id=tracker.run_id, db=db,
                    )
                rows_written += int(result.created)
                found.append(result.document_id)
            status = "partial" if transient_failures else "success"
            finish_details = {
                **details,
                "confirmed_not_found_count": not_found_count,
                "downloaded_count": len(found),
                "transient_failure_count": len(transient_failures),
                "transient_failures": transient_failures,
                "document_ids": found,
            }
            tracker.finish(
                status,
                validation_status="failed" if transient_failures else "passed",
                rows_read=len(candidates),
                rows_written=rows_written,
                details=finish_details,
            )
        output = {
            "mode": "apply",
            "run_id": tracker.run_id,
            "status": status,
            "candidate_count": len(candidates),
            "confirmed_not_found_count": not_found_count,
            "downloaded_count": len(found),
            "rows_written": rows_written,
            "transient_failure_count": len(transient_failures),
            "document_ids": found,
        }
        print(json.dumps(output, indent=2, sort_keys=True))
        return 1 if transient_failures else 0
    except Exception as exc:
        print(f"Official injury-report historical backfill failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1


if __name__ == "__main__":
    raise SystemExit(main())
