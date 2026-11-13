"""The scheduled official PDF writer must respect the daily ingestion lock."""

from argparse import Namespace
from unittest.mock import MagicMock

from scripts import run_official_injury_pipeline as pipeline
import pytest

identity_count_query = pipeline.unresolved_identity_count
pending_count_query = pipeline.pending_parse_count


@pytest.fixture(autouse=True)
def no_live_identity_query(monkeypatch):
    monkeypatch.setattr(pipeline, "unresolved_identity_count", lambda start, end: 0)
    monkeypatch.setattr(pipeline, "pending_parse_count", lambda start, end: 0)


def _args(tmp_path):
    return Namespace(
        archive_root=str(tmp_path),
        season="2026-27",
        report_date="2026-10-23",
        lookback_days=2,
        retry_interval_hours=2,
        freshness_threshold_hours=4,
        parse_max_documents=100,
    )


def test_lock_collision_prevents_both_writers(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = False
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    collect = MagicMock()
    parse = MagicMock()
    monkeypatch.setattr(pipeline, "engine", engine)
    monkeypatch.setattr(pipeline, "collect_main", collect)
    monkeypatch.setattr(pipeline, "parse_main", parse)
    reconcile = MagicMock()
    monkeypatch.setattr(pipeline, "reconcile_main", reconcile)

    assert pipeline.run_pipeline(_args(tmp_path)) == 3
    collect.assert_not_called()
    parse.assert_not_called()
    reconcile.assert_not_called()


def test_parser_runs_after_partial_collection_and_lock_is_released(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = True
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    order = []
    monkeypatch.setattr(pipeline, "engine", engine)
    monkeypatch.setattr(pipeline, "collect_main", lambda argv: order.append(("collect", argv)) or 1)
    monkeypatch.setattr(pipeline, "parse_main", lambda argv: order.append(("parse", argv)) or 0)
    monkeypatch.setattr(pipeline, "reconcile_main", lambda argv: order.append(("identity", argv)) or 0)

    assert pipeline.run_pipeline(_args(tmp_path)) == 1
    assert [phase for phase, _ in order] == ["collect", "parse", "identity"]
    assert "--apply" in order[0][1]
    assert order[1][1][order[1][1].index("--start-date") + 1] == "2026-10-21"
    assert connection.execute.call_count == 2  # acquire and release


def test_identity_failure_makes_pipeline_fail(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = True
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(pipeline, "engine", engine)
    monkeypatch.setattr(pipeline, "collect_main", lambda argv: 0)
    monkeypatch.setattr(pipeline, "parse_main", lambda argv: 0)
    identity = MagicMock(return_value=1)
    monkeypatch.setattr(pipeline, "reconcile_main", identity)
    assert pipeline.run_pipeline(_args(tmp_path)) == 1
    argv = identity.call_args.args[0]
    assert argv[argv.index('--to-date') + 1] == '2026-10-24'
    assert '--resolve-player' in argv


def test_unresolved_identities_do_not_report_pipeline_success(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = True
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(pipeline, "engine", engine)
    monkeypatch.setattr(pipeline, "collect_main", lambda argv: 0)
    monkeypatch.setattr(pipeline, "parse_main", lambda argv: 0)
    monkeypatch.setattr(pipeline, "reconcile_main", lambda argv: 0)
    monkeypatch.setattr(pipeline, "unresolved_identity_count", lambda start, end: 2)
    assert pipeline.run_pipeline(_args(tmp_path)) == 1


def test_parser_cap_exhaustion_keeps_pipeline_retryable(monkeypatch, tmp_path):
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = True
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(pipeline, "engine", engine)
    monkeypatch.setattr(pipeline, "collect_main", lambda argv: 0)
    monkeypatch.setattr(pipeline, "parse_main", lambda argv: 0)
    monkeypatch.setattr(pipeline, "reconcile_main", lambda argv: 0)
    monkeypatch.setattr(pipeline, "pending_parse_count", lambda start, end: 1)
    assert pipeline.run_pipeline(_args(tmp_path)) == 1


def test_completion_queries_include_submission_only_reports_and_unparsed_queue(monkeypatch):
    from datetime import date
    from sqlalchemy import create_engine, text, event
    from sqlalchemy.engine import Engine
    from app.database import set_search_path
    from types import SimpleNamespace

    database = create_engine("sqlite://")
    event.remove(Engine, "connect", set_search_path)
    try:
        connection = database.connect()
    finally:
        event.listen(Engine, "connect", set_search_path)
    with connection:
        for statement in [
            "CREATE TABLE availability_report_documents (document_id TEXT, report_date TEXT, parse_status TEXT)",
            "CREATE TABLE availability_observations (report_document_id TEXT, game_id TEXT, team_id INT, player_id INT)",
            "CREATE TABLE team_report_submission_status (report_document_id TEXT, game_id TEXT, team_id INT)",
            "INSERT INTO availability_report_documents VALUES ('inside','2026-10-23','parsed'), ('pending','2026-10-23',NULL), ('outside','2026-10-20','not_parsed')",
            "INSERT INTO team_report_submission_status VALUES ('inside',NULL,1), ('outside',NULL,NULL)",
        ]:
            connection.execute(text(statement))
        adapter = SimpleNamespace(
            execute=lambda statement, *args: None if str(statement).startswith('SET TRANSACTION') else connection.execute(statement, *args),
            rollback=lambda: None,
        )
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value = adapter
        monkeypatch.setattr(pipeline, 'engine', engine)
        assert identity_count_query(date(2026, 10, 23), date(2026, 10, 23)) == 1
        assert pending_count_query(date(2026, 10, 23), date(2026, 10, 23)) == 1
