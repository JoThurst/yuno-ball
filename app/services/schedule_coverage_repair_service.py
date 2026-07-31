"""Fail-closed planning and promotion for bounded canonical schedule coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Connection


_IDENTITY_FIELDS = (
    "season",
    "season_type",
    "team_id",
    "opponent_team_id",
    "home_or_away",
)


@dataclass(frozen=True)
class ScheduleCoveragePlan:
    source_games: int
    already_matched_games: int
    candidate_rows: tuple[Mapping[str, object], ...]
    conflicts: tuple[str, ...]

    @property
    def candidate_games(self) -> int:
        return len({str(row["game_id"]) for row in self.candidate_rows})


@dataclass(frozen=True)
class ScheduleIntegrityRepairPlan:
    source_games: int
    repair_rows: tuple[Mapping[str, object], ...]
    conflicts: tuple[str, ...]

    @property
    def repair_games(self) -> int:
        return len({str(row["game_id"]) for row in self.repair_rows})


def _group(rows: Iterable[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["game_id"]), []).append(row)
    return grouped


def _same_schedule_row(source: Mapping[str, object], existing: Mapping[str, object]) -> bool:
    if not all(source[field] == existing[field] for field in _IDENTITY_FIELDS):
        return False
    source_date = source["game_date"]
    existing_date = existing["game_date"]
    return getattr(source_date, "date", lambda: source_date)() == getattr(
        existing_date, "date", lambda: existing_date
    )()


def build_schedule_coverage_plan(
    source_rows: Sequence[Mapping[str, object]],
    existing_rows: Sequence[Mapping[str, object]],
    valid_team_ids: Iterable[int],
) -> ScheduleCoveragePlan:
    """Build an exact two-row promotion plan without changing database state."""
    source_by_game = _group(source_rows)
    existing_by_game = _group(existing_rows)
    valid_teams = {int(team_id) for team_id in valid_team_ids}
    conflicts: list[str] = []
    candidates: list[Mapping[str, object]] = []
    already_matched = 0

    for game_id in sorted(source_by_game):
        rows = sorted(source_by_game[game_id], key=lambda row: str(row["home_or_away"]))
        if len(rows) != 2:
            conflicts.append(f"{game_id}: source row count is {len(rows)}, expected 2")
            continue
        team_ids = {int(row["team_id"]) for row in rows}
        opponent_pairs = {
            (int(row["team_id"]), int(row["opponent_team_id"])) for row in rows
        }
        sides = {str(row["home_or_away"]) for row in rows}
        if not team_ids <= valid_teams:
            conflicts.append(f"{game_id}: source contains unknown team IDs {sorted(team_ids - valid_teams)}")
            continue
        if sides != {"H", "A"} or len(team_ids) != 2:
            conflicts.append(f"{game_id}: source is not one reciprocal H/A pair")
            continue
        if len(opponent_pairs) != 2 or any(
            (opponent, team) not in opponent_pairs
            for team, opponent in opponent_pairs
        ):
            conflicts.append(f"{game_id}: source team/opponent rows are not reciprocal")
            continue

        existing = sorted(
            existing_by_game.get(game_id, ()),
            key=lambda row: str(row["home_or_away"]),
        )
        if not existing:
            candidates.extend(rows)
            continue
        if len(existing) != 2 or not all(
            any(_same_schedule_row(source, stored) for stored in existing)
            for source in rows
        ):
            conflicts.append(f"{game_id}: existing canonical rows conflict with source")
            continue
        already_matched += 1

    return ScheduleCoveragePlan(
        source_games=len(source_by_game),
        already_matched_games=already_matched,
        candidate_rows=tuple(candidates),
        conflicts=tuple(conflicts),
    )


def load_existing_schedule_rows(
    connection: Connection,
    *,
    season: str,
    season_types: Sequence[str],
) -> tuple[tuple[Mapping[str, object], ...], tuple[int, ...]]:
    rows = connection.execute(
        text(
            """
            SELECT game_id, season, season_type, team_id, opponent_team_id,
                   game_date, home_or_away, result, team_score, opponent_score
            FROM game_schedule
            WHERE season = :season
              AND season_type = ANY(CAST(:season_types AS varchar[]))
            ORDER BY game_id, team_id
            """
        ),
        {"season": season, "season_types": list(season_types)},
    ).mappings().all()
    team_ids = tuple(
        int(row[0])
        for row in connection.execute(text("SELECT team_id FROM teams ORDER BY team_id")).all()
    )
    return tuple(rows), team_ids


def apply_schedule_coverage_plan(
    connection: Connection,
    plan: ScheduleCoveragePlan,
    *,
    source_run_id: str,
) -> int:
    """Insert only the reviewed missing rows in the caller's transaction."""
    if plan.conflicts:
        raise ValueError(
            f"Schedule coverage promotion blocked by {len(plan.conflicts)} conflict(s): "
            + "; ".join(plan.conflicts[:10])
        )
    if not plan.candidate_rows:
        return 0

    payloads = [
        {
            **dict(row),
            "source_run_id": source_run_id,
        }
        for row in plan.candidate_rows
    ]
    result = connection.execute(
        text(
            """
            INSERT INTO game_schedule (
                game_id, season, season_type, team_id, opponent_team_id,
                game_date, game_date_precision, home_or_away, result, score,
                team_score, opponent_score, source_name, source_run_id,
                source_parser_version
            ) VALUES (
                :game_id, :season, :season_type, :team_id, :opponent_team_id,
                :game_date, :game_date_precision, :home_or_away, :result, :score,
                :team_score, :opponent_score, :source_name, :source_run_id,
                :source_parser_version
            )
            """
        ),
        payloads,
    )
    written = int(result.rowcount or 0)
    if written != len(payloads):
        raise ValueError(
            f"Schedule coverage insert count {written} did not match plan {len(payloads)}"
        )
    return written


