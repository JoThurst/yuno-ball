from datetime import date

import pytest

from app.services.player_game_fact_collection_service import (
    CompletedGameSpec,
    collect_traditional_games,
    validate_game_bound,
)


class _Adapter:
    def __init__(self, payloads):
        self.payloads = payloads

    def fetch_game(self, game_id):
        return self.payloads[game_id]


def _payload(game_id, home=1, away=2):
    return {
        "boxScoreTraditional": {
            "gameId": game_id,
            "homeTeam": {
                "teamId": home,
                "players": [
                    {
                        "personId": 10,
                        "comment": "",
                        "statistics": {"minutes": "10:00", "points": 7},
                    }
                ],
                "statistics": {"points": 7},
            },
            "awayTeam": {
                "teamId": away,
                "players": [
                    {
                        "personId": 20,
                        "comment": "",
                        "statistics": {"minutes": "12:00", "points": 9},
                    }
                ],
                "statistics": {"points": 9},
            },
        }
    }


def test_validate_game_bound_is_unique_and_fail_closed():
    assert validate_game_bound(["g1", "g1", "g2"], max_games=2) == ["g1", "g2"]
    with pytest.raises(ValueError, match="within max_games"):
        validate_game_bound(["g1", "g2"], max_games=1)
    with pytest.raises(ValueError, match="between"):
        validate_game_bound(["g1"], max_games=26)


def test_collect_traditional_games_reconciles_complete_batch():
    specs = [
        CompletedGameSpec("g1", date(2026, 3, 3), "2025-26", "Regular Season", (1, 2)),
        CompletedGameSpec("g2", date(2026, 3, 4), "2025-26", "Regular Season", (3, 4)),
    ]
    facts, games = collect_traditional_games(
        specs,
        run_id="run",
        max_games=2,
        adapter=_Adapter({"g1": _payload("g1"), "g2": _payload("g2", 3, 4)}),
    )
    assert len(facts) == 4
    assert [game["game_id"] for game in games] == ["g1", "g2"]


def test_collect_traditional_games_rejects_team_identity_drift():
    spec = CompletedGameSpec(
        "g1", date(2026, 3, 3), "2025-26", "Regular Season", (1, 99)
    )
    with pytest.raises(ValueError, match="team identity mismatch"):
        collect_traditional_games(
            [spec],
            run_id="run",
            max_games=1,
            adapter=_Adapter({"g1": _payload("g1")}),
        )
