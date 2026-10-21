from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameFactORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.services.completed_slate_audit_service import (
    _utc_slate_bounds,
    build_completed_slate_audit,
)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(self.rows.get(model, []))


def _rows(*, advanced=True, team_margin=True):
    day = datetime(2026, 10, 20)
    return {
        GameScheduleORM: [
            SimpleNamespace(game_id="g1", team_id=1, opponent_team_id=2,
                            home_or_away="H", result="W", team_score=111,
                            opponent_score=100, source_name="nba", game_date=day),
            SimpleNamespace(game_id="g1", team_id=2, opponent_team_id=1,
                            home_or_away="A", result="L", team_score=100,
                            opponent_score=111, source_name="nba", game_date=day),
        ],
        TeamGameStatsORM: [
            SimpleNamespace(game_id="g1", team_id=1, opponent_team_id=2,
                            pts=111, wl="W", plus_minus=11 if team_margin else None),
            SimpleNamespace(game_id="g1", team_id=2, opponent_team_id=1,
                            pts=100, wl="L", plus_minus=-11),
        ],
        GameLogORM: [SimpleNamespace(game_id="g1")],
        PlayerGameFactORM: [SimpleNamespace(canonical_game_id="g1")],
        PlayerGameAdvancedFactORM: (
            [SimpleNamespace(canonical_game_id="g1")] if advanced else []
        ),
    }


def test_utc_slate_bounds_include_late_eastern_game_and_dst_transition():
    assert _utc_slate_bounds(date(2026, 10, 20)) == (
        datetime(2026, 10, 20, 4), datetime(2026, 10, 21, 4),
    )
    assert _utc_slate_bounds(date(2026, 11, 1)) == (
        datetime(2026, 11, 1, 4), datetime(2026, 11, 2, 5),
    )


@patch("app.services.completed_slate_audit_service.build_reconciliation_report",
       return_value={"status": "passed"})
def test_completed_slate_passes_only_with_expected_game_and_reconciliation(reconcile):
    report = build_completed_slate_audit(
        FakeDB(_rows()), season="2026-27", target_date=date(2026, 10, 20),
        expected_games=1,
    )
    assert report["status"] == "passed"
    reconcile.assert_called_once()
    assert report["games"][0]["problems"] == []


@patch("app.services.completed_slate_audit_service.build_reconciliation_report")
def test_completed_slate_fails_closed_on_missing_advanced_and_margin(reconcile):
    report = build_completed_slate_audit(
        FakeDB(_rows(advanced=False, team_margin=False)), season="2026-27",
        target_date=date(2026, 10, 20), expected_games=1,
    )
    assert report["status"] == "failed"
    assert "advanced_facts_missing" in report["games"][0]["problems"]
    assert "team_result_or_margin_conflict" in report["games"][0]["problems"]
    reconcile.assert_not_called()


@patch("app.services.completed_slate_audit_service.build_reconciliation_report",
       return_value={"status": "passed"})
def test_canonical_reconciliation_runs_when_only_legacy_logs_are_missing(reconcile):
    rows = _rows()
    rows[GameLogORM] = []
    report = build_completed_slate_audit(
        FakeDB(rows), season="2026-27", target_date=date(2026, 10, 20),
        expected_games=1,
    )
    assert report["status"] == "failed"
    assert report["canonical_reconciliation"] == {"status": "passed"}
    reconcile.assert_called_once()


@patch("app.services.completed_slate_audit_service.build_reconciliation_report")
def test_completed_slate_rejects_empty_local_coverage(reconcile):
    report = build_completed_slate_audit(
        FakeDB({}), season="2026-27", target_date=date(2026, 10, 20),
        expected_games=3,
    )
    assert report["status"] == "failed"
    assert report["observed_games"] == 0
    reconcile.assert_not_called()


@patch("app.services.completed_slate_audit_service.build_reconciliation_report",
       return_value={"status": "passed"})
def test_completed_slate_rejects_missing_expected_game_even_when_observed_game_passes(reconcile):
    report = build_completed_slate_audit(
        FakeDB(_rows()), season="2026-27", target_date=date(2026, 10, 20),
        expected_games=2,
    )
    assert report["status"] == "failed"
    assert report["observed_games"] == 1
    reconcile.assert_called_once()
