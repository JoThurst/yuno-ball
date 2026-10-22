from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.player_game_fact_replay_service import (
    replay_published_player_game_facts,
    source_row_set_sha256,
)


class _Column:
    def __init__(self, name):
        self.name = name


class _Revision:
    __table__ = SimpleNamespace(
        columns=[
            _Column("canonical_game_id"), _Column("canonical_player_id"),
            _Column("canonical_team_id"), _Column("source_row_sha256"),
            _Column("raw_payload"),
        ]
    )

    def __init__(self, game_id, response_hash):
        self.canonical_game_id = game_id
        self.canonical_player_id = 1
        self.canonical_team_id = 2
        self.source_row_sha256 = "d" * 64
        self.raw_payload = {"response_sha256": response_hash}


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self):
        self.traditional = [SimpleNamespace(canonical_game_id="g1", revision_id="t1")]
        self.advanced = [SimpleNamespace(canonical_game_id="g1", revision_id="a1")]

    def query(self, model):
        from app.models.player_game_fact_sqlalchemy import (
            PlayerGameAdvancedFactORM,
        )

        return _Query(self.advanced if model is PlayerGameAdvancedFactORM else self.traditional)

    def get(self, _model, revision_id):
        return _Revision("g1", "a" * 64 if revision_id == "t1" else "b" * 64)


def test_database_replay_checks_hashes_reconciles_and_replays_role_history():
    db = _DB()
    with patch(
        "app.services.player_game_fact_replay_service.publish_player_game_facts",
        return_value={"revisions_created": 0, "facts_created": 0},
    ) as traditional, patch(
        "app.services.player_game_fact_replay_service.publish_advanced_facts",
        return_value={"revisions_created": 0, "facts_created": 0},
    ) as advanced, patch(
        "app.services.player_game_fact_replay_service.build_reconciliation_report",
        return_value={"status": "passed", "blocking_count": 0},
    ) as reconcile, patch(
        "app.services.player_game_fact_replay_service.role_history_records_from_facts",
        return_value=[{"canonical_game_id": "g1"}],
    ), patch(
        "app.services.player_game_fact_replay_service.publish_role_history",
        return_value=0,
    ) as role_history:
        result = replay_published_player_game_facts(
            db,
            game_ids=["g1"],
            season="2026-27",
            season_type="Regular Season",
            expected_response_hashes={
                "traditional": {"g1": "a" * 64},
                "advanced": {"g1": "b" * 64},
            },
        )

    traditional.assert_called_once()
    advanced.assert_called_once()
    reconcile.assert_called_once_with(
        db, season="2026-27", game_ids=["g1"], max_games=25
    )
    role_history.assert_called_once()
    assert result["role_history_rows"] == 0
    assert result["reconciliation"]["blocking_count"] == 0


def test_database_replay_refuses_source_hash_change_before_publication():
    db = _DB()
    with patch(
        "app.services.player_game_fact_replay_service.publish_player_game_facts"
    ) as publish:
        with pytest.raises(ValueError, match="source hash differs"):
            replay_published_player_game_facts(
                db,
                game_ids=["g1"],
                expected_response_hashes={
                    "traditional": {"g1": "c" * 64},
                    "advanced": {"g1": "b" * 64},
                },
            )
    publish.assert_not_called()


def test_database_replay_checks_row_set_when_response_drift_was_reviewed():
    db = _DB()
    expected_rows = source_row_set_sha256([{
        "canonical_game_id": "g1", "canonical_player_id": 1,
        "canonical_team_id": 2, "source_row_sha256": "d" * 64,
    }], "g1")
    with patch(
        "app.services.player_game_fact_replay_service.publish_player_game_facts",
        return_value={"revisions_created": 0},
    ), patch(
        "app.services.player_game_fact_replay_service.publish_advanced_facts",
        return_value={"revisions_created": 0},
    ), patch(
        "app.services.player_game_fact_replay_service.role_history_records_from_facts",
        return_value=[],
    ), patch(
        "app.services.player_game_fact_replay_service.publish_role_history",
        return_value=0,
    ):
        replay_published_player_game_facts(
            db, game_ids=["g1"],
            expected_response_hashes={
                "traditional": {"g1": "a" * 64},
                "advanced": {"g1": "b" * 64},
            },
            expected_source_row_set_hashes={
                "traditional": {"g1": expected_rows},
                "advanced": {"g1": expected_rows},
            },
        )

    with patch(
        "app.services.player_game_fact_replay_service.publish_player_game_facts"
    ) as publish:
        with pytest.raises(ValueError, match="source rows differ"):
            replay_published_player_game_facts(
                db, game_ids=["g1"],
                expected_source_row_set_hashes={
                    "traditional": {"g1": "0" * 64},
                    "advanced": {"g1": expected_rows},
                },
            )
    publish.assert_not_called()
