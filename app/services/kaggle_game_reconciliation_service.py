"""Pure classification rules for staged Kaggle games versus Yuno schedules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class SourceGameEvidence:
    game_id: str
    season: str
    season_type: str
    game_date: Optional[date]
    team_ids: Tuple[int, ...]
    opponent_team_ids: Tuple[int, ...]
    home_flags: Tuple[bool, ...]
    results: Tuple[Optional[str], ...]
    points: Tuple[Optional[int], ...]


@dataclass(frozen=True)
class CanonicalGameEvidence:
    row_count: int
    team_ids: Tuple[int, ...]
    opponent_team_ids: Tuple[int, ...]
    seasons: Tuple[str, ...]
    game_dates: Tuple[date, ...]
    home_or_away: Tuple[str, ...]
    results: Tuple[Optional[str], ...]


@dataclass(frozen=True)
class GameReconciliationResult:
    status: str
    conflict_reasons: Tuple[str, ...]


@dataclass(frozen=True)
class PlayerGameDateEvidence:
    row_count: int
    dates: Tuple[date, ...]
    seasons: Tuple[str, ...]
    season_types: Tuple[str, ...]
    team_ids: Tuple[int, ...]


@dataclass(frozen=True)
class DateRepairResult:
    status: str
    proposed_date: Optional[date]
    conflict_reasons: Tuple[str, ...]


def _source_score_conflicts(source: SourceGameEvidence) -> Tuple[str, ...]:
    if len(source.points) != 2 or any(value is None for value in source.points):
        return ()
    if len(source.results) != 2 or set(source.results) != {"W", "L"}:
        return ()
    winner_index = source.results.index("W")
    loser_index = source.results.index("L")
    if source.points[winner_index] <= source.points[loser_index]:
        return ("source_score_result_conflict",)
    return ()


def classify_game(
    source: SourceGameEvidence,
    canonical: Optional[CanonicalGameEvidence],
) -> GameReconciliationResult:
    """Classify one exact NBA game ID without fuzzy identity guessing."""
    source_conflicts = list(_source_score_conflicts(source))
    if canonical is None or canonical.row_count == 0:
        return GameReconciliationResult(
            status=("conflict" if source_conflicts else "canonical_missing"),
            conflict_reasons=tuple(source_conflicts),
        )
    if canonical.row_count != 2:
        return GameReconciliationResult(
            status="canonical_incomplete",
            conflict_reasons=("canonical_row_count",),
        )

    reasons = source_conflicts
    if tuple(sorted(source.team_ids)) != tuple(sorted(canonical.team_ids)):
        reasons.append("team_ids")
    if tuple(sorted(source.opponent_team_ids)) != tuple(
        sorted(canonical.opponent_team_ids)
    ):
        reasons.append("opponent_team_ids")
    if set(canonical.seasons) != {source.season}:
        reasons.append("season")
    if source.game_date is not None and set(canonical.game_dates) != {
        source.game_date
    }:
        reasons.append("game_date")
    if set(canonical.home_or_away) != {"H", "A"}:
        reasons.append("home_away_pair")
    if set(canonical.results) != {"W", "L"}:
        reasons.append("result_pair")
    return GameReconciliationResult(
        status="conflict" if reasons else "matched",
        conflict_reasons=tuple(sorted(set(reasons))),
    )


def classify_date_repair(
    source: SourceGameEvidence,
    player_evidence: Optional[PlayerGameDateEvidence],
) -> DateRepairResult:
    """Propose a missing source date only from unanimous player-game evidence."""
    if source.game_date is not None:
        return DateRepairResult("not_needed", source.game_date, ())
    if player_evidence is None or player_evidence.row_count == 0:
        return DateRepairResult("unavailable", None, ("no_player_game_rows",))

    reasons = []
    if len(player_evidence.dates) != 1:
        reasons.append("ambiguous_player_game_dates")
    if set(player_evidence.seasons) != {source.season}:
        reasons.append("player_game_season")
    if set(player_evidence.season_types) != {source.season_type}:
        reasons.append("player_game_season_type")
    if set(player_evidence.team_ids) != set(source.team_ids):
        reasons.append("player_game_team_ids")
    if reasons:
        return DateRepairResult("conflict", None, tuple(sorted(reasons)))
    return DateRepairResult("unique_repair", player_evidence.dates[0], ())
