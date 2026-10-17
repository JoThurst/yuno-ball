"""Contract tests for the read-only Daily Intelligence V1 package."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from app.services.daily_intelligence_service import build_daily_intelligence_v1
from app.services.slate_service import _serialize_market_observations, _pair_games
from app.services.daily_archive_service import _summarize_schedule_rows, build_daily_archive_index
from app.utils.date_utils import current_eastern_date
from app import create_app
from tests.config import TestConfig
from tests.test_base import BaseTestCase


TARGET_DATE = date(2025, 3, 3)


def test_current_eastern_date_observes_dst_and_standard_time_boundaries():
    assert current_eastern_date(datetime(2026, 10, 16, 3, 59, tzinfo=timezone.utc)) == date(2026, 10, 15)
    assert current_eastern_date(datetime(2026, 10, 16, 4, 0, tzinfo=timezone.utc)) == date(2026, 10, 16)
    assert current_eastern_date(datetime(2026, 12, 16, 4, 59, tzinfo=timezone.utc)) == date(2026, 12, 15)
    assert current_eastern_date(datetime(2026, 12, 16, 5, 0, tzinfo=timezone.utc)) == date(2026, 12, 16)


def test_paired_schedule_rows_expose_postgame_result_and_final_score():
    matchups = _pair_games([
        {
            "game_id": "0022400001", "home_or_away": "H", "team_id": 1,
            "opponent_team_id": 2, "team_name": "Home Team", "opponent_name": "Away Team",
            "team_abbreviation": "HOM", "opponent_abbreviation": "AWY",
            "result": "W", "score": "112 - 105.0", "game_date": datetime(2025, 3, 3),
            "game_date_precision": "exact",
        },
        {
            "game_id": "0022400001", "home_or_away": "A", "team_id": 2,
            "opponent_team_id": 1, "team_name": "Away Team", "opponent_name": "Home Team",
            "team_abbreviation": "AWY", "opponent_abbreviation": "HOM",
            "result": "L", "score": "105 - 112.0", "game_date": datetime(2025, 3, 3),
            "game_date_precision": "exact",
        },
    ])

    actual = matchups[0]["actual"]
    assert actual["status"] == "final"
    assert actual["home_score"] == 112
    assert actual["away_score"] == 105
    assert actual["winner"] == "Home Team"
    assert actual["margin"] == 7


def _context(games=None):
    return {
        "season": "2024-25",
        "games": games or [],
        "hot_players": [],
        "cold_players": [],
        "freshness": {},
        "team_snapshot": {"source": "versioned_snapshot", "completeness": "complete"},
        "player_snapshot": {"source": "versioned_snapshot", "completeness": "complete"},
    }


def _game():
    return {
        "game_id": "0022400888",
        "game_date": datetime(2025, 3, 4, 0, tzinfo=timezone.utc),
        "game_time": "07:00 PM",
        "result_home": None,
        "home_team_id": 1,
        "away_team_id": 2,
        "home_name": "Home Team",
        "away_name": "Away Team",
        "home_abbr": "HOM",
        "away_abbr": "AWY",
        "home_net_delta": 4.2,
        "away_net_delta": -3.4,
        "home_flags": ["surging_net_rating"],
        "away_flags": ["cooling_net_rating"],
        "home_schedule": {
            "team_id": 1,
            "days_rest": 0,
            "is_b2b": True,
            "rest_edge": "even",
            "rest_diff": 0,
            "opponent_days_rest": 0,
        },
        "away_schedule": {
            "team_id": 2,
            "days_rest": 2,
            "is_b2b": False,
            "rest_edge": "away",
            "rest_diff": -2,
            "opponent_days_rest": 0,
        },
        "environment": {
            "pace_projection": 103.1,
            "scoring_env_index": 104.0,
            "pace_label": "fast",
            "feature_as_of": datetime(2025, 3, 3, 15, tzinfo=timezone.utc),
            "calculation_version": "team-v2.1",
            "completeness": "complete",
        },
        "home_availability": {
            "source": "official_nba",
            "as_of": datetime(2025, 3, 3, 23, 30, tzinfo=timezone.utc),
            "completeness": "complete",
            "observations": [{"status": "Out"}, {"status": "Questionable"}],
            "unresolved_count": 0,
        },
        "away_availability": {
            "source": "official_nba",
            "as_of": datetime(2025, 3, 3, 23, 30, tzinfo=timezone.utc),
            "completeness": "complete",
            "observations": [],
            "unresolved_count": 1,
        },
        "home_players": [],
        "away_players": [],
    }


def test_package_is_typed_json_safe_and_deterministic():
    with patch(
        "app.services.daily_intelligence_service.build_slate_context",
        return_value=_context([_game()]),
    ):
        first = build_daily_intelligence_v1(TARGET_DATE, "2024-25")
        second = build_daily_intelligence_v1(TARGET_DATE, "2024-25")

    payload = first.to_dict()
    assert payload == second.to_dict()
    assert payload["contract_version"] == "daily-intelligence-v1"
    assert payload["status"] == "available"
    assert payload["games"][0]["matchup_priority"]["rank"] == 1
    assert payload["games"][0]["state"] == "scheduled"
    assert payload["games"][0]["signals"]["environment"]["feature_as_of"].startswith("2025-03-03")
    assert payload["games"][0]["signals"]["availability_readout"]["home"]["summary"] == "1 out · 1 questionable"
    assert len(payload["games"][0]["signals"]["availability_uncertainty"]["home"]["observations"]) == 2
    assert payload["summary"]["availability"]["readout"] == "2/2 team reports complete · 1 out · 1 questionable · 1 unresolved"
    assert "HOM availability" in payload["games"][0]["matchup_priority"]["reasons"]
    assert any(item["kind"] == "availability_uncertainty" for item in payload["insights"])
    assert any(item["kind"] == "schedule_pressure" for item in payload["insights"])
    assert all("prediction" not in item["kind"] for item in payload["insights"])


def test_missing_ingest_marker_is_explicit_not_fresh():
    with patch(
        "app.services.daily_intelligence_service.build_slate_context",
        return_value=_context([_game()]),
    ):
        payload = build_daily_intelligence_v1(TARGET_DATE, "2024-25").to_dict()

    assert payload["freshness"]["status"] == "unknown"
    assert payload["freshness"]["completeness"] == "unknown"
    assert payload["freshness"]["has_marker"] is False
    assert payload["freshness"]["as_of"] is None


def test_empty_slate_has_a_useful_empty_state():
    with patch(
        "app.services.daily_intelligence_service.build_slate_context",
        return_value=_context(),
    ):
        payload = build_daily_intelligence_v1(TARGET_DATE, "2024-25").to_dict()

    assert payload["status"] == "empty"
    assert payload["summary"]["game_count"] == 0
    assert payload["games"] == []
    assert payload["insights"][0]["kind"] == "slate_summary"


def test_timestamped_market_observation_is_context_only():
    game = _game()
    game["observed_markets"] = {
        "source": "nba_live_odds",
        "status": "available",
        "completeness": "complete_pair_observed",
        "books_count": 2,
        "observations_total": 4,
        "markets": [{"observed_at": "2025-03-03T18:00:00+00:00"}],
    }
    with patch(
        "app.services.daily_intelligence_service.build_slate_context",
        return_value=_context([game]),
    ):
        payload = build_daily_intelligence_v1(TARGET_DATE, "2024-25").to_dict()

    assert payload["games"][0]["market"]["books_count"] == 2
    market_insight = next(item for item in payload["insights"] if item["kind"] == "market_coverage")
    assert market_insight["metric_context"]["observations_total"] == 4
    assert "not a model edge" in market_insight["explanation"]


def test_market_projection_selects_latest_observation_per_book_and_market():
    headers = [
        SimpleNamespace(
            canonical_game_id="0022400888",
            sportsbook_id="book-a",
            market_type="moneyline",
            sportsbook_name="Book A",
            observation_id="old",
            observed_at=datetime(2025, 3, 3, 17, tzinfo=timezone.utc),
            data_available_at=datetime(2025, 3, 3, 17, tzinfo=timezone.utc),
            created_at=datetime(2025, 3, 3, 17, 1, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            canonical_game_id="0022400888",
            sportsbook_id="book-a",
            market_type="moneyline",
            sportsbook_name="Book A",
            observation_id="new",
            observed_at=datetime(2025, 3, 3, 18, tzinfo=timezone.utc),
            data_available_at=datetime(2025, 3, 3, 18, tzinfo=timezone.utc),
            created_at=datetime(2025, 3, 3, 18, 1, tzinfo=timezone.utc),
        ),
    ]
    selections = {
        "old": [SimpleNamespace(selection_key="home", selection_label="Home", line_value=None, price_american=-105)],
        "new": [SimpleNamespace(selection_key="home", selection_label="Home", line_value=None, price_american=-110)],
    }

    projected = _serialize_market_observations(headers, {key: value for key, value in selections.items()})

    assert projected["0022400888"]["observations_total"] == 2
    assert projected["0022400888"]["books_count"] == 1
    assert projected["0022400888"]["markets"][0]["observed_at"].startswith("2025-03-03T18:00")
    assert projected["0022400888"]["markets"][0]["selections"][0]["price_american"] == -110


def test_archive_groups_schedule_rows_by_eastern_slate_date():
    rows = [
        SimpleNamespace(
            game_id="0022400888",
            season="2024-25",
            game_date=datetime(2025, 3, 4, 1, tzinfo=timezone.utc),
            team_id=1,
            opponent_team_id=2,
            home_or_away="H",
            result="W",
        ),
        SimpleNamespace(
            game_id="0022400888",
            season="2024-25",
            game_date=datetime(2025, 3, 4, 1, tzinfo=timezone.utc),
            team_id=2,
            opponent_team_id=1,
            home_or_away="A",
            result="L",
        ),
    ]
    entries = _summarize_schedule_rows(
        rows,
        {
            1: {"team_id": 1, "name": "Home Team", "abbreviation": "HOM"},
            2: {"team_id": 2, "name": "Away Team", "abbreviation": "AWY"},
        },
    )

    assert entries[0]["date"] == date(2025, 3, 3)
    assert entries[0]["game_count"] == 1
    assert entries[0]["completed_count"] == 1
    assert entries[0]["matchups"][0]["away"]["abbreviation"] == "AWY"
    assert entries[0]["matchups"][0]["home"]["abbreviation"] == "HOM"


def test_archive_excludes_next_eastern_date_before_eastern_midnight():
    rows = [
        SimpleNamespace(
            game_id="same-day", season="2026-27",
            game_date=datetime(2026, 10, 16, 1, tzinfo=timezone.utc),
            team_id=1, opponent_team_id=2, home_or_away="H", result=None,
        ),
        SimpleNamespace(
            game_id="next-day", season="2026-27",
            game_date=datetime(2026, 10, 16, 5, tzinfo=timezone.utc),
            team_id=3, opponent_team_id=4, home_or_away="H", result=None,
        ),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    db_context = MagicMock()
    db_context.__enter__.return_value = db

    with (
        patch("app.services.daily_archive_service.get_db_context", return_value=db_context),
        patch("app.services.daily_archive_service.current_eastern_date", return_value=date(2026, 10, 15)),
        patch(
            "app.services.daily_archive_service._team_name_map",
            return_value={
                1: {"team_id": 1, "name": "One", "abbreviation": "ONE"},
                2: {"team_id": 2, "name": "Two", "abbreviation": "TWO"},
            },
        ),
    ):
        archive = build_daily_archive_index(season="2026-27")

    assert [entry["date"] for entry in archive["entries"]] == [date(2026, 10, 15)]


class TestDailyIntelligenceRoute(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.app.config["IS_LOCAL"] = True
        self.app.config["FORCE_HTTPS"] = False
        self.client = self.app.test_client()

    def test_versioned_route_rejects_ambiguous_date(self):
        response = self.client.get("/daily/api/v1?date=03-03-2025")
        assert response.status_code == 400
        assert response.get_json()["error"] == "INVALID_DATE"

    def test_public_daily_defaults_to_current_eastern_date(self):
        with (
            patch("app.routes.daily_routes.current_eastern_date", return_value=date(2026, 10, 15)),
            patch("app.services.daily_intelligence_service.build_daily_intelligence_v1") as builder,
        ):
            builder.return_value.to_dict.return_value = {
                "contract_version": "daily-intelligence-v1",
                "target_date": "2026-10-15",
                "season": "2026-27",
                "status": "empty",
                "freshness": {"status": "unknown", "explanation": "No marker"},
                "summary": {"game_count": 0, "team_snapshot": {}, "player_snapshot": {}},
                "games": [], "insights": [], "disclaimers": [],
            }
            response = self.client.get("/daily/")

        assert response.status_code == 200
        assert builder.call_args.kwargs["target_date"] == date(2026, 10, 15)

    def test_versioned_route_returns_contract(self):
        with patch(
            "app.services.daily_intelligence_service.build_daily_intelligence_v1",
        ) as builder:
            builder.return_value.to_dict.return_value = {
                "contract_version": "daily-intelligence-v1",
                "status": "empty",
                "games": [],
            }
            response = self.client.get("/daily/api/v1?date=2025-03-03&season=2024-25")

        assert response.status_code == 200
        assert response.get_json()["contract_version"] == "daily-intelligence-v1"

    def test_public_daily_date_query_redirects_to_permanent_date_route(self):
        response = self.client.get("/daily/?date=2025-03-03&season=2024-25")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/daily/2025-03-03?season=2024-25")

    def test_canonical_historical_date_route_renders_v1_contract(self):
        with patch(
            "app.services.daily_intelligence_service.build_daily_intelligence_v1",
        ) as builder:
            builder.return_value.to_dict.return_value = {
                "contract_version": "daily-intelligence-v1",
                "target_date": "2025-03-03",
                "season": "2024-25",
                "status": "empty",
                "freshness": {"status": "unknown", "explanation": "No marker"},
                "summary": {"game_count": 0, "insight_count": 1, "team_snapshot": {}, "player_snapshot": {}},
                "games": [],
                "insights": [],
                "disclaimers": ["descriptive only"],
            }
            response = self.client.get("/daily/2025-03-03?season=2024-25")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "The slate, interpreted." in html
        assert "/daily/2025-03-03" in html
        assert "/daily/2025-03-02?season=2024-25" in html
        assert "/daily/2025-03-04?season=2024-25" in html
        assert "/daily/archive?season=2024-25" in html

    def test_archive_route_renders_historical_index(self):
        with patch(
            "app.services.daily_archive_service.build_daily_archive_index",
            return_value={
                "entries": [
                    {
                        "date": date(2025, 3, 3),
                        "season": "2024-25",
                        "game_count": 1,
                        "completed_count": 1,
                        "matchups": [
                            {
                                "game_id": "0022400888",
                                "completed": True,
                                "away": {"abbreviation": "AWY"},
                                "home": {"abbreviation": "HOM"},
                            }
                        ],
                    }
                ],
                "season": None,
                "limit": 60,
                "offset": 0,
                "has_previous": False,
                "has_next": False,
                "total_dates": 1,
            },
        ):
            response = self.client.get("/daily/archive")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "The archive" in html
        assert "AWY" in html
        assert "/matchup/2025-03-03/AWY-HOM" in html
        assert "Durable schedule rows, grouped by Eastern slate date" in html
        assert "schedule rows only" in html

    def test_historical_matchup_route_renders_and_rejects_bad_slug(self):
        detail = {
            "package": {
                "contract_version": "daily-intelligence-v1",
                "freshness": {"status": "unknown", "as_of": None},
            },
            "season": "2024-25",
            "game": {
                "game_id": "0022400888",
                "state": "completed",
                "tipoff": "07:00 PM",
                "matchup_priority": {"score": 3.0, "reasons": ["team form signal"]},
                "home": {"name": "Home Team", "abbreviation": "HOM", "team_id": 1},
                "away": {"name": "Away Team", "abbreviation": "AWY", "team_id": 2},
                "actual": {
                    "status": "final",
                    "home_score": 112,
                    "away_score": 105,
                    "home_result": "W",
                    "away_result": "L",
                    "winner": "Home Team",
                    "margin": 7,
                    "box_score": {
                        "source": "canonical_player_game_facts",
                        "completeness": "partial",
                        "coverage": "one_team",
                        "as_of": "2025-03-04T04:00:00+00:00",
                        "note": "Available canonical traditional player-game rows. Full official game coverage is not verified.",
                        "teams": {
                            "1": [{"player_name": "Test Scorer", "participation_status": "played",
                                   "completeness_status": "complete", "minutes": "32:10", "points": 0,
                                   "field_goals_made": 0, "field_goals_attempted": 4,
                                   "three_pointers_made": None, "three_pointers_attempted": None,
                                   "free_throws_made": 0, "free_throws_attempted": 0,
                                   "rebounds": 3, "assists": 2, "steals": 0, "blocks": 0,
                                   "turnovers": 1, "fouls": 2, "plus_minus": -3}],
                            "2": [],
                        },
                    },
                },
                "signals": {
                    "environment": {"pace_projection": 101.0, "scoring_env_index": 100.0, "completeness": "complete"},
                    "team_form": {"home": {"net_rating_delta": 2.0}, "away": {"net_rating_delta": -1.0}},
                    "schedule_pressure": {"home": {"days_rest": 1}, "away": {"days_rest": 2}},
                    "availability_uncertainty": {"home": {"observations": []}, "away": {"observations": []}},
                },
                "market": {"books_count": 2},
                "players_to_watch": [{"player_name": "Future Player Page"}],
            },
            "insights": [],
        }
        with patch("app.services.daily_archive_service.build_historical_matchup", return_value=detail):
            response = self.client.get("/matchup/2025-03-03/AWY-HOM")

        assert response.status_code == 200
        assert "Away Team" in response.get_data(as_text=True)
        assert "What actually happened" in response.get_data(as_text=True)
        assert "112" in response.get_data(as_text=True)
        assert "Test Scorer" in response.get_data(as_text=True)
        assert "0/4" in response.get_data(as_text=True)
        assert "No canonical player rows are available for AWY" in response.get_data(as_text=True)
        assert "Full official game coverage is not verified" in response.get_data(as_text=True)
        assert "Odds pilot" not in response.get_data(as_text=True)
        assert "Future Player Page" not in response.get_data(as_text=True)
        detail["game"]["actual"]["status"] = "scheduled"
        with patch("app.services.daily_archive_service.build_historical_matchup", return_value=detail):
            scheduled_response = self.client.get("/matchup/2025-03-03/AWY-HOM")
        assert "What actually happened" not in scheduled_response.get_data(as_text=True)
        assert "Test Scorer" not in scheduled_response.get_data(as_text=True)
        assert self.client.get("/matchup/2025-03-03/not-a-matchup").status_code == 404

    def test_design_lab_renders_the_daily_v1_shell(self):
        with patch(
            "app.services.daily_intelligence_service.build_daily_intelligence_v1"
        ) as builder:
            builder.return_value.to_dict.return_value = {
                "contract_version": "daily-intelligence-v1",
                "target_date": "2025-03-03",
                "status": "available",
                "freshness": {
                    "status": "unknown",
                    "explanation": "No validated ingest marker is available",
                },
                "summary": {
                    "game_count": 1,
                    "team_snapshot": {"completeness": "complete"},
                    "player_snapshot": {"completeness": "legacy_unversioned"},
                },
                "games": [],
                "insights": [
                    {
                        "kind": "slate_summary",
                        "priority": 1,
                        "headline": "1 game",
                        "explanation": "demo",
                        "source": "test",
                    }
                ],
                "disclaimers": [],
            }

            response = self.client.get("/design/daily-v1")

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "The slate" in html
        assert "daily-intelligence-v1" in html
        assert "daily/api/v1?date=2025-03-03&amp;season=2024-25" in html
        assert "freshness and source health remain explicit" in html
        assert "The package is healthy" not in html
