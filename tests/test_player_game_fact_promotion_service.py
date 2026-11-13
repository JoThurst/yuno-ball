"""Shared pre-collection correction-token contracts."""

from types import SimpleNamespace

from app.models.player_game_fact_sqlalchemy import PlayerGameAdvancedFactORM
from app.services.player_game_fact_promotion_service import (
    attach_player_game_predecessors,
    load_player_game_predecessors,
)


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def all(self):
        return self.rows


class _DB:
    def query(self, model):
        assert model is PlayerGameAdvancedFactORM
        return _Query([
            SimpleNamespace(
                canonical_game_id="g1",
                canonical_player_id=1,
                canonical_team_id=2,
                revision_id="revision-a",
            )
        ])


def test_predecessor_snapshot_is_attached_to_changed_and_new_grains():
    predecessors = load_player_game_predecessors(
        _DB(), ["g1"], family="advanced"
    )
    facts = [
        {"canonical_game_id": "g1", "canonical_player_id": 1, "canonical_team_id": 2},
        {"canonical_game_id": "g1", "canonical_player_id": 3, "canonical_team_id": 2},
    ]

    attach_player_game_predecessors(
        facts, predecessors, publication_key="attempt-1"
    )

    assert facts[0]["expected_previous_revision_id"] == "revision-a"
    assert facts[1]["expected_previous_revision_id"] is None
    assert {fact["publication_key"] for fact in facts} == {"attempt-1"}
