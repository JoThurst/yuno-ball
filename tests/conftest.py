"""Shared pytest policy for explicitly selected CI test partitions."""

import os
import socket

import pytest


@pytest.fixture(scope='session', autouse=True)
def ephemeral_database():
    if os.environ.get('YUNOBALL_EPHEMERAL_TEST_DB') == '1':
        from tests.integration_support import bootstrap_ephemeral_database
        bootstrap_ephemeral_database()


@pytest.fixture(autouse=True)
def integration_network_boundary(monkeypatch):
    """Allow local DB/Redis, never real NBA calls from disposable CI tests."""
    if os.environ.get('YUNOBALL_EPHEMERAL_TEST_DB') != '1':
        return
    original = socket.getaddrinfo

    def local_only(host, *args, **kwargs):
        if host not in {'localhost', '127.0.0.1', '::1'}:
            raise OSError('External network disabled for disposable integration tests')
        return original(host, *args, **kwargs)

    monkeypatch.setattr(socket, 'getaddrinfo', local_only)


@pytest.fixture(autouse=True)
def offline_network_boundary(monkeypatch):
    """Offline verification must not wait on real NBA, Redis, or DB sockets."""
    if os.environ.get("YUNOBALL_OFFLINE_TESTS") != "1":
        return

    def blocked(*args, **kwargs):
        raise OSError("Network disabled in the offline test partition; mock the dependency")

    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


def pytest_sessionfinish(session, exitstatus):
    """Do not report a manually requested integration gate as passing if it skips."""
    if os.environ.get("YUNOBALL_FAIL_ON_SKIPS") != "1":
        return

    terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = terminal_reporter.stats.get("skipped", []) if terminal_reporter else []
    if skipped and exitstatus == 0:
        session.exitstatus = 1
