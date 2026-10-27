"""Live BoxScore must use CDN-safe headers and configured transport."""

from requests.exceptions import HTTPError
from contextlib import nullcontext
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.utils.fetch import injury_fetcher


def test_boxscore_uses_proxy_without_stats_host(monkeypatch):
    captured = {}

    class FakeEndpoint:
        game = type("Game", (), {"get_dict": lambda self: {
            "homeTeam": {"teamId": 1, "players": [{"personId": 10, "status": "ACTIVE", "played": "1"}]},
            "awayTeam": {"teamId": 2, "players": [{"personId": 20, "status": "ACTIVE", "played": "1"}]},
        }})()

    def fake_create_endpoint(endpoint_class, **kwargs):
        captured.update(kwargs)
        return FakeEndpoint()

    monkeypatch.setattr(injury_fetcher, "create_api_endpoint", fake_create_endpoint)
    monkeypatch.setattr(injury_fetcher.rate_limiter, "wait_if_needed", lambda: None)
    fetcher = injury_fetcher.InjuryFetcher()
    fetcher.api_config = {
        "proxy": "http://proxy.example",
        "headers": {"Host": "stats.nba.com", "Accept": "application/json"},
        "timeout": 17,
    }

    assert fetcher._fetch_single_game_status("0022600006") == []
    assert captured == {
        "game_id": "0022600006",
        "proxy": "http://proxy.example",
        "headers": {"Accept": "application/json"},
        "timeout": 17,
    }


def test_boxscore_403_is_fetch_failure(monkeypatch):
    def denied(*args, **kwargs):
        raise HTTPError("403 Forbidden")

    monkeypatch.setattr(injury_fetcher, "create_api_endpoint", denied)
    monkeypatch.setattr(injury_fetcher.rate_limiter, "wait_if_needed", lambda: None)
    fetcher = injury_fetcher.InjuryFetcher()
    fetcher.api_config = {"proxy": None, "headers": {}, "timeout": 17}

    assert fetcher._fetch_single_game_status("0022600006") is None


def test_empty_completed_boxscore_is_fetch_failure(monkeypatch):
    monkeypatch.setattr(injury_fetcher, "create_api_endpoint", lambda *a, **k: SimpleNamespace(
        game=SimpleNamespace(get_dict=lambda: {})))
    monkeypatch.setattr(injury_fetcher.rate_limiter, "wait_if_needed", lambda: None)
    assert injury_fetcher.InjuryFetcher()._fetch_single_game_status("0022600006") is None


def test_completed_game_date_scope_uses_eastern_slate(monkeypatch):
    class Query:
        filters = []

        def filter(self, *values):
            self.filters.extend(values)
            return self

        def all(self):
            return [SimpleNamespace(game_id="0022600003", game_date=datetime(2026, 10, 21, 1, 30))]

    query = Query()
    monkeypatch.setattr(injury_fetcher.PlayerGameStatusORM, "get_games_with_status_data", lambda *a, **k: [])
    result = injury_fetcher.InjuryFetcher()._get_games_to_process(
        "2026-27", date(2026, 10, 20), date(2026, 10, 20),
        SimpleNamespace(query=lambda *a: query),
    )
    where = " ".join(str(value.compile(compile_kwargs={"literal_binds": True})) for value in query.filters)
    assert "2026-10-20 04:00:00" in where
    assert "2026-10-21 04:00:00" in where
    assert result[0]["game_date"] == date(2026, 10, 20)


def test_all_failed_completed_game_fetches_mark_task_failed(monkeypatch):
    fetcher = injury_fetcher.InjuryFetcher()
    monkeypatch.setattr(injury_fetcher, "get_db_context", lambda: nullcontext(object()))
    monkeypatch.setattr(injury_fetcher.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(fetcher, "_get_games_to_process", lambda *args: [
        {"game_id": "0022600006", "game_date": date(2026, 10, 22), "season": "2026-27"}
    ])
    monkeypatch.setattr(fetcher, "_fetch_single_game_status", lambda game_id: None)

    with pytest.raises(RuntimeError, match="failed for 1/1 games"):
        fetcher.fetch_injury_data(
            season="2026-27",
            start_date=date(2026, 10, 22),
            end_date=date(2026, 10, 22),
            batch_size=1,
        )


def test_status_storage_failure_marks_task_failed(monkeypatch):
    fetcher = injury_fetcher.InjuryFetcher()
    monkeypatch.setattr(injury_fetcher, "get_db_context", lambda: nullcontext(object()))
    monkeypatch.setattr(injury_fetcher.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(fetcher, "_get_games_to_process", lambda *args: [
        {"game_id": "0022600006", "game_date": date(2026, 10, 22), "season": "2026-27"}
    ])
    monkeypatch.setattr(fetcher, "_fetch_single_game_status", lambda game_id: [{
        "game_id": game_id, "player_id": 1, "team_id": 2, "played": False
    }])
    monkeypatch.setattr(injury_fetcher.PlayerGameStatusORM, "bulk_create", lambda *a, **k: (_ for _ in ()).throw(ValueError("write failed")))
    with pytest.raises(RuntimeError, match="Could not persist postgame BoxScore"):
        fetcher.fetch_injury_data(season="2026-27", start_date=date(2026, 10, 22),
                                  end_date=date(2026, 10, 22), batch_size=1)
