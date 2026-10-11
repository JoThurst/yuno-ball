from contextlib import contextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM
from app.models.player_sqlalchemy import PlayerORM
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)
from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
from app.models.player_game_status_sqlalchemy import PlayerGameStatusORM
from app.services.slate_service import build_slate_context


UTC = timezone.utc
GAME_ID = "0022500197"
TARGET_DATE = date(2025, 11, 9)


def _schedule_rows():
    tipoff = datetime(2025, 11, 10, 0, tzinfo=UTC)
    common = {"game_id": GAME_ID, "game_date": tipoff}
    return [
        {
            **common,
            "team_id": 1,
            "opponent_team_id": 2,
            "team_name": "Home Team",
            "opponent_name": "Away Team",
            "team_abbreviation": "HOM",
            "opponent_abbreviation": "AWY",
            "home_or_away": "H",
            "result": None,
        },
        {
            **common,
            "team_id": 2,
            "opponent_team_id": 1,
            "team_name": "Away Team",
            "opponent_name": "Home Team",
            "team_abbreviation": "AWY",
            "opponent_abbreviation": "HOM",
            "home_or_away": "A",
            "result": None,
        },
    ]


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def distinct(self, *args):
        return self

    def limit(self, *args):
        return self

    def all(self):
        return list(self.rows)


class _Session:
    def __init__(self, rows_by_model):
        self.rows_by_model = rows_by_model
        self.queried = []

    def query(self, *models):
        model_key = models[0] if len(models) == 1 else tuple(models)
        self.queried.append(model_key)
        return _Query(self.rows_by_model.get(model_key, []))


def _context_for(session):
    @contextmanager
    def context():
        yield session

    return context


def _build(session):
    with (
        patch("app.services.slate_service.get_db_context", _context_for(session)),
        patch(
            "app.services.slate_service.GameScheduleORM.get_by_date",
            return_value=_schedule_rows(),
        ),
        patch("app.services.slate_service._load_roster_players", return_value={}),
        patch("app.services.slate_service.get_ingest_freshness", return_value={}),
    ):
        return build_slate_context(
            target_date=TARGET_DATE,
            season="2025-26",
            include_odds=False,
            include_injuries=False,
            player_limit_per_team=0,
        )


def test_historical_slate_uses_versioned_team_and_environment_snapshots():
    cutoff = datetime(2025, 11, 9, 15, tzinfo=UTC)
    teams = [
        SimpleNamespace(
            game_id=GAME_ID,
            team_id=team_id,
            net_rtg_delta=delta,
            flags=[{"flag_type": "surging_net_rating"}],
        )
        for team_id, delta in ((1, 4.2), (2, -2.1))
    ]
    environment = SimpleNamespace(
        game_id=GAME_ID,
        pace_projection=101.5,
        scoring_env_index=103.0,
        three_env_index=100.0,
        chaos_index=98.0,
        home_off_rtg_lastn=114.0,
        away_off_rtg_lastn=111.0,
        home_def_rtg_lastn=108.0,
        away_def_rtg_lastn=112.0,
        tags=["fast_pace"],
        feature_as_of=cutoff,
        calculation_version="team-v2.1",
        completeness_status="complete",
    )
    session = _Session(
        {
            TeamGameFeatureSnapshotORM: teams,
            GameEnvironmentSnapshotORM: [environment],
        }
    )

    result = _build(session)

    assert result["team_snapshot"]["source"] == "versioned_snapshot"
    assert result["team_snapshot"]["fallback_used"] is False
    assert result["team_snapshot"]["completeness"] == "complete"
    assert result["games"][0]["home_net_delta"] == 4.2
    assert result["games"][0]["environment"]["feature_as_of"] == cutoff.isoformat()
    assert TeamDailyMetricsORM not in session.queried
    assert GameEnvironmentDailyORM not in session.queried


