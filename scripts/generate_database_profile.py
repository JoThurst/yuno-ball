"""
Generate sanitized database and metric catalogs for evaluation.

Produces (under docs/ by default):
  - DATABASE_PROFILE.md  — live schema + data-quality snapshot (read-only DB)
  - SOURCE_CATALOG.md    — curated ingestion source inventory
  - METRIC_CATALOG.md    — curated Yuno metric definitions

Safety:
  - Every DB session is READ ONLY (PostgreSQL default_transaction_read_only /
    SET TRANSACTION READ ONLY). No writes, DDL, or commits of mutations.
  - Credentials and connection strings are never written to output.

Usage:
    venv\\Scripts\\activate
    python scripts/generate_database_profile.py
    python scripts/generate_database_profile.py --out-dir docs
    python scripts/generate_database_profile.py --skip-catalogs
    python scripts/generate_database_profile.py --profile-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "psycopg2 is required. Activate the project venv and install dependencies."
    ) from exc


# ---------------------------------------------------------------------------
# Configuration: tables / columns used for quality checks
# ---------------------------------------------------------------------------

CORE_FACT_TABLES = (
    "game_schedule",
    "gamelogs",
    "team_game_stats",
    "leaguedashplayerstats",
    "league_dash_team_stats",
    "roster",
)

SNAPSHOT_TABLES = (
    "player_consecutive_streak_snapshots",
    "player_stat_window_snapshots",
    "player_heat_index_snapshots",
    "player_consistency_snapshots",
    "team_game_feature_snapshots",
    "game_environment_snapshots",
)

SEASON_COLUMN_CANDIDATES = (
    "season",
    "season_year",
)

TEAM_COLUMN_CANDIDATES = (
    "team_id",
)

IMPORTANT_NULL_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "game_schedule": (
        "game_id",
        "team_id",
        "opponent_team_id",
        "season",
        "game_date",
        "home_or_away",
        "result",
        "score",
    ),
    "gamelogs": (
        "player_id",
        "game_id",
        "team_id",
        "season",
        "points",
        "rebounds",
        "assists",
        "minutes_played",
    ),
    "team_game_stats": (
        "game_id",
        "team_id",
        "opponent_team_id",
        "season",
        "game_date",
        "pts",
        "plus_minus",
        "fg_pct",
        "reb",
        "ast",
    ),
    "players": ("player_id", "name", "position", "available_seasons"),
    "teams": ("team_id", "name", "abbreviation"),
    "roster": ("team_id", "player_id", "season", "player_name", "position"),
    "leaguedashplayerstats": (
        "player_id",
        "season",
        "team_id",
        "gp",
        "pts",
        "min",
    ),
    "league_dash_team_stats": (
        "team_id",
        "season",
        "season_type",
        "team_name",
    ),
    "game_odds": (
        "game_id",
        "game_date",
        "home_ml_odds",
        "away_ml_odds",
        "home_spread",
        "recorded_at",
    ),
    "player_game_status": (
        "game_id",
        "player_id",
        "team_id",
        "status",
        "played",
        "not_playing_reason",
    ),
    "player_heat_index": ("player_id", "stat", "season", "z_score", "status"),
    "player_consistency": ("player_id", "season", "stat_name", "cv", "consistency_tier"),
    "team_daily_metrics": ("stat_date", "team_id", "window_size", "net_rtg_season", "net_rtg_l10"),
    "team_schedule_factors": ("game_id", "team_id", "days_rest", "is_b2b"),
    "team_game_feature_snapshots": (
        "game_id",
        "team_id",
        "opponent_team_id",
        "season",
        "feature_as_of",
        "calculation_version",
        "completeness_status",
        "season_games_played",
        "season_games_used",
    ),
    "game_environment_snapshots": (
        "game_id",
        "home_team_id",
        "away_team_id",
        "season",
        "feature_as_of",
        "calculation_version",
        "completeness_status",
    ),
}

# Child -> (parent_table, child_cols, parent_cols)
ORPHAN_CHECKS: Tuple[Dict[str, Any], ...] = (
    {
        "name": "gamelogs missing schedule row",
        "child": "gamelogs",
        "parent": "game_schedule",
        "child_cols": ("game_id", "team_id"),
        "parent_cols": ("game_id", "team_id"),
    },
    {
        "name": "team_game_stats missing schedule row",
        "child": "team_game_stats",
        "parent": "game_schedule",
        "child_cols": ("game_id", "team_id"),
        "parent_cols": ("game_id", "team_id"),
    },
    {
        "name": "team feature snapshot missing schedule row",
        "child": "team_game_feature_snapshots",
        "parent": "game_schedule",
        "child_cols": ("game_id", "team_id"),
        "parent_cols": ("game_id", "team_id"),
    },
    {
        "name": "game environment snapshot missing home schedule row",
        "child": "game_environment_snapshots",
        "parent": "game_schedule",
        "child_cols": ("game_id", "home_team_id"),
        "parent_cols": ("game_id", "team_id"),
    },
    {
        "name": "game environment snapshot missing away schedule row",
        "child": "game_environment_snapshots",
        "parent": "game_schedule",
        "child_cols": ("game_id", "away_team_id"),
        "parent_cols": ("game_id", "team_id"),
    },
    {
        "name": "roster missing player",
        "child": "roster",
        "parent": "players",
        "child_cols": ("player_id",),
        "parent_cols": ("player_id",),
    },
    {
        "name": "roster missing team",
        "child": "roster",
        "parent": "teams",
        "child_cols": ("team_id",),
        "parent_cols": ("team_id",),
    },
    {
        "name": "gamelogs missing player",
        "child": "gamelogs",
        "parent": "players",
        "child_cols": ("player_id",),
        "parent_cols": ("player_id",),
    },
    {
        "name": "statistics missing player",
        "child": "statistics",
        "parent": "players",
        "child_cols": ("player_id",),
        "parent_cols": ("player_id",),
    },
    {
        "name": "player_game_status missing player",
        "child": "player_game_status",
        "parent": "players",
        "child_cols": ("player_id",),
        "parent_cols": ("player_id",),
    },
    {
        "name": "game_odds missing known schedule game",
        "child": "game_odds",
        "parent": "game_schedule",
        "child_cols": ("game_id",),
        "parent_cols": ("game_id",),
    },
)

TWO_ROW_TABLES = ("game_schedule", "team_game_stats")

DERIVED_DATE_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "team_daily_metrics": ("stat_date",),
    "team_daily_flags": ("stat_date",),
    "game_environment_daily": ("game_date",),
    "team_schedule_factors": ("game_date", "created_at"),
    "player_heat_index": ("created_at",),
    "player_consistency": ("created_at",),
    "player_consecutive_streaks": ("created_at",),
    "player_stat_windows": ("created_at",),
    "player_streaks": ("created_at",),
    "game_odds": ("game_date", "recorded_at"),
    "player_game_status": ("game_date", "recorded_at"),
    "player_consecutive_streak_snapshots": ("feature_as_of", "data_available_at"),
    "player_stat_window_snapshots": ("feature_as_of", "data_available_at"),
    "player_heat_index_snapshots": ("feature_as_of", "data_available_at"),
    "player_consistency_snapshots": ("feature_as_of", "data_available_at"),
    "team_game_feature_snapshots": ("feature_as_of", "data_available_at"),
    "game_environment_snapshots": ("feature_as_of", "data_available_at"),
}

CANDIDATE_KEY_CHECKS: Dict[str, Tuple[str, ...]] = {
    "game_schedule": ("game_id", "team_id"),
    "gamelogs": ("player_id", "game_id"),
    "team_game_stats": ("game_id", "team_id"),
    "roster": ("team_id", "player_id", "season"),
    "leaguedashplayerstats": ("player_id", "season"),
    "league_dash_team_stats": ("team_id", "season", "season_type"),
    "statistics": ("player_id", "season_year"),
    "player_streaks": ("player_id", "stat", "season", "threshold"),
    "player_heat_index": ("player_id", "stat", "season", "window_size"),
    "player_consistency": ("player_id", "season", "stat_name", "window_size"),
    "team_daily_metrics": ("stat_date", "team_id", "window_size"),
    "team_daily_flags": ("stat_date", "team_id", "flag_type"),
    "team_schedule_factors": ("game_id", "team_id"),
    "game_odds": ("game_id", "sportsbook_id"),
    "player_game_status": ("game_id", "player_id"),
    "game_environment_daily": ("game_id", "game_date"),
    "player_consecutive_streak_snapshots": (
        "player_id", "stat", "threshold", "season", "season_type",
        "feature_as_of", "calculation_version", "streak_kind",
    ),
    "player_stat_window_snapshots": (
        "player_id", "stat", "threshold", "season", "season_type",
        "window_size", "feature_as_of", "calculation_version",
    ),
    "player_heat_index_snapshots": (
        "player_id", "stat", "season", "season_type", "window_size",
        "feature_as_of", "calculation_version",
    ),
    "player_consistency_snapshots": (
        "player_id", "season", "season_type", "stat_name", "window_size",
        "feature_as_of", "calculation_version",
    ),
    "team_game_feature_snapshots": (
        "game_id", "team_id", "window_size", "feature_as_of", "calculation_version",
    ),
    "game_environment_snapshots": (
        "game_id", "window_size", "feature_as_of", "calculation_version",
    ),
}

# Tables excluded from profile noise (auth / alembic bookkeeping still listed in schema)
SANITIZE_SKIP_ROW_DETAIL = frozenset({"users", "alembic_version"})


# ---------------------------------------------------------------------------
# DB helpers (read-only)
# ---------------------------------------------------------------------------


def _redact_database_url(url: str) -> str:
    """Return a non-sensitive fingerprint of the connection target."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "unknown-host"
        db = (parsed.path or "/").lstrip("/") or "unknown-db"
        host_hash = hashlib.sha256(host.encode("utf-8")).hexdigest()[:10]
        return f"postgresql://***@{host_hash}…/{db} (host redacted)"
    except Exception:
        return "postgresql://*** (unparseable; redacted)"


