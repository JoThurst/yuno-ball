from datetime import date, datetime, timezone

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


def test_advanced_progress_is_emitted_before_a_later_game_fails():
    class FailingAdapter:
        def __init__(self):
            self.returned_at = None

        def fetch_game(self, game_id):
            if game_id == "g2":
                raise RuntimeError("provider timeout")
            self.returned_at = datetime.now(timezone.utc)
            return {
                "boxScoreAdvanced": {
                    "gameId": game_id,
                    "homeTeam": {"teamId": 1, "players": [{
                        "personId": 10, "comment": "",
                        "statistics": {"minutes": "10:00", "usagePercentage": 0.2},
                    }]},
                    "awayTeam": {"teamId": 2, "players": [{
                        "personId": 20, "comment": "",
                        "statistics": {"minutes": "12:00", "trueShootingPercentage": 0.6},
                    }]},
                }
            }

    specs = [
        CompletedGameSpec("g1", date(2026, 3, 3), "2025-26", "Regular Season", (1, 2)),
        CompletedGameSpec("g2", date(2026, 3, 4), "2025-26", "Regular Season", (3, 4)),
    ]
    adapter = FailingAdapter()
    progress = []

    with pytest.raises(RuntimeError, match="provider timeout"):
        _advanced_games(
            specs,
            run_id="run",
            adapter=adapter,
            progress_callback=progress.append,
        )

    assert [entry["game_id"] for entry in progress] == ["g1"]
    assert datetime.fromisoformat(progress[0]["retrieved_at"]) >= adapter.returned_at


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
