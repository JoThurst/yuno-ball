import importlib.util
from datetime import date
from pathlib import Path
from unittest.mock import Mock


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "reconcile_release_databases.py"
SPEC = importlib.util.spec_from_file_location("reconcile_release_databases", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def _snapshot():
    return {
        "alembic_revision": "head",
        "table_counts": {"game_schedule": 4},
        "release_season_counts": {"game_schedule": 4},
        "release_seasons": ["2024-25"],
        "duplicate_groups": {"game_schedule": 0},
        "pair_failures": {"game_schedule": 0},
        "representative_dates": {"2025-03-03": {"rows": 2, "games": 1}},
        "latest_validated_ingest": {"run_id": "run-1"},
    }


def test_matching_clean_snapshots_pass():
    assert module.compare_snapshots(_snapshot(), _snapshot()) == []


def test_mismatch_and_invariant_failures_are_credential_free():
    source = _snapshot()
    target = _snapshot()
    target["table_counts"] = {"game_schedule": 2}
    target["duplicate_groups"] = {"game_schedule": 1}
    target["pair_failures"] = {"game_schedule": 1}

    assert module.compare_snapshots(source, target) == [
        "source_target_mismatch:table_counts",
        "target:duplicate_groups:game_schedule",
        "target:pair_failures:game_schedule",
    ]


def test_table_allowlist_is_static():
    assert module.TABLES == (
        "teams",
        "game_schedule",
        "team_game_stats",
        "gamelogs",
        "player_game_facts",
        "ingestion_runs",
        "ingestion_task_runs",
    )


def test_representative_date_uses_canonical_eastern_calendar_contract():
    cursor = Mock()
    cursor.fetchone.return_value = (18, 9)
    target_date = date(2025, 3, 3)

    result = module._representative_date_count(cursor, target_date)

    query, parameters = cursor.execute.call_args.args
    assert module.EASTERN_GAME_DATE_SQL in query
    assert "game_date::date" not in query
    assert parameters == (target_date,)
    assert result == {"rows": 18, "games": 9}


def test_snapshot_rejects_partial_or_validation_only_ingest_markers(monkeypatch):
    cursor = Mock()
    cursor.fetchone.side_effect = [
        ("head",),
        *((0,) for _ in module.TABLES),
        *((0,) for _ in range(7)),
        None,
    ]
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    connection = Mock()
    connection.cursor.return_value = cursor
    monkeypatch.setattr(module.psycopg2, "connect", Mock(return_value=connection))

    snapshot = module.collect_snapshot("hidden", [], ["2024-25"])

    ingest_query = cursor.execute.call_args_list[-1].args[0]
    assert "validate_only" in ingest_query
    assert "fetch_only" in ingest_query
    assert "calc_only" in ingest_query
    assert snapshot["latest_validated_ingest"] is None
    connection.set_session.assert_called_once_with(readonly=True, autocommit=False)
