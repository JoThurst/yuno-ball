"""Regression tests for fail-closed season team-stat ingestion."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.utils.fetch.team_fetcher import (
    TeamFetcher,
    TeamSeasonStatsFetchResult,
    _has_completed_regular_season_game,
)


def test_team_stats_season_raises_when_one_team_fetch_fails():
    teams = [SimpleNamespace(team_id=1), SimpleNamespace(team_id=2)]
    outcomes = [
        TeamSeasonStatsFetchResult(1, "2022-23", True, rows=82),
        TeamSeasonStatsFetchResult(
            2,
            "2022-23",
            False,
            error="SSLError: proxy request failed",
        ),
    ]

    context = patch(
        "app.utils.fetch.team_fetcher.get_db_context"
    )
    with context as get_db_context, patch(
        "app.utils.fetch.team_fetcher.TeamORM.get_all", return_value=teams
    ), patch.object(
        TeamFetcher,
        "_fetch_team_season_stats",
        side_effect=outcomes,
    ):
        get_db_context.return_value.__enter__.return_value = object()
        with pytest.raises(RuntimeError, match="team 2: SSLError: proxy request failed"):
            TeamFetcher().fetch_team_game_stats_for_season("2022-23")


def test_team_stats_season_returns_summary_when_all_teams_succeed():
    teams = [SimpleNamespace(team_id=1), SimpleNamespace(team_id=2)]
    outcomes = [
        TeamSeasonStatsFetchResult(1, "2022-23", True, rows=82),
        TeamSeasonStatsFetchResult(2, "2022-23", True, rows=82),
    ]

    context = patch(
        "app.utils.fetch.team_fetcher.get_db_context"
    )
    with context as get_db_context, patch(
        "app.utils.fetch.team_fetcher.TeamORM.get_all", return_value=teams
    ), patch.object(
        TeamFetcher,
        "_fetch_team_season_stats",
        side_effect=outcomes,
    ):
        get_db_context.return_value.__enter__.return_value = object()
        result = TeamFetcher().fetch_team_game_stats_for_season("2022-23")

    assert result == {
        "season": "2022-23",
        "teams_succeeded": 2,
        "team_rows_processed": 164,
    }


def test_schedule_classifies_preseason_only_team_as_no_eligible_regular_games():
    schedule_rows = [
        SimpleNamespace(season_type="Pre Season", result="W", game_date=datetime(2026, 10, 1), score="100-90"),
        SimpleNamespace(season_type="Regular Season", result=None, game_date=datetime(2026, 10, 23), score=None),
    ]

    assert _has_completed_regular_season_game(
        schedule_rows, as_of=date(2026, 10, 22)
    ) is False


def test_schedule_classifies_completed_regular_game_as_eligible():
    schedule_rows = [
        SimpleNamespace(season_type="Regular Season", result="W", game_date=datetime(2026, 10, 21), score="110-100"),
    ]

    assert _has_completed_regular_season_game(schedule_rows) is True


def test_missing_regular_schedule_is_unknown_not_no_games():
    assert _has_completed_regular_season_game([]) is None


def test_past_null_result_is_unresolved_not_no_games_yet():
    schedule_rows = [
        SimpleNamespace(
            season_type="Regular Season",
            result=None,
            game_date=datetime(2026, 10, 21, 23, 30),
            score=None,
        ),
    ]

    assert _has_completed_regular_season_game(
        schedule_rows, as_of=date(2026, 10, 22)
    ) is None


def test_same_day_score_with_null_result_is_unresolved():
    schedule_rows = [
        SimpleNamespace(
            season_type="Regular Season",
            result=None,
            game_date=datetime(2026, 10, 22, 19, 30),
            score="117-109",
        ),
    ]

    assert _has_completed_regular_season_game(
        schedule_rows, as_of=date(2026, 10, 22)
    ) is None


def test_team_with_no_completed_regular_game_skips_empty_provider_request():
    team = SimpleNamespace(team_id=1)
    schedule_rows = [
        SimpleNamespace(season_type="Pre Season", result="W", game_date=datetime(2026, 10, 1), score="100-90"),
        SimpleNamespace(season_type="Regular Season", result=None, game_date=datetime(2099, 10, 23), score=None),
    ]
    with patch("app.utils.fetch.team_fetcher.get_db_context") as db_context, patch(
        "app.utils.fetch.team_fetcher.GameScheduleORM.get_by_team",
        return_value=schedule_rows,
    ), patch.object(TeamFetcher, "create_endpoint") as create_endpoint:
        db_context.return_value.__enter__.return_value = object()
        result = TeamFetcher()._fetch_team_season_stats(team, "2026-27")

    assert result == TeamSeasonStatsFetchResult(1, "2026-27", True, rows=0)
    create_endpoint.assert_not_called()


def test_empty_provider_response_still_fails_when_completed_game_exists():
    team = SimpleNamespace(team_id=1)
    schedule_rows = [
        SimpleNamespace(season_type="Regular Season", result="W"),
    ]
    endpoint = SimpleNamespace(
        get_dict=lambda: {"resultSets": [{"headers": [], "rowSet": []}]}
    )
    with patch("app.utils.fetch.team_fetcher.get_db_context") as db_context, patch(
        "app.utils.fetch.team_fetcher.GameScheduleORM.get_by_team",
        return_value=schedule_rows,
    ), patch.object(TeamFetcher, "create_endpoint", return_value=endpoint):
        db_context.return_value.__enter__.return_value = object()
        result = TeamFetcher()._fetch_team_season_stats(team, "2026-27")

    assert result.succeeded is False
    assert "No rows returned" in result.error
