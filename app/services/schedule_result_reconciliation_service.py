"""Fail-closed reconciliation of historical schedule results from team game facts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session

from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.utils.season_utils import normalize_season


MISSING_SCORE_SENTINELS = {None, "", "-", "0-0"}


@dataclass(frozen=True)
class ScheduleResultSource:
    game_id: str
    season: str
    team_id: int
    opponent_team_id: int
    slate_date: date
    home_or_away: str
    result: str | None
    score: str | None


@dataclass(frozen=True)
class TeamGameResultSource:
    game_id: str
    season: str
    team_id: int
    opponent_team_id: int
    game_date: date
    result: str | None
    points: int | None


@dataclass(frozen=True)
class ScheduleResultUpdate:
    game_id: str
    season: str
    team_id: int
    result: str
    score: str


@dataclass(frozen=True)
class ReconciliationIssue:
    game_id: str
    reason: str


@dataclass(frozen=True)
class ScheduleResultPlan:
    inspected_games: int
    eligible_games: int
    already_complete_games: int
    updates: tuple[ScheduleResultUpdate, ...]
    issues: tuple[ReconciliationIssue, ...]


class ScheduleResultReconciliationBlocked(RuntimeError):
    """Raised when a fail-closed invariant prevents applying the plan."""


def _reciprocal_team_pair(rows: Sequence[object]) -> bool:
    if len(rows) != 2:
        return False
    first, second = rows
    return (
        first.team_id == second.opponent_team_id
        and second.team_id == first.opponent_team_id
    )


def build_schedule_result_plan(
    schedule_rows: Iterable[ScheduleResultSource],
    team_game_rows: Iterable[TeamGameResultSource],
) -> ScheduleResultPlan:
    """Build a deterministic plan without modifying either source collection."""
    schedules_by_game: dict[str, list[ScheduleResultSource]] = defaultdict(list)
    stats_by_game: dict[str, list[TeamGameResultSource]] = defaultdict(list)
    for row in schedule_rows:
        schedules_by_game[str(row.game_id)].append(row)
    for row in team_game_rows:
        stats_by_game[str(row.game_id)].append(row)

    updates: list[ScheduleResultUpdate] = []
    issues: list[ReconciliationIssue] = []
    eligible_games = 0
    already_complete_games = 0

    for game_id in sorted(schedules_by_game):
        schedules = schedules_by_game[game_id]
        stats = stats_by_game.get(game_id, [])

        if len(schedules) != 2:
            issues.append(
                ReconciliationIssue(game_id, f"expected 2 schedule rows; found {len(schedules)}")
            )
            continue
        if not _reciprocal_team_pair(schedules):
            issues.append(ReconciliationIssue(game_id, "schedule team pair is not reciprocal"))
            continue
        if {row.home_or_away for row in schedules} != {"H", "A"}:
            issues.append(ReconciliationIssue(game_id, "schedule must contain one H and one A row"))
            continue
        if len({row.season for row in schedules}) != 1 or len(
            {row.slate_date for row in schedules}
        ) != 1:
            issues.append(ReconciliationIssue(game_id, "schedule rows disagree on season or date"))
            continue

        existing_results = [row.result for row in schedules]
        if all(value is not None for value in existing_results):
            if set(existing_results) == {"W", "L"}:
                already_complete_games += 1
            else:
                issues.append(
                    ReconciliationIssue(game_id, "existing schedule results are not a W/L pair")
                )
            continue
        if any(value is not None for value in existing_results):
            issues.append(
                ReconciliationIssue(game_id, "schedule has a mixed null/non-null result pair")
            )
            continue

        if len(stats) != 2:
            issues.append(
                ReconciliationIssue(game_id, f"expected 2 team-game rows; found {len(stats)}")
            )
            continue
        if not _reciprocal_team_pair(stats):
            issues.append(ReconciliationIssue(game_id, "team-game pair is not reciprocal"))
            continue
        if {row.team_id for row in schedules} != {row.team_id for row in stats}:
            issues.append(ReconciliationIssue(game_id, "schedule and team-game team IDs differ"))
            continue
        if len({row.season for row in stats}) != 1 or schedules[0].season != stats[0].season:
            issues.append(ReconciliationIssue(game_id, "schedule and team-game seasons differ"))
            continue
        if {row.game_date for row in stats} != {schedules[0].slate_date}:
            issues.append(ReconciliationIssue(game_id, "schedule and team-game dates differ"))
            continue
        if {row.result for row in stats} != {"W", "L"}:
            issues.append(ReconciliationIssue(game_id, "team-game rows are not a W/L pair"))
            continue
        if any(row.points is None for row in stats):
            issues.append(ReconciliationIssue(game_id, "team-game score is missing"))
            continue

        stats_by_team = {row.team_id: row for row in stats}
        winner = next(row for row in stats if row.result == "W")
        loser = next(row for row in stats if row.result == "L")
        if winner.points <= loser.points:
            issues.append(ReconciliationIssue(game_id, "W/L disagrees with team-game points"))
            continue

        home_schedule = next(row for row in schedules if row.home_or_away == "H")
        away_schedule = next(row for row in schedules if row.home_or_away == "A")
        home_points = stats_by_team[home_schedule.team_id].points
        away_points = stats_by_team[away_schedule.team_id].points
        canonical_score = f"{home_points}-{away_points}"
        conflicting_scores = {
            row.score
            for row in schedules
            if row.score not in MISSING_SCORE_SENTINELS and row.score != canonical_score
        }
        if conflicting_scores:
            issues.append(
                ReconciliationIssue(game_id, "existing schedule score disagrees with team-game points")
            )
            continue

        eligible_games += 1
        for schedule in schedules:
            source = stats_by_team[schedule.team_id]
            updates.append(
                ScheduleResultUpdate(
                    game_id=game_id,
                    season=schedule.season,
                    team_id=schedule.team_id,
                    result=str(source.result),
                    score=canonical_score,
                )
            )

    return ScheduleResultPlan(
        inspected_games=len(schedules_by_game),
        eligible_games=eligible_games,
        already_complete_games=already_complete_games,
        updates=tuple(updates),
        issues=tuple(issues),
    )


def load_schedule_result_sources(
    db: Session,
    *,
    season: str,
    from_date: date,
    to_date: date,
) -> tuple[list[ScheduleResultSource], list[TeamGameResultSource]]:
    """Load Regular Season schedule rows and their local team-game sources."""
    eastern_date = func.date(
        func.timezone(
            "America/New_York",
            func.timezone("UTC", GameScheduleORM.game_date),
        )
    )
    schedule_query_rows = (
        db.query(
            GameScheduleORM.game_id,
            GameScheduleORM.season,
            GameScheduleORM.team_id,
            GameScheduleORM.opponent_team_id,
            eastern_date.label("slate_date"),
            GameScheduleORM.home_or_away,
            GameScheduleORM.result,
            GameScheduleORM.score,
        )
        .filter(
            GameScheduleORM.season == season,
            func.ltrim(GameScheduleORM.game_id, "0").like("2%"),
            eastern_date.between(from_date, to_date),
        )
        .order_by(GameScheduleORM.game_date, GameScheduleORM.game_id, GameScheduleORM.team_id)
        .all()
    )
    schedule_rows = [ScheduleResultSource(*row) for row in schedule_query_rows]
    game_ids = sorted({row.game_id for row in schedule_rows})
    if not game_ids:
        return schedule_rows, []

    team_query_rows = (
        db.query(
            TeamGameStatsORM.game_id,
            TeamGameStatsORM.season,
            TeamGameStatsORM.team_id,
            TeamGameStatsORM.opponent_team_id,
            TeamGameStatsORM.game_date,
            TeamGameStatsORM.wl,
            TeamGameStatsORM.pts,
        )
        .filter(
            TeamGameStatsORM.season == season,
            TeamGameStatsORM.game_id.in_(game_ids),
        )
        .order_by(TeamGameStatsORM.game_date, TeamGameStatsORM.game_id, TeamGameStatsORM.team_id)
        .all()
    )
    return schedule_rows, [TeamGameResultSource(*row) for row in team_query_rows]


def apply_schedule_result_plan(db: Session, plan: ScheduleResultPlan) -> int:
    """Apply every eligible row atomically; a stale or ambiguous row rolls back all writes."""
    if plan.issues:
        raise ScheduleResultReconciliationBlocked(
            f"refusing to apply a plan with {len(plan.issues)} reconciliation issue(s)"
        )

    updated_rows = 0
    for candidate in plan.updates:
        statement = (
            update(GameScheduleORM)
            .where(
                GameScheduleORM.game_id == candidate.game_id,
                GameScheduleORM.team_id == candidate.team_id,
                GameScheduleORM.season == candidate.season,
                GameScheduleORM.result.is_(None),
                or_(
                    GameScheduleORM.score.is_(None),
                    GameScheduleORM.score == candidate.score,
                    GameScheduleORM.score.in_(("", "-", "0-0")),
                ),
            )
            .values(result=candidate.result, score=candidate.score)
        )
        result = db.execute(statement)
        if result.rowcount != 1:
            raise ScheduleResultReconciliationBlocked(
                "schedule row changed after planning; refusing partial reconciliation for "
                f"game={candidate.game_id} team={candidate.team_id}"
            )
        updated_rows += result.rowcount

    db.flush()
    return updated_rows


def reconcile_schedule_results_from_team_stats(
    db: Session,
    *,
    season: str,
) -> dict[str, int]:
    """Repair every eligible final Regular Season game during normal ingestion.

    Future schedule rows are deliberately excluded until at least one matching
    team-game fact exists. A partial or ambiguous team-game pair remains a hard
    failure so downstream calculations cannot publish against inconsistent
    completion state.
    """
    canonical_season = normalize_season(season)
    start_year = int(canonical_season[:4])
    schedule_rows, team_game_rows = load_schedule_result_sources(
        db,
        season=canonical_season,
        from_date=date(start_year, 7, 1),
        to_date=date(start_year + 1, 6, 30),
    )
    source_game_ids = {row.game_id for row in team_game_rows}
    source_schedule_rows = [
        row for row in schedule_rows if row.game_id in source_game_ids
    ]
    plan = build_schedule_result_plan(source_schedule_rows, team_game_rows)
    updated_rows = apply_schedule_result_plan(db, plan)
    return {
        "source_games": len(source_game_ids),
        "inspected_games": plan.inspected_games,
        "eligible_games": plan.eligible_games,
        "already_complete_games": plan.already_complete_games,
        "updated_rows": updated_rows,
    }
