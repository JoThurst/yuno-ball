from datetime import date, datetime, timezone

from app.services.traditional_boxscore_v3_adapter import transform_payload


def test_transform_preserves_dnp_nulls_and_hashes():
    payload = {"player_stats": {"headers": ["PLAYER_ID", "TEAM_ID", "MIN", "PTS", "START_POSITION", "PLAYER_STATUS"],
                                "data": [[7, 1, "0:00", None, None, "DNP"], [8, 1, "12:34", 9, "F", None]]}}
    facts = transform_payload(payload, game_id="0022500879", game_date=date(2026, 3, 3),
                               season="2025-26", season_type="Regular Season", run_id="run",
                               retrieved_at=datetime(2026, 3, 4, tzinfo=timezone.utc))
    assert facts[0]["participation_status"] == "did_not_play"
    assert facts[0]["points"] is None
    assert facts[0]["starter_status"] == "unknown"
    assert facts[1]["participation_status"] == "played"
    assert facts[1]["starter_status"] == "unknown"
    assert len(facts[0]["source_row_sha256"]) == 64
    assert facts[0]["source_row_key"] == "0022500879:7:1"


def test_transform_is_deterministic_for_same_row():
    payload = {"player_stats": {"headers": ["PLAYER_ID", "TEAM_ID", "MIN", "PTS"], "data": [[7, 1, "0:00", 0]]}}
    kwargs = dict(game_id="g", game_date=date(2026, 3, 3), season="2025-26", season_type="Regular Season", run_id="r",
                  retrieved_at=datetime(2026, 3, 4, tzinfo=timezone.utc))
    assert transform_payload(payload, **kwargs)[0]["source_row_sha256"] == transform_payload(payload, **kwargs)[0]["source_row_sha256"]


def test_transform_classifies_provider_dnp_reason_without_zero_filling():
    payload = {
        "player_stats": {
            "headers": ["PLAYER_ID", "TEAM_ID", "MIN", "PTS", "PLAYER_STATUS"],
            "data": [[7, 1, "0:00", None, "DNP - Coach's Decision"]],
        }
    }
    fact = transform_payload(
        payload,
        game_id="g",
        game_date=date(2026, 3, 3),
        season="2025-26",
        season_type="Regular Season",
        run_id="r",
        retrieved_at=datetime(2026, 3, 4, tzinfo=timezone.utc),
    )[0]
    assert fact["participation_status"] == "did_not_play"
    assert fact["points"] is None
    assert fact["parser_version"] == "boxscore-traditional-v3-fact-v2"
