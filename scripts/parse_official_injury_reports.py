"""Parse archived official injury-report PDFs into source observations."""

from __future__ import annotations

import argparse
from datetime import date
import json
import logging
from pathlib import Path
import sys
from typing import Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.availability_report_document_sqlalchemy import (  # noqa: E402
    AvailabilityReportDocumentORM,
)
from app.services.availability_observation_service import (  # noqa: E402
    mark_report_document_parse_failed,
    persist_parsed_report_document,
)
from app.services.ingestion_run_service import IngestionRunTracker  # noqa: E402
from app.utils.parse.official_injury_report_parser import (  # noqa: E402
    PARSER_VERSION,
    parse_official_injury_report_pdf,
)
from app.utils.season_utils import normalize_season, season_end_year, season_start_year  # noqa: E402


MAX_DOCUMENTS = 5_000
logging.getLogger("pdfminer").setLevel(logging.WARNING)


def _season_bounds(season: str) -> tuple[date, date]:
    return date(season_start_year(season), 10, 1), date(season_end_year(season), 6, 30)


def _date(value: Optional[str], option: str, default: date) -> date:
    if value is None:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{option} must use YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse durable official NBA injury-report PDFs into source observations"
    )
    parser.add_argument("--season", required=True, help="Canonical NBA season, e.g. 2024-25")
    parser.add_argument("--start-date", help="Optional bounded report date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Optional bounded report date (YYYY-MM-DD)")
    parser.add_argument("--max-documents", type=int, default=500, help=f"Maximum documents in one run (1-{MAX_DOCUMENTS})")
    parser.add_argument("--reparse", action="store_true", help="Re-run the parser for already parsed documents")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Read and parse without database updates")
    mode.add_argument("--apply", action="store_true", help="Persist parsed observations and parse status")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        season = normalize_season(args.season)
        season_start, season_end = _season_bounds(season)
        start_date = _date(args.start_date, "--start-date", season_start)
        end_date = _date(args.end_date, "--end-date", season_end)
        if end_date < start_date:
            raise ValueError("--end-date cannot precede --start-date")
        if not 1 <= args.max_documents <= MAX_DOCUMENTS:
            raise ValueError(f"--max-documents must be between 1 and {MAX_DOCUMENTS}")

        with SessionLocal() as db:
            query = (
                db.query(AvailabilityReportDocumentORM)
                .filter(
                    AvailabilityReportDocumentORM.report_date >= start_date,
                    AvailabilityReportDocumentORM.report_date <= end_date,
                )
                .order_by(
                    AvailabilityReportDocumentORM.report_date,
                    AvailabilityReportDocumentORM.report_published_at,
                    AvailabilityReportDocumentORM.document_id,
                )
            )
            if not args.reparse:
                query = query.filter(
                    AvailabilityReportDocumentORM.parse_status != "parsed"
                )
            documents = query.limit(args.max_documents).all()

        details = {
            "season": season,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "selected_documents": len(documents),
            "reparse": args.reparse,
            "parser_version": PARSER_VERSION,
        }
        parsed_documents = 0
        failed_documents = []
        observations_seen = 0
        submissions_seen = 0
        rows_written = 0

        tracker = None
        if args.apply:
            tracker = IngestionRunTracker(
                run_type="official_injury_report_observation_parse",
                source="official_nba",
                season=season,
                target_date=end_date,
                provider="local_official_archive",
                calculation_version=PARSER_VERSION,
                details=details,
                lock_name="yunoball:official_injury_report_observations",
            )
            tracker.__enter__()

        try:
            for index, document in enumerate(documents, start=1):
                print(
                    f"Parsing {index}/{len(documents)}: {document.file_name}",
                    file=sys.stderr,
                    flush=True,
                )
                try:
                    parsed = parse_official_injury_report_pdf(document.raw_storage_locator)
                    if parsed.parse_status == "failed":
                        raise ValueError(
                            parsed.parse_error_summary or "Official report parse failed"
                        )
                    parsed_documents += 1
                    observations_seen += len(parsed.observations)
                    submissions_seen += len(parsed.team_submission_statuses)
                    if args.apply:
                        with SessionLocal.begin() as db:
                            current = (
                                db.query(AvailabilityReportDocumentORM)
                                .filter_by(document_id=document.document_id)
                                .one()
                            )
                            result = persist_parsed_report_document(
                                current,
                                parsed,
                                db=db,
                            )
                            rows_written += result.rows_written
                except Exception as exc:
                    failed_documents.append(
                        {
                            "document_id": document.document_id,
                            "source_url": document.source_url,
                            "error_class": type(exc).__name__,
                            "error_summary": str(exc)[:500],
                        }
                    )
                    if args.apply:
                        with SessionLocal.begin() as db:
                            current = (
                                db.query(AvailabilityReportDocumentORM)
                                .filter_by(document_id=document.document_id)
                                .one()
                            )
                            mark_report_document_parse_failed(current, exc, db=db)

            status = "partial" if failed_documents else "success"
            if tracker is not None:
                tracker.finish(
                    status,
                    validation_status="failed" if failed_documents else "passed",
                    rows_read=len(documents),
                    rows_written=rows_written,
                    details={
                        **details,
                        "parsed_documents": parsed_documents,
                        "failed_documents": failed_documents,
                        "observations_seen": observations_seen,
                        "team_submission_statuses_seen": submissions_seen,
                    },
                )
        finally:
            if tracker is not None:
                tracker.__exit__(None, None, None)

        output = {
            "mode": "apply" if args.apply else "dry-run",
            "database_write": bool(args.apply),
            "season": season,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "selected_documents": len(documents),
            "parsed_documents": parsed_documents,
            "failed_documents": failed_documents,
            "observations_seen": observations_seen,
            "team_submission_statuses_seen": submissions_seen,
            "rows_written": rows_written,
            "parser_version": PARSER_VERSION,
        }
        print(json.dumps(output, indent=2, sort_keys=True))
        return 1 if failed_documents else 0
    except Exception as exc:
        print(f"Official injury-report parsing failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
