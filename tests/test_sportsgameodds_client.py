from datetime import datetime, timezone
import os
from unittest.mock import Mock

import pytest

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.services.sportsgameodds_client import (
    SportsGameOddsSafetyError,
    api_key_from_environment,
    build_events_request,
    fetch_events,
    normalize_events,
    review_normalized_events,
)


def _event():
    return {
        "eventID": "event-nba-1",
        "leagueID": "NBA",
        "teams": {
            "home": {"teamID": "BOS_NBA", "names": {"long": "Boston Celtics"}},
            "away": {"teamID": "NY_NBA", "names": {"long": "New York Knicks"}},
        },
        "status": {"startsAt": "2026-10-22T23:30:00.000Z", "live": False},
        "odds": {
            "points-home-game-ml-home": {
                "statID": "points",
                "periodID": "game",
                "betTypeID": "ml",
                "sideID": "home",
                "byBookmaker": {
                    "draftkings": {
                        "odds": "-115",
                        "available": True,
                        "lastUpdatedAt": "2026-10-22T20:00:00.000Z",
                    }
                },
            },
            "points-away-game-ml-away": {
                "statID": "points",
                "periodID": "game",
                "betTypeID": "ml",
                "sideID": "away",
                "byBookmaker": {
                    "draftkings": {"odds": "+105", "available": True}
                },
            },
            "points-home-game-sp-home": {
                "statID": "points",
                "periodID": "game",
                "betTypeID": "sp",
                "sideID": "home",
                "byBookmaker": {
                    "draftkings": {
                        "odds": "-110",
                        "overUnder": "-2.5",
                        "available": True,
                    }
                },
            },
            "points-away-game-sp-away": {
                "statID": "points",
                "periodID": "game",
                "betTypeID": "sp",
                "sideID": "away",
                "byBookmaker": {
                    "draftkings": {
                        "odds": "-110",
                        "overUnder": "+2.5",
                        "available": True,
                    }
                },
            },
            "points-home-game-ou-over": {
                "statID": "points",
                "periodID": "game",
                "betTypeID": "ou",
                "sideID": "over",
                "byBookmaker": {
                    "draftkings": {
                        "odds": "-110",
                        "overUnder": "224.5",
                        "available": True,
                    }
                },
            },
        },
    }


def test_request_plan_uses_header_auth_and_bounded_defaults():
    request = build_events_request(api_key="secret", limit=1)
    assert request.url == "https://api.sportsgameodds.com/v2/events"
    assert request.params == {
        "leagueID": "NBA",
        "finalized": "false",
        "oddsAvailable": "true",
        "limit": 1,
    }
    assert request.headers == {"x-api-key": "secret"}
    assert "secret" not in request.url


def test_live_network_is_fail_closed_without_explicit_opt_in():
    request = build_events_request(api_key="secret")
    session = Mock()
    with pytest.raises(SportsGameOddsSafetyError, match="Network access is disabled"):
        fetch_events(request, session=session)
    session.get.assert_not_called()


def test_normalizer_preserves_provider_identity_and_featured_game_markets():
    events = normalize_events([_event()])
    assert len(events) == 1
    event = events[0]
    assert event["source_event_id"] == "event-nba-1"
    assert event["home_provider_team_id"] == "BOS_NBA"
    assert event["starts_at"] == datetime(2026, 10, 22, 23, 30, tzinfo=timezone.utc)
    assert {market["market_type"] for market in event["markets"]} == {
        "moneyline",
        "spread",
        "total",
    }
    moneyline = next(m for m in event["markets"] if m["market_type"] == "moneyline")
    assert moneyline["bookmakers"][0]["price_american"] == -115


def test_normalizer_excludes_props_and_non_game_periods():
    event = _event()
    event["odds"]["player-points-game-ou-over"] = {
        "statID": "player_points",
        "periodID": "game",
        "betTypeID": "ou",
        "sideID": "over",
        "byBookmaker": {"book": {"odds": "+100", "available": True}},
    }
    event["odds"]["points-home-q1-ml-home"] = {
        "periodID": "q1",
        "betTypeID": "ml",
        "sideID": "home",
        "byBookmaker": {"book": {"odds": "-110", "available": True}},
    }
    markets = normalize_events([event])[0]["markets"]
    assert all(market["odd_id"] != "player-points-game-ou-over" for market in markets)
    assert all(market["odd_id"] != "points-home-q1-ml-home" for market in markets)


def test_pair_review_reports_complete_and_incomplete_fixture_groups_without_identity_claims():
    review = review_normalized_events(normalize_events([_event()]))

    assert review["status"] == "reviewable"
    assert review["complete_pair_groups"] == 2
    assert review["incomplete_pair_groups"] == 1
    assert review["timestamped_bookmaker_rows"] == 1
    assert review["provider_team_ids"] == ["BOS_NBA", "NY_NBA"]
    assert review["identity_status"] == "unresolved"
    assert review["writes_performed"] is False


def test_pair_review_flags_duplicate_selections():
    normalized = normalize_events([_event()])
    normalized[0]["markets"].append(normalized[0]["markets"][0])

    review = review_normalized_events(normalized)

    assert review["duplicate_selection_rows"] == 1
    assert review["status"] == "needs_review"


def test_pair_review_does_not_count_unlined_or_nonreciprocal_spreads():
    event = _event()
    odds = event["odds"]
    odds["points-home-game-sp-home"]["byBookmaker"]["draftkings"].pop("overUnder")
    odds["points-away-game-sp-away"]["byBookmaker"]["draftkings"].pop("overUnder")
    review = review_normalized_events(normalize_events([event]))
    assert review["complete_pair_groups"] == 1  # moneyline only
    assert review["incomplete_pair_groups"] == 2

    odds["points-home-game-sp-home"]["byBookmaker"]["draftkings"]["overUnder"] = "-2.5"
    odds["points-away-game-sp-away"]["byBookmaker"]["draftkings"]["overUnder"] = "-2.5"
    review = review_normalized_events(normalize_events([event]))
    assert review["complete_pair_groups"] == 1  # same-sign spread is not reciprocal
    assert review["incomplete_pair_groups"] == 2


def test_pair_review_requires_finite_total_line_and_preserves_zero_spread():
    event = _event()
    odds = event["odds"]
    odds["points-home-game-sp-home"]["byBookmaker"]["draftkings"]["overUnder"] = 0
    odds["points-away-game-sp-away"]["byBookmaker"]["draftkings"]["overUnder"] = 0
    odds["points-home-game-ou-over"]["byBookmaker"]["draftkings"]["overUnder"] = "nan"
    odds["points-away-game-ou-under"] = {
        "statID": "points",
        "periodID": "game",
        "betTypeID": "ou",
        "sideID": "under",
        "byBookmaker": {
            "draftkings": {"odds": "-110", "overUnder": "inf", "available": True}
        },
    }
    normalized = normalize_events([event])
    spread_rows = [
        book for market in normalized[0]["markets"]
        if market["market_type"] == "spread"
        for book in market["bookmakers"]
    ]
    assert [book["line_value"] for book in spread_rows] == [0.0, 0.0]
    review = review_normalized_events(normalized)
    assert review["complete_pair_groups"] == 2
    assert review["incomplete_pair_groups"] == 1
