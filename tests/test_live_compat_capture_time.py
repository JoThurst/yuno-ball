"""Legacy Live captures must store aware UTC observation times."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from app.models.game_odds_sqlalchemy import GameOddsORM
from app.models.player_game_status_sqlalchemy import PlayerGameStatusORM


@pytest.mark.parametrize("model,record", [
    (PlayerGameStatusORM, {
        "game_id": "0022600001", "player_id": 1, "team_id": 2,
        "game_date": date(2026, 10, 20), "season": "2026-27", "played": False,
    }),
    (GameOddsORM, {
        "game_id": "0022600008", "game_date": date(2026, 10, 23),
        "season": "2026-27", "home_team_id": 1, "away_team_id": 2,
        "sportsbook_id": "book-1", "home_ml_odds": 1.8, "away_ml_odds": 2.0,
    }),
])
def test_bulk_capture_timestamps_are_aware_utc(model, record):
    class Session:
        params = None

        def execute(self, statement):
            self.params = statement.compile(dialect=postgresql.dialect()).params

        def flush(self):
            pass

    session = Session()
    assert model.bulk_create([record], db=session) == 1
    for key in ("recorded_at_m0", "updated_at_m0"):
        captured = session.params[key]
        assert captured.tzinfo is not None
        assert captured.utcoffset().total_seconds() == 0
        assert abs((datetime.now(timezone.utc) - captured).total_seconds()) < 10
