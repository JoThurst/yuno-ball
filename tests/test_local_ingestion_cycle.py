from datetime import datetime, timezone
from unittest.mock import MagicMock
import subprocess

import pytest

from scripts import run_local_ingestion_cycle as cycle
from app.utils.fetch.smart_gamelog_fetcher import normalize_completed_gamelogs


@pytest.mark.parametrize('when,last,due', [
    ('2026-10-26T11:59:00+00:00', None, False),
    ('2026-10-26T12:00:00+00:00', '2026-10-24', True),
    ('2026-10-26T13:30:00+00:00', '2026-10-26', False),
    ('2026-12-01T12:59:00+00:00', None, False),
    ('2026-12-01T13:00:00+00:00', '2026-11-28', True),
])
def test_eastern_due_gate_and_missed_days(when, last, due):
    assert cycle.cycle_due(datetime.fromisoformat(when), last) is due


def response(rows):
    return {'resultSets': [{'headers': ['PLAYER_ID', 'GAME_ID', 'TEAM_ID', 'PTS', 'MIN', 'AST', 'REB', 'STL', 'BLK', 'TOV'],
                            'rowSet': [row + [0, 0, 0, 0, 0] for row in rows]}]}


def test_bulk_source_filters_other_games_and_preserves_zeros():
    rows = [[1, '0022600001', 10, 0, '5:00'], [2, '0022600001', 20, 4, '6:00'],
            [3, '0012600001', 10, 9, '1:00']]
    result = normalize_completed_gamelogs(response(rows), {('0022600001', 10), ('0022600001', 20)}, '2026-27')
    assert len(result) == 2
    assert result[0]['points'] == 0
    assert all(r['season'] == '2026-27' for r in result)


def test_bulk_source_rejects_missing_persisted_field_or_null_before_publication():
    data = response([[1, '0022600001', 10, 3, '5:00']])
    data['resultSets'][0]['headers'].remove('AST')
    with pytest.raises(ValueError, match='required columns'):
        normalize_completed_gamelogs(data, {('0022600001', 10)}, '2026-27')
    data = response([[1, '0022600001', 10, None, '5:00']])
    with pytest.raises(ValueError, match='required value'):
        normalize_completed_gamelogs(data, {('0022600001', 10)}, '2026-27')


@pytest.mark.parametrize('rows', [[], [[1, '0022600001', 99, 3, '5:00']],
    [[1, '0022600001', 10, 3, '5:00'], [1, '0022600001', 10, 3, '5:00']]])
def test_bulk_source_rejects_empty_wrong_team_and_duplicate_keys(rows):
    with pytest.raises(ValueError):
        normalize_completed_gamelogs(response(rows), {('0022600001', 10)}, '2026-27')


def test_bulk_source_rejects_missing_completed_game():
    with pytest.raises(ValueError, match='omits'):
        normalize_completed_gamelogs(response([[1, '0022600001', 10, 3, '5:00']]),
            {('0022600001', 10), ('0022600002', 20)}, '2026-27')


def test_bulk_source_rejects_missing_opponent_before_publication():
    with pytest.raises(ValueError, match='game/team'):
        normalize_completed_gamelogs(response([[1, '0022600001', 10, 3, '5:00']]),
            {('0022600001', 10), ('0022600001', 20)}, '2026-27')


@pytest.mark.parametrize('details,eligible', [
    ({'fetch_tasks': ['players', 'schedule'], 'calc_tasks': ['snapshots']}, True),
    ({'fetch_tasks': ['players'], 'calc_tasks': ['snapshots']}, False),
    ({'fetch_tasks': ['players', 'schedule'], 'calc_tasks': []}, False),
    ({'fetch_tasks': ['players', 'schedule']}, False),
    (None, False),
])
def test_checkpoint_requires_full_task_scope(details, eligible):
    assert cycle.full_daily_scope(details, ['players', 'schedule', 'injury'], ['snapshots']) is eligible


def test_timeout_terminates_the_exact_windows_child_tree(monkeypatch):
    child = MagicMock(pid=1234)
    child.wait.side_effect = [subprocess.TimeoutExpired(['fixture'], 1), 1]
    monkeypatch.setattr(cycle.subprocess, 'Popen', MagicMock(return_value=child))
    terminate = MagicMock()
    monkeypatch.setattr(cycle.subprocess, 'run', terminate)
    with pytest.raises(subprocess.TimeoutExpired):
        cycle.run_child(['fixture'], env={}, timeout=1)
    if cycle.os.name == 'nt':
        assert terminate.call_args.args[0] == ['taskkill', '/PID', '1234', '/T', '/F']
    else:
        child.kill.assert_called_once()


def test_preflight_failure_publishes_local_status(monkeypatch, tmp_path):
    monkeypatch.setattr(cycle, 'run', MagicMock(side_effect=ConnectionError('fixture')))
    assert cycle.main(['--archive-root', str(tmp_path), '--state-dir', str(tmp_path), '--pg-bin', str(tmp_path)]) == 1
    assert 'preflight' in (tmp_path / 'ingestion-status.json').read_text()


def test_remote_database_is_rejected_before_connect_or_ledger(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import app.database
    engine = MagicMock()
    engine.url = SimpleNamespace(host='remote.example', database='yunoball_local', query={})
    monkeypatch.setattr(app.database, 'engine', engine)
    args = SimpleNamespace(force=True, check_only=False, state_dir=tmp_path)
    with pytest.raises(ValueError, match='local yunoball_local'):
        cycle.run(args)
    engine.connect.assert_not_called()


@pytest.mark.parametrize('query,env', [({'host': 'remote.example'}, {}),
                                      ({'hostaddr': '192.0.2.1'}, {}),
                                      ({'service': 'remote'}, {}),
                                      ({}, {'PGHOSTADDR': '192.0.2.1'}),
                                      ({}, {'PGSERVICE': 'remote'})])
def test_local_cycle_rejects_libpq_routing_overrides_before_connect(monkeypatch, tmp_path, query, env):
    from types import SimpleNamespace
    import app.database
    engine = MagicMock()
    engine.url = SimpleNamespace(host='localhost', database='yunoball_local', query=query)
    monkeypatch.setattr(app.database, 'engine', engine)
    for key in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE'):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match='local yunoball_local'):
        cycle.run(SimpleNamespace(force=True, check_only=False, state_dir=tmp_path))
    engine.connect.assert_not_called()


@pytest.mark.parametrize('passed,force,needs_daily', [(True, False, False), (False, False, True), (True, True, True)])
def test_retry_reuses_validated_daily_phase(tmp_path, passed, force, needs_daily):
    from types import SimpleNamespace
    args = SimpleNamespace(state_dir=tmp_path, pg_bin=tmp_path, archive_root=tmp_path, force=force)
    commands = cycle.build_commands(args, passed)
    assert any(c[0] == 'daily_ingest.py' for c in commands) is needs_daily
    assert commands[0][0] == 'scripts/backup_local_database.py'
    assert commands[-1][0] == 'scripts/run_official_injury_pipeline.py'
