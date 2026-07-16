from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.dialects import postgresql

from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.player_z_scores_sqlalchemy import PlayerZScoresORM
from app.models.team_sqlalchemy import RosterORM, TeamORM
from app.services.roster_reconciliation_service import (
    EmptyRosterPayload,
    normalize_roster_payload,
    reconcile_team_roster,
)
from app.utils.id_utils import InvalidNBAIdentifier, normalize_nba_game_id
from app.z_score_creator import DeprecatedZScorePipeline, populate_z_scores


def test_game_id_normalization_restores_provider_leading_zeroes():
    assert normalize_nba_game_id("22500001") == "0022500001"
    assert normalize_nba_game_id(22500001) == "0022500001"
    with pytest.raises(InvalidNBAIdentifier):
        normalize_nba_game_id("not-an-id")


def test_roster_payload_uses_requested_canonical_season_and_preserves_missing_jersey():
    rows = [
        {
            "PLAYER_ID": 1,
            "PLAYER": "One Player",
            "NUM": "",
            "POSITION": "G",
            "HOW_ACQUIRED": None,
            "SEASON": "2025",
        }
    ]

    result = normalize_roster_payload(rows, season="2025-26")

    assert result[0]["season"] == "2025-26"
    assert result[0]["player_number"] is None
    with pytest.raises(EmptyRosterPayload):
        normalize_roster_payload([], season="2025-26")


def test_clearing_all_roster_history_is_prohibited():
    with pytest.raises(ValueError, match="clearing all roster history"):
        TeamORM(team_id=10, name="Test").clear_roster()


class _RosterQuery:
    def __init__(self, rows, deleted=0):
        self.rows = rows
        self.deleted = deleted
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(str(item) for item in criteria)
        return self

    def __iter__(self):
        return iter(self.rows)

    def delete(self, **kwargs):
        return self.deleted


class _RosterSession:
    def __init__(self):
        self.queries = [
            _RosterQuery([SimpleNamespace(player_id=1), SimpleNamespace(player_id=2)]),
            _RosterQuery([], deleted=1),
        ]
        self.flushed = False

    def query(self, model):
        assert model is RosterORM
        return self.queries.pop(0)

    def flush(self):
        self.flushed = True


def test_roster_reconciliation_only_operates_on_requested_team_season():
    session = _RosterSession()
    entries = [
        {"player_id": 2, "player_name": "Existing"},
        {"player_id": 3, "player_name": "New"},
    ]

    with patch.object(RosterORM, "create") as create:
        result = reconcile_team_roster(
            session,
            team_id=10,
            season="2025-26",
            entries=entries,
        )

    assert result.inserted == 1
    assert result.updated == 1
    assert result.removed == 1
    assert result.season == "2025-26"
    assert all(call.kwargs["season"] == "2025-26" for call in create.call_args_list)
    assert session.flushed is True


class _StatementSession:
    def __init__(self):
        self.statement = None
        self.flushed = False

    def execute(self, statement):
        self.statement = statement

    def flush(self):
        self.flushed = True


def test_gamelog_bulk_upsert_updates_mutable_fields_without_zero_fill():
    session = _StatementSession()
    count = GameLogORM.bulk_upsert(
        [
            {
                "player_id": 1,
                "game_id": "22500001",
                "team_id": 10,
                "season": "2025-26",
                "points": 12,
            },
            {
                "player_id": 1,
                "game_id": "0022500001",
                "team_id": 10,
                "season": "2025-26",
                "points": None,
            },
        ],
        db=session,
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert count == 1
    assert "ON CONFLICT (player_id, game_id) DO UPDATE" in str(compiled)
    assert "0022500001" in compiled.params.values()
    assert any(key.startswith("points") and value is None for key, value in compiled.params.items())
    assert session.flushed is True


def test_legacy_z_score_writes_fail_closed_but_reads_remain_available():
    with pytest.raises(DeprecatedZScorePipeline):
        populate_z_scores("2025-26")
    with pytest.raises(RuntimeError, match="read-only legacy"):
        PlayerZScoresORM.create(object(), 1, pts_z_score=1.0)
