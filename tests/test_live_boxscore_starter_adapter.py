from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.services.live_boxscore_starter_adapter import (
    LiveBoxScoreStarterAdapter,
    transform_payload,
)


def _payload():
    return {
        "game": {
            "gameId": "0022600001",
            "homeTeam": {
                "teamId": 1,
                "players": [
                    {"personId": 11, "starter": "1", "position": "G", "status": "ACTIVE"},
                    {"personId": 12, "starter": "0", "position": "F", "status": "ACTIVE"},
                ],
            },
            "awayTeam": {
                "teamId": 2,
                "players": [
                    {"personId": 21, "starter": "1", "position": "C", "status": "ACTIVE"},
                ],
            },
        }
    }


def test_live_boxscore_maps_explicit_starters_and_keeps_other_rows_unknown():
    rows = transform_payload(
        _payload(), game_id="0022600001", season="2026-27",
        season_type="Regular Season", run_id="run-1",
        retrieved_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )

    assert [row["starter_status"] for row in rows] == ["starter", "unknown", "starter"]
    assert rows[0]["start_position"] == "G"
    assert rows[1]["start_position"] is None


def test_live_boxscore_rejects_wrong_game():
    payload = _payload()
    try:
        transform_payload(
            payload, game_id="0022600002", season="2026-27",
            season_type="Regular Season", run_id="run-1",
        )
    except ValueError as exc:
        assert "game mismatch" in str(exc)
    else:
        raise AssertionError("expected game identity validation failure")


def test_live_boxscore_fetch_uses_configured_proxy_and_returns_json():
    response = Mock()
    response.json.return_value = {"game": {"gameId": "0022501162"}}
    with patch.dict(
        "os.environ",
        {
            "FORCE_PROXY": "true",
            "FORCE_LOCAL": "false",
            "NBA_API_PROXY_ATTEMPTS": "1",
        },
    ), patch(
        "app.services.live_boxscore_starter_adapter.ProxyManager.get_healthy_proxy",
        return_value="http://user:password@proxy.test:7000",
    ), patch(
        "app.services.live_boxscore_starter_adapter.requests.get",
        return_value=response,
    ) as get:
        payload = LiveBoxScoreStarterAdapter().fetch_game("0022501162")

    assert payload["game"]["gameId"] == "0022501162"
    assert get.call_args.kwargs["proxies"] == {
        "http": "http://user:password@proxy.test:7000",
        "https": "http://user:password@proxy.test:7000",
    }
    response.raise_for_status.assert_called_once_with()
