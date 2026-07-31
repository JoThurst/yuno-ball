"""Contract tests for exact schedule coverage planning."""

from datetime import datetime

from app.services.schedule_coverage_repair_service import (
    build_schedule_coverage_plan,
)


def _row(game_id="0042500101", team_id=1, opponent_team_id=2, side="H"):
    home = side == "H"
    return {
        "game_id": game_id,
        "season": "2025-26",
        "season_type": "Playoffs",
        "team_id": team_id,
        "opponent_team_id": opponent_team_id,
        "game_date": datetime(2026, 4, 15, 23, 30),
        "game_date_precision": "exact",
        "home_or_away": side,
        "result": "W" if home else "L",
        "score": "110-105",
        "team_score": 110 if home else 105,
        "opponent_score": 105 if home else 110,
        "source_name": "nba-stats-scheduleleaguev2",
        "source_parser_version": "scheduleleaguev2-v1",
    }


def test_missing_game_plans_both_reciprocal_rows():
    plan = build_schedule_coverage_plan(
        [_row(), _row(team_id=2, opponent_team_id=1, side="A")],
        [],
        [1, 2],
    )

    assert plan.source_games == 1
    assert plan.candidate_games == 1
    assert len(plan.candidate_rows) == 2
    assert not plan.conflicts


def test_exact_existing_game_is_not_rewritten():
    source = [_row(), _row(team_id=2, opponent_team_id=1, side="A")]
    plan = build_schedule_coverage_plan(source, source, [1, 2])

    assert plan.already_matched_games == 1
    assert plan.candidate_games == 0
    assert not plan.conflicts


def test_conflicting_existing_game_blocks_promotion():
    source = [_row(), _row(team_id=2, opponent_team_id=1, side="A")]
    conflicting = [
        {**source[0], "game_date": datetime(2026, 4, 16, 23, 30)},
        source[1],
    ]
    plan = build_schedule_coverage_plan(source, conflicting, [1, 2])

    assert plan.candidate_games == 0
    assert len(plan.conflicts) == 1


def test_unknown_team_blocks_promotion():
    plan = build_schedule_coverage_plan(
        [_row(), _row(team_id=2, opponent_team_id=1, side="A")],
        [],
        [1],
    )

    assert plan.candidate_games == 0
    assert "unknown team IDs" in plan.conflicts[0]
