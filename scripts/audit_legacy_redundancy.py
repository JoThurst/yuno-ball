"""Inventory legacy, canonical, and source tables without changing the database.

This is an evidence-gathering step for the final redundancy and rollback audit.
It intentionally does not infer that a similarly shaped table is redundant:
table grain, cutoff semantics, lineage, and active consumers determine that
decision.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine


TABLES: tuple[dict[str, Any], ...] = (
    {
        "table": "gamelogs",
        "role": "compatibility_source",
        "grain": "player-game",
        "candidate_replacement": "player_game_facts",
        "decision": "preserve_until_canonical_readers and rollback audit pass",
        "consumer_boundary": "canonical-first player-game reader fallback",
    },
    {
        "table": "player_game_facts",
        "role": "canonical_projection",
        "grain": "player-team-game",
        "candidate_replacement": None,
        "decision": "retain as canonical selected projection",
        "consumer_boundary": "Program C/D and canonical-first readers",
    },
    {
        "table": "player_game_advanced_facts",
        "role": "canonical_projection",
        "grain": "player-team-game",
        "candidate_replacement": None,
        "decision": "retain as canonical selected projection",
        "consumer_boundary": "Program C/D advanced inputs",
    },
    {
        "table": "team_game_stats",
        "role": "source_foundation",
        "grain": "team-game",
        "candidate_replacement": "team_game_feature_snapshots",
        "decision": "preserve; snapshots depend on this source",
        "consumer_boundary": "schedule reconciliation and feature snapshots",
    },
    {
        "table": "team_daily_metrics",
        "role": "legacy_compatibility_projection",
        "grain": "team-date-window",
        "candidate_replacement": "team_game_feature_snapshots",
        "decision": "preserve until consumer migration and rollback proof",
        "consumer_boundary": "legacy metrics/flags and current-state UI",
    },
    {
        "table": "team_daily_flags",
        "role": "legacy_compatibility_projection",
        "grain": "team-date",
        "candidate_replacement": "team_game_feature_snapshots",
        "decision": "preserve until consumer migration and rollback proof",
        "consumer_boundary": "legacy flags/current-state UI",
    },
    {
        "table": "game_environment_daily",
        "role": "legacy_compatibility_projection",
        "grain": "game-date",
        "candidate_replacement": "game_environment_snapshots",
        "decision": "preserve until consumer migration and rollback proof",
        "consumer_boundary": "legacy environment/slate fallback",
    },
    {
        "table": "player_heat_index",
        "role": "legacy_compatibility_projection",
        "grain": "player-stat-season-window",
        "candidate_replacement": "player_heat_index_snapshots",
        "decision": "preserve; current consumers still exist",
        "consumer_boundary": "legacy heat service/slate fallback",
    },
    {
        "table": "player_consecutive_streaks",
        "role": "legacy_compatibility_projection",
        "grain": "player-stat-threshold-season",
        "candidate_replacement": "player_consecutive_streak_snapshots",
        "decision": "preserve; current consumers still exist",
        "consumer_boundary": "legacy streak service",
    },
    {
        "table": "player_stat_windows",
        "role": "legacy_compatibility_projection",
        "grain": "player-stat-window",
        "candidate_replacement": "player_stat_window_snapshots",
        "decision": "preserve until consumer migration and rollback proof",
        "consumer_boundary": "legacy streak/stat-window service",
    },
    {
        "table": "player_streaks",
        "role": "legacy_compatibility_projection",
        "grain": "player-stat-threshold-season",
        "candidate_replacement": "player_consecutive_streak_snapshots",
        "decision": "preserve; semantics differ from consecutive streaks",
        "consumer_boundary": "legacy streak compatibility path",
    },
    {
        "table": "player_z_scores",
        "role": "legacy_read_only",
        "grain": "player-stat",
        "candidate_replacement": "player_heat_index_snapshots",
        "decision": "preserve read-only; no new writes",
        "consumer_boundary": "inspection/deprecated compatibility only",
    },
    {
        "table": "game_odds",
        "role": "legacy_market_source",
        "grain": "game-market snapshot",
        "candidate_replacement": "market_observation_headers/selections",
        "decision": "preserve until market migration and rollback proof",
        "consumer_boundary": "legacy betting compatibility path",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only inventory for the legacy redundancy and rollback audit"
    )
    parser.add_argument("--season", default=None, help="Optional YYYY-YY coverage slice")
    return parser.parse_args()


def _table_columns(db, table: str) -> set[str]:
    rows = db.execute(
        text(
            """select column_name from information_schema.columns
               where table_schema='public' and table_name=:table"""
        ),
        {"table": table},
    )
    return {row[0] for row in rows}


def _table_inventory(db, spec: dict[str, Any], season: str | None) -> dict[str, Any]:
    table = spec["table"]
    exists = bool(
        db.execute(
            text(
                """select 1 from information_schema.tables
                   where table_schema='public' and table_name=:table"""
            ),
            {"table": table},
        ).first()
    )
    result = {
        **spec,
        "exists": exists,
        "row_count": None,
        "season_row_count": None,
        "season_value_counts": [],
    }
    if not exists:
        return result

    result["row_count"] = int(
        db.execute(text(f"select count(*) from \"{table}\"")).scalar() or 0
    )
    columns = _table_columns(db, table)
    if season and "season" in columns:
        result["season_row_count"] = int(
            db.execute(
                text(f"select count(*) from \"{table}\" where season=:season"),
                {"season": season},
            ).scalar()
            or 0
        )
    if "season" in columns:
        season_rows = db.execute(
            text(f"""select season::text as season, count(*) as rows
                    from \"{table}\"
                    group by season
                    order by season nulls last
                    limit 20""")
        )
        result["season_value_counts"] = [
            {"season": row[0], "rows": int(row[1])} for row in season_rows
        ]
    result["columns"] = sorted(columns)
    return result


def _overlap_metrics(db, season: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    season_filter = ""
    if season:
        params["season"] = season
        season_filter = " and g.season=:season"
    metrics = {
        "gamelogs_game_ids": 0,
        "canonical_traditional_game_ids": 0,
        "gamelogs_and_traditional_overlap_game_ids": 0,
    }
    for key, query in {
        "gamelogs_game_ids": f"select count(distinct g.game_id) from gamelogs g where 1=1{season_filter}",
        "canonical_traditional_game_ids": f"select count(distinct p.canonical_game_id) from player_game_facts p where 1=1{season_filter.replace('g.', 'p.')}",
        "gamelogs_and_traditional_overlap_game_ids": f"""select count(distinct g.game_id)
            from gamelogs g join player_game_facts p
              on p.canonical_game_id=g.game_id
            where 1=1{season_filter}
              and p.season=g.season""",
    }.items():
        metrics[key] = int(db.execute(text(query), params).scalar() or 0)
    return metrics


def run_audit(season: str | None = None) -> dict[str, Any]:
    with engine.connect() as db:
        tables = [_table_inventory(db, spec, season) for spec in TABLES]
        overlap = _overlap_metrics(db, season)
    return {
        "mode": "read-only-audit",
        "audit": "legacy_redundancy_and_rollback_inventory",
        "season": season,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "writes_performed": False,
        "deletions_performed": False,
        "overlap_metrics": overlap,
        "tables": tables,
        "decision_rule": "No table is removable from this inventory alone; require consumer migration, rollback proof, and an explicit final approval.",
    }


def main() -> int:
    print(json.dumps(run_audit(parse_args().season), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
