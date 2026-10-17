"""Regression tests for fail-closed season team-stat ingestion."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.utils.fetch.team_fetcher import TeamFetcher, TeamSeasonStatsFetchResult


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
