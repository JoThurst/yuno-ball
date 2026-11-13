from unittest.mock import MagicMock

import pytest
from sqlalchemy.engine import make_url

from tests.integration_support import validate_ephemeral_target
from tests.test_base import BaseTestCase


@pytest.mark.parametrize('url,environ', [
    ('postgresql://localhost/yunoball_local', {'YUNOBALL_EPHEMERAL_TEST_DB': '1'}),
    ('postgresql://remote.example/yunoball_test', {'YUNOBALL_EPHEMERAL_TEST_DB': '1'}),
    ('postgresql://localhost/yunoball_test', {}),
    ('sqlite://', {'YUNOBALL_EPHEMERAL_TEST_DB': '1'}),
    ('postgresql://localhost/yunoball_test?host=remote.example', {'YUNOBALL_EPHEMERAL_TEST_DB': '1'}),
    ('postgresql://localhost/yunoball_test', {'YUNOBALL_EPHEMERAL_TEST_DB': '1', 'PGHOSTADDR': '192.0.2.1'}),
])
def test_fixture_bootstrap_rejects_unsafe_targets(url, environ):
    with pytest.raises(ValueError):
        validate_ephemeral_target(make_url(url), environ)


def test_fixture_target_requires_explicit_test_database():
    validate_ephemeral_target(make_url('postgresql://127.0.0.1/yunoball_test'),
                              {'YUNOBALL_EPHEMERAL_TEST_DB': '1'})


@pytest.mark.parametrize('ready', [True, False])
def test_external_test_redis_is_checked_and_never_spawned_or_stopped(monkeypatch, ready):
    import tests.test_base as base
    monkeypatch.delenv('YUNOBALL_OFFLINE_TESTS', raising=False)
    monkeypatch.setenv('YUNOBALL_TEST_REDIS_EXTERNAL', '1')
    monkeypatch.setenv('TEST_REDIS_URL', 'redis://127.0.0.1:6399/1')
    client = MagicMock()
    client.ping.return_value = ready
    monkeypatch.setattr(base.redis.Redis, 'from_url', MagicMock(return_value=client))
    spawn = MagicMock()
    monkeypatch.setattr(base.subprocess, 'Popen', spawn)

    class Fixture(BaseTestCase):
        pass

    if ready:
        Fixture.setUpClass()
    else:
        with pytest.raises(RuntimeError):
            Fixture.setUpClass()
    Fixture.tearDownClass()
    spawn.assert_not_called()
    client.close.assert_called_once()
    assert Fixture.redis_process is None
