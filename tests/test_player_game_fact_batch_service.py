from datetime import date

import pytest

from app.services.player_game_fact_batch_service import (
    _advanced_games,
    validate_batch_identity,
)
from app.services.player_game_fact_collection_service import CompletedGameSpec


def fact(game, player, team):
    return {
        "canonical_game_id": game,
        "canonical_player_id": player,
        "canonical_team_id": team,
    }


def test_batch_identity_requires_exact_traditional_advanced_grain():
    traditional = [fact("g1", 10, 1), fact("g1", 20, 2)]
    advanced = [fact("g1", 10, 1), fact("g1", 20, 2)]
    validate_batch_identity(traditional, advanced)


def test_batch_identity_rejects_drift():
    with pytest.raises(ValueError, match="identity mismatch"):
        validate_batch_identity([fact("g1", 10, 1)], [fact("g1", 11, 1)])


class DuplicateAdvancedAdapter:
    def fetch_game(self, game_id):
        return {
            "boxScoreAdvanced": {
                "gameId": game_id,
                "homeTeam": {
                    "teamId": 1,
                    "players": [
                        {"personId": 10, "comment": "", "statistics": {"minutes": "10:00"}},
                        {"personId": 10, "comment": "", "statistics": {"minutes": "11:00"}},
                    ],
                },
                "awayTeam": {
                    "teamId": 2,
                    "players": [
                        {"personId": 20, "comment": "", "statistics": {"minutes": "12:00"}},
                    ],
                },
            }
        }


def test_advanced_batch_reports_duplicate_key_details():
    spec = CompletedGameSpec(
        game_id="g1",
        game_date=date(2026, 3, 3),
        season="2025-26",
        season_type="Regular Season",
        team_ids=(1, 2),
    )
    with pytest.raises(ValueError, match="duplicate_keys"):
        _advanced_games([spec], run_id="run", adapter=DuplicateAdvancedAdapter())
