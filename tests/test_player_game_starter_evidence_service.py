from datetime import date, datetime, timezone

import pytest

from app.services.player_game_starter_evidence_service import validate_starter_evidence


def _evidence(**overrides):
    value = {
        "source_name": "nba_boxscore_traditional_v2_starter_trial",
        "source_row_key": "0022400001:7:1",
        "parser_version": "boxscore-traditional-v2-starter-trial-v1",
        "source_game_id": "0022400001",
        "source_player_id": 7,
        "source_team_id": 1,
        "canonical_game_id": "0022400001",
        "canonical_player_id": 7,
        "canonical_team_id": 1,
        "game_date": date(2024, 11, 12),
        "season": "2024-25",
        "season_type": "Regular Season",
        "starter_status": "starter",
        "start_position": "G",
        "source_row_sha256": "a" * 64,
        "source_response_sha256": "b" * 64,
        "source_run_id": "run-1",
        "retrieved_at": datetime(2026, 8, 31, tzinfo=timezone.utc),
        "data_available_at": datetime(2026, 8, 31, tzinfo=timezone.utc),
    }
    value.update(overrides)
    return value


def test_validation_normalizes_aware_timestamps_and_preserves_position():
    normalized = validate_starter_evidence(_evidence())
    assert normalized["start_position"] == "G"
    assert normalized["retrieved_at"].tzinfo == timezone.utc


def test_validation_rejects_unknown_with_position():
    with pytest.raises(ValueError, match="unknown starter_status"):
        validate_starter_evidence(_evidence(starter_status="unknown"))


def test_validation_rejects_uppercase_hash():
    with pytest.raises(ValueError, match="SHA-256"):
        validate_starter_evidence(_evidence(source_row_sha256="A" * 64))
