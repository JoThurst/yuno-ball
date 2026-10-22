from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.player_game_advanced_fact_service import (
    register_advanced_revision,
    validate_advanced_fact,
)


def _fact(**overrides):
    fact = {
        "source_name": "nba_boxscore_advanced_v3",
        "source_row_key": "g:10:1",
        "parser_version": "boxscore-advanced-v3-fact-v1",
        "source_game_id": "g",
        "source_player_id": 10,
        "source_team_id": 1,
        "canonical_game_id": "g",
        "canonical_player_id": 10,
        "canonical_team_id": 1,
        "source_row_sha256": "a" * 64,
        "source_run_id": "run",
        "game_date": date(2026, 3, 3),
        "season": "2025-26",
        "season_type": "Regular Season",
        "completeness_status": "complete",
        "participation_status": "played",
        "retrieved_at": datetime(2026, 3, 4, tzinfo=timezone.utc),
        "data_available_at": datetime(2026, 3, 4, tzinfo=timezone.utc),
    }
    fact.update(overrides)
    return fact


def test_validate_advanced_fact_preserves_nulls():
    normalized = validate_advanced_fact(_fact(usage_percentage=None))
    assert normalized["usage_percentage"] is None


def test_validate_advanced_fact_requires_aware_time_and_hash():
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_advanced_fact(_fact(retrieved_at=datetime(2026, 3, 4)))
    with pytest.raises(ValueError, match="SHA-256"):
        validate_advanced_fact(_fact(source_row_sha256="x" * 64))


def test_advanced_fact_captures_explicit_response_provenance():
    normalized = validate_advanced_fact(
        _fact(raw_payload={"response_sha256": "c" * 64})
    )
    assert normalized["source_response_sha256"] == "c" * 64
    assert normalized["data_available_at_basis"] == "retrieved_proxy"
    with pytest.raises(ValueError, match="data_available_at_basis"):
        validate_advanced_fact(_fact(data_available_at_basis="estimated"))


def test_legacy_advanced_revision_exact_replay_does_not_rewrite_time_basis():
    normalized = validate_advanced_fact(_fact())
    existing = SimpleNamespace(
        revision_id="revision-1",
        **{**normalized, "data_available_at_basis": "legacy_unspecified"},
    )

    class Query:
        def filter_by(self, **_kwargs):
            return self

        def one_or_none(self):
            return existing

    db = SimpleNamespace(query=lambda _model: Query())

    registration = register_advanced_revision(_fact(), db=db)

    assert registration.revision_id == "revision-1"
    assert registration.created is False
    assert existing.data_available_at_basis == "legacy_unspecified"
