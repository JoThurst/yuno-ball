"""Small, fail-closed classifiers for starter and availability coverage."""

from __future__ import annotations


def classify_starter_game_coverage(*, starter_rows: int, team_count: int) -> str:
    """Classify explicit starter evidence for one completed game."""
    if starter_rows == 10 and team_count == 2:
        return "complete"
    if starter_rows > 0:
        return "partial"
    return "missing"


def classify_availability_team_coverage(
    *,
    pregame_observation_rows: int,
    pregame_submission_rows: int,
    any_observation_rows: int,
) -> str:
    """Classify one game-team without treating an absent report as available."""
    if pregame_observation_rows or pregame_submission_rows:
        return "reported"
    if any_observation_rows:
        return "postgame_only"
    return "unknown"
