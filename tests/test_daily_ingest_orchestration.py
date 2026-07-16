"""Unit tests for daily ingestion gating and publication behavior."""

from datetime import date, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import daily_ingest


def _args(**overrides):
    values = {
        "validate_only": False,
        "calc_only": False,
        "fetch_only": False,
        "proxy": False,
        "local": False,
        "force_gamelogs": False,
        "fetch_tasks": None,
        "exclude_fetch": None,
        "force_calc": False,
        "calc_tasks": None,
        "exclude_calc": None,
        "skip_validate": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_full_pipeline_passes_explicit_season_and_date_to_children():
    args = _args()
    with patch.object(daily_ingest, "run_script", return_value=True) as run_script, patch.object(
        daily_ingest, "_run_validation", return_value=True
    ) as validate:
        result = daily_ingest.execute_pipeline(
            args,
            "2025-26",
            date(2026, 7, 15),
            "run-123",
        )

    assert result["overall_ok"] is True
    assert result["validation_status"] == "passed"
    fetch_call, calculate_call = run_script.call_args_list
    assert fetch_call.args[0] == "daily_fetch.py"
    assert fetch_call.args[1][:2] == ["--season", "2025-26"]
    assert calculate_call.args[0] == "daily_calculate.py"
    assert ["--date", "2026-07-15"] == calculate_call.args[1][2:4]
    validate.assert_called_once_with("run-123", "2025-26", date(2026, 7, 15))


def test_default_fetch_order_reconciles_results_before_gamelog_refresh():
    assert daily_ingest.FETCH_TASKS.index("schedule") < daily_ingest.FETCH_TASKS.index(
        "teamstats"
    )
    assert daily_ingest.FETCH_TASKS.index(
        "teamstats"
    ) < daily_ingest.FETCH_TASKS.index("schedule_reconcile")
    assert daily_ingest.FETCH_TASKS.index(
        "schedule_reconcile"
    ) < daily_ingest.FETCH_TASKS.index("gamelogs")


def test_default_calculation_order_publishes_team_snapshots_after_schedule_factors():
    assert daily_ingest.CALC_TASKS.index("schedule") < daily_ingest.CALC_TASKS.index(
        "team_snapshots"
    )
    assert daily_ingest.CALC_TASKS.index("team_snapshots") < daily_ingest.CALC_TASKS.index(
        "metrics"
    )


def test_critical_fetch_failure_skips_calculation_and_validation():
    args = _args()
    with patch.object(daily_ingest, "run_script", return_value=False) as run_script, patch.object(
        daily_ingest, "_run_validation"
    ) as validate:
        result = daily_ingest.execute_pipeline(
            args,
            "2025-26",
            date(2026, 7, 15),
            "run-123",
        )

    assert result["overall_ok"] is False
    assert result["skipped_calc"] is True
    assert run_script.call_count == 1
    validate.assert_not_called()


def test_success_marker_is_atomic_and_contains_run_metadata(tmp_path: Path):
    with patch.object(daily_ingest, "project_root", tmp_path):
        daily_ingest.write_success_marker(
            "2025-26",
            date(2026, 7, 15),
            "run-123",
            True,
            True,
            True,
        )

    marker_path = tmp_path / "data" / "last_ingest_success.json"
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-123"
    assert payload["target_date"] == "2026-07-15"
    assert payload["validation_success"] is True
    assert not marker_path.with_suffix(".json.tmp").exists()


def test_main_rejects_historical_mutating_run_before_database_access():
    historical_date = date.today() - timedelta(days=1)
    args = _args(
        list=False,
        date=historical_date.isoformat(),
        season="2025-26",
        skip_validate=False,
    )
    with patch.object(daily_ingest, "parse_args", return_value=args), patch.object(
        daily_ingest, "resolve_active_ingestion_season"
    ) as resolve_season, patch.object(daily_ingest, "IngestionRunTracker") as tracker:
        exit_code = daily_ingest.main()

    assert exit_code == 2
    resolve_season.assert_not_called()
    tracker.assert_not_called()
