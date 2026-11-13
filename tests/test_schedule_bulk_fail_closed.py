"""Schedule batches must fail before a partial refresh is reported successful."""

from datetime import datetime
from unittest.mock import patch

import pytest

from app.database import Base
from app.models.gameschedule_sqlalchemy import GameScheduleORM


def test_schedule_fk_target_is_registered_with_the_model():
    assert "external_dataset_imports" in Base.metadata.tables


def test_schedule_bulk_create_propagates_first_row_failure():
    rows = [
        {
            "game_id": f"game-{number}",
            "season": "2026-27",
            "team_id": number,
            "opponent_team_id": number + 1,
            "game_date": datetime(2026, 10, 21),
            "home_or_away": "H",
        }
        for number in (1, 2, 3)
    ]

    class Session:
        def flush(self):
            pytest.fail("bulk flush must not follow a row failure")

    seen = []

    def create(**values):
        seen.append(values["game_id"])
        if values["game_id"] == "game-2":
            raise RuntimeError("mapping failed")

    with patch.object(GameScheduleORM, "create", side_effect=create):
        with pytest.raises(RuntimeError, match="mapping failed"):
            GameScheduleORM.bulk_create(rows, db=Session())

    assert seen == ["game-1", "game-2"]
