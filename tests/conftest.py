"""Shared pytest policy for explicitly selected CI test partitions."""

import os


def pytest_sessionfinish(session, exitstatus):
    """Do not report a manually requested integration gate as passing if it skips."""
    if os.environ.get("YUNOBALL_FAIL_ON_SKIPS") != "1":
        return

    terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = terminal_reporter.stats.get("skipped", []) if terminal_reporter else []
    if skipped and exitstatus == 0:
        session.exitstatus = 1
