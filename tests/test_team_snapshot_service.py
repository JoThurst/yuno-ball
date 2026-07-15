from datetime import date, datetime, timedelta, timezone

from app.models.team_analytics_snapshot_sqlalchemy import (
    TEAM_SNAPSHOT_COMPLETENESS_COMPLETE,
    TEAM_SNAPSHOT_COMPLETENESS_PARTIAL,
)
from app.services.team_snapshot_service import (
    SlateTeam,
    TeamGameFact,
    build_game_environment_records,
    build_team_feature_records,
    build_team_snapshot_context,
)


UTC = timezone.utc


def _fact(
    *,
    game_id: str,
    team_id: int,
    opponent_team_id: int,
    game_time: datetime,
    pts: int | None,
    fg: int = 40,
    fga: int = 85,
    fg3: int = 12,
    fta: int = 22,
    oreb: int = 10,
    dreb: int = 32,
    tov: int = 13,
) -> TeamGameFact:
    return TeamGameFact(
        game_id=game_id,
        team_id=team_id,
        opponent_team_id=opponent_team_id,
        game_time=game_time,
        fg=fg,
        fga=fga,
        fg3=fg3,
        fta=fta,
        oreb=oreb,
        dreb=dreb,
        tov=tov,
        pts=pts,
    )


def _paired_history(start: date, games: int = 10) -> list[TeamGameFact]:
    facts = []
    for index in range(games):
        game_time = datetime.combine(
            start + timedelta(days=index),
            datetime.min.time(),
            tzinfo=UTC,
        ) + timedelta(hours=23)
        game_id = f"002250{index:04d}"
        facts.extend(
            [
                _fact(
                    game_id=game_id,
                    team_id=1,
                    opponent_team_id=2,
                    game_time=game_time,
                    pts=105 + index,
                ),
                _fact(
                    game_id=game_id,
                    team_id=2,
                    opponent_team_id=1,
                    game_time=game_time,
                    pts=101 + index,
                    fg=38,
                    fg3=10,
                ),
            ]
        )
    return facts


def _context(target: date):
    return build_team_snapshot_context(
        season="2025-26",
        target_date=target,
        source_run_id="test-run",
    )


def _slate(target: date) -> list[SlateTeam]:
    tipoff = datetime.combine(target, datetime.min.time(), tzinfo=UTC) + timedelta(hours=23)
    return [
        SlateTeam("0022509999", 1, 2, tipoff, True),
        SlateTeam("0022509999", 2, 1, tipoff, False),
    ]


def test_historical_features_ignore_target_and_future_games():
    target = date(2025, 11, 10)
    context = _context(target)
    facts = _paired_history(date(2025, 10, 21))
    baseline = build_team_feature_records(context, _slate(target), facts)

    target_time = datetime(2025, 11, 10, 20, tzinfo=UTC)
    march_time = datetime(2026, 3, 1, 20, tzinfo=UTC)
    contaminated = facts + [
        _fact(
            game_id="0022509999",
            team_id=1,
            opponent_team_id=2,
            game_time=target_time,
            pts=250,
        ),
        _fact(
            game_id="0022509999",
            team_id=2,
            opponent_team_id=1,
            game_time=target_time,
            pts=80,
        ),
        _fact(
            game_id="0022519998",
            team_id=1,
            opponent_team_id=2,
            game_time=march_time,
            pts=300,
        ),
        _fact(
            game_id="0022519998",
            team_id=2,
            opponent_team_id=1,
            game_time=march_time,
            pts=70,
        ),
    ]
    rebuilt = build_team_feature_records(context, _slate(target), contaminated)

    keys = (
        "season_games_played",
        "window_games_played",
        "off_rtg_season",
        "off_rtg_lastn",
        "source_latest_game_id",
        "source_latest_game_date",
    )
    assert [{key: row[key] for key in keys} for row in rebuilt] == [
        {key: row[key] for key in keys} for row in baseline
    ]
    assert all(row["source_latest_game_date"] < target for row in rebuilt)


def test_complete_paired_history_builds_two_team_rows_and_one_environment():
    target = date(2025, 11, 10)
    context = _context(target)
    records = build_team_feature_records(
        context,
        _slate(target),
        _paired_history(date(2025, 10, 21)),
    )

    assert len(records) == 2
    assert all(row["completeness_status"] == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE for row in records)
    assert all(row["season_games_used"] == 10 for row in records)
    assert all(row["data_available_at"] <= row["feature_as_of"] for row in records)

    environments = build_game_environment_records(context, records)
    assert len(environments) == 1
    assert environments[0]["completeness_status"] == TEAM_SNAPSHOT_COMPLETENESS_COMPLETE
    assert environments[0]["home_team_id"] == 1
    assert environments[0]["away_team_id"] == 2
    assert environments[0]["pace_projection"] is not None


def test_missing_box_score_value_is_excluded_and_reported_not_zero_filled():
    target = date(2025, 11, 10)
    context = _context(target)
    facts = _paired_history(date(2025, 10, 21))
    broken = facts[0]
    facts[0] = _fact(
        game_id=broken.game_id,
        team_id=broken.team_id,
        opponent_team_id=broken.opponent_team_id,
        game_time=broken.game_time,
        pts=None,
    )

    records = build_team_feature_records(context, _slate(target), facts)
    home = next(row for row in records if row["team_id"] == 1)
    assert home["season_games_played"] == 10
    assert home["season_games_used"] == 9
    assert home["completeness_status"] == TEAM_SNAPSHOT_COMPLETENESS_PARTIAL
    assert broken.game_id in home["missing_input_flags"]["excluded_season_games"]
    assert "team.pts" in home["missing_input_flags"]["excluded_season_games"][broken.game_id]


def test_early_season_rows_are_honestly_partial():
    target = date(2025, 10, 25)
    context = _context(target)
    records = build_team_feature_records(
        context,
        _slate(target),
        _paired_history(date(2025, 10, 21), games=3),
    )

    assert all(row["completeness_status"] == TEAM_SNAPSHOT_COMPLETENESS_PARTIAL for row in records)
    assert all(row["missing_input_flags"]["insufficient_window_games"]["available"] == 3 for row in records)
