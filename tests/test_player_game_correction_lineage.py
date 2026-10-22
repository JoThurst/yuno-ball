"""Concurrency guards for immutable player-game correction promotion."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameAdvancedFactPromotionORM,
    PlayerGameFactORM,
    PlayerGameFactPromotionORM,
)
from app.services.player_game_advanced_fact_service import (
    AdvancedRegistration,
    publish_advanced_facts,
)
from app.services.player_game_fact_ingestion_service import publish_player_game_facts
from app.services.player_game_fact_service import PlayerGameFactRegistration


class _Query:
    def __init__(self, row, historical_revision_ids=()):
        self.row = row
        self.historical_revision_ids = set(historical_revision_ids)
        self.filters = {}

    def filter_by(self, **kwargs):
        self.filters = kwargs
        return self

    def with_for_update(self):
        return self

    def one_or_none(self):
        return self.row

    def first(self):
        if self.filters.get("selected_revision_id") in self.historical_revision_ids:
            return SimpleNamespace()
        return None


class _Session:
    def __init__(
        self,
        fact_model,
        existing,
        revision,
        *,
        previous_revision=None,
        promotion_model=None,
        historical_revision_ids=(),
    ):
        self.fact_model = fact_model
        self.existing = existing
        self.revision = revision
        self.previous_revision = previous_revision
        self.promotion_model = promotion_model
        self.historical_revision_ids = historical_revision_ids
        self.added = []

    def query(self, model):
        if model is self.fact_model:
            return _Query(self.existing)
        assert model is self.promotion_model
        return _Query(None, self.historical_revision_ids)

    def get(self, _model, revision_id):
        if revision_id == self.revision.revision_id:
            return self.revision
        if (
            self.previous_revision is not None
            and revision_id == self.previous_revision.revision_id
        ):
            return self.previous_revision
        raise AssertionError(f"Unexpected revision lookup: {revision_id}")

    def execute(self, *_args, **_kwargs):
        return None

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None


def _fact(**overrides):
    value = {
        "canonical_game_id": "g1",
        "canonical_player_id": 1,
        "canonical_team_id": 2,
        "source_run_id": "run-2",
        "expected_previous_revision_id": "old-revision",
    }
    value.update(overrides)
    return value


def _revision(revision_id):
    return SimpleNamespace(
        revision_id=revision_id,
        canonical_game_id="g1",
        canonical_player_id=1,
        canonical_team_id=2,
        game_date=None,
        season="2026-27",
        season_type="Regular Season",
        completeness_status="complete",
        participation_status="played",
        starter_status="unknown",
        source_name="fixture",
        source_row_key="g1:1:2",
        parser_version="v1",
        source_row_sha256="a" * 64,
        source_run_id="run-1",
        data_available_at=None,
    )


def test_same_content_concurrent_traditional_attempt_becomes_noop():
    existing = SimpleNamespace(revision_id="new-revision")
    revision = SimpleNamespace(revision_id="new-revision")
    db = _Session(PlayerGameFactORM, existing, revision)

    with patch(
        "app.services.player_game_fact_ingestion_service.validate_schedule_identity"
    ), patch(
        "app.services.player_game_fact_ingestion_service.register_player_game_fact_revision",
        return_value=PlayerGameFactRegistration("new-revision", False),
    ):
        result = publish_player_game_facts([_fact()], db=db)

    assert result == {
        "revisions_created": 0,
        "facts_created": 0,
        "facts_updated": 0,
        "facts_unchanged": 1,
    }
    assert db.added == []


def test_competing_traditional_correction_fails_stale_predecessor():
    existing = SimpleNamespace(revision_id="other-correction")
    revision = _revision("our-correction")
    db = _Session(
        PlayerGameFactORM,
        existing,
        revision,
        previous_revision=_revision("other-correction"),
    )

    with patch(
        "app.services.player_game_fact_ingestion_service.validate_schedule_identity"
    ), patch(
        "app.services.player_game_fact_ingestion_service.register_player_game_fact_revision",
        return_value=PlayerGameFactRegistration("our-correction", True),
    ):
        with pytest.raises(ValueError, match="Stale Traditional correction predecessor"):
            publish_player_game_facts([_fact()], db=db)

    assert db.added == []


def test_traditional_correction_refuses_changed_source_identity():
    existing = SimpleNamespace(revision_id="old-revision")
    revision = _revision("new-revision")
    revision.source_row_key = "different-source-row"
    db = _Session(
        PlayerGameFactORM,
        existing,
        revision,
        previous_revision=_revision("old-revision"),
    )

    with patch(
        "app.services.player_game_fact_ingestion_service.validate_schedule_identity"
    ), patch(
        "app.services.player_game_fact_ingestion_service.register_player_game_fact_revision",
        return_value=PlayerGameFactRegistration("new-revision", True),
    ):
        with pytest.raises(ValueError, match="changed source or canonical identity"):
            publish_player_game_facts([_fact()], db=db)

    assert db.added == []


def test_same_content_concurrent_advanced_attempt_becomes_noop():
    existing = SimpleNamespace(revision_id="new-revision")
    revision = SimpleNamespace(revision_id="new-revision")
    db = _Session(PlayerGameAdvancedFactORM, existing, revision)

    with patch(
        "app.services.player_game_advanced_fact_service.validate_schedule_identity"
    ), patch(
        "app.services.player_game_advanced_fact_service.validate_traditional_identity_set"
    ), patch(
        "app.services.player_game_advanced_fact_service.register_advanced_revision",
        return_value=AdvancedRegistration("new-revision", False),
    ):
        result = publish_advanced_facts([_fact()], db=db)

    assert result == {
        "revisions_created": 0,
        "facts_created": 0,
        "facts_updated": 0,
        "facts_unchanged": 1,
    }
    assert db.added == []


def test_competing_advanced_correction_fails_stale_predecessor():
    existing = SimpleNamespace(revision_id="other-correction")
    revision = _revision("our-correction")
    db = _Session(
        PlayerGameAdvancedFactORM,
        existing,
        revision,
        previous_revision=_revision("other-correction"),
    )

    with patch(
        "app.services.player_game_advanced_fact_service.validate_schedule_identity"
    ), patch(
        "app.services.player_game_advanced_fact_service.validate_traditional_identity_set"
    ), patch(
        "app.services.player_game_advanced_fact_service.register_advanced_revision",
        return_value=AdvancedRegistration("our-correction", True),
    ):
        with pytest.raises(ValueError, match="Stale Advanced correction predecessor"):
            publish_advanced_facts([_fact()], db=db)

    assert db.added == []


def test_traditional_correction_appends_promotion_and_updates_projection():
    existing = SimpleNamespace(revision_id="old-revision")
    revision = _revision("new-revision")
    db = _Session(
        PlayerGameFactORM,
        existing,
        revision,
        previous_revision=_revision("old-revision"),
        promotion_model=PlayerGameFactPromotionORM,
    )

    with patch(
        "app.services.player_game_fact_ingestion_service.validate_schedule_identity"
    ), patch(
        "app.services.player_game_fact_ingestion_service.register_player_game_fact_revision",
        return_value=PlayerGameFactRegistration("new-revision", True),
    ), patch(
        "app.services.player_game_fact_ingestion_service.fact_values_from_revision",
        return_value={},
    ):
        result = publish_player_game_facts([_fact()], db=db)

    assert result["facts_updated"] == 1
    assert existing.revision_id == "new-revision"
    assert len(db.added) == 1
    assert db.added[0].previous_revision_id == "old-revision"
    assert db.added[0].selected_revision_id == "new-revision"
    assert db.added[0].reason == "correction"


def test_advanced_reversion_reuses_revision_and_appends_event():
    existing = SimpleNamespace(revision_id="revision-b")
    revision = _revision("revision-a")
    db = _Session(
        PlayerGameAdvancedFactORM,
        existing,
        revision,
        previous_revision=_revision("revision-b"),
        promotion_model=PlayerGameAdvancedFactPromotionORM,
        historical_revision_ids={"revision-a"},
    )

    with patch(
        "app.services.player_game_advanced_fact_service.validate_schedule_identity"
    ), patch(
        "app.services.player_game_advanced_fact_service.validate_traditional_identity_set"
    ), patch(
        "app.services.player_game_advanced_fact_service.register_advanced_revision",
        return_value=AdvancedRegistration("revision-a", False),
    ), patch(
        "app.services.player_game_advanced_fact_service.advanced_fact_values_from_revision",
        return_value={},
    ):
        result = publish_advanced_facts(
            [_fact(expected_previous_revision_id="revision-b")], db=db
        )

    assert result["facts_updated"] == 1
    assert existing.revision_id == "revision-a"
    assert len(db.added) == 1
    assert db.added[0].previous_revision_id == "revision-b"
    assert db.added[0].selected_revision_id == "revision-a"
    assert db.added[0].source_run_id == "run-2"
    assert db.added[0].reason == "reversion"
