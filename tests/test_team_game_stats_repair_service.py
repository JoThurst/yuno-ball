from datetime import date

import pytest

from app.services.team_game_stats_repair_service import parse_team_game_log


HEADERS = [
    "Game_ID",
    "GAME_DATE",
    "PTS",
    "REB",
    "OREB",
    "DREB",
    "WL",
    "W",
    "L",
    "W_PCT",
]


def _response(rows):
    return {"resultSets": [{"headers": list(HEADERS), "rowSet": rows}]}


def test_parse_team_game_log_uses_named_fields():
    parsed = parse_team_game_log(
        _response([["0022400001", "OCT 22, 2024", 110, 44, 12, 32, "W", 1, 0, 1.0]])
    )

    row = parsed["0022400001"]
    assert row.game_date == date(2024, 10, 22)
    assert row.oreb == 12
    assert row.dreb == 32
    assert row.wl == "W"
    assert row.w_pct == 1.0


def test_parse_team_game_log_rejects_missing_required_header():
    response = _response([["0022400001", "OCT 22, 2024", 110, 44, 12, 32, "W", 1, 0, 1.0]])
    response["resultSets"][0]["headers"].remove("DREB")

    with pytest.raises(ValueError, match="missing headers"):
        parse_team_game_log(response)


def test_parse_team_game_log_rejects_duplicate_game():
    row = ["0022400001", "OCT 22, 2024", 110, 44, 12, 32, "W", 1, 0, 1.0]

    with pytest.raises(ValueError, match="duplicate"):
        parse_team_game_log(_response([row, row]))
