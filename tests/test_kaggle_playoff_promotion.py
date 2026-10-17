"""Pure contract tests for playoff-only canonical schedule promotion."""

from datetime import date

from app.services.kaggle_playoff_promotion_service import (
    CanonicalScheduleRow,
    StagedPlayoffRow,
    build_playoff_promotion_plan,
)


def _staged(game_id, team_id, opponent_id, is_home, result, points):
    return StagedPlayoffRow(
        game_id=game_id,
        season="2015-16",
        game_date=date(2016, 4, 16),
        team_id=team_id,
        opponent_team_id=opponent_id,
        is_home=is_home,
        result=result,
        points=points,
        source_row_number=team_id % 1000 + 2,
        source_row_sha256="a" * 64,
        parser_version="kaggle-games-v1",
    )


def _canonical(row):
    return CanonicalScheduleRow(
        game_id=row.game_id,
        season=row.season,
        game_date=row.game_date,
        team_id=row.team_id,
        opponent_team_id=row.opponent_team_id,
        home_or_away="H" if row.is_home else "A",
        result=row.result,
    )


def test_plan_separates_exact_matches_from_missing_candidates():
    first = (
        _staged("0041500101", 1, 2, True, "W", 105),
        _staged("0041500101", 2, 1, False, "L", 99),
    )
    second = (
        _staged("0041500102", 3, 4, False, "L", 88),
        _staged("0041500102", 4, 3, True, "W", 101),
    )

    plan = build_playoff_promotion_plan(
        (*first, *second),
        tuple(_canonical(row) for row in first),
        {1, 2, 3, 4},
    )

    assert plan.source_games == 2
    assert plan.already_matched_games == 1
    assert plan.candidate_games == 1
    assert plan.candidate_row_count == 2
    assert plan.conflicts == ()


def test_plan_blocks_unknown_teams_and_score_result_conflicts():
    unknown_team = (
        _staged("0041500101", 1, 9, True, "W", 105),
        _staged("0041500101", 9, 1, False, "L", 99),
    )
    bad_score = (
        _staged("0041500102", 3, 4, True, "W", 88),
        _staged("0041500102", 4, 3, False, "L", 101),
    )

    plan = build_playoff_promotion_plan(
        (*unknown_team, *bad_score),
        (),
        {1, 3, 4},
    )

    assert plan.candidate_games == 0
    assert set(plan.conflicts) == {
        "0041500101:unknown_team",
        "0041500102:score_result_conflict",
    }


def test_plan_blocks_canonical_identity_conflicts():
    source = (
        _staged("0041500101", 1, 2, True, "W", 105),
        _staged("0041500101", 2, 1, False, "L", 99),
    )
    canonical = list(_canonical(row) for row in source)
    canonical[0] = CanonicalScheduleRow(
        **{**canonical[0].__dict__, "game_date": date(2016, 4, 17)}
    )

    plan = build_playoff_promotion_plan(source, canonical, {1, 2})

    assert plan.already_matched_games == 0
    assert plan.candidate_games == 0
    assert plan.conflicts == ("0041500101:canonical_identity_conflict",)
