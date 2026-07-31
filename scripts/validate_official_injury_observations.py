"""Read-only quality checks for official injury-document observations."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import engine  # noqa: E402
from app.utils.season_utils import normalize_season, season_end_year, season_start_year  # noqa: E402


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
        description="Validate official injury observations without changing the database"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
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

        params = {"start_date": start_date, "end_date": end_date}
        with engine.connect() as conn:
            documents = conn.execute(
                text("""
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE parse_status = 'parsed') AS parsed,
                           COUNT(*) FILTER (WHERE parse_status = 'failed') AS failed,
                           COUNT(*) FILTER (WHERE parse_status = 'not_parsed') AS not_parsed,
                           COUNT(DISTINCT report_date) AS report_dates,
                           COUNT(DISTINCT source_url) AS source_urls,
                           COUNT(DISTINCT raw_sha256) AS hashes,
                           COUNT(*) FILTER (
                               WHERE printed_report_published_at IS NOT NULL
                                 AND printed_report_published_at < report_published_at
                           ) AS printed_before_filename
                    FROM availability_report_documents
                    WHERE report_date BETWEEN :start_date AND :end_date
                """),
                params,
            ).mappings().one()
            observations = conn.execute(
                text("""
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE game_id IS NULL) AS unresolved_game,
                           COUNT(*) FILTER (WHERE team_id IS NULL) AS unresolved_team,
                           COUNT(*) FILTER (WHERE player_id IS NULL) AS unresolved_player,
                           COUNT(*) FILTER (WHERE o.source_url IS NULL OR o.raw_sha256 IS NULL) AS missing_lineage
                    FROM availability_observations o
                    JOIN availability_report_documents d
                      ON d.document_id = o.report_document_id
                    WHERE d.report_date BETWEEN :start_date AND :end_date
                """),
                params,
            ).mappings().one()
            submissions = conn.execute(
                text("""
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE submission_status = 'NOT YET SUBMITTED') AS explicit_not_submitted
                    FROM team_report_submission_status s
                    JOIN availability_report_documents d
                      ON d.document_id = s.report_document_id
                    WHERE d.report_date BETWEEN :start_date AND :end_date
                """),
                params,
            ).mappings().one()
            duplicate_parse_rows = conn.execute(
                text("""
                    SELECT COUNT(*) FROM (
                        SELECT o.report_document_id, o.parser_version, o.source_row_key
                        FROM availability_observations o
                        JOIN availability_report_documents d
                          ON d.document_id = o.report_document_id
                        WHERE d.report_date BETWEEN :start_date AND :end_date
                        GROUP BY o.report_document_id, o.parser_version, o.source_row_key
                        HAVING COUNT(*) > 1
                    ) duplicates
                """),
                params,
            ).scalar_one()
            duplicate_submissions = conn.execute(
                text("""
                    SELECT COUNT(*) FROM (
                        SELECT s.report_document_id, s.parser_version, s.source_row_key
                        FROM team_report_submission_status s
                        JOIN availability_report_documents d
                          ON d.document_id = s.report_document_id
                        WHERE d.report_date BETWEEN :start_date AND :end_date
                        GROUP BY s.report_document_id, s.parser_version, s.source_row_key
                        HAVING COUNT(*) > 1
                    ) duplicates
                """),
                params,
            ).scalar_one()
            timestamp_mismatches = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM availability_observations o
                    JOIN availability_report_documents d
                      ON d.document_id = o.report_document_id
                    WHERE d.report_date BETWEEN :start_date AND :end_date
                      AND o.report_published_at IS DISTINCT FROM
                          COALESCE(d.printed_report_published_at, d.report_published_at)
                """),
                params,
            ).scalar_one()
            revised_urls = conn.execute(
                text("""
                    SELECT COUNT(*) FROM (
                        SELECT source_url
                        FROM availability_report_documents
                        WHERE report_date BETWEEN :start_date AND :end_date
                        GROUP BY source_url
                        HAVING COUNT(DISTINCT raw_sha256) > 1
                    ) revised
                """),
                params,
            ).scalar_one()
            rerun_zero_write_runs = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM ingestion_runs
                    WHERE run_type = 'official_injury_report_observation_parse'
                      AND status = 'success'
                      AND rows_written = 0
                      AND season = :season
                """),
                {"season": season},
            ).scalar_one()
            observed_dates = {
                row[0]
                for row in conn.execute(
                    text("""
                        SELECT DISTINCT report_date
                        FROM availability_report_documents
                        WHERE report_date BETWEEN :start_date AND :end_date
                    """),
                    params,
                ).all()
            }
            expected_dates = {
                row[0]
                for row in conn.execute(
                    text("""
                        SELECT DISTINCT
                            (((game_date AT TIME ZONE 'UTC')
                              AT TIME ZONE 'America/New_York')::date) AS local_date
                        FROM game_schedule
                        WHERE (((game_date AT TIME ZONE 'UTC')
                                AT TIME ZONE 'America/New_York')::date)
                              BETWEEN :start_date AND :end_date
                          AND season = :season
                          AND season_type IN ('Regular Season', 'Playoffs', 'Play-In', 'NBA Cup')
                    """),
                    {
                        "start_date": start_date,
                        "end_date": end_date,
                        "season": season,
                    },
                ).all()
            }

        missing_dates = sorted(str(value) for value in expected_dates - observed_dates)
        checks = {
            "duplicate_parse_rows": int(duplicate_parse_rows),
            "duplicate_submission_rows": int(duplicate_submissions),
            "parse_failures": int(documents["failed"]),
            "printed_before_filename": int(documents["printed_before_filename"]),
            "timestamp_mismatches": int(timestamp_mismatches),
            "missing_lineage": int(observations["missing_lineage"]),
            "missing_report_dates": len(missing_dates),
            "revision_url_count": int(revised_urls),
            "rerun_zero_write_runs": int(rerun_zero_write_runs),
        }
        output = {
            "season": season,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "documents": dict(documents),
            "observations": dict(observations),
            "team_submission_statuses": dict(submissions),
            "checks": checks,
            "missing_report_dates": missing_dates[:100],
            "missing_report_dates_truncated": len(missing_dates) > 100,
            "status": "pass" if all(
                checks[key] == 0
                for key in (
                    "duplicate_parse_rows",
                    "duplicate_submission_rows",
                    "parse_failures",
                    "timestamp_mismatches",
                    "missing_lineage",
                )
            ) else "fail",
        }
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        return 0 if output["status"] == "pass" else 1
    except Exception as exc:
        print(f"Official injury observation validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