def test_missing_historical_snapshot_does_not_fall_forward_to_legacy_latest():
    session = _Session({})

    result = _build(session)

    assert result["team_snapshot"]["completeness"] == "partial_or_missing"
    assert result["team_snapshot"]["fallback_used"] is False
    assert result["games"][0]["home_net_delta"] is None
    assert result["games"][0]["environment"] is None
    assert result["games"][0]["actual"]["status"] == "scheduled"
    assert result["games"][0]["actual"]["box_score"]["leaders"] == {}
    assert result["games"][0]["actual"]["box_score"]["teams"] == {}
    assert TeamDailyMetricsORM not in session.queried
    assert GameEnvironmentDailyORM not in session.queried


def test_slate_does_not_render_postgame_status_as_pregame_injury_data():
    session = _Session({PlayerGameStatusORM: [object()]})

    with (
        patch("app.services.slate_service.get_db_context", _context_for(session)),
        patch(
            "app.services.slate_service.GameScheduleORM.get_by_date",
            return_value=_schedule_rows(),
        ),
        patch("app.services.slate_service._load_roster_players", return_value={}),
        patch("app.services.slate_service.get_ingest_freshness", return_value={}),
    ):
        build_slate_context(
            target_date=TARGET_DATE,
            season="2025-26",
            include_odds=False,
            include_injuries=True,
            player_limit_per_team=0,
        )

    assert PlayerGameStatusORM not in session.queried


def test_final_slate_exposes_partial_canonical_rows_and_preserves_v1_leaders():
    scheduled = [
        {
            **row,
            "result": "W" if row["team_id"] == 1 else "L",
            "team_score": 112 if row["team_id"] == 1 else 105,
            "opponent_score": 105 if row["team_id"] == 1 else 112,
        }
        for row in _schedule_rows()
    ]
    selected_at = datetime(2025, 11, 10, 4, tzinfo=UTC)
    played = SimpleNamespace(
        canonical_game_id=GAME_ID, canonical_team_id=1, canonical_player_id=10,
        minutes="32:10", participation_status="played", completeness_status="complete",
        field_goals_made=5, field_goals_attempted=8, three_pointers_made=1,
        three_pointers_attempted=2, free_throws_made=2, free_throws_attempted=2,
        points=13, rebounds_total=3, assists=2, steals=1, blocks=0, turnovers=1,
        fouls_personal=2, plus_minus_points=4, source_name="BoxScoreTraditionalV3",
        selected_at=selected_at,
    )
    dnp = SimpleNamespace(
        canonical_game_id=GAME_ID, canonical_team_id=1, canonical_player_id=11,
        minutes=None, participation_status="did_not_play", completeness_status="partial",
        field_goals_made=None, field_goals_attempted=None, three_pointers_made=None,
        three_pointers_attempted=None, free_throws_made=None, free_throws_attempted=None,
        points=None, rebounds_total=None, assists=None, steals=None, blocks=None,
        turnovers=None, fouls_personal=None, plus_minus_points=None,
        source_name="BoxScoreTraditionalV3", selected_at=selected_at,
    )
    session = _Session({
        PlayerGameFactORM: [played, dnp],
        (PlayerORM.player_id, PlayerORM.name): [(10, "Scorer"), (11, "Inactive")],
    })
    with (
        patch("app.services.slate_service.get_db_context", _context_for(session)),
        patch("app.services.slate_service.GameScheduleORM.get_by_date", return_value=scheduled),
        patch("app.services.slate_service._load_roster_players", return_value={}),
        patch("app.services.slate_service.get_ingest_freshness", return_value={}),
    ):
        result = build_slate_context(
            target_date=TARGET_DATE, season="2025-26", include_odds=False,
            include_injuries=False, player_limit_per_team=0,
        )

    box = result["games"][0]["actual"]["box_score"]
    assert box["coverage"] == "one_team"
    assert box["completeness"] == "partial"
    assert [row["player_name"] for row in box["teams"]["1"]] == ["Scorer", "Inactive"]
    assert box["leaders"]["1"][0]["player_name"] == "Scorer"
    assert "2" not in box["leaders"]
