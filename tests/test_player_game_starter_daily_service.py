from types import SimpleNamespace

from app.services.player_game_starter_daily_service import _eligible_games


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self, schedule_rows, evidence_rows):
        self.schedule_rows = schedule_rows
        self.evidence_rows = evidence_rows
        self.calls = 0

    def query(self, *models):
        self.calls += 1
        return _Query(self.schedule_rows if self.calls == 1 else self.evidence_rows)


def test_eligible_games_require_completed_reciprocal_schedule_and_skip_live_evidence():
    rows = [
        SimpleNamespace(
            game_id="0022600001", team_id=1, opponent_team_id=2, result="W",
            game_date=SimpleNamespace(date=lambda: None),
        ),
        SimpleNamespace(
            game_id="0022600001", team_id=2, opponent_team_id=1, result="L",
            game_date=SimpleNamespace(date=lambda: None),
        ),
        SimpleNamespace(
            game_id="0022600002", team_id=1, opponent_team_id=2, result=None,
            game_date=SimpleNamespace(date=lambda: None),
        ),
    ]

    assert _eligible_games(
        _DB(rows, []), season="2026-27", season_type="Regular Season"
    ) == ["0022600001"]
