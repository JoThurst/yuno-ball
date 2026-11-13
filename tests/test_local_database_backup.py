from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest

from scripts import backup_local_database as backup


def test_backup_credentials_are_not_arguments_and_replay_checks_hash(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:secret@127.0.0.1/yunoball_local')
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert not any('secret' in value for value in command)
        if '--file' in command:
            assert kwargs['env']['PGPASSWORD'] == 'secret'
            Path(command[-1]).write_bytes(b'fixture archive')
        return SimpleNamespace(returncode=0, stdout='archive contents')
    monkeypatch.setattr(backup.subprocess, 'run', execute)
    report = backup.backup_database(tmp_path / 'backups', tmp_path / 'bin')
    assert report['archive_listing_verified'] is True
    assert report['restore_tested'] is False
    assert backup.backup_database(tmp_path / 'backups', tmp_path / 'bin')['sha256'] == report['sha256']
    assert len(calls) == 2


def test_backup_failure_never_publishes_success_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:secret@127.0.0.1/yunoball_local')
    monkeypatch.setattr(backup.subprocess, 'run', MagicMock(return_value=SimpleNamespace(returncode=1)))
    with pytest.raises(RuntimeError):
        backup.backup_database(tmp_path / 'backups', tmp_path)
    assert not list((tmp_path / 'backups').glob('*.json'))


def test_backup_rejects_remote_database(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:secret@remote.example/yunoball_local')
    with pytest.raises(ValueError, match='local yunoball_local'):
        backup.backup_database(tmp_path, tmp_path)


@pytest.mark.parametrize('query,env', [('?host=remote.example', {}),
                                      ('?hostaddr=192.0.2.1', {}),
                                      ('?service=remote', {}),
                                      ('', {'PGHOSTADDR': '192.0.2.1'}),
                                      ('', {'PGSERVICE': 'remote'})])
def test_backup_rejects_routing_overrides_before_pg_dump(monkeypatch, tmp_path, query, env):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:secret@localhost/yunoball_local' + query)
    for key in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE'):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    execute = MagicMock()
    monkeypatch.setattr(backup.subprocess, 'run', execute)
    with pytest.raises(ValueError, match='local yunoball_local'):
        backup.backup_database(tmp_path, tmp_path)
    execute.assert_not_called()


def test_backup_uses_eastern_date_across_utc_midnight(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:secret@127.0.0.1/yunoball_local')
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 27, 1, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(backup, 'datetime', FixedDatetime)
    def execute(command, **kwargs):
        if '--file' in command:
            Path(command[-1]).write_bytes(b'fixture archive')
        return SimpleNamespace(returncode=0, stdout='archive contents')
    monkeypatch.setattr(backup.subprocess, 'run', execute)
    report = backup.backup_database(tmp_path / 'backups', tmp_path / 'bin')
    assert Path(report['file']).name == 'yunoball_local_20261026.dump'


def test_legacy_utc_date_collision_is_not_reused(monkeypatch, tmp_path):
    import hashlib
    import json
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture:secret@127.0.0.1/yunoball_local')
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 27, 12, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(backup, 'datetime', FixedDatetime)
    directory = tmp_path / 'backups'
    directory.mkdir()
    dump = directory / 'yunoball_local_20261027.dump'
    dump.write_bytes(b'previous eastern day')
    dump.with_suffix('.json').write_text(json.dumps({
        'format': 'yunoball-local-backup-v1',
        'created_at': '2026-10-27T01:00:00+00:00',
        'sha256': hashlib.sha256(dump.read_bytes()).hexdigest(),
    }))
    execute = MagicMock()
    monkeypatch.setattr(backup.subprocess, 'run', execute)
    with pytest.raises(ValueError, match='Eastern-date'):
        backup.backup_database(directory, tmp_path / 'bin')
    assert dump.read_bytes() == b'previous eastern day'
    execute.assert_not_called()


def test_retention_preserves_foreign_files_and_only_removes_owned_siblings(tmp_path):
    import hashlib
    import json
    root = tmp_path / 'backups'
    root.mkdir()
    unrelated = root / 'manual.dump'
    unrelated.write_bytes(b'keep')
    for day in range(1, 16):
        dump = root / f'yunoball_local_202610{day:02}.dump'
        dump.write_bytes(b'owned')
        dump.with_suffix('.json').write_text(json.dumps({
            'format': 'yunoball-local-backup-v1', 'file': str(dump),
            'sha256': hashlib.sha256(b'owned').hexdigest()}))
    foreign = root / 'yunoball_local_19990101.json'
    foreign.write_text(json.dumps({'format': 'other', 'file': str(unrelated)}))
    backup.prune_owned_backups(root)
    assert unrelated.read_bytes() == b'keep'
    assert foreign.exists()
    assert not (root / 'yunoball_local_20261001.dump').exists()
    assert (root / 'yunoball_local_20261015.dump').exists()
