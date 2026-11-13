"""Shared pytest policy for explicitly selected CI test partitions."""

import os
import socket

import pytest


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
