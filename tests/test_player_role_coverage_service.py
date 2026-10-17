from app.services.player_role_coverage_service import (
    classify_availability_team_coverage,
    classify_starter_game_coverage,
)


def test_starter_coverage_requires_ten_rows_across_two_teams():
    assert classify_starter_game_coverage(starter_rows=10, team_count=2) == "complete"
    assert classify_starter_game_coverage(starter_rows=5, team_count=1) == "partial"
    assert classify_starter_game_coverage(starter_rows=0, team_count=0) == "missing"


def test_availability_absence_is_unknown_not_available():
    assert classify_availability_team_coverage(
        pregame_observation_rows=0, pregame_submission_rows=0, any_observation_rows=0
    ) == "unknown"
    assert classify_availability_team_coverage(
        pregame_observation_rows=0, pregame_submission_rows=1, any_observation_rows=0
    ) == "reported"
    assert classify_availability_team_coverage(
        pregame_observation_rows=0, pregame_submission_rows=0, any_observation_rows=1
    ) == "postgame_only"