def build_schedule_integrity_repair_plan(
    source_rows: Sequence[Mapping[str, object]],
    existing_rows: Sequence[Mapping[str, object]],
) -> ScheduleIntegrityRepairPlan:
    """Plan repairs for existing game IDs whose reciprocal rows are malformed."""
    source_by_game = _group(source_rows)
    existing_by_game = _group(existing_rows)
    repairs: list[Mapping[str, object]] = []
    conflicts: list[str] = []
    for game_id, source_game_rows in sorted(source_by_game.items()):
        existing_game_rows = existing_by_game.get(game_id, [])
        if len(source_game_rows) != 2 or len(existing_game_rows) != 2:
            continue
        source_teams = {int(row["team_id"]) for row in source_game_rows}
        existing_teams = {int(row["team_id"]) for row in existing_game_rows}
        if source_teams != existing_teams:
            continue
        source_sides = {str(row["home_or_away"]) for row in source_game_rows}
        existing_sides = {str(row["home_or_away"]) for row in existing_game_rows}
        reciprocal = all(
            int(row["opponent_team_id"]) in source_teams
            and int(row["opponent_team_id"]) != int(row["team_id"])
            for row in source_game_rows
        )
        malformed = existing_sides != {"H", "A"} or any(
            int(row["opponent_team_id"]) == int(row["team_id"])
            for row in existing_game_rows
        )
        if not reciprocal:
            conflicts.append(f"{game_id}: source pair is not reciprocal")
        elif malformed:
            repairs.extend(source_game_rows)
    return ScheduleIntegrityRepairPlan(
        source_games=len(source_by_game),
        repair_rows=tuple(repairs),
        conflicts=tuple(conflicts),
    )


def apply_schedule_integrity_repair_plan(
    connection: Connection,
    plan: ScheduleIntegrityRepairPlan,
    *,
    source_run_id: str,
) -> int:
    if plan.conflicts:
        raise ValueError("Schedule integrity repair blocked: " + "; ".join(plan.conflicts[:10]))
    if not plan.repair_rows:
        return 0
    result = connection.execute(
        text(
            """
            UPDATE game_schedule
            SET season = :season,
                season_type = :season_type,
                opponent_team_id = :opponent_team_id,
                game_date = :game_date,
                game_date_precision = :game_date_precision,
                home_or_away = :home_or_away,
                result = :result,
                score = :score,
                team_score = :team_score,
                opponent_score = :opponent_score,
                source_name = :source_name,
                source_run_id = :source_run_id,
                source_parser_version = :source_parser_version
            WHERE game_id = :game_id AND team_id = :team_id
            """
        ),
        [{**dict(row), "source_run_id": source_run_id} for row in plan.repair_rows],
    )
    written = int(result.rowcount or 0)
    if written != len(plan.repair_rows):
        raise ValueError(f"Schedule integrity update count {written} did not match plan {len(plan.repair_rows)}")
    return written
