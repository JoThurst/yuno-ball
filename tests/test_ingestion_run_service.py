"""Focused unit tests for ingestion run tracking contracts."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.ingestion_run_service import (
    IngestionRunTracker,
    finish_task,
    infer_row_count,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, None),
        (False, None),
        (7, 7),
        ([1, 2, 3], 3),
        ((1, 2), 2),
        ({"a": 1}, 1),
        ("not a row collection", None),
    ],
)
def test_infer_row_count_is_conservative(value, expected):
    assert infer_row_count(value) == expected


def test_run_rejects_invalid_terminal_status_before_database_access():
    tracker = IngestionRunTracker(
        run_type="test",
        source="unit",
        season="2025-26",
        target_date=date(2026, 1, 1),
    )
    with pytest.raises(ValueError, match="Invalid terminal ingestion run status"):
        tracker.finish("unknown")


def test_run_constructor_enforces_canonical_season():
    with pytest.raises(ValueError, match="expected YYYY-YY"):
        IngestionRunTracker(
            run_type="test",
            source="unit",
            season="2025",
            target_date=date(2026, 1, 1),
        )


def test_task_rejects_invalid_terminal_status_before_database_access():
    with pytest.raises(ValueError, match="Invalid terminal task status"):
        finish_task("not-used", "partial")


def test_lock_connection_closes_when_acquisition_query_fails():
    connection = MagicMock()
    connection.execute.side_effect = RuntimeError("database unavailable")
    fake_engine = MagicMock()
    fake_engine.connect.return_value = connection
    tracker = IngestionRunTracker(
        run_type="test",
        source="unit",
        season="2025-26",
        target_date=date(2026, 1, 1),
        code_version="test-version",
    )

    with patch("app.services.ingestion_run_service.engine", fake_engine):
        with pytest.raises(RuntimeError, match="database unavailable"):
            tracker.__enter__()

    connection.close.assert_called_once_with()
    assert tracker._lock_connection is None
