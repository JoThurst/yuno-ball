from datetime import datetime

from app.services.slate_service import _pair_games


def _row(game_id, team_id, opponent_id, home_or_away, game_date, precision):
    return {
        "game_id": game_id,
        "team_id": team_id,
        "opponent_team_id": opponent_id,
        "home_or_away": home_or_away,
        "game_date": game_date,
        "game_date_precision": precision,
        "team_name": f"Team {team_id}",
        "opponent_name": f"Team {opponent_id}",
        "team_abbreviation": f"T{team_id}",
        "opponent_abbreviation": f"T{opponent_id}",
        "result": None,
    }


def test_pair_games_does_not_invent_midnight_tipoff_for_date_only_schedule():
    rows = [
        _row(
            "0012500001",
            1,
            2,
            "H",
            datetime(2025, 4, 12),
            "date_only",
        ),
        _row(
            "0012500001",
            2,
            1,
            "A",
            datetime(2025, 4, 12),
            "date_only",
        ),
        _row(
            "0012500002",
            3,
            4,
            "H",
            datetime(2025, 4, 12, 19, 30),
            "exact",
        ),
        _row(
            "0012500002",
            4,
            3,
            "A",
            datetime(2025, 4, 12, 19, 30),
            "exact",
        ),
    ]

    matchups = {matchup["game_id"]: matchup for matchup in _pair_games(rows)}

    assert matchups["0012500001"]["game_time"] is None
    assert matchups["0012500001"]["game_date_precision"] == "date_only"
    assert matchups["0012500002"]["game_time"] == "07:30 PM"
