from datetime import date, datetime, timezone

import pytest

from scripts.collect_nba_live_market_observations import collect
from app.utils.fetch import odds_fetcher


def test_collect_enforces_game_bound_before_adaptation():
    with pytest.raises(ValueError, match="limit is 1"):
        collect(
            [{"gameId": "1"}, {"gameId": "2"}],
            season="2025-26",
            target_date=date(2026, 7, 24),
            source_run_id="run-1",
            observation_batch_id="poll-1",
            retrieved_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
            max_games=1,
            max_observations=10,
            country_filter="US",
        )


def test_collect_returns_validated_game_market_payloads():
    games = [
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
                            "countryCode": "US",
                            "outcomes": [
                                {"type": "home", "odds": 1.91},
                                {"type": "away", "odds": 2.1},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    payloads = collect(
        games,
        season="2025-26",
        target_date=date(2026, 7, 24),
        source_run_id="run-1",
        observation_batch_id="poll-1",
        retrieved_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        max_games=30,
        max_observations=10,
        country_filter="US",
    )
    assert len(payloads) == 1
    assert payloads[0][0]["source_run_id"] == "run-1"


def test_collect_fails_closed_when_games_have_no_complete_market_coverage():
    with pytest.raises(ValueError, match="no complete market observations"):
        collect(
            [{"gameId": "0022500001", "homeTeamId": 1, "awayTeamId": 2, "markets": []}],
            season="2025-26", target_date=date(2026, 7, 24), source_run_id="run-1",
            observation_batch_id="poll-1", retrieved_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
            max_games=30, max_observations=10, country_filter="US",
        )


def test_odds_fetcher_uses_shared_proxy_and_headers(monkeypatch):
    captured = {}

    class FakeOdds:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.games = type("Games", (), {"get_dict": lambda self: []})()

    def fake_create_endpoint(endpoint_class, **kwargs):
        assert endpoint_class is odds_fetcher.odds.Odds
        captured.update(kwargs)
        return type("Endpoint", (), {"games": type("Games", (), {"get_dict": lambda self: []})()})()

    monkeypatch.setattr(odds_fetcher, "create_api_endpoint", fake_create_endpoint)
    fetcher = odds_fetcher.OddsFetcher()
    fetcher.api_config = {
        "proxy": "http://proxy.example",
        "headers": {"Host": "cdn.nba.com"},
        "timeout": 17,
    }
    assert fetcher._fetch_raw_odds() == []
    assert captured == {
        "proxy": "http://proxy.example",
        "headers": {"Host": "cdn.nba.com"},
        "timeout": 17,
    }
