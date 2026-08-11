"""Read-only coverage inventory for the Program C player-game fact pipeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameFactORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM


def _row_date(value: Any) -> date:
    return value.date() if hasattr(value, "date") else value


def _is_reciprocal_completed(pair: list[GameScheduleORM]) -> bool:
    if len(pair) != 2:
        return False
    first, second = pair
    dates = {_row_date(row.game_date) for row in pair}
    return (
        first.team_id == second.opponent_team_id
        and second.team_id == first.opponent_team_id
        and len(dates) == 1
        and all(row.result in {"W", "L"} for row in pair)
    )


def _has_team_stats_pair(
    rows: list[TeamGameStatsORM],
    schedule_pair: list[GameScheduleORM],
) -> bool:
    if len(rows) != 2:
        return False
    schedule_teams = {int(row.team_id) for row in schedule_pair}
    return {int(row.team_id) for row in rows} == schedule_teams


def build_player_game_fact_coverage_report(
    db: Session,
    *,
    season: str,
    season_type: str,
    max_batch_size: int = 25,
) -> dict[str, Any]:
    """Return a season/game coverage report without writing to PostgreSQL."""
    if not 1 <= max_batch_size <= 25:
        raise ValueError("max_batch_size must be between 1 and 25")

    schedule_rows = (
        db.query(GameScheduleORM)
        .filter(
            GameScheduleORM.season == season,
            GameScheduleORM.season_type == season_type,
        )
        .all()
    )
    team_stats_rows = (
        db.query(TeamGameStatsORM)
        .filter(TeamGameStatsORM.season == season)
        .all()
    )
    legacy_rows = db.query(GameLogORM).filter(GameLogORM.season == season).all()
    traditional_rows = (
        db.query(PlayerGameFactORM)
        .filter(
            PlayerGameFactORM.season == season,
            PlayerGameFactORM.season_type == season_type,
        )
        .all()
    )
    advanced_rows = (
        db.query(PlayerGameAdvancedFactORM)
        .filter(
            PlayerGameAdvancedFactORM.season == season,
            PlayerGameAdvancedFactORM.season_type == season_type,
        )
        .all()
    )

    schedule_by_game: dict[str, list[GameScheduleORM]] = defaultdict(list)
    stats_by_game: dict[str, list[TeamGameStatsORM]] = defaultdict(list)
    legacy_by_game: dict[str, int] = defaultdict(int)
    traditional_by_game: dict[str, int] = defaultdict(int)
    advanced_by_game: dict[str, int] = defaultdict(int)
    for row in schedule_rows:
        schedule_by_game[str(row.game_id)].append(row)
    for row in team_stats_rows:
        stats_by_game[str(row.game_id)].append(row)
    for row in legacy_rows:
        legacy_by_game[str(row.game_id)] += 1
    for row in traditional_rows:
        traditional_by_game[str(row.canonical_game_id)] += 1
    for row in advanced_rows:
        advanced_by_game[str(row.canonical_game_id)] += 1

    games: list[dict[str, Any]] = []
    for game_id, pair in schedule_by_game.items():
        if not _is_reciprocal_completed(pair):
            continue
        game_date = _row_date(pair[0].game_date)
        has_stats_pair = _has_team_stats_pair(stats_by_game[game_id], pair)
        traditional_count = traditional_by_game[game_id]
        advanced_count = advanced_by_game[game_id]
        if not has_stats_pair:
            state = "blocked_team_stats"
        elif traditional_count == 0:
            state = "traditional_missing"
        elif advanced_count == 0:
            state = "advanced_missing"
        else:
            state = "covered"
        games.append(
            {
                "game_id": game_id,
                "game_date": game_date.isoformat(),
                "schedule_rows": len(pair),
                "team_stats_rows": len(stats_by_game[game_id]),
                "team_stats_pair": has_stats_pair,
                "legacy_player_rows": legacy_by_game[game_id],
                "traditional_facts": traditional_count,
                "advanced_facts": advanced_count,
                "state": state,
            }
        )

    games.sort(key=lambda row: (row["game_date"], row["game_id"]))
    traditional_missing = [
        row["game_id"] for row in games if row["state"] == "traditional_missing"
    ]
    advanced_missing = [
        row["game_id"]
        for row in games
        if row["state"] in {"traditional_missing", "advanced_missing"}
    ]
    blocked = [row for row in games if row["state"] == "blocked_team_stats"]

    return {
        "season": season,
        "season_type": season_type,
        "max_batch_size": max_batch_size,
        "schedule_rows": len(schedule_rows),
        "schedule_game_ids": len(schedule_by_game),
        "eligible_completed_games": len(games),
        "completed_date_min": games[0]["game_date"] if games else None,
        "completed_date_max": games[-1]["game_date"] if games else None,
        "team_stats_game_ids": len(stats_by_game),
        "legacy_game_ids": len(legacy_by_game),
        "traditional_covered_games": sum(row["traditional_facts"] > 0 for row in games),
        "advanced_covered_games": sum(row["advanced_facts"] > 0 for row in games),
        "traditional_missing_games": len(traditional_missing),
        "advanced_missing_games": len(advanced_missing),
        "blocked_games": len(blocked),
        "traditional_backfill_batches": [
            traditional_missing[index : index + max_batch_size]
            for index in range(0, len(traditional_missing), max_batch_size)
        ],
        "advanced_backfill_batches": [
            traditional_missing[index : index + max_batch_size]
            for index in range(0, len(traditional_missing), max_batch_size)
        ],
        "games": games,
    }
