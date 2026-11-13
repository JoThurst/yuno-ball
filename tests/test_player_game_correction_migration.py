"""Fail-closed rollback contract for correction-lineage schema."""

import importlib.util
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "2026_10_22_1200-j6k7l8m9n0p1_add_player_game_correction_lineage.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("correction_lineage_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _Bind:
    def __init__(self, values):
        self.values = iter(values)

    def execute(self, _statement):
        return _Result(next(self.values))


def test_downgrade_guard_allows_only_baseline_without_distinct_corrections():
    _migration_module()._assert_downgrade_safe(_Bind([0, 0]))


@pytest.mark.parametrize("values", ([1, 0], [0, 1]))
def test_downgrade_guard_blocks_promotion_or_distinct_content(values):
    with pytest.raises(RuntimeError, match="Destructive correction-lineage downgrade blocked"):
        _migration_module()._assert_downgrade_safe(_Bind(values))
