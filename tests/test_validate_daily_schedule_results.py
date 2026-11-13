"""Validation regression for an opening game skipped before TeamGameLog."""

import os
from datetime import date
from unittest.mock import patch

from app.services.schedule_result_reconciliation_service import ScheduleResultSource


with patch.dict(os.environ, {"DATABASE_URL": "postgresql://fixture/unused"}), patch(
    "db_config.init_db"
):
    from scripts import validate_daily_data


def _schedule(team_id: int, opponent_id: int, side: str) -> ScheduleResultSource:
    return ScheduleResultSource(
        game_id="0022600001",
        season="2026-27",
        team_id=team_id,
        opponent_team_id=opponent_id,
        slate_date=date(2026, 10, 21),
        home_or_away=side,
        result=None,
        score=None,
    )


def test_validation_fails_when_past_null_result_has_no_team_game_rows():
    schedule_rows = [_schedule(10, 20, "H"), _schedule(20, 10, "A")]

    with patch.object(
        validate_daily_data,
        "load_schedule_result_sources",
        return_value=(schedule_rows, []),
    ):
        result = validate_daily_data.check_schedule_result_consistency(
            object(), "2026-27", date(2026, 10, 22)
        )

    assert result.severity == validate_daily_data.CRITICAL
    assert result.passed is False
    assert result.details == {"missing_team_game_ids": ["0022600001"]}
