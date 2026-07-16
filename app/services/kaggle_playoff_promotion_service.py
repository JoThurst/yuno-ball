"""Validated, idempotent promotion of staged Kaggle playoff schedules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection


EXPECTED_SOURCE_NAME = "kaggle-uploaded-pack"
EXPECTED_DATASET_NAME = "nba-team-game-facts"
EXPECTED_PARSER_VERSION = "kaggle-games-v1"


@dataclass(frozen=True)
class StagedPlayoffRow:
    game_id: str
    season: str
    game_date: date
    team_id: int
    opponent_team_id: int
    is_home: bool
    result: str
    points: int
    source_row_number: int
    source_row_sha256: str
    parser_version: str


@dataclass(frozen=True)
class CanonicalScheduleRow:
    game_id: str
    season: str
    game_date: date
    team_id: int
    opponent_team_id: int
    home_or_away: str
    result: str | None


@dataclass(frozen=True)
class PlayoffPromotionPlan:
    source_games: int
    already_matched_games: int
    candidate_games: int
    candidate_rows: Tuple[StagedPlayoffRow, ...]
    conflicts: Tuple[str, ...]

    @property
    def candidate_row_count(self) -> int:
        return len(self.candidate_rows)


@dataclass(frozen=True)
class PlayoffPromotionResult:
    source_games: int
    already_matched_games: int
    promoted_games: int
    inserted_schedule_rows: int
    updated_match_rows: int
    updated_promoted_rows: int
    persisted_external_games: int
    persisted_external_rows: int


def _source_pair_error(
    game_id: str,
    rows: Sequence[StagedPlayoffRow],
    valid_team_ids: set[int],
) -> str | None:
    if len(rows) != 2:
        return f"{game_id}:source_row_count"
    first, second = rows
    if first.season != second.season or first.game_date != second.game_date:
        return f"{game_id}:source_game_identity"
    if first.parser_version != EXPECTED_PARSER_VERSION or second.parser_version != EXPECTED_PARSER_VERSION:
        return f"{game_id}:parser_version"
    if not (
        first.team_id == second.opponent_team_id
        and first.opponent_team_id == second.team_id
    ):
        return f"{game_id}:reciprocal_teams"
    if {first.is_home, second.is_home} != {True, False}:
        return f"{game_id}:home_away_pair"
    if {first.result, second.result} != {"W", "L"}:
        return f"{game_id}:result_pair"
    if first.team_id not in valid_team_ids or second.team_id not in valid_team_ids:
        return f"{game_id}:unknown_team"
    winner = first if first.result == "W" else second
    loser = second if first.result == "W" else first
    if winner.points <= loser.points:
        return f"{game_id}:score_result_conflict"
    return None


def _canonical_pair_error(
    game_id: str,
    source: Sequence[StagedPlayoffRow],
    canonical: Sequence[CanonicalScheduleRow],
) -> str | None:
    if len(canonical) != 2:
        return f"{game_id}:canonical_row_count"
    if {row.team_id for row in canonical} != {row.team_id for row in source}:
        return f"{game_id}:canonical_teams"
    source_by_team = {row.team_id: row for row in source}
    for row in canonical:
        expected = source_by_team[row.team_id]
        if (
            row.opponent_team_id != expected.opponent_team_id
            or row.season != expected.season
            or row.game_date != expected.game_date
            or row.home_or_away != ("H" if expected.is_home else "A")
            or row.result != expected.result
        ):
            return f"{game_id}:canonical_identity_conflict"
    return None


def build_playoff_promotion_plan(
    staged_rows: Iterable[StagedPlayoffRow],
    canonical_rows: Iterable[CanonicalScheduleRow],
    valid_team_ids: Iterable[int],
) -> PlayoffPromotionPlan:
    """Partition exact playoff games into matched, promotable, or blocked."""
    staged_by_game: Dict[str, list[StagedPlayoffRow]] = defaultdict(list)
    canonical_by_game: Dict[str, list[CanonicalScheduleRow]] = defaultdict(list)
    for row in staged_rows:
        staged_by_game[row.game_id].append(row)
    for row in canonical_rows:
        canonical_by_game[row.game_id].append(row)

    valid_ids = {int(value) for value in valid_team_ids}
    matched = 0
    candidates = []
    conflicts = []
    for game_id in sorted(staged_by_game):
        source = sorted(staged_by_game[game_id], key=lambda row: row.team_id)
        error = _source_pair_error(game_id, source, valid_ids)
        if error:
            conflicts.append(error)
            continue
        canonical = canonical_by_game.get(game_id, [])
        if not canonical:
            candidates.extend(source)
            continue
        error = _canonical_pair_error(game_id, source, canonical)
        if error:
            conflicts.append(error)
        else:
            matched += 1

    return PlayoffPromotionPlan(
        source_games=len(staged_by_game),
        already_matched_games=matched,
        candidate_games=len({row.game_id for row in candidates}),
        candidate_rows=tuple(candidates),
        conflicts=tuple(conflicts),
    )


def _validate_manifest(connection: Connection, source_import_id: str) -> None:
    manifest = connection.execute(
        text(
            """
            SELECT source_name, dataset_name, license_status,
                   commercial_use_status, validation_status
            FROM external_dataset_imports
            WHERE import_id = :source_import_id
            """
        ),
        {"source_import_id": source_import_id},
    ).mappings().one_or_none()
    if manifest is None:
        raise ValueError(f"Unknown external dataset manifest: {source_import_id}")
    expected = {
        "source_name": EXPECTED_SOURCE_NAME,
        "dataset_name": EXPECTED_DATASET_NAME,
        "license_status": "approved_public",
        "commercial_use_status": "permitted",
    }
    mismatches = [
        key for key, value in expected.items() if manifest[key] != value
    ]
    if manifest["validation_status"] not in {"registered", "profiled"}:
        mismatches.append("validation_status")
    if mismatches:
        raise ValueError(
            "Manifest is not eligible for playoff promotion: "
            + ", ".join(sorted(set(mismatches)))
        )


def load_playoff_promotion_plan(
    connection: Connection,
    *,
    source_import_id: str,
    lock_staging: bool = False,
) -> PlayoffPromotionPlan:
    """Load the exact eligible playoff scope and build a deterministic plan."""
    _validate_manifest(connection, source_import_id)
    scope_counts = connection.execute(
        text(
            """
            SELECT count(*) AS eligible_rows,
                   count(*) FILTER (
                       WHERE result_status = 'final'
                         AND date_status = 'parsed'
                   ) AS promotable_rows
            FROM stg_kaggle_games
            WHERE source_import_id = :source_import_id
              AND promotion_eligibility = 'eligible_market_range'
              AND season_type = 'Playoffs'
            """
        ),
        {"source_import_id": source_import_id},
    ).mappings().one()
    if int(scope_counts["eligible_rows"]) != int(scope_counts["promotable_rows"]):
        raise ValueError(
            "Eligible playoff scope contains an unparsed date or non-final result"
        )
    lock_clause = " FOR SHARE" if lock_staging else ""
    staged = connection.execute(
        text(
            """
            SELECT game_id, season, game_date, team_id, opponent_team_id,
                   is_home, wl, pts, source_row_number, row_sha256,
                   parser_version
            FROM stg_kaggle_games
            WHERE source_import_id = :source_import_id
              AND promotion_eligibility = 'eligible_market_range'
              AND season_type = 'Playoffs'
              AND result_status = 'final'
              AND date_status = 'parsed'
            ORDER BY game_id, team_id
            """
            + lock_clause
        ),
        {"source_import_id": source_import_id},
    ).mappings().all()
    if not staged:
        raise ValueError("Manifest has no eligible staged playoff rows")
    staged_rows = tuple(
        StagedPlayoffRow(
            game_id=str(row["game_id"]),
            season=str(row["season"]),
            game_date=row["game_date"],
            team_id=int(row["team_id"]),
            opponent_team_id=int(row["opponent_team_id"]),
            is_home=bool(row["is_home"]),
            result=str(row["wl"]),
            points=int(row["pts"]),
            source_row_number=int(row["source_row_number"]),
            source_row_sha256=str(row["row_sha256"]),
            parser_version=str(row["parser_version"]),
        )
        for row in staged
    )
    canonical = connection.execute(
        text(
            """
            SELECT gs.game_id, gs.season, gs.game_date::date AS game_date,
                   gs.team_id, gs.opponent_team_id, gs.home_or_away, gs.result
            FROM game_schedule gs
            WHERE gs.game_id IN (
                SELECT DISTINCT game_id
                FROM stg_kaggle_games
                WHERE source_import_id = :source_import_id
                  AND promotion_eligibility = 'eligible_market_range'
                  AND season_type = 'Playoffs'
                  AND result_status = 'final'
                  AND date_status = 'parsed'
            )
            ORDER BY gs.game_id, gs.team_id
            """
        ),
        {"source_import_id": source_import_id},
    ).mappings().all()
    canonical_rows = tuple(
        CanonicalScheduleRow(
            game_id=str(row["game_id"]),
            season=str(row["season"]),
            game_date=row["game_date"],
            team_id=int(row["team_id"]),
            opponent_team_id=int(row["opponent_team_id"]),
            home_or_away=str(row["home_or_away"]),
            result=row["result"],
        )
        for row in canonical
    )
    team_ids = connection.execute(text("SELECT team_id FROM teams")).scalars().all()
    return build_playoff_promotion_plan(staged_rows, canonical_rows, team_ids)


def apply_playoff_promotion(
    connection: Connection,
    *,
    source_import_id: str,
    source_run_id: str,
) -> PlayoffPromotionResult:
    """Promote one validated plan atomically on the caller's transaction."""
    plan = load_playoff_promotion_plan(
        connection,
        source_import_id=source_import_id,
        lock_staging=True,
    )
    if plan.conflicts:
        raise ValueError(
            f"Playoff promotion blocked by {len(plan.conflicts)} conflict(s): "
            + ", ".join(plan.conflicts[:10])
        )

    score_by_team = {
        (row.game_id, row.team_id): row.points for row in plan.candidate_rows
    }
    payloads = [
        {
            "game_id": row.game_id,
            "season": row.season,
            "season_type": "Playoffs",
            "team_id": row.team_id,
            "opponent_team_id": row.opponent_team_id,
            "game_date": row.game_date,
            "game_date_precision": "date_only",
            "home_or_away": "H" if row.is_home else "A",
            "result": row.result,
            "score": f"{row.points}-{score_by_team[(row.game_id, row.opponent_team_id)]}",
            "team_score": row.points,
            "opponent_score": score_by_team[(row.game_id, row.opponent_team_id)],
            "source_name": EXPECTED_SOURCE_NAME,
            "source_import_id": source_import_id,
            "source_run_id": source_run_id,
            "source_row_number": row.source_row_number,
            "source_row_sha256": row.source_row_sha256,
            "source_parser_version": row.parser_version,
        }
        for row in plan.candidate_rows
    ]
    inserted = 0
    if payloads:
        result = connection.execute(
            text(
                """
                INSERT INTO game_schedule (
                    game_id, season, season_type, team_id, opponent_team_id,
                    game_date, game_date_precision, home_or_away, result, score,
                    team_score, opponent_score, source_name, source_import_id,
                    source_run_id, source_row_number, source_row_sha256,
                    source_parser_version
                ) VALUES (
                    :game_id, :season, :season_type, :team_id, :opponent_team_id,
                    :game_date, :game_date_precision, :home_or_away, :result, :score,
                    :team_score, :opponent_score, :source_name, :source_import_id,
                    :source_run_id, :source_row_number, :source_row_sha256,
                    :source_parser_version
                )
                """
            ),
            payloads,
        )
        inserted = int(result.rowcount or 0)
        if inserted != len(payloads):
            raise ValueError("Canonical insert count does not match the promotion plan")

    candidate_ids = sorted({row.game_id for row in plan.candidate_rows})
    promoted_status_rows = 0
    if candidate_ids:
        promoted_status_rows = int(
            connection.execute(
                text(
                    """
                    UPDATE stg_kaggle_games
                    SET validation_status = 'promoted'
                    WHERE source_import_id = :source_import_id
                      AND game_id = ANY(CAST(:candidate_ids AS varchar[]))
                      AND validation_status <> 'promoted'
                    """
                ),
                {
                    "source_import_id": source_import_id,
                    "candidate_ids": candidate_ids,
                },
            ).rowcount
            or 0
        )
    matched_status_rows = int(
        connection.execute(
            text(
                """
                UPDATE stg_kaggle_games
                SET canonical_match_status = 'matched'
                WHERE source_import_id = :source_import_id
                  AND promotion_eligibility = 'eligible_market_range'
                  AND season_type = 'Playoffs'
                  AND canonical_match_status <> 'matched'
                """
            ),
            {"source_import_id": source_import_id},
        ).rowcount
        or 0
    )

    persisted = connection.execute(
        text(
            """
            SELECT count(*) AS row_count, count(DISTINCT game_id) AS game_count
            FROM game_schedule
            WHERE source_import_id = :source_import_id
              AND source_name = 'kaggle-uploaded-pack'
              AND season_type = 'Playoffs'
            """
        ),
        {"source_import_id": source_import_id},
    ).mappings().one()
    final_plan = load_playoff_promotion_plan(
        connection,
        source_import_id=source_import_id,
        lock_staging=False,
    )
    if final_plan.conflicts or final_plan.candidate_games:
        raise ValueError("Post-insert reconciliation did not reach exact coverage")
    if final_plan.already_matched_games != final_plan.source_games:
        raise ValueError("Post-insert playoff match count is incomplete")
    return PlayoffPromotionResult(
        source_games=plan.source_games,
        already_matched_games=plan.already_matched_games,
        promoted_games=plan.candidate_games,
        inserted_schedule_rows=inserted,
        updated_match_rows=matched_status_rows,
        updated_promoted_rows=promoted_status_rows,
        persisted_external_games=int(persisted["game_count"]),
        persisted_external_rows=int(persisted["row_count"]),
    )
