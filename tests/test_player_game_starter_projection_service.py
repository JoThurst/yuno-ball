from types import SimpleNamespace

import pytest

from app.services.player_game_starter_projection_service import (
    StarterProjectionConflict,
    project_starter_evidence,
)


class _Query:
    def __init__(self, fact):
        self.fact = fact

    def filter_by(self, **_filters):
        return self

    def one_or_none(self):
        return self.fact


class _DB:
    def __init__(self, fact):
        self.fact = fact

    def query(self, _model):
        return _Query(self.fact)

    def flush(self):
        return None


def _fact(**overrides):
    value = {
        "starter_status": "unknown",
        "starter_position": None,
        "starter_evidence_id": None,
    }
    value.update(overrides)
    return SimpleNamespace(**value)


def _evidence(**overrides):
    value = {
        "evidence_id": "evidence-1",
        "canonical_game_id": "0022400001",
        "canonical_player_id": 7,
        "canonical_team_id": 1,
        "starter_status": "starter",
        "start_position": "G",
    }
    value.update(overrides)
    return value


def test_projection_links_explicit_starter_evidence():
    fact = _fact()

    counts = project_starter_evidence([_evidence()], db=_DB(fact))

    assert counts["facts_updated"] == 1
    assert fact.starter_status == "starter"
    assert fact.starter_position == "G"
    assert fact.starter_evidence_id == "evidence-1"


def test_projection_leaves_unknown_evidence_untouched():
    fact = _fact()

    counts = project_starter_evidence(
        [_evidence(starter_status="unknown", start_position=None)], db=_DB(fact)
    )

    assert counts["starter_rows"] == 0
    assert counts["facts_updated"] == 0
    assert fact.starter_status == "unknown"


def test_projection_rejects_existing_bench_status():
    with pytest.raises(StarterProjectionConflict, match="conflicts"):
        project_starter_evidence([_evidence()], db=_DB(_fact(starter_status="bench")))
