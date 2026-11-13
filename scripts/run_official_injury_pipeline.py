"""Collect and parse recent official injury PDFs, then reconcile exact identities.

The shared daily lock covers both phases so this scheduled writer cannot
overlap a daily ingestion run. Identity reconciliation then reacquires that lock.
Each phase keeps its own durable run record; pending identities remain explicit.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import engine  # noqa: E402
from app.services.ingestion_run_service import PIPELINE_LOCK_NAME  # noqa: E402
from app.utils.season_utils import get_current_season, normalize_season  # noqa: E402
from scripts.collect_official_injury_reports import main as collect_main  # noqa: E402
from scripts.parse_official_injury_reports import main as parse_main  # noqa: E402
from scripts.reconcile_official_availability_identities import main as reconcile_main  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--season")
    parser.add_argument("--report-date", help="Eastern report date, YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--retry-interval-hours", type=int, default=2)
    parser.add_argument("--freshness-threshold-hours", type=int, default=4)
    parser.add_argument("--parse-max-documents", type=int, default=1000)
    return parser


def unresolved_identity_count(start_date: date, end_date: date) -> int:
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        count = connection.execute(text("""SELECT (
            SELECT count(*)
            FROM availability_observations o
            JOIN availability_report_documents d ON d.document_id=o.report_document_id
            WHERE d.report_date BETWEEN :start AND :end
              AND (o.game_id IS NULL OR o.team_id IS NULL OR o.player_id IS NULL)
            ) + (
            SELECT count(*)
            FROM team_report_submission_status s
            JOIN availability_report_documents d ON d.document_id=s.report_document_id
            WHERE d.report_date BETWEEN :start AND :end
              AND (s.game_id IS NULL OR s.team_id IS NULL))"""),
            {"start": start_date, "end": end_date}).scalar_one()
        connection.rollback()
        return int(count)


def pending_parse_count(start_date: date, end_date: date) -> int:
    """A bounded parser batch must not certify an unfinished report window."""
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        count = connection.execute(text("""SELECT count(*)
            FROM availability_report_documents
            WHERE report_date BETWEEN :start AND :end
              AND (parse_status IS NULL OR parse_status <> 'parsed')"""),
            {"start": start_date, "end": end_date}).scalar_one()
        connection.rollback()
        return int(count)


def run_pipeline(args: argparse.Namespace) -> int:
    if not 0 <= args.lookback_days <= 7:
        raise ValueError("--lookback-days must be between 0 and 7")
    if not 1 <= args.parse_max_documents <= 5000:
        raise ValueError("--parse-max-documents must be between 1 and 5000")
    report_date = (
        date.fromisoformat(args.report_date)
        if args.report_date
        else datetime.now(ZoneInfo("America/New_York")).date()
    )
    season = normalize_season(args.season or get_current_season(report_date))
    start_date = report_date - timedelta(days=args.lookback_days)
    archive_root = Path(args.archive_root).resolve()
    if not archive_root.is_dir() or archive_root == PROJECT_ROOT or PROJECT_ROOT in archive_root.parents:
        raise ValueError("--archive-root must be an existing directory outside the repository")

    with engine.connect() as connection:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:lock_name))"),
                {"lock_name": PIPELINE_LOCK_NAME},
            ).scalar_one()
        )
        connection.commit()
        if not acquired:
            print("The shared daily ingestion lock is already held", file=sys.stderr)
            return 3
        try:
            collect_code = collect_main(
                [
                    "--apply", "--archive-root", str(archive_root),
                    "--season", season, "--report-date", report_date.isoformat(),
                    "--lookback-days", str(args.lookback_days),
                    "--retry-interval-hours", str(args.retry_interval_hours),
                    "--freshness-threshold-hours", str(args.freshness_threshold_hours),
                ]
            )
            # Parse already archived PDFs even if today's discovery failed.
            parse_code = parse_main(
                [
                    "--apply", "--season", season,
                    "--start-date", start_date.isoformat(),
                    "--end-date", report_date.isoformat(),
                    "--max-documents", str(args.parse_max_documents),
                ]
            )
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
                {"lock_name": PIPELINE_LOCK_NAME},
            )
            connection.commit()

    # Reacquire the daily lock through the existing identity command. A daily
    # writer may start between phases; in that case reconciliation fails safely
    # and the scheduler retries. Never nest the same session lock across owners.
    identity_code = reconcile_main([
        "--apply", "--resolve-player", "--season", season,
        "--from-date", start_date.isoformat(),
        "--to-date", (report_date + timedelta(days=1)).isoformat(),
    ])
    unresolved = unresolved_identity_count(start_date, report_date) if identity_code == 0 else None
    pending = pending_parse_count(start_date, report_date)
    print(json.dumps({
        "season": season,
        "report_date": report_date.isoformat(),
        "parse_start_date": start_date.isoformat(),
        "collector_exit": collect_code,
        "parser_exit": parse_code,
        "identity_exit": identity_code,
        "identity_unresolved_rows": unresolved,
        "pending_parse_documents": pending,
    }, sort_keys=True))
    return collect_code or parse_code or identity_code or (1 if unresolved or pending else 0)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_pipeline(args)
    except (OSError, ValueError) as exc:
        print(f"Official injury pipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
