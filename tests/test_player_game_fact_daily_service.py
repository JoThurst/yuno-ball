"""Focused tests for the daily canonical player-fact selector."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.player_game_fact_daily_service import (
    build_daily_player_fact_replay_manifest,
    _publish_and_reconcile,
    select_pending_completed_game_ids,
    validate_daily_player_fact_replay_manifest,
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


def test_daily_manifest_preserves_one_game_scope_and_hashes():
    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1",
        season="2026-27",
        season_type="Regular Season",
        batches=[
            {
                "batch": 1,
                "game_ids": ["0022600001"],
                "traditional": [{"game_id": "0022600001", "response_sha256": "a" * 64}],
                "advanced": [{"game_id": "0022600001", "response_sha256": "b" * 64}],
            }
        ],
        status="completed",
    )

    assert validate_daily_player_fact_replay_manifest(manifest) == ["0022600001"]
    assert manifest["endpoints"] == {
        "traditional": "BoxScoreTraditionalV3",
        "advanced": "BoxScoreAdvancedV3",
    }


def test_daily_manifest_rejects_absent_or_overlapping_scope():
    with pytest.raises(ValueError, match="manifest version"):
        validate_daily_player_fact_replay_manifest({})

    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1",
        season="2026-27",
        season_type="Regular Season",
        batches=[
            {"batch": 1, "game_ids": ["g1"]},
            {"batch": 2, "game_ids": ["g1"]},
        ],
        status="partial",
    )
    with pytest.raises(ValueError, match="overlaps"):
        validate_daily_player_fact_replay_manifest(manifest)


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


def test_daily_batch_reconciliation_shares_transaction_and_rolls_back_on_failure():
    class Context:
        def __init__(self):
            self.db = object()
            self.entered = 0
            self.exit_args = None

        def __enter__(self):
            self.entered += 1
            return self.db

        def __exit__(self, *args):
            self.exit_args = args
            return False

    context = Context()
    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        return_value=context,
    ), patch(
        "app.services.player_game_fact_daily_service._resolve_missing_players",
        return_value={"requested": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_player_game_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_advanced_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.build_reconciliation_report",
        return_value={"status": "failed", "reason": "mismatch"},
    ) as reconcile:
        with pytest.raises(ValueError, match="C5 reconciliation failed"):
            _publish_and_reconcile(
                {"traditional_facts": [], "advanced_facts": [], "traditional_games": [], "advanced_games": []},
                season="2026-27",
                game_ids=["g1"],
                max_games=25,
            )

    assert context.entered == 1
    assert context.exit_args[0] is ValueError
    assert reconcile.call_args.args[0] is context.db


def test_daily_batch_publishes_role_history_only_after_reconciliation_passes():
    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    collected = {
        "traditional_facts": [{"canonical_game_id": "g1"}],
        "advanced_facts": [],
        "traditional_games": [],
        "advanced_games": [],
    }
    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        return_value=Context(),
    ), patch(
        "app.services.player_game_fact_daily_service._resolve_missing_players",
        return_value={"requested": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_player_game_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_advanced_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.build_reconciliation_report",
        return_value={"status": "passed"},
    ), patch(
        "app.services.player_game_fact_daily_service.role_history_records_from_facts",
        return_value=[{"role_history_id": "history-1"}],
    ) as build_history, patch(
        "app.services.player_game_fact_daily_service.publish_role_history",
        return_value=1,
    ) as publish_history:
        result = _publish_and_reconcile(
            collected,
            season="2026-27",
            game_ids=["g1"],
            max_games=25,
        )

    build_history.assert_called_once_with(collected["traditional_facts"])
    publish_history.assert_called_once()
    assert result["role_history_rows"] == 1
