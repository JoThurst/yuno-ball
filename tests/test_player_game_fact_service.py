from datetime import date, datetime, timezone

import pytest

from app.services.player_game_fact_service import (
    PlayerGameFactContractError,
    validate_player_game_fact,
)


def _fact(**overrides):
    value = {
        "source_name": "nba_boxscore_traditional_v3",
        "source_row_key": "0022500879:1641731:traditional-v3",
        "parser_version": "boxscore-traditional-v3-fact-v1",
        "source_game_id": "0022500879",
        "source_player_id": 1641731,
        "source_team_id": 1610612764,
        "canonical_game_id": "0022500879",
        "canonical_player_id": 1641731,
        "canonical_team_id": 1610612764,
        "source_row_sha256": "a" * 64,
        "source_run_id": "run-1",
        "game_date": date(2026, 3, 3),
        "season": "2025-26",
        "season_type": "Regular Season",
        "completeness_status": "complete",
        "participation_status": "played",
        "starter_status": "unknown",
        "minutes": "26:30",
        "field_goals_made": 9,
        "field_goals_attempted": 16,
        "rebounds_total": 1,
        "points": 23,
        "retrieved_at": datetime(2026, 7, 28, 18, tzinfo=timezone.utc),
        "data_available_at": datetime(2026, 7, 28, 18, tzinfo=timezone.utc),
    }
    value.update(overrides)
    return value


def test_traditional_fact_preserves_dnp_and_normalizes_time():
    normalized = validate_player_game_fact(
        _fact(participation_status="did_not_play", minutes=None, points=0)
    )
    assert normalized["participation_status"] == "did_not_play"
    assert normalized["data_available_at"].tzinfo == timezone.utc


def test_traditional_fact_rejects_invalid_minutes_and_negative_stats():
    with pytest.raises(PlayerGameFactContractError, match="minutes"):
        validate_player_game_fact(_fact(minutes="26"))
    with pytest.raises(PlayerGameFactContractError, match="cannot be negative"):
        validate_player_game_fact(_fact(points=-1))


def test_traditional_fact_requires_lowercase_source_hash():
    with pytest.raises(PlayerGameFactContractError, match="SHA-256"):
        validate_player_game_fact(_fact(source_row_sha256="G" * 64))


def test_traditional_fact_captures_response_hash_and_time_basis():
    normalized = validate_player_game_fact(
        _fact(raw_payload={"response_sha256": "b" * 64})
    )
    assert normalized["source_response_sha256"] == "b" * 64
    assert normalized["data_available_at_basis"] == "retrieved_proxy"
    with pytest.raises(PlayerGameFactContractError, match="data_available_at_basis"):
        validate_player_game_fact(_fact(data_available_at_basis="guessed"))
