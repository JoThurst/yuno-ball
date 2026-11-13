"""Read-only, date-bounded quality gate for a completed NBA slate."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameFactORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.services.player_game_fact_reconciliation_service import build_reconciliation_report


def _problems_for_game(schedule: list[Any], team_stats: list[Any], legacy_count: int,
                       traditional_count: int, advanced_count: int) -> list[str]:
    problems: list[str] = []
    if len(schedule) != 2:
        return ["schedule_pair_missing"]
    first, second = schedule
    if (first.team_id != second.opponent_team_id
            or second.team_id != first.opponent_team_id
            or {first.home_or_away, second.home_or_away} != {"H", "A"}):
        problems.append("schedule_pair_not_reciprocal")
    if {first.result, second.result} != {"W", "L"}:
        problems.append("final_result_missing_or_conflicting")
    if (first.team_score is None or second.team_score is None
            or first.team_score != second.opponent_score
            or second.team_score != first.opponent_score):
        problems.append("final_score_missing_or_conflicting")
    if (len(team_stats) != 2
            or {row.team_id for row in team_stats} != {first.team_id, second.team_id}
            or any(row.opponent_team_id not in {first.team_id, second.team_id} - {row.team_id}
                   for row in team_stats)):
        problems.append("team_stats_pair_missing_or_conflicting")
    else:
        scores = {row.team_id: row.pts for row in team_stats}
        for row in schedule:
            if scores[row.team_id] is None or scores[row.team_id] != row.team_score:
                problems.append("team_points_disagree_with_schedule")
                break
        for row in team_stats:
            opponent_points = scores[row.opponent_team_id]
            if (row.wl != next(s.result for s in schedule if s.team_id == row.team_id)
                    or (row.pts is not None and opponent_points is not None
                        and row.plus_minus != row.pts - opponent_points)):
                problems.append("team_result_or_margin_conflict")
                break
    if legacy_count == 0:
        problems.append("legacy_gamelogs_missing")
    if traditional_count == 0:
        problems.append("traditional_facts_missing")
    if advanced_count == 0:
        problems.append("advanced_facts_missing")
    return problems


def _utc_slate_bounds(target_date: date) -> tuple[datetime, datetime]:
    """Return UTC-naive DB bounds for one Eastern NBA slate date."""
    eastern = ZoneInfo("America/New_York")
    return tuple(
        datetime.combine(day, datetime.min.time(), eastern)
        .astimezone(timezone.utc).replace(tzinfo=None)
        for day in (target_date, target_date + timedelta(days=1))
    )


def build_completed_slate_audit(db: Session, *, season: str, target_date: date,
                                expected_games: int) -> dict[str, Any]:
    """Inspect one known completed Regular Season slate; never infer an empty slate is healthy."""
    if not 1 <= expected_games <= 25:
        raise ValueError("expected_games must be between 1 and 25")
    # game_schedule stores UTC tipoffs as naive timestamps. Bound the Eastern
    # slate in UTC so late games do not fall onto the next local calendar day.
    start, end = _utc_slate_bounds(target_date)
    schedule = (db.query(GameScheduleORM)
                .filter(GameScheduleORM.season == season,
                        GameScheduleORM.season_type == "Regular Season",
                        GameScheduleORM.game_date >= start,
                        GameScheduleORM.game_date < end).all())
    by_game: dict[str, list[Any]] = defaultdict(list)
    for row in schedule:
        by_game[str(row.game_id)].append(row)
    game_ids = sorted(by_game)
    if game_ids:
        stats = db.query(TeamGameStatsORM).filter(TeamGameStatsORM.game_id.in_(game_ids)).all()
        logs = db.query(GameLogORM).filter(GameLogORM.game_id.in_(game_ids)).all()
        traditional = (db.query(PlayerGameFactORM)
                       .filter(PlayerGameFactORM.canonical_game_id.in_(game_ids)).all())
        advanced = (db.query(PlayerGameAdvancedFactORM)
                    .filter(PlayerGameAdvancedFactORM.canonical_game_id.in_(game_ids)).all())
    else:
        stats, logs, traditional, advanced = [], [], [], []
    stats_by_game: dict[str, list[Any]] = defaultdict(list)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in stats:
        stats_by_game[str(row.game_id)].append(row)
    for rows, name, id_field in (
        (logs, "legacy_gamelogs", "game_id"),
        (traditional, "traditional_facts", "canonical_game_id"),
        (advanced, "advanced_facts", "canonical_game_id"),
    ):
        for row in rows:
            counts[str(getattr(row, id_field))][name] += 1

    games = []
    for game_id in game_ids:
        pair = by_game[game_id]
        game_counts = counts[game_id]
        problems = _problems_for_game(
            pair, stats_by_game[game_id], game_counts["legacy_gamelogs"],
            game_counts["traditional_facts"], game_counts["advanced_facts"],
        )
        games.append({
            "game_id": game_id,
            "schedule_rows": len(pair),
            "team_stats_rows": len(stats_by_game[game_id]),
            "legacy_gamelogs": game_counts["legacy_gamelogs"],
            "traditional_facts": game_counts["traditional_facts"],
            "advanced_facts": game_counts["advanced_facts"],
            "schedule_sources": sorted({row.source_name for row in pair}),
            "problems": problems,
        })
    # Legacy logs are an independent compatibility lane. C5 can still prove
    # canonical Traditional/Advanced and team-score parity without them.
    reconciled_ids = [
        game["game_id"] for game in games
        if not (set(game["problems"]) - {"legacy_gamelogs_missing"})
    ]
    reconciliation = (build_reconciliation_report(
        db, season=season, game_ids=reconciled_ids, max_games=25,
    ) if reconciled_ids else None)
    passed = (len(game_ids) == expected_games and all(not game["problems"] for game in games)
              and reconciliation is not None and reconciliation["status"] == "passed")
    return {
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": season,
        "date": target_date.isoformat(),
        "expected_games": expected_games,
        "observed_games": len(game_ids),
        "status": "passed" if passed else "failed",
        "games": games,
        "canonical_reconciliation": reconciliation,
    }
