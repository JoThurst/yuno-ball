from datetime import date, datetime, timezone

import pytest

from app.services.nba_live_market_observation_adapter import build_market_observations


def _games():
    return [
        {
            "gameId": "0022500001",
            "homeTeamId": 1,
            "awayTeamId": 2,
            "markets": [
                {
                    "name": "2way",
                    "books": [
                        {
                            "id": "book-a",
                            "name": "Book A",
                            "countryCode": "US",
                            "outcomes": [
                                {"type": "home", "odds": 1.91},
                                {"type": "away", "odds": 2.1},
                            ],
                        }
                    ],
                },
                {
                    "name": "total",
                    "books": [
                        {
                            "id": "book-a",
                            "name": "Book A",
                            "countryCode": "US",
                            "outcomes": [
                                {"type": "over", "points": 224.5, "odds": 1.91},
                                {"type": "under", "points": 224.5, "odds": 1.91},
                            ],
                        }
                    ],
                },
            ],
        }
    ]


def test_adapter_emits_separate_game_market_headers_and_preserves_observation_time():
    retrieved_at = datetime(2026, 7, 24, 16, 30, tzinfo=timezone.utc)
    payloads = build_market_observations(
        _games(),
        season="2025-26",
        game_date=date(2026, 4, 12),
        source_run_id="run-1",
        observation_batch_id="poll-1",
        retrieved_at=retrieved_at,
    )

    assert [header["market_type"] for header, _ in payloads] == ["moneyline", "total"]
    assert all(header["timing_precision"] == "second" for header, _ in payloads)
    assert all(header["observed_at"] == retrieved_at for header, _ in payloads)
    assert payloads[0][1][0]["price_american"] == -110
    assert payloads[1][1][0]["line_value"] == 224.5


def test_adapter_filters_non_us_books_and_rejects_naive_retrieval_time():
    games = _games()
    games[0]["markets"][0]["books"][0]["countryCode"] = "GB"
    with pytest.raises(ValueError, match="timezone-aware"):
        build_market_observations(
            games,
            season="2025-26",
            game_date=date(2026, 4, 12),
            source_run_id="run-1",
            observation_batch_id="poll-1",
            retrieved_at=datetime(2026, 7, 24, 16, 30),
        )
    assert len(
        build_market_observations(
            games,
            season="2025-26",
            game_date=date(2026, 4, 12),
            source_run_id="run-1",
            observation_batch_id="poll-1",
            retrieved_at=datetime(2026, 7, 24, 16, 30, tzinfo=timezone.utc),
        )
    ) == 1
    games[0]["markets"][0]["books"][0]["countryCode"] = "US"
    assert len(
        build_market_observations(
            games,
            season="2025-26",
            game_date=date(2026, 4, 12),
            source_run_id="run-1",
            observation_batch_id="poll-1",
            retrieved_at=datetime(2026, 7, 24, 16, 30, tzinfo=timezone.utc),
        )
    ) == 2
