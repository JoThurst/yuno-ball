"""Pure contract tests for staged market identity reconciliation."""

from datetime import date

from app.services.kaggle_market_reconciliation_service import (
    CanonicalMarketGameEvidence,
    MarketIdentityEvidence,
    classify_market_identity,
)


def _market(**overrides):
    values = {
        "game_id": "0041600401",
        "team_id": 1,
        "opponent_team_id": 2,
        "season": "2016-17",
        "season_type": "Playoffs",
        "game_date": date(2017, 6, 1),
        "is_home": False,
    }
    values.update(overrides)
    return MarketIdentityEvidence(**values)


def _canonical(**overrides):
    values = {
        "row_count": 2,
        "team_ids": (1, 2),
        "opponent_team_ids": (2, 1),
        "seasons": ("2016-17", "2016-17"),
        "season_types": ("Playoffs", "Playoffs"),
        "game_dates": (date(2017, 6, 1), date(2017, 6, 1)),
    }
    values.update(overrides)
    return CanonicalMarketGameEvidence(**values)


def test_exact_game_team_and_opponent_identity_matches():
    result = classify_market_identity(_market(), _canonical())

    assert result.status == "matched"
    assert result.conflict_reasons == ()


def test_missing_and_incomplete_canonical_games_are_distinct():
    assert classify_market_identity(_market(), None).status == "canonical_missing"
    incomplete = classify_market_identity(_market(), _canonical(row_count=1))
    assert incomplete.status == "canonical_incomplete"
    assert incomplete.conflict_reasons == ("canonical_row_count",)


def test_team_season_and_type_conflicts_are_explicit():
    result = classify_market_identity(
        _market(),
        _canonical(
            team_ids=(1, 3),
            opponent_team_ids=(3, 1),
            seasons=("2017-18", "2017-18"),
            season_types=("Regular Season", "Regular Season"),
            game_dates=(date(2017, 6, 2), date(2017, 6, 2)),
        ),
    )

    assert result.status == "conflict"
    assert set(result.conflict_reasons) == {
        "opponent_team_id",
        "team_opponent_pair",
        "season",
        "season_type",
        "game_date",
    }


def test_market_team_must_retain_the_source_away_selection_mapping():
    result = classify_market_identity(_market(is_home=True), _canonical())

    assert result.status == "conflict"
    assert result.conflict_reasons == ("market_team_not_away",)
