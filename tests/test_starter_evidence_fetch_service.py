from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests

from app.services.starter_evidence_fetch_service import fetch_starter_evidence


def _v2_payload():
    rows = []
    for team_id, offset in ((1, 0), (2, 10)):
        for index in range(6):
            rows.append([
                "0022400001", team_id, 100 + offset + index,
                "Player", "G" if index < 5 else "",
            ])
    return {
        "resultSets": [{
            "name": "PlayerStats",
            "headers": ["GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "START_POSITION"],
            "rowSet": rows,
        }]
    }


def _live_error():
    return requests.HTTPError("403 Client Error: Access Denied")


def test_live_transport_failure_uses_v2_with_source_provenance():
    endpoint = Mock()
    endpoint.get_dict.return_value = _v2_payload()
    with patch(
        "app.services.starter_evidence_fetch_service.LiveBoxScoreStarterAdapter.fetch_game",
        side_effect=_live_error(),
    ), patch(
        "app.services.starter_evidence_fetch_service.create_api_endpoint",
        return_value=endpoint,
    ), patch.dict("os.environ", {"STARTER_EVIDENCE_FALLBACK_SOURCE": "traditional_v2"}):
        fetched = fetch_starter_evidence(
            game_id="0022400001",
            season="2024-25",
            season_type="Regular Season",
            run_id="run",
            retrieved_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        )

    assert fetched.source_name == "nba_boxscore_traditional_v2_starter_trial"
    assert fetched.fallback_reason == str(_live_error())
    assert sum(row["starter_status"] == "starter" for row in fetched.rows) == 10


def test_live_success_keeps_live_source():
    live_payload = {
        "game": {
            "gameId": "0022600001",
            "homeTeam": {"teamId": 1, "players": [
                {"personId": 11, "starter": "1", "position": "G"},
            ]},
            "awayTeam": {"teamId": 2, "players": [
                {"personId": 21, "starter": "1", "position": "C"},
            ]},
        }
    }
    with patch(
        "app.services.starter_evidence_fetch_service.LiveBoxScoreStarterAdapter.fetch_game",
        return_value=live_payload,
    ):
        fetched = fetch_starter_evidence(
            game_id="0022600001",
            season="2026-27",
            season_type="Regular Season",
            run_id="run",
            retrieved_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        )

    assert fetched.source_name == "nba_live_boxscore_starter"
    assert fetched.fallback_reason is None
