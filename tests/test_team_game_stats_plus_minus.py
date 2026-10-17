from types import SimpleNamespace

from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM


def _row(team_id, opponent_team_id, pts):
    return SimpleNamespace(
        game_id="0022600001",
        team_id=team_id,
        opponent_team_id=opponent_team_id,
        pts=pts,
    )


def test_plus_minus_requires_exact_reciprocal_pair():
    values = TeamGameStatsORM.derive_plus_minus_for_pair(
        [_row(1, 2, 112), _row(2, 1, 105)]
    )

    assert values == {("0022600001", 1): 7, ("0022600001", 2): -7}


def test_plus_minus_is_null_for_incomplete_or_missing_points():
    assert TeamGameStatsORM.derive_plus_minus_for_pair([_row(1, 2, 112)]) == {
        ("0022600001", 1): None
    }
    assert TeamGameStatsORM.derive_plus_minus_for_pair(
        [_row(1, 2, None), _row(2, 1, 105)]
    ) == {
        ("0022600001", 1): None,
        ("0022600001", 2): None,
    }


def test_plus_minus_rejects_non_reciprocal_rows():
    values = TeamGameStatsORM.derive_plus_minus_for_pair(
        [_row(1, 3, 112), _row(2, 1, 105)]
    )

    assert values == {("0022600001", 1): None, ("0022600001", 2): None}
