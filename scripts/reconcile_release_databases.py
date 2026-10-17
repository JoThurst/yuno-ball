"""Read-only source/target reconciliation for a managed PostgreSQL cutover.

Connection URLs are read from environment variables and are never emitted.
The script performs no DDL or DML and exits non-zero when the snapshots differ
or either database violates the release invariants.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from typing import Any, Iterable

import psycopg2


TABLES = (
    "teams",
    "game_schedule",
    "team_game_stats",
    "gamelogs",
    "player_game_facts",
    "ingestion_runs",
    "ingestion_task_runs",
)
EASTERN_GAME_DATE_SQL = (
    "DATE((game_date AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York')"
)


def _scalar(cursor, query: str, parameters: tuple[Any, ...] = ()) -> Any:
    cursor.execute(query, parameters)
    return cursor.fetchone()[0]


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _representative_date_count(cursor, target_date: date) -> dict[str, int]:
    """Count a slate with the same Eastern-calendar contract as Daily."""
    cursor.execute(
        f"""SELECT COUNT(*), COUNT(DISTINCT game_id)
            FROM game_schedule
            WHERE {EASTERN_GAME_DATE_SQL} = %s""",
        (target_date,),
    )
    rows, games = cursor.fetchone()
    return {"rows": rows, "games": games}


def collect_snapshot(
    dsn: str,
    representative_dates: Iterable[date],
    release_seasons: Iterable[str],
) -> dict[str, Any]:
    """Collect a bounded release snapshot in a read-only transaction."""
    connection = psycopg2.connect(
        dsn,
        connect_timeout=5,
        options="-c statement_timeout=10000",
    )
    try:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor() as cursor:
            revision = _scalar(
                cursor,
                "SELECT version_num FROM alembic_version ORDER BY version_num LIMIT 1",
            )
            table_counts = {
                table: _scalar(cursor, f'SELECT COUNT(*) FROM "{table}"')
                for table in TABLES
            }
            duplicate_groups = {
                "game_schedule": _scalar(
                    cursor,
                    """SELECT COUNT(*) FROM (
                           SELECT game_id, team_id FROM game_schedule
                           GROUP BY game_id, team_id HAVING COUNT(*) > 1
                       ) AS duplicate_keys""",
                ),
                "team_game_stats": _scalar(
                    cursor,
                    """SELECT COUNT(*) FROM (
                           SELECT game_id, team_id FROM team_game_stats
                           GROUP BY game_id, team_id HAVING COUNT(*) > 1
                       ) AS duplicate_keys""",
                ),
                "gamelogs": _scalar(
                    cursor,
                    """SELECT COUNT(*) FROM (
                           SELECT player_id, game_id FROM gamelogs
                           GROUP BY player_id, game_id HAVING COUNT(*) > 1
                       ) AS duplicate_keys""",
                ),
            }
            seasons = tuple(release_seasons)
            pair_failures = {}
            release_season_counts = {}
            for table in ("game_schedule", "team_game_stats"):
                placeholders = ", ".join(["%s"] * len(seasons))
                pair_failures[table] = _scalar(
                    cursor,
                    f"""SELECT COUNT(*) FROM (
                            SELECT game_id FROM \"{table}\"
                            WHERE season IN ({placeholders})
                            GROUP BY game_id HAVING COUNT(*) <> 2
                        ) AS invalid_pairs""",
                    seasons,
                )
                release_season_counts[table] = _scalar(
                    cursor,
                    f'SELECT COUNT(*) FROM "{table}" WHERE season IN ({placeholders})',
                    seasons,
                )
            date_counts = {}
            for target_date in representative_dates:
                date_counts[target_date.isoformat()] = _representative_date_count(
                    cursor, target_date
                )
            cursor.execute(
                """SELECT run_id, season, target_date, finished_at, code_version
                   FROM ingestion_runs
                   WHERE run_type = 'daily_ingest'
                     AND status = 'success'
                     AND validation_status = 'passed'
                     AND NOT COALESCE((details ->> 'validate_only')::boolean, FALSE)
                     AND NOT COALESCE((details ->> 'fetch_only')::boolean, FALSE)
                     AND NOT COALESCE((details ->> 'calc_only')::boolean, FALSE)
                   ORDER BY finished_at DESC NULLS LAST
                   LIMIT 1"""
            )
            latest = cursor.fetchone()
            latest_ingest = (
                dict(
                    zip(
                        ("run_id", "season", "target_date", "finished_at", "code_version"),
                        (_json_value(value) for value in latest),
                    )
                )
                if latest
                else None
            )
        connection.rollback()
        return {
            "alembic_revision": revision,
            "table_counts": table_counts,
            "duplicate_groups": duplicate_groups,
            "pair_failures": pair_failures,
            "release_season_counts": release_season_counts,
            "release_seasons": list(seasons),
            "representative_dates": date_counts,
            "latest_validated_ingest": latest_ingest,
        }
    finally:
        connection.close()


def compare_snapshots(source: dict[str, Any], target: dict[str, Any]) -> list[str]:
    """Return stable, credential-free reconciliation failures."""
    failures = []
    for field in (
        "alembic_revision",
        "table_counts",
        "release_season_counts",
        "release_seasons",
        "representative_dates",
        "latest_validated_ingest",
    ):
        if source.get(field) != target.get(field):
            failures.append(f"source_target_mismatch:{field}")
    for side, snapshot in (("source", source), ("target", target)):
        for table, count in snapshot.get("duplicate_groups", {}).items():
            if count:
                failures.append(f"{side}:duplicate_groups:{table}")
        for table, count in snapshot.get("pair_failures", {}).items():
            if count:
                failures.append(f"{side}:pair_failures:{table}")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        action="append",
        default=[],
        type=date.fromisoformat,
        help="Representative slate date to reconcile; repeat for multiple dates.",
    )
    parser.add_argument(
        "--season",
        action="append",
        required=True,
        help="Supported beta season whose reciprocal game rows must be complete; repeat as needed.",
    )
    parser.add_argument(
        "--source-env",
        default="YUNOBALL_SOURCE_DATABASE_URL",
        help="Environment variable containing the source PostgreSQL URL.",
    )
    parser.add_argument(
        "--target-env",
        default="YUNOBALL_TARGET_DATABASE_URL",
        help="Environment variable containing the target PostgreSQL URL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dsn = os.getenv(args.source_env)
    target_dsn = os.getenv(args.target_env)
    if not source_dsn or not target_dsn:
        print(json.dumps({"ok": False, "error": "database_environment_missing"}))
        return 2
    try:
        source = collect_snapshot(source_dsn, args.date, args.season)
        target = collect_snapshot(target_dsn, args.date, args.season)
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "database_snapshot_failed",
                    "error_class": type(error).__name__,
                }
            )
        )
        return 2
    failures = compare_snapshots(source, target)
    print(
        json.dumps(
            {
                "ok": not failures,
                "failures": failures,
                "source": source,
                "target": target,
            },
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
