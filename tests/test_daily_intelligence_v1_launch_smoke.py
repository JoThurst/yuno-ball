"""Focused launch smoke tests for the public Daily Intelligence V1 API."""

import os
from datetime import date, datetime, timezone
from unittest.mock import patch

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from app.services.daily_intelligence_service import build_daily_intelligence_v1
from tests.config import TestConfig


TARGET_DATE = date(2025, 3, 3)


def _context(*, games=None, freshness=None):
    return {
        "season": "2024-25",
        "games": games or [],
        "hot_players": [],
        "cold_players": [],
        "freshness": freshness or {},
        "team_snapshot": {"source": "versioned_snapshot", "completeness": "complete"},
        "player_snapshot": {"source": "versioned_snapshot", "completeness": "complete"},
    }


def _game(*, with_environment=True):
    return {
        "game_id": "0022400888",
        "game_date": datetime(2025, 3, 3, 0, tzinfo=timezone.utc),
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
        "home_schedule": {"team_id": 1, "days_rest": 0, "is_b2b": True},
        "away_schedule": {"team_id": 2, "days_rest": 2, "is_b2b": False},
        "environment": {
            "pace_projection": 103.1,
            "scoring_env_index": 104.0,
            "pace_label": "fast",
            "feature_as_of": datetime(2025, 3, 3, 15, tzinfo=timezone.utc),
            "calculation_version": "team-v2.1",
            "completeness": "complete",
        }
        if with_environment
        else {},
        "home_availability": {
            "source": "official_nba",
            "as_of": datetime(2025, 3, 3, 16, tzinfo=timezone.utc),
            "completeness": "complete",
            "observations": [],
            "unresolved_count": 0,
        },
        "away_availability": {
            "source": "official_nba",
            "as_of": datetime(2025, 3, 3, 16, tzinfo=timezone.utc),
            "completeness": "partial",
            "observations": [{"status": "Questionable"}],
            "unresolved_count": 1,
        },
        "home_players": [],
        "away_players": [],
    }


def _client():
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_LOCAL=True, FORCE_HTTPS=False)
    return app.test_client()


def test_public_api_exposes_descriptive_v1_contract_with_provenance():
    with patch(
        "app.services.daily_intelligence_service.build_slate_context",
        return_value=_context(
            games=[_game()],
            freshness={
                "source": "daily_ingest",
                "has_marker": True,
                "is_complete": True,
                "status": "success",
                "as_of": datetime(2025, 3, 3, 16, tzinfo=timezone.utc),
                "run_id": "run-daily-smoke",
            },
        ),
    ):
        response = _client().get("/daily/api/v1?date=2025-03-03&season=2024-25")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["contract_version"] == "daily-intelligence-v1"
    assert payload["target_date"] == "2025-03-03"
    assert payload["season"] == "2024-25"
    assert payload["status"] == "available"
    assert payload["freshness"] == {
        "source": "daily_ingest",
        "status": "fresh",
        "completeness": "complete",
        "as_of": "2025-03-03T16:00:00+00:00",
        "run_id": "run-daily-smoke",
        "target_date": "2025-03-03",
        "season": "2024-25",
        "is_stale": False,
        "has_marker": True,
        "explanation": "The latest ingest marker reports a validated run.",
    }
    assert payload["summary"]["game_count"] == 1
    game = payload["games"][0]
    assert game["state"] == "scheduled"
    assert game["home"]["abbreviation"] == "HOM"
    assert game["signals"]["environment"]["feature_as_of"] == "2025-03-03T15:00:00+00:00"
    assert game["provenance"]["availability"]["away"]["completeness"] == "partial"
    assert payload["disclaimers"]
    assert all("prediction" not in insight["kind"] for insight in payload["insights"])
    assert any("descriptive" in insight["explanation"] for insight in payload["insights"])


def test_public_api_returns_explicit_empty_state_without_fabricated_values():
    with patch(
        "app.services.daily_intelligence_service.build_slate_context",
        return_value=_context(),
    ):
        response = _client().get("/daily/api/v1?date=2025-03-03&season=2024-25")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "empty"
    assert payload["games"] == []
    assert payload["summary"]["game_count"] == 0
    assert payload["freshness"]["status"] == "unknown"
    assert payload["freshness"]["completeness"] == "unknown"
    assert payload["freshness"]["as_of"] is None
    assert payload["insights"][0]["kind"] == "slate_summary"
    assert payload["insights"][0]["metric_context"]["game_count"] == 0


def test_public_api_marks_partial_slate_and_preserves_partial_evidence():
    with patch(
        "app.services.daily_intelligence_service.build_slate_context",
        return_value=_context(
            games=[_game(with_environment=False)],
            freshness={
                "source": "daily_ingest",
                "has_marker": True,
                "is_complete": False,
                "status": "partial",
                "as_of": datetime(2025, 3, 3, 16, tzinfo=timezone.utc),
            },
        ),
    ):
        response = _client().get("/daily/api/v1?date=2025-03-03&season=2024-25")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "partial"
    assert payload["freshness"]["status"] == "partial"
    assert payload["freshness"]["completeness"] == "partial"
    assert payload["games"][0]["signals"]["environment"] == {}
    assert payload["games"][0]["provenance"]["availability"]["away"]["completeness"] == "partial"
    availability_insight = next(
        insight for insight in payload["insights"] if insight["kind"] == "availability_uncertainty"
    )
    assert availability_insight["completeness"] == "partial"
    assert availability_insight["metric_context"]["unresolved_count"] == 1


def test_public_api_rejects_ambiguous_date_before_building_package():
    with patch("app.services.daily_intelligence_service.build_daily_intelligence_v1") as builder:
        response = _client().get("/daily/api/v1?date=03-03-2025")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "INVALID_DATE",
        "message": "date must use YYYY-MM-DD",
    }
    builder.assert_not_called()
