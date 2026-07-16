"""Pure contract tests for staged-to-canonical game reconciliation."""

from __future__ import annotations

from datetime import date

from app.services.kaggle_game_reconciliation_service import (
    CanonicalGameEvidence,
    PlayerGameDateEvidence,
    SourceGameEvidence,
    classify_date_repair,
    classify_game,
)


def _source(**overrides):
    values = {
        "game_id": "0041600401",
        "season": "2016-17",
        "season_type": "Playoffs",
        "game_date": date(2017, 6, 1),
        "team_ids": (1, 2),
        "opponent_team_ids": (2, 1),
        "home_flags": (True, False),
        "results": ("W", "L"),
        "points": (113, 91),
    }
    values.update(overrides)
    return SourceGameEvidence(**values)


def _canonical(**overrides):
    values = {
        "row_count": 2,
        "team_ids": (1, 2),
        "opponent_team_ids": (2, 1),
        "seasons": ("2016-17", "2016-17"),
        "game_dates": (date(2017, 6, 1), date(2017, 6, 1)),
        "home_or_away": ("H", "A"),
        "results": ("W", "L"),
    }
    values.update(overrides)
    return CanonicalGameEvidence(**values)


def test_exact_game_id_and_reciprocal_contract_matches():
    result = classify_game(_source(), _canonical())

    assert result.status == "matched"
    assert result.conflict_reasons == ()


def test_missing_and_incomplete_canonical_games_remain_distinct():
    assert classify_game(_source(), None).status == "canonical_missing"
    incomplete = classify_game(_source(), _canonical(row_count=1))
    assert incomplete.status == "canonical_incomplete"
    assert incomplete.conflict_reasons == ("canonical_row_count",)


def test_conflicts_are_explicit_and_never_fuzzy_matched():
    result = classify_game(
        _source(),
        _canonical(
            team_ids=(1, 3),
            seasons=("2017-18", "2017-18"),
            game_dates=(date(2017, 6, 2), date(2017, 6, 2)),
        ),
    )

    assert result.status == "conflict"
    assert set(result.conflict_reasons) == {"team_ids", "season", "game_date"}


def test_source_score_result_conflict_blocks_missing_game_backfill():
    result = classify_game(_source(points=(90, 100)), None)

    assert result.status == "conflict"
    assert result.conflict_reasons == ("source_score_result_conflict",)


def test_date_repair_requires_unanimous_date_season_type_and_teams():
    source = _source(game_date=None)
    evidence = PlayerGameDateEvidence(
        row_count=20,
        dates=(date(2017, 6, 1),),
        seasons=("2016-17",),
        season_types=("Playoffs",),
        team_ids=(1, 2),
    )

    result = classify_date_repair(source, evidence)

    assert result.status == "unique_repair"
    assert result.proposed_date == date(2017, 6, 1)


def test_date_repair_reports_ambiguous_or_missing_evidence():
    source = _source(game_date=None)
    ambiguous = PlayerGameDateEvidence(
        row_count=20,
        dates=(date(2017, 6, 1), date(2017, 6, 2)),
        seasons=("2016-17",),
        season_types=("Regular Season",),
        team_ids=(1,),
    )

    conflict = classify_date_repair(source, ambiguous)
    unavailable = classify_date_repair(source, None)

    assert conflict.status == "conflict"
    assert set(conflict.conflict_reasons) == {
        "ambiguous_player_game_dates",
        "player_game_season_type",
        "player_game_team_ids",
    }
    assert unavailable.status == "unavailable"
