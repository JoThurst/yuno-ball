from datetime import datetime, timezone

import pytest

from app.services.traditional_boxscore_v2_starter_adapter import transform_payload


def _payload():
    return {
        "resultSets": [
            {
                "name": "PlayerStats",
                "headers": ["GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "START_POSITION"],
                "rowSet": [
                    ["0022400001", 1, 7, "Starter", "G"],
                    ["0022400001", 1, 8, "Bench", ""],
                ],
            }
        ]
    }


def test_transform_extracts_trial_starter_evidence_without_full_fact_contract():
    evidence = transform_payload(
        _payload(),
        game_id="0022400001",
        season="2024-25",
        season_type="Regular Season",
        run_id="run",
        retrieved_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    assert evidence[0]["starter_status"] == "starter"
    assert evidence[0]["start_position"] == "G"
    assert evidence[1]["starter_status"] == "unknown"
    assert evidence[0]["source_name"].endswith("_trial")
    assert len(evidence[0]["source_row_sha256"]) == 64


def test_transform_rejects_empty_player_rows():
    payload = {"resultSets": [{"name": "PlayerStats", "headers": ["PLAYER_ID"], "rowSet": []}]}
    with pytest.raises(ValueError, match="no PlayerStats rows"):
        transform_payload(
            payload,
            game_id="0022400001",
            season="2024-25",
            season_type="Regular Season",
            run_id="run",
        )


def test_transform_rejects_game_mismatch():
    payload = _payload()
    payload["resultSets"][0]["rowSet"][0][0] = "0022400002"
    with pytest.raises(ValueError, match="game mismatch"):
        transform_payload(
            payload,
            game_id="0022400001",
            season="2024-25",
            season_type="Regular Season",
            run_id="run",
        )