def connect_readonly(database_url: str):
    """Open a PostgreSQL connection forced into read-only mode."""
    if "neon.tech" in database_url and "sslmode=" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{sep}sslmode=require"

    conn = psycopg2.connect(database_url)
    # Session-level read-only: blocks INSERT/UPDATE/DELETE/DDL for this connection.
    conn.set_session(readonly=True, autocommit=False)
    with conn.cursor() as cur:
        cur.execute("SET default_transaction_read_only = on")
        cur.execute("SET search_path TO public, nba, mlb")
        cur.execute("SET statement_timeout = '120s'")
    conn.commit()  # only persists session GUCs; no data mutation
    return conn


def fetchall(conn, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(sql, params or ())
        rows = cur.fetchall()
    conn.commit()  # end read-only txn cleanly
    return [dict(r) for r in rows]


def fetchone(conn, sql: str, params: Optional[Sequence[Any]] = None) -> Optional[Dict[str, Any]]:
    rows = fetchall(conn, sql, params)
    return rows[0] if rows else None


def fetch_scalar(conn, sql: str, params: Optional[Sequence[Any]] = None) -> Any:
    row = fetchone(conn, sql, params)
    if not row:
        return None
    return next(iter(row.values()))


def table_exists(conn, table: str) -> bool:
    return bool(
        fetch_scalar(
            conn,
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
    )


def column_exists(conn, table: str, column: str) -> bool:
    return bool(
        fetch_scalar(
            conn,
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            (table, column),
        )
    )


def identify_season_column(conn, table: str) -> Optional[str]:
    for col in SEASON_COLUMN_CANDIDATES:
        if column_exists(conn, table, col):
            return col
    return None


def identify_team_column(conn, table: str) -> Optional[str]:
    for col in TEAM_COLUMN_CANDIDATES:
        if column_exists(conn, table, col):
            return col
    return None


def quote_ident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Refusing unsafe SQL identifier: {name!r}")
    return f'"{name}"'


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------


def collect_tables(conn) -> List[str]:
    rows = fetchall(
        conn,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
    )
    return [r["table_name"] for r in rows]


def collect_columns(conn) -> Dict[str, List[Dict[str, Any]]]:
    rows = fetchall(
        conn,
        """
        SELECT table_name, column_name, data_type, udt_name, is_nullable,
               column_default, character_maximum_length, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """,
    )
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r["table_name"]].append(r)
    return out


def collect_constraints(conn) -> Dict[str, List[Dict[str, Any]]]:
    rows = fetchall(
        conn,
        """
        SELECT
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns,
            max(fk_kcu.table_name) AS foreign_table,
            string_agg(
                fk_kcu.column_name,
                ', ' ORDER BY kcu.ordinal_position
            ) FILTER (WHERE fk_kcu.column_name IS NOT NULL) AS foreign_columns
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.referential_constraints rc
          ON rc.constraint_name = tc.constraint_name
         AND rc.constraint_schema = tc.table_schema
        LEFT JOIN information_schema.key_column_usage fk_kcu
          ON fk_kcu.constraint_name = rc.unique_constraint_name
         AND fk_kcu.constraint_schema = rc.unique_constraint_schema
         AND fk_kcu.ordinal_position = kcu.position_in_unique_constraint
        WHERE tc.table_schema = 'public'
        GROUP BY tc.table_name, tc.constraint_name, tc.constraint_type
        ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
        """,
    )
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r["table_name"]].append(r)
    return out


def collect_indexes(conn) -> Dict[str, List[Dict[str, Any]]]:
    rows = fetchall(
        conn,
        """
        SELECT
            tablename AS table_name,
            indexname AS index_name,
            indexdef AS index_def
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
        """,
    )
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        out[r["table_name"]].append(r)
    return out


