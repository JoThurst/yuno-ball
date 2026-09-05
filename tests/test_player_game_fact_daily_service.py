"""Focused tests for the daily canonical player-fact selector."""

from datetime import date
from types import SimpleNamespace

from app.services.player_game_fact_daily_service import (
    select_pending_completed_game_ids,
)


def _pair(game_id: str, *, result: str = "W"):
    game_date = date(2026, 4, 1)
    return [
        SimpleNamespace(
            game_id=game_id,
            game_date=game_date,
            team_id=1,
            opponent_team_id=2,
            result=result,
        ),
        SimpleNamespace(
            game_id=game_id,
            game_date=game_date,
            team_id=2,
            opponent_team_id=1,
            result="L" if result == "W" else result,
        ),
    ]


def test_selector_returns_completed_game_missing_either_canonical_source():
    rows = _pair("game-1") + _pair("game-2") + _pair("game-3")

    pending = select_pending_completed_game_ids(
        rows,
        traditional_game_ids={"game-2"},
        advanced_game_ids={"game-3"},
    )

    assert pending == ["game-1", "game-2", "game-3"]


def test_selector_excludes_games_with_both_sources():
    assert select_pending_completed_game_ids(
        _pair("game-1"),
        traditional_game_ids={"game-1"},
        advanced_game_ids={"game-1"},
    ) == []


def test_selector_ignores_unfinished_nonreciprocal_and_incomplete_pairs():
    unfinished = _pair("game-1", result="")
    nonreciprocal = _pair("game-2")
    nonreciprocal[1].opponent_team_id = 99
    incomplete = _pair("game-3")[:1]

    assert select_pending_completed_game_ids(
        unfinished + nonreciprocal + incomplete,
        traditional_game_ids=set(),
        advanced_game_ids=set(),
    ) == []
