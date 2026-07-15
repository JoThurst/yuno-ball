"""Fail-closed contract tests for bounded schedule result reconciliation."""

from datetime import date
from unittest.mock import patch

import app.services.schedule_result_reconciliation_service as reconciliation_service
from app.services.schedule_result_reconciliation_service import (
    ScheduleResultSource,
    TeamGameResultSource,
    build_schedule_result_plan,
)


GAME_DATE = date(2026, 3, 3)


def _schedule(team_id, opponent_id, side, result=None, score=None, game_id="0022500911"):
    return ScheduleResultSource(
        game_id=game_id,
        season="2025-26",
        team_id=team_id,
        opponent_team_id=opponent_id,
        slate_date=GAME_DATE,
        home_or_away=side,
        result=result,
        score=score,
    )


def _team_game(team_id, opponent_id, result, points, game_id="0022500911"):
    return TeamGameResultSource(
        game_id=game_id,
        season="2025-26",
        team_id=team_id,
        opponent_team_id=opponent_id,
        game_date=GAME_DATE,
        result=result,
        points=points,
    )


def test_null_schedule_pair_builds_two_canonical_updates():
    plan = build_schedule_result_plan(
        [_schedule(10, 20, "H"), _schedule(20, 10, "A")],
        [_team_game(10, 20, "W", 112), _team_game(20, 10, "L", 105)],
    )

    assert plan.inspected_games == 1
    assert plan.eligible_games == 1
    assert plan.already_complete_games == 0
    assert not plan.issues
    assert {(row.team_id, row.result, row.score) for row in plan.updates} == {
        (10, "W", "112-105"),
        (20, "L", "112-105"),
    }


def test_mixed_existing_schedule_result_blocks_the_game():
    plan = build_schedule_result_plan(
        [_schedule(10, 20, "H", result="W"), _schedule(20, 10, "A")],
        [_team_game(10, 20, "W", 112), _team_game(20, 10, "L", 105)],
    )

    assert not plan.updates
    assert "mixed null/non-null" in plan.issues[0].reason


def test_invalid_team_game_pair_blocks_the_game():
    plan = build_schedule_result_plan(
        [_schedule(10, 20, "H"), _schedule(20, 10, "A")],
        [_team_game(10, 20, "W", 112), _team_game(30, 10, "L", 105)],
    )

    assert not plan.updates
    assert "team-game pair is not reciprocal" in plan.issues[0].reason


def test_winner_points_must_exceed_loser_points():
    plan = build_schedule_result_plan(
        [_schedule(10, 20, "H"), _schedule(20, 10, "A")],
        [_team_game(10, 20, "W", 100), _team_game(20, 10, "L", 105)],
    )

    assert not plan.updates
    assert "W/L disagrees" in plan.issues[0].reason


def test_complete_schedule_pair_is_never_rewritten():
    plan = build_schedule_result_plan(
        [
            _schedule(10, 20, "H", result="W", score="112-105"),
            _schedule(20, 10, "A", result="L", score="112-105"),
        ],
        [],
    )

    assert plan.already_complete_games == 1
    assert not plan.updates
    assert not plan.issues


def test_conflicting_existing_score_blocks_the_game():
    plan = build_schedule_result_plan(
        [_schedule(10, 20, "H", score="99-98"), _schedule(20, 10, "A")],
        [_team_game(10, 20, "W", 112), _team_game(20, 10, "L", 105)],
    )

    assert not plan.updates
    assert "score disagrees" in plan.issues[0].reason


def test_zero_zero_placeholder_is_replaced_by_canonical_score():
    plan = build_schedule_result_plan(
        [_schedule(10, 20, "H", score="0-0"), _schedule(20, 10, "A", score="0-0")],
        [_team_game(10, 20, "W", 112), _team_game(20, 10, "L", 105)],
    )

    assert not plan.issues
    assert {row.score for row in plan.updates} == {"112-105"}


def test_ingestion_reconciliation_ignores_future_games_without_team_facts():
    completed_schedule = [
        _schedule(10, 20, "H", score="0-0"),
        _schedule(20, 10, "A", score="0-0"),
    ]
    future_schedule = [
        _schedule(30, 40, "H", game_id="0022500912"),
        _schedule(40, 30, "A", game_id="0022500912"),
    ]
    completed_stats = [
        _team_game(10, 20, "W", 112),
        _team_game(20, 10, "L", 105),
    ]

    with patch.object(
        reconciliation_service,
        "load_schedule_result_sources",
        return_value=(completed_schedule + future_schedule, completed_stats),
    ), patch.object(
        reconciliation_service,
        "apply_schedule_result_plan",
        return_value=2,
    ) as apply_plan:
        result = reconciliation_service.reconcile_schedule_results_from_team_stats(
            object(),
            season="2025-26",
        )

    planned = apply_plan.call_args.args[1]
    assert planned.inspected_games == 1
    assert planned.eligible_games == 1
    assert result == {
        "source_games": 1,
        "inspected_games": 1,
        "eligible_games": 1,
        "already_complete_games": 0,
        "updated_rows": 2,
    }