def collect_alembic(conn, alembic_versions_dir: Path) -> Dict[str, Any]:
    current = None
    if table_exists(conn, "alembic_version"):
        current = fetch_scalar(conn, "SELECT version_num FROM alembic_version LIMIT 1")

    heads: List[str] = []
    revisions: Dict[str, Optional[str]] = {}
    if alembic_versions_dir.exists():
        for path in alembic_versions_dir.glob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            rev_m = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
            down_m = re.search(r"^down_revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
            if not down_m:
                down_m = re.search(r"^down_revision\s*=\s*None", text, re.M)
                down = None if down_m else None
            else:
                down = down_m.group(1)
            if rev_m:
                revisions[rev_m.group(1)] = down

        children = set(revisions.keys())
        parents = {p for p in revisions.values() if p}
        heads = sorted(children - parents)

    return {
        "current_revision": current,
        "head_revisions": heads,
        "in_sync": bool(current) and current in heads and len(heads) == 1,
        "revision_count": len(revisions),
    }


# ---------------------------------------------------------------------------
# Data quality probes
# ---------------------------------------------------------------------------


def row_counts(conn, tables: Sequence[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for table in tables:
        t = quote_ident(table)
        counts[table] = int(fetch_scalar(conn, f"SELECT COUNT(*) AS c FROM {t}") or 0)
    return counts


def counts_by_season(conn, tables: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for table in tables:
        if not table_exists(conn, table):
            continue
        season_col = identify_season_column(conn, table)
        if not season_col:
            continue
        t = quote_ident(table)
        c = quote_ident(season_col)
        rows = fetchall(
            conn,
            f"""
            SELECT {c} AS season, COUNT(*) AS row_count
            FROM {t}
            GROUP BY {c}
            ORDER BY {c}
            """,
        )
        result[table] = rows
    return result


def counts_by_season_team(conn, tables: Sequence[str], limit_per_table: int = 200) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for table in tables:
        if not table_exists(conn, table):
            continue
        season_col = identify_season_column(conn, table)
        team_col = identify_team_column(conn, table)
        if not season_col or not team_col:
            continue
        t = quote_ident(table)
        s = quote_ident(season_col)
        tm = quote_ident(team_col)
        rows = fetchall(
            conn,
            f"""
            SELECT {s} AS season, {tm} AS team_id, COUNT(*) AS row_count
            FROM {t}
            GROUP BY {s}, {tm}
            ORDER BY {s}, row_count DESC
            LIMIT %s
            """,
            (limit_per_table,),
        )
        result[table] = rows
    return result


def game_date_bounds(conn) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if table_exists(conn, "game_schedule") and column_exists(conn, "game_schedule", "game_date"):
        row = fetchone(
            conn,
            """
            SELECT MIN(game_date) AS min_game_date,
                   MAX(game_date) AS max_game_date,
                   MIN(game_date) FILTER (WHERE result IS NOT NULL) AS min_completed_date,
                   MAX(game_date) FILTER (WHERE result IS NOT NULL) AS max_completed_date
            FROM game_schedule
            """,
        )
        out["game_schedule"] = row
    if table_exists(conn, "team_game_stats") and column_exists(conn, "team_game_stats", "game_date"):
        row = fetchone(
            conn,
            """
            SELECT MIN(game_date) AS min_game_date,
                   MAX(game_date) AS max_game_date
            FROM team_game_stats
            """,
        )
        out["team_game_stats"] = row
    return out


def null_rates(conn) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for table, cols in IMPORTANT_NULL_COLUMNS.items():
        if not table_exists(conn, table):
            continue
        t = quote_ident(table)
        total = int(fetch_scalar(conn, f"SELECT COUNT(*) FROM {t}") or 0)
        col_stats: List[Dict[str, Any]] = []
        for col in cols:
            if not column_exists(conn, table, col):
                continue
            c = quote_ident(col)
            nulls = int(
                fetch_scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE {c} IS NULL") or 0
            )
            rate = (nulls / total) if total else 0.0
            col_stats.append(
                {
                    "column": col,
                    "nulls": nulls,
                    "total": total,
                    "null_rate": round(rate, 4),
                }
            )
        result[table] = col_stats
    return result


def duplicate_keys(conn) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for table, cols in CANDIDATE_KEY_CHECKS.items():
        if not table_exists(conn, table):
            continue
        if not all(column_exists(conn, table, c) for c in cols):
            continue
        t = quote_ident(table)
        col_sql = ", ".join(quote_ident(c) for c in cols)
        row = fetchone(
            conn,
            f"""
            SELECT COUNT(*) AS duplicate_groups,
                   COALESCE(SUM(cnt - 1), 0) AS extra_rows
            FROM (
                SELECT {col_sql}, COUNT(*) AS cnt
                FROM {t}
                GROUP BY {col_sql}
                HAVING COUNT(*) > 1
            ) d
            """,
        )
        result[table] = {
            "columns": list(cols),
            "duplicate_groups": int(row["duplicate_groups"] or 0) if row else 0,
            "extra_rows": int(row["extra_rows"] or 0) if row else 0,
        }
    return result


def orphan_counts(conn) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for check in ORPHAN_CHECKS:
        child = check["child"]
        parent = check["parent"]
        if not table_exists(conn, child) or not table_exists(conn, parent):
            continue
        child_cols = check["child_cols"]
        parent_cols = check["parent_cols"]
        if not all(column_exists(conn, child, c) for c in child_cols):
            continue
        if not all(column_exists(conn, parent, c) for c in parent_cols):
            continue
        ct = quote_ident(child)
        pt = quote_ident(parent)
        on_clause = " AND ".join(
            f"c.{quote_ident(cc)} = p.{quote_ident(pc)}"
            for cc, pc in zip(child_cols, parent_cols)
        )
        null_guard = " OR ".join(f"c.{quote_ident(cc)} IS NULL" for cc in child_cols)
        count = fetch_scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM {ct} c
            LEFT JOIN {pt} p ON {on_clause}
            WHERE p.{quote_ident(parent_cols[0])} IS NULL
              AND NOT ({null_guard})
            """,
        )
        results.append(
            {
                "name": check["name"],
                "child": child,
                "parent": parent,
                "orphan_rows": int(count or 0),
            }
        )
    return results


def two_row_failures(conn) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for table in TWO_ROW_TABLES:
        if not table_exists(conn, table) or not column_exists(conn, table, "game_id"):
            continue
        t = quote_ident(table)
        summary = fetchone(
            conn,
            f"""
            SELECT
                COUNT(*) FILTER (WHERE cnt <> 2) AS bad_games,
                COUNT(*) FILTER (WHERE cnt = 1) AS singleton_games,
                COUNT(*) FILTER (WHERE cnt > 2) AS overfull_games,
                COUNT(*) FILTER (WHERE cnt = 2) AS paired_games,
                COUNT(*) AS total_games
            FROM (
                SELECT game_id, COUNT(*) AS cnt
                FROM {t}
                GROUP BY game_id
            ) x
            """,
        )
        samples = fetchall(
            conn,
            f"""
            SELECT game_id, COUNT(*) AS row_count
            FROM {t}
            GROUP BY game_id
            HAVING COUNT(*) <> 2
            ORDER BY COUNT(*) DESC, game_id
            LIMIT 15
            """,
        )
        out[table] = {"summary": summary, "sample_failures": samples}
    return out


def latest_completed_coverage(conn) -> Dict[str, Any]:
    if not table_exists(conn, "game_schedule"):
        return {"error": "game_schedule missing"}

    latest = fetchone(
        conn,
        """
        SELECT MAX(game_date::date) AS latest_completed_date
        FROM game_schedule
        WHERE result IS NOT NULL
        """,
    )
    latest_date = latest["latest_completed_date"] if latest else None
    if not latest_date:
        return {"latest_completed_date": None, "games": []}

    schedule_games = fetchall(
        conn,
        """
        SELECT game_id,
               MIN(game_date) AS tip,
               COUNT(*) AS schedule_rows,
               COUNT(result) AS results,
               BOOL_OR(result IS NOT NULL) AS has_result
        FROM game_schedule
        WHERE game_date::date = %s
        GROUP BY game_id
        ORDER BY game_id
        """,
        (latest_date,),
    )
    game_ids = [g["game_id"] for g in schedule_games]
    if not game_ids:
        return {"latest_completed_date": str(latest_date), "games": []}

    tgs = {}
    if table_exists(conn, "team_game_stats"):
        rows = fetchall(
            conn,
            """
            SELECT game_id, COUNT(*) AS team_stat_rows
            FROM team_game_stats
            WHERE game_id = ANY(%s)
            GROUP BY game_id
            """,
            (game_ids,),
        )
        tgs = {r["game_id"]: r["team_stat_rows"] for r in rows}

    logs = {}
    if table_exists(conn, "gamelogs"):
        rows = fetchall(
            conn,
            """
            SELECT game_id, COUNT(*) AS player_log_rows
            FROM gamelogs
            WHERE game_id = ANY(%s)
            GROUP BY game_id
            """,
            (game_ids,),
        )
        logs = {r["game_id"]: r["player_log_rows"] for r in rows}

    games = []
    for g in schedule_games:
        gid = g["game_id"]
        games.append(
            {
                "game_id": gid,
                "schedule_rows": g["schedule_rows"],
                "results": g["results"],
                "team_game_stats_rows": tgs.get(gid, 0),
                "gamelog_rows": logs.get(gid, 0),
                "coverage_ok": (
                    g["schedule_rows"] == 2
                    and g["results"] == 2
                    and tgs.get(gid, 0) == 2
                    and logs.get(gid, 0) > 0
                ),
            }
        )

    covered = sum(1 for g in games if g["coverage_ok"])
    return {
        "latest_completed_date": str(latest_date),
        "games_on_date": len(games),
        "fully_covered_games": covered,
        "coverage_rate": round(covered / len(games), 4) if games else 0.0,
        "games": games,
    }


def derived_counts_by_date(conn) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for table, date_cols in DERIVED_DATE_COLUMNS.items():
        if not table_exists(conn, table):
            continue
        date_col = next((c for c in date_cols if column_exists(conn, table, c)), None)
        if not date_col:
            continue
        t = quote_ident(table)
        c = quote_ident(date_col)
        # Cast timestamptz/timestamp to date for grouping
        rows = fetchall(
            conn,
            f"""
            SELECT ({c})::date AS calc_date, COUNT(*) AS row_count
            FROM {t}
            WHERE {c} IS NOT NULL
            GROUP BY ({c})::date
            ORDER BY calc_date DESC
            LIMIT 30
            """,
        )
        result[f"{table}.{date_col}"] = rows
    return result


def snapshot_coverage(conn) -> Dict[str, List[Dict[str, Any]]]:
    """Summarize durable snapshot versions, cutoffs, and completeness."""
    result: Dict[str, List[Dict[str, Any]]] = {}
    for table in SNAPSHOT_TABLES:
        if not table_exists(conn, table):
            continue
        required = ("season", "calculation_version", "feature_as_of", "completeness_status")
        if not all(column_exists(conn, table, column) for column in required):
            continue
        t = quote_ident(table)
        result[table] = fetchall(
            conn,
            f"""
            SELECT season,
                   calculation_version,
                   completeness_status,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT feature_as_of) AS distinct_cutoffs,
                   MIN(feature_as_of) AS earliest_cutoff,
                   MAX(feature_as_of) AS latest_cutoff,
                   COUNT(*) FILTER (
                       WHERE data_available_at IS NOT NULL
                         AND data_available_at > feature_as_of
                   ) AS invalid_availability_rows
            FROM {t}
            GROUP BY season, calculation_version, completeness_status
            ORDER BY season, calculation_version, completeness_status
            """,
        )
    return result


def odds_and_availability_by_game(conn, limit: int = 40) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if table_exists(conn, "game_odds"):
        summary = fetchone(
            conn,
            """
            SELECT COUNT(*) AS observation_rows,
                   COUNT(DISTINCT game_id) AS distinct_games,
                   COUNT(DISTINCT sportsbook_id) AS distinct_books
            FROM game_odds
            """,
        )
        by_game = fetchall(
            conn,
            """
            SELECT game_id, game_date, COUNT(*) AS observations,
                   COUNT(DISTINCT sportsbook_id) AS sportsbooks
            FROM game_odds
            GROUP BY game_id, game_date
            ORDER BY game_date DESC NULLS LAST, observations DESC
            LIMIT %s
            """,
            (limit,),
        )
        out["game_odds"] = {"summary": summary, "by_game_sample": by_game}

    if table_exists(conn, "player_game_status"):
        summary = fetchone(
            conn,
            """
            SELECT COUNT(*) AS observation_rows,
                   COUNT(DISTINCT game_id) AS distinct_games,
                   COUNT(*) FILTER (WHERE status = 'INACTIVE') AS inactive_rows,
                   COUNT(*) FILTER (WHERE played IS TRUE) AS played_true_rows
            FROM player_game_status
            """,
        )
        by_game = fetchall(
            conn,
            """
            SELECT game_id, game_date, COUNT(*) AS observations,
                   COUNT(*) FILTER (WHERE status = 'INACTIVE') AS inactive_count
            FROM player_game_status
            GROUP BY game_id, game_date
            ORDER BY game_date DESC NULLS LAST, observations DESC
            LIMIT %s
            """,
            (limit,),
        )
        out["player_game_status"] = {"summary": summary, "by_game_sample": by_game}
    return out


def load_recent_validation_results(root: Path, limit: int = 3) -> List[Dict[str, Any]]:
    """Load last N validation JSON reports from data/ if present."""
    data_dir = root / "data"
    candidates: List[Path] = []
    if data_dir.exists():
        candidates.extend(sorted(data_dir.glob("validation_*.json")))
        candidates.extend(sorted(data_dir.glob("*validation*.json")))
        last = data_dir / "last_validation.json"
        if last.exists():
            candidates.append(last)

    # Deduplicate by resolved path, newest first by mtime
    unique: Dict[Path, Path] = {}
    for p in candidates:
        unique[p.resolve()] = p
    ordered = sorted(unique.values(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    results: List[Dict[str, Any]] = []
    for path in ordered:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            results.append(
                {
                    "path": str(path.relative_to(root)).replace("\\", "/"),
                    "mtime": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "payload": payload,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "path": str(path.relative_to(root)).replace("\\", "/"),
                    "error": str(exc),
                }
            )

    # Also peek at log tails if no JSON
    if not results:
        for log_name in ("daily_ingest.log", "daily_fetch.log", "daily_calculate.log"):
            log_path = root / log_name
            if not log_path.exists():
                continue
            try:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                tail = lines[-40:] if lines else []
                results.append(
                    {
                        "path": log_name,
                        "mtime": datetime.fromtimestamp(
                            log_path.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "log_tail": tail,
                    }
                )
            except Exception:
                continue
            if len(results) >= limit:
                break
    return results[:limit]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _md_escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def _fmt_dt(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)


def render_database_profile(profile: Dict[str, Any]) -> str:
    lines: List[str] = []
    meta = profile["meta"]
    lines.append("# Yuno Ball Database Profile")
    lines.append("")
    lines.append("Status: generated sanitized snapshot for analytics evaluation")
    lines.append(f"Generated (UTC): {meta['generated_at_utc']}")
    lines.append(f"Connection: `{meta['connection_fingerprint']}`")
    lines.append("")
    lines.append(
        "This file is produced by `scripts/generate_database_profile.py` using "
        "**read-only** PostgreSQL transactions. It intentionally omits credentials, "
        "hostnames, dumps, and PII beyond public NBA identifiers."
    )
    lines.append("")
    lines.append("## Alembic")
    lines.append("")
    alb = profile["alembic"]
    lines.append(f"- Current revision (DB `alembic_version`): `{alb.get('current_revision')}`")
    lines.append(
        f"- Head revision(s) (migration files): "
        + (", ".join(f"`{h}`" for h in alb.get("head_revisions") or []) or "—")
    )
    lines.append(f"- In sync with single head: `{alb.get('in_sync')}`")
    lines.append(f"- Migration files parsed: {alb.get('revision_count')}")
    lines.append("")

    lines.append("## Tables overview")
    lines.append("")
    lines.append("| Table | Rows | Columns |")
    lines.append("| --- | ---: | ---: |")
    for table in profile["tables"]:
        counts = profile["row_counts"].get(table, 0)
        ncols = len(profile["columns"].get(table, []))
        lines.append(f"| `{table}` | {counts} | {ncols} |")
    lines.append("")

    lines.append("## Schema detail")
    lines.append("")
    for table in profile["tables"]:
        lines.append(f"### `{table}`")
        lines.append("")
        lines.append("#### Columns")
        lines.append("")
        lines.append("| # | Column | Type | Nullable | Default |")
        lines.append("| ---: | --- | --- | --- | --- |")
        for col in profile["columns"].get(table, []):
            dtype = col["data_type"]
            if col.get("character_maximum_length"):
                dtype = f"{dtype}({col['character_maximum_length']})"
            elif col.get("udt_name") and col["data_type"] == "USER-DEFINED":
                dtype = col["udt_name"]
            lines.append(
                f"| {col['ordinal_position']} | `{col['column_name']}` | "
                f"{_md_escape(dtype)} | {col['is_nullable']} | "
                f"{_md_escape(col['column_default'])} |"
            )
        lines.append("")

        cons = profile["constraints"].get(table, [])
        if cons:
            lines.append("#### Constraints")
            lines.append("")
            lines.append("| Name | Type | Columns | References |")
            lines.append("| --- | --- | --- | --- |")
            for c in cons:
                ref = ""
                if c["constraint_type"] == "FOREIGN KEY" and c.get("foreign_table"):
                    ref = f"`{c['foreign_table']}` ({c.get('foreign_columns') or ''})"
                lines.append(
                    f"| `{c['constraint_name']}` | {c['constraint_type']} | "
                    f"{_md_escape(c.get('columns'))} | {_md_escape(ref)} |"
                )
            lines.append("")

        idxs = profile["indexes"].get(table, [])
        if idxs:
            lines.append("#### Indexes")
            lines.append("")
            for idx in idxs:
                lines.append(f"- `{idx['index_name']}`: `{idx['index_def']}`")
            lines.append("")

    lines.append("## Row counts by season")
    lines.append("")
    for table, rows in profile["counts_by_season"].items():
        lines.append(f"### `{table}`")
        lines.append("")
        lines.append("| Season | Rows |")
        lines.append("| --- | ---: |")
        for r in rows:
            lines.append(f"| {_md_escape(r['season'])} | {r['row_count']} |")
        lines.append("")

    lines.append("## Rows per season and team (sample)")
    lines.append("")
    lines.append(
        "Limited to 200 groups per table (highest row counts within each season ordering)."
    )
    lines.append("")
    for table, rows in profile["counts_by_season_team"].items():
        lines.append(f"### `{table}`")
        lines.append("")
        lines.append("| Season | Team ID | Rows |")
        lines.append("| --- | ---: | ---: |")
        for r in rows[:80]:
            lines.append(
                f"| {_md_escape(r['season'])} | {r['team_id']} | {r['row_count']} |"
            )
        if len(rows) > 80:
            lines.append(f"| … | … | ({len(rows) - 80} more groups truncated) |")
        lines.append("")

    lines.append("## Game date bounds")
    lines.append("")
    for table, bounds in profile["game_date_bounds"].items():
        lines.append(f"### `{table}`")
        lines.append("")
        if not bounds:
            lines.append("No data.")
        else:
            for k, v in bounds.items():
                lines.append(f"- `{k}`: {_fmt_dt(v)}")
        lines.append("")

    lines.append("## Null rates (important columns)")
    lines.append("")
    for table, cols in profile["null_rates"].items():
        lines.append(f"### `{table}`")
        lines.append("")
        lines.append("| Column | Nulls | Total | Null rate |")
        lines.append("| --- | ---: | ---: | ---: |")
        for c in cols:
            lines.append(
                f"| `{c['column']}` | {c['nulls']} | {c['total']} | {c['null_rate']:.2%} |"
            )
        lines.append("")

    lines.append("## Duplicate primary / candidate keys")
    lines.append("")
    lines.append("| Table | Key columns | Duplicate groups | Extra rows |")
    lines.append("| --- | --- | ---: | ---: |")
    for table, info in profile["duplicate_keys"].items():
        cols = ", ".join(f"`{c}`" for c in info["columns"])
        lines.append(
            f"| `{table}` | {cols} | {info['duplicate_groups']} | {info['extra_rows']} |"
        )
    lines.append("")

    lines.append("## Orphan counts")
    lines.append("")
    lines.append("| Check | Child | Parent | Orphan rows |")
    lines.append("| --- | --- | --- | ---: |")
    for o in profile["orphans"]:
        lines.append(
            f"| {_md_escape(o['name'])} | `{o['child']}` | `{o['parent']}` | {o['orphan_rows']} |"
        )
    lines.append("")

    lines.append("## Two-rows-per-game failures")
    lines.append("")
    for table, info in profile["two_row_failures"].items():
        lines.append(f"### `{table}`")
        lines.append("")
        s = info.get("summary") or {}
        lines.append(f"- Total distinct `game_id`: {s.get('total_games', 0)}")
        lines.append(f"- Paired (exactly 2 rows): {s.get('paired_games', 0)}")
        lines.append(f"- Failures (≠ 2): {s.get('bad_games', 0)}")
        lines.append(f"- Singletons: {s.get('singleton_games', 0)}")
        lines.append(f"- Overfull (>2): {s.get('overfull_games', 0)}")
        lines.append("")
        samples = info.get("sample_failures") or []
        if samples:
            lines.append("| game_id | row_count |")
            lines.append("| --- | ---: |")
            for sample in samples:
                lines.append(f"| `{sample['game_id']}` | {sample['row_count']} |")
            lines.append("")

    lines.append("## Latest completed game coverage")
    lines.append("")
    cov = profile["latest_completed_coverage"]
    if cov.get("error"):
        lines.append(f"Error: {cov['error']}")
    else:
        lines.append(f"- Latest completed date: `{cov.get('latest_completed_date')}`")
        lines.append(f"- Games on date: {cov.get('games_on_date')}")
        lines.append(f"- Fully covered (schedule+team stats+player logs): {cov.get('fully_covered_games')}")
        lines.append(f"- Coverage rate: {cov.get('coverage_rate', 0):.1%}")
        lines.append("")
        lines.append("| game_id | schedule_rows | results | team_game_stats | gamelogs | ok |")
        lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
        for g in cov.get("games") or []:
            lines.append(
                f"| `{g['game_id']}` | {g['schedule_rows']} | {g['results']} | "
                f"{g['team_game_stats_rows']} | {g['gamelog_rows']} | {g['coverage_ok']} |"
            )
    lines.append("")

    lines.append("## Derived-table counts by calculation date")
    lines.append("")
    for key, rows in profile["derived_by_date"].items():
        lines.append(f"### `{key}` (latest 30 dates)")
        lines.append("")
        lines.append("| Date | Rows |")
        lines.append("| --- | ---: |")
        for row in rows:
            lines.append(f"| {_fmt_dt(row['calc_date'])} | {row['row_count']} |")
        lines.append("")

    lines.append("## Durable snapshot coverage")
    lines.append("")
    for table, rows in profile["snapshot_coverage"].items():
        lines.append(f"### `{table}`")
        lines.append("")
        lines.append(
            "| Season | Version | Completeness | Rows | Cutoffs | Earliest | Latest | Invalid availability |"
        )
        lines.append("| --- | --- | --- | ---: | ---: | --- | --- | ---: |")
        for row in rows:
            lines.append(
                f"| {_md_escape(row['season'])} | {_md_escape(row['calculation_version'])} | "
                f"{_md_escape(row['completeness_status'])} | {row['row_count']} | "
                f"{row['distinct_cutoffs']} | {_fmt_dt(row['earliest_cutoff'])} | "
                f"{_fmt_dt(row['latest_cutoff'])} | {row['invalid_availability_rows']} |"
            )
        lines.append("")

    lines.append("## Odds and availability observations by game")
    lines.append("")
    oa = profile["odds_availability"]
    for name, block in oa.items():
        lines.append(f"### `{name}`")
        lines.append("")
        summary = block.get("summary") or {}
        for k, v in summary.items():
            lines.append(f"- `{k}`: {v}")
        lines.append("")
        lines.append("| game_id | game_date | observations | extra |")
        lines.append("| --- | --- | ---: | --- |")
        for r in block.get("by_game_sample") or []:
            extra = r.get("sportsbooks", r.get("inactive_count", ""))
            lines.append(
                f"| `{r['game_id']}` | {_fmt_dt(r.get('game_date'))} | "
                f"{r['observations']} | {extra} |"
            )
        lines.append("")

    lines.append("## Last three ingestion / validation results")
    lines.append("")
    validations = profile.get("validation_results") or []
    if not validations:
        lines.append(
            "No `data/*validation*.json` or daily log artifacts found. "
            "Run `python scripts/validate_daily_data.py --offline` to create "
            "`data/last_validation.json`, then regenerate this profile."
        )
    else:
        for i, item in enumerate(validations, 1):
            lines.append(f"### Result {i}: `{item.get('path')}`")
            lines.append("")
            lines.append(f"- mtime (UTC): `{item.get('mtime')}`")
            if item.get("error"):
                lines.append(f"- error: {item['error']}")
            elif item.get("payload"):
                payload = item["payload"]
                lines.append(f"- ok: `{payload.get('ok')}`")
                lines.append(f"- season: `{payload.get('season')}`")
                lines.append(f"- date: `{payload.get('date')}`")
                lines.append(f"- timestamp: `{payload.get('timestamp')}`")
                checks = payload.get("checks") or []
                if checks:
                    lines.append("")
                    lines.append("| Check | Severity | Passed | Message |")
                    lines.append("| --- | --- | --- | --- |")
                    for c in checks:
                        lines.append(
                            f"| {_md_escape(c.get('name'))} | {c.get('severity')} | "
                            f"{c.get('passed')} | {_md_escape(c.get('message'))} |"
                        )
            elif item.get("log_tail"):
                lines.append("")
                lines.append("```")
                lines.extend(item["log_tail"])
                lines.append("```")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Regenerate with:* `python scripts/generate_database_profile.py` "
        "(venv activated; `DATABASE_URL` set)."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Static catalogs (SOURCE + METRIC)
# ---------------------------------------------------------------------------


SOURCE_CATALOG_MD = """# Yuno Ball Source Catalog

Status: canonical inventory of external data sources feeding Yuno Ball
Reviewed: 2026-07-15 against fetch utilities, daily pipeline, and `DATA_DICTIONARY.md`.

This catalog describes **where data comes from**, not what is currently populated.
Use `DATABASE_PROFILE.md` for live coverage.

## Conventions

* Refresh cadence is intended production behavior; local/dev may run ad hoc.
* Latency is expected wall time for a healthy path (direct or approved proxy), not a SLA.
* Failure behavior is what operators should expect today.

## Sources

| Source | Endpoint / module | Grain | Refresh cadence | Historical availability | Expected latency | Owner | Failure behavior |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NBA static players | `nba_api.stats.static.players` + `CommonPlayerInfo` via `player_fetcher` | one player | weekly / discovery; also daily `players` task | career identity; `available_seasons` text | minutes–tens of minutes for full discovery | ingestion / `daily_fetch.players` | retry with rate limit; skip failed IDs; do not wipe `players` |
| NBA team identity | static / seed team list → `teams` | one team | rare (season verify) | franchise IDs are stable | seconds | ingestion seed | abort if NBA IDs missing; never remapped |
| CommonTeamRoster | `CommonTeamRoster` via roster fetch | player-team-season | daily in season | canonical requested season; earlier seasons retained | ~30 team calls | `daily_fetch.rosters` | per-team retry; empty/unresolved payload fails closed before requested-season reconciliation |
| LeagueGameFinder / schedule | `LeagueGameFinder` + CDN `scheduleLeagueV2_1.json`; null-result repair may use validated paired `team_game_stats` | team-perspective game `(game_id, team_id)` | daily results + future slate; local reconciliation after team stats and before gamelogs; bounded CLI for recovery | multi-season backfill supported | seconds–minutes per season | `daily_fetch.schedule` / `future` / `schedule_reconcile`; `reconcile_schedule_results.py` | CDN timeout → keep last DB schedule; reconciliation requires reciprocal two-row W/L and score agreement or fails closed before calculations |
| PlayerGameLogs | `PlayerGameLogs` | player-game | daily current season; historical by player/season | box scores for requested seasons | high (hundreds of calls) | `daily_fetch.gamelogs` | rate-limit sleep; atomic mutable-field upsert refreshes corrected boxes without zero-filling missing values |
| TeamGameLog | `TeamGameLog` → `team_game_stats` | team-game | daily / seasonal backfill after schedule; feeds local schedule-result reconciliation | requires schedule FK rows | medium–high | `daily_fetch.teamstats` → `schedule_reconcile` | skip games lacking schedule; partial/conflicting result pairs block reconciliation; plus/minus historically forced 0 |
| LeagueDashPlayerStats | `LeagueDashPlayerStats` | player-season | daily current; seasonal backfill | season aggregates + ranks | medium | `daily_fetch.leagueplayer` | update on conflict; traded-player grain ambiguous |
| LeagueDashTeamStats | `LeagueDashTeamStats` (measures × per-modes × season types) | team-season-season_type | daily current; seasonal backfill | wide endpoint-shaped columns | medium–high | `daily_fetch.leagueteam` | dynamic column allowlist required; partial measure failure should not drop other measures |
| Live box score injuries | Live BoxScore / injury fetcher → `player_game_status` | player-game status | daily for recent/upcoming games | sparse historically; best for recent windows | medium (batched) | `daily_fetch.injury` | offseason empty is OK; warn if completed games have zero status |
| NBA live odds | NBA odds endpoint → `game_odds` | game × sportsbook observation | daily for today's slate | not a historical closing-line archive | low–medium | `daily_fetch.odds` / `odds_service` | skip when slate empty; never invent lines |
| Derived streaks | calculated from `gamelogs` | player-stat-threshold-season | daily calculate | snapshot tables rebuilt; not pregame historical | medium | `daily_calculate.streaks` | clear/rebuild season slice; empty if logs missing |
| Heat index | calculated from `gamelogs` | player-stat-season-window | daily calculate | current-season snapshot | medium | `daily_calculate.heat` | skip players with <3 games |
| Consistency | calculated from `gamelogs` | player-stat-season-window | daily calculate | current-season snapshot | medium | `daily_calculate.consistency` | skip <5 games; mean 0 → undefined CV |
| Team daily metrics / flags (legacy) | `league_dash_team_stats` + unbounded `team_game_stats` | team × date × window | daily compatibility projection | current endpoint state only; unsafe historical labels | medium | `daily_calculate.metrics` / `flags` | never use for historical reconstruction; retained for current UI compatibility |
| Team/game analytical snapshots | paired pre-cutoff `team_game_stats` + `game_schedule` | scheduled game/team/cutoff/version plus paired game environment | daily after schedule factors; bounded backfill | reproducible for validated team-game coverage | medium | `daily_calculate.team_snapshots`; `backfill_team_game_snapshots.py` | excludes target/future games, reports incomplete pairs as partial, publishes both grains transactionally |
| Schedule factors | `game_schedule` | team-game | daily calculate | rebuildable for any scheduled season in DB | low–medium | `daily_calculate.schedule` | missing prior game → null rest |
| Game environment (legacy) | schedule + legacy metrics | game-date | daily compatibility projection | today's context oriented | low | `daily_calculate.environment` | not a historical feature source; use `game_environment_snapshots` |

## Ownership notes

* External NBA HTTP stays behind `app/utils/fetch/` (and related services). Routes must not grow new direct endpoint clients.
* PostgreSQL is durable; Redis is disposable cache (`CACHE_CATALOG.md`).
* `daily_ingest.py`, standalone `daily_fetch.py`, and standalone `daily_calculate.py` share one PostgreSQL advisory lock and write per-task source status. Legacy initial/backfill utilities remain outside that lock and must not overlap the daily pipeline.

## Related docs

* `DATA_DICTIONARY.md` — table grains
* `INGESTION_RUNBOOK.md` — order, idempotency, recovery
* `DATABASE_PROFILE.md` — live row counts and quality
* `METRIC_CATALOG.md` — derived metric formulas
"""


METRIC_CATALOG_MD = """# Yuno Ball Metric Catalog

Status: canonical definitions for Yuno-derived metrics
Reviewed: 2026-07-15 against services in `app/services/` and daily calculate tasks.

Use this for interpretation and leakage-safe evaluation. Endpoint-native NBA fields
(e.g. raw `pts` from box scores) are documented in `DATA_DICTIONARY.md`, not duplicated here.

## Contract fields

For each metric:

* **Formula** — exact definition used in code
* **Grain** — uniqueness / observation unit
* **As-of rules** — what time cut the value represents
* **Version** — logical version string for this contract
* **Interpretation** — how to read the number
* **Prohibited uses** — what not to do

---

## Legacy player z-scores

| Field | Value |
| --- | --- |
| Metric ID | `player.legacy_z_scores` |
| Version | unversioned legacy; deprecated/read-only |
| Implementation | retained `player_z_scores` table; writer fails closed |
| Formula | Historical implementation standardized current provider aggregates against a league distribution. Exact season and calculation inputs were not persisted. |
| Grain | one overwrite row per `player_id`; insufficient for historical analytics |
| As-of rules | None are recoverable from the table. |
| Interpretation | Inspection-only legacy values. Use `player.heat_index` v2 for supported normalized player form. |
| Prohibited uses | Do not refresh, backfill, train from, or present as historical/pregame data. |

---

## Player heat index

| Field | Value |
| --- | --- |
| Metric ID | `player.heat_index` |
| Version | `player-v2.1` (`heat_index.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_heat_index_snapshots`; `HeatIndexService` → legacy `player_heat_index` |
| Formula | `z = (recent_avg(stat, window) - season_avg(stat)) / season_std(stat)`; status `on_fire` if `z ≥ 1.0`, `ice_cold` if `z ≤ -1.0`, else neutral. Stats: PTS, REB, AST, PRA (`PTS+REB+AST`). Windows: 3, 5, 10. Requires ≥3 season games and enough recent games for the window. |
| Grain | `(player_id, stat, season, season_type, window_size, feature_as_of, calculation_version)` |
| As-of rules | v2 uses only source games on Eastern calendar dates strictly before the target slate date, ordered by the canonical schedule timestamp. Canonical publication is 10:00 ET; source availability is scheduled tipoff + 6h. |
| Interpretation | Positive z = recent form above that player's own season distribution. |
| Prohibited uses | Do not treat as league-relative strength. Do not use the legacy table as a historical feature. A missing PTS/REB/AST component makes PRA missing; never replace it with zero. |

---

## Player consistency (CV)

| Field | Value |
| --- | --- |
| Metric ID | `player.consistency_cv` |
| Version | `player-v2.1` (`consistency.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_consistency_snapshots`; `ConsistencyService` → legacy `player_consistency` |
| Formula | `CV = stddev(stat) / mean(stat)` over season game logs. Tiers: `steady` if `CV < 0.35`, `volatile` if `CV > 0.55`, else mid. Stats: pts, reb, ast, pra, stl, blk, tov. Requires ≥5 games. |
| Grain | `(player_id, season, season_type, stat_name, window_size, feature_as_of, calculation_version)` |
| As-of rules | Same strict pre-slate v2 cutoff and availability rule as heat index. Only complete player/stat samples with at least five games publish. |
| Interpretation | Lower CV ⇒ more predictable game-to-game volume for that stat. |
| Prohibited uses | Do not compare CV across stats with different means without context; do not use when mean≈0; not a shooting-efficiency volatility metric. |

---

## Consecutive streaks

| Field | Value |
| --- | --- |
| Metric ID | `player.consecutive_streak` |
| Version | `player-v2.1` (`consecutive_streak.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_consecutive_streak_snapshots`; `StreakCalculationService` → legacy `player_consecutive_streaks` |
| Formula | Count consecutive games (ordered by game date) where `stat ≥ threshold`. Also tracks season max. Thresholds e.g. PTS 10/15/20/25/30, REB 4/6/8/10/12, AST 2/4/6/8/10, STL/BLK 1–4, PRA 20–40. |
| Grain | `(player_id, stat, threshold, season, season_type, feature_as_of, calculation_version, streak_kind)` |
| As-of rules | v2 uses only games strictly before the target slate date and orders by schedule event time. Missing source values prevent a complete player/stat publication. |
| Interpretation | True consecutive hit streak, unlike legacy `player_streaks` “X of last 10”. |
| Prohibited uses | Do not label legacy `player_streaks` as consecutive; do not use FG3M until present on gamelogs. |

---

## Stat windows (recent form hits)

| Field | Value |
| --- | --- |
| Metric ID | `player.stat_window` |
| Version | `player-v2.1` (`stat_window.v1` remains the legacy projection) |
| Implementation | `player_snapshot_service` → `player_stat_window_snapshots`; `StreakCalculationService` → legacy `player_stat_windows` |
| Formula | Count of games in last N where `stat ≥ threshold` (recent form), plus related season hit-rate fields persisted by the service. |
| Grain | `(player_id, stat, threshold, season, season_type, window_size, feature_as_of, calculation_version)` |
| As-of rules | v2 recent windows end at the latest eligible pre-slate game and record actual games played when fewer than N exist. Readers pin all metric families to the stat-window anchor cutoff. |
| Interpretation | “X of last N” rate at a threshold. |
| Prohibited uses | Do not call this a consecutive streak. |

---

## Legacy player streaks

| Field | Value |
| --- | --- |
| Metric ID | `player.legacy_streaks` |
| Version | `player_streaks.v0` |
| Implementation | `player_streaks` table / older streak path |
| Formula | Qualifying games among last 10 vs fixed thresholds (PTS/REB/AST/FG3M families). |
| Grain | `(player_id, stat, season, threshold)` |
| As-of rules | Table cleared/rebuilt daily — latest snapshot only. |
| Interpretation | Recent hit density, not necessarily consecutive. |
| Prohibited uses | Do not use as historical pregame training labels; prefer `player_consecutive_streaks` / `player_stat_windows`. |

---

## Team game feature snapshots

| Field | Value |
| --- | --- |
| Metric ID | `team.game_features` |
| Version | `team-v2.1` |
| Implementation | `team_snapshot_service` → `team_game_feature_snapshots` |
| Formula | Season and trailing-window efficiency are rebuilt from paired `team_game_stats`. Possessions = `FGA + 0.44 × FTA - OREB + TOV`; ratings are points per 100 estimated possessions; eFG% = `(FGM + 0.5 × 3PM) / FGA`; TOV%, ORB%, FTR, three-point scoring share, deltas, opponent net-rating summaries, rest/density factors, and threshold flags use the same eligible pre-cutoff facts. |
| Grain | `(game_id, team_id, window_size, feature_as_of, calculation_version)` |
| As-of rules | Canonical publication is 10:00 ET on the target slate date. Only final paired games on an Eastern date strictly before the slate are eligible; scheduled tipoff + 6h is the source-availability proxy. Target/future games are defensively excluded in both SQL and the pure builder. |
| Interpretation | A reproducible pregame team perspective. `complete` requires the requested recent window and no excluded paired box scores; early-season or incomplete-source rows remain `partial` with played/used counts and missing flags. |
| Prohibited uses | Never substitute `league_dash_team_stats` for a historical row, never zero-fill a missing box-score input, never use the target game, and never overwrite an earlier meaning under the same calculation version. |

---

## Game environment snapshots

| Field | Value |
| --- | --- |
| Metric ID | `game.environment_snapshot` |
| Version | `team-v2.1` |
| Implementation | `team_snapshot_service` → `game_environment_snapshots` |
| Formula | Pairs the exact-cutoff home and away team snapshots. Pace projection blends 70% mean pace and 30% faster-team pace; scoring environment combines each offense with opponent defense and pace; three-point and chaos indices use the paired recent values. |
| Grain | `(game_id, window_size, feature_as_of, calculation_version)` |
| As-of rules | Uses only the two team rows published at the same cutoff/version. Environment completeness is `complete` only when both team inputs are complete and required recent metrics exist. |
| Interpretation | Auditable pregame matchup context with home/away source values, tags, freshness, and missing state. |
| Prohibited uses | Do not join a team snapshot from another cutoff/version and do not use legacy `game_environment_daily` for historical modeling. |

---

## Team daily metrics (season vs recent; legacy compatibility)

| Field | Value |
| --- | --- |
| Metric ID | `team.daily_metrics` |
| Version | `team_daily_metrics.v1` (+ SoS columns `sos.v1`) |
| Implementation | `TeamMetricsService` → `team_daily_metrics` |
| Formula | Season-to-date efficiency/pace/four-factors from `league_dash_team_stats` (Regular Season) compared to trailing `window_size` (default 10) team-game averages from `team_game_stats`. Deltas = recent − season. SoS columns summarize opponent strength faced in-window. Percent fields normalized to 0–1 when stored as 0–100. |
| Grain | `(stat_date, team_id, window_size)` |
| As-of rules | `stat_date` is the calculation date. Season endpoint slice is **current endpoint state** unless rebuilt from game-level history — dangerous for historical reconstruction (see `MODEL_FEATURE_PLAN.md`). |
| Interpretation | Positive net-rating delta ⇒ recent form stronger than season baseline. |
| Prohibited uses | Do not backfill historical `stat_date` rows using today's season aggregates; do not use `team_game_stats.plus_minus` until ingestion stops forcing 0. |

---

## Team daily flags

| Field | Value |
| --- | --- |
| Metric ID | `team.daily_flags` |
| Version | `team_daily_flags.v1` |
| Implementation | `TeamFlagsService` → `team_daily_flags` |
| Formula | Qualitative tags derived from deltas / thresholds on `team_daily_metrics` for a `stat_date`. |
| Grain | `(stat_date, team_id, flag_type)` |
| As-of rules | Same as parent metrics for that `stat_date`. |
| Interpretation | Human-readable performance tags for daily UI. |
| Prohibited uses | Not a calibrated probability; do not treat as model features without encoding version. |

---

## Schedule factors

| Field | Value |
| --- | --- |
| Metric ID | `team.schedule_factors` |
| Version | `schedule_factors.v1` |
| Implementation | `ScheduleAnalysisService` → `team_schedule_factors` |
| Formula | `days_rest = game_date - previous_game_date - 1` (team perspective); `is_b2b = (days_rest == 0)`; rest edge vs opponent when both sides available; denser windows (e.g. 3-in-4 / 4-in-6) as implemented in service. |
| Grain | `(game_id, team_id)` |
| As-of rules | Uses schedule rows known for that game; safe if prior games are historical facts. |
| Interpretation | Schedule pressure / rest advantage entering the game. |
| Prohibited uses | Do not use post-game reschedule artifacts without actual tip semantics; exclude All-Star/special games from modeling sets. |

---

## Game environment (daily context)

| Field | Value |
| --- | --- |
| Metric ID | `game.environment_daily` |
| Version | `game_environment.v1` |
| Implementation | daily environment calc → `game_environment_daily` |
| Formula | Assembles matchup context from schedule factors + team metrics for a game date (see service/table columns). |
| Grain | `(game_id, game_date)` |
| As-of rules | Oriented to the calculation day's slate; verify column-level sources before modeling. |
| Interpretation | Packaged pregame context for daily UI. |
| Prohibited uses | Do not assume leakage-safe historical rebuild until each input is pinned to pre-tipoff snapshots. |

---

## Odds observations

| Field | Value |
| --- | --- |
| Metric ID | `game.odds_observation` |
| Version | `game_odds.v1` |
| Implementation | `OddsService` / `game_odds` |
| Formula | Store sportsbook moneyline + spread (current/open/trend) as returned by NBA odds feed at `recorded_at`. |
| Grain | `(game_id, sportsbook_id)` observation (updated in place) |
| As-of rules | Timestamped by `recorded_at` / `updated_at`. Not guaranteed closing line. |
| Interpretation | Market snapshot for today's games. |
| Prohibited uses | Do not backfill historical model evaluation with later lines; do not treat as full multi-book consensus without book coverage checks. |

---

## Availability / injury observations

| Field | Value |
| --- | --- |
| Metric ID | `player.game_status` |
| Version | `player_game_status.v1` |
| Implementation | injury/boxscore fetch → `player_game_status` |
| Formula | Per player-game: ACTIVE/INACTIVE, reason codes, description, `played` flag from live boxscore. |
| Grain | `(game_id, player_id)` |
| As-of rules | Captured at fetch time (`recorded_at`); may lag true injury news. |
| Interpretation | Availability observation for a game, not a medical diagnosis. |
| Prohibited uses | Do not invent historical injury timelines; sparse coverage ≠ healthy roster. |

---

## Planned (not implemented as production metrics)

See `MODEL_FEATURE_PLAN.md` for future labels and model predictions. Those must record immutable `model_version`, `feature_version`, prediction time, training cutoff, and input completeness before product use.

## Related docs

* `SOURCE_CATALOG.md` — upstream endpoints
* `DATABASE_PROFILE.md` — live coverage / null rates
* `MODEL_FEATURE_PLAN.md` — leakage rules
* `DATA_DICTIONARY.md` — raw table columns
"""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_profile(conn, root: Path) -> Dict[str, Any]:
    tables = collect_tables(conn)
    print(f"  tables: {len(tables)}")
    columns = collect_columns(conn)
    constraints = collect_constraints(conn)
    indexes = collect_indexes(conn)
    alembic = collect_alembic(conn, root / "alembic" / "versions")
    print("  row counts…")
    counts = row_counts(conn, tables)
    season_tables = [t for t in tables if t not in SANITIZE_SKIP_ROW_DETAIL]
    print("  counts by season…")
    by_season = counts_by_season(conn, season_tables)
    print("  counts by season/team…")
    by_season_team = counts_by_season_team(
        conn, [t for t in CORE_FACT_TABLES if t in tables] + ["roster", "game_odds", "player_game_status"]
    )
    print("  date bounds / nulls / keys…")
    dates = game_date_bounds(conn)
    nulls = null_rates(conn)
    dupes = duplicate_keys(conn)
    print("  orphans / two-row / coverage…")
    orphans = orphan_counts(conn)
    two_row = two_row_failures(conn)
    coverage = latest_completed_coverage(conn)
    print("  derived + odds…")
    derived = derived_counts_by_date(conn)
    snapshots = snapshot_coverage(conn)
    odds_avail = odds_and_availability_by_game(conn)
    validations = load_recent_validation_results(root, limit=3)

    return {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "connection_fingerprint": _redact_database_url(os.environ.get("DATABASE_URL", "")),
            "table_count": len(tables),
        },
        "alembic": alembic,
        "tables": tables,
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "row_counts": counts,
        "counts_by_season": by_season,
        "counts_by_season_team": by_season_team,
        "game_date_bounds": dates,
        "null_rates": nulls,
        "duplicate_keys": dupes,
        "orphans": orphans,
        "two_row_failures": two_row,
        "latest_completed_coverage": coverage,
        "derived_by_date": derived,
        "snapshot_coverage": snapshots,
        "odds_availability": odds_avail,
        "validation_results": validations,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate sanitized DATABASE_PROFILE.md (+ catalogs) via read-only DB access"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=project_root / "docs",
        help="Output directory (default: docs/)",
    )
    parser.add_argument(
        "--skip-catalogs",
        action="store_true",
        help="Only write DATABASE_PROFILE.md",
    )
    parser.add_argument(
        "--catalogs-only",
        action="store_true",
        help="Only write SOURCE_CATALOG.md and METRIC_CATALOG.md (no DB)",
    )
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="Alias for --skip-catalogs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    skip_catalogs = args.skip_catalogs or args.profile_only

    if not args.catalogs_only:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("ERROR: DATABASE_URL is not set", file=sys.stderr)
            return 1

        print("Connecting (read-only)…")
        conn = connect_readonly(database_url)
        try:
            # Prove read-only: a write should fail. Soft-check via transaction attribute.
            ro = fetch_scalar(conn, "SHOW default_transaction_read_only")
            print(f"  default_transaction_read_only = {ro}")
            print("Profiling database…")
            profile = build_profile(conn, project_root)
        finally:
            conn.close()

        profile_path = out_dir / "DATABASE_PROFILE.md"
        profile_path.write_text(render_database_profile(profile), encoding="utf-8")
        print(f"Wrote {profile_path}")

    if not skip_catalogs:
        source_path = out_dir / "SOURCE_CATALOG.md"
        metric_path = out_dir / "METRIC_CATALOG.md"
        source_path.write_text(SOURCE_CATALOG_MD.lstrip("\n"), encoding="utf-8")
        metric_path.write_text(METRIC_CATALOG_MD.lstrip("\n"), encoding="utf-8")
        print(f"Wrote {source_path}")
        print(f"Wrote {metric_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
