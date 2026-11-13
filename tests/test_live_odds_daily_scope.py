"""Legacy Live odds writes must stay inside the canonical Eastern slate."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from app.utils.fetch import odds_fetcher


def _game(game_id, home_id=1, away_id=2):
    return {
        "gameId": game_id,
        "homeTeamId": str(home_id),
        "awayTeamId": str(away_id),
        "markets": [{
            "name": "2way",
            "books": [{
                "id": "book-1", "name": "Example", "countryCode": "US", "url": "",
                "outcomes": [
                    {"type": "home", "odds": "1.80"},
                    {"type": "away", "odds": "2.00"},
                ],
            }],
        }],
    }


def test_legacy_odds_store_only_exact_current_slate_game(monkeypatch):
    fetcher = odds_fetcher.OddsFetcher()
    monkeypatch.setattr(fetcher, "_current_slate_games", lambda *a: {"current": (1, 2)})
    monkeypatch.setattr(fetcher, "_fetch_raw_odds", lambda: [_game("prior"), _game("current")])
    monkeypatch.setattr(odds_fetcher, "get_db_context", lambda: nullcontext(SimpleNamespace(commit=lambda: None)))
    stored = []
    monkeypatch.setattr(odds_fetcher.GameOddsORM, "bulk_create", lambda rows, db: (stored.extend(rows), len(rows))[1])

    assert fetcher.fetch_todays_odds("2026-27") == (1, 1)
    assert [row["game_id"] for row in stored] == ["current"]


def test_legacy_odds_reject_team_mismatch_before_write(monkeypatch):
    fetcher = odds_fetcher.OddsFetcher()
    monkeypatch.setattr(fetcher, "_current_slate_games", lambda *a: {"current": (1, 2)})
    monkeypatch.setattr(fetcher, "_fetch_raw_odds", lambda: [_game("current", home_id=3)])
    monkeypatch.setattr(odds_fetcher.GameOddsORM, "bulk_create", lambda *a, **k: pytest.fail("unexpected write"))

    with pytest.raises(RuntimeError, match="team identity differs"):
        fetcher.fetch_todays_odds("2026-27")


@pytest.mark.parametrize("feed", [None, [], [_game("prior")]])
def test_legacy_odds_reject_missing_current_slate_source(monkeypatch, feed):
    fetcher = odds_fetcher.OddsFetcher()
    monkeypatch.setattr(fetcher, "_current_slate_games", lambda *a: {"current": (1, 2)})
    monkeypatch.setattr(fetcher, "_fetch_raw_odds", lambda: feed)
    with pytest.raises(RuntimeError):
        fetcher.fetch_todays_odds("2026-27")
