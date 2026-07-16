"""Pure contract tests for deterministic Stat Surge identity resolution."""

from datetime import date

from app.services.statsurge_identity_reconciliation_service import (
    CanonicalGameIdentity,
    normalize_player_name,
    resolve_statsurge_identity,
)


GAME = CanonicalGameIdentity(
    game_id="0022100001",
    game_date=date(2021, 10, 19),
    season="2021-22",
    away_team_id=1,
    away_abbreviation="BKN",
    home_team_id=2,
    home_abbreviation="MIL",
)


def _resolve(**overrides):
    values = {
        "reported_player_name": "Irving, Kyrie",
        "reported_team_name": "Brooklyn Nets",
        "matchup_text": "BKN@MIL",
        "report_date": date(2021, 10, 19),
        "season": "2021-22",
        "teams_by_name": {"Brooklyn Nets": (1,), "Milwaukee Bucks": (2,)},
        "players_by_name": {"kyrieirving": (10,)},
        "games_by_key": {(date(2021, 10, 19), "BKN", "MIL"): (GAME,)},
    }
    values.update(overrides)
    return resolve_statsurge_identity(**values)


def test_exact_team_game_and_unique_normalized_player_resolve():
    result = _resolve()

    assert result.identity_status == "resolved"
    assert result.resolved_player_id == 10
    assert result.resolved_team_id == 1
    assert result.resolved_game_id == "0022100001"
    assert result.cutoff_status == "unknown"
    assert result.completeness_status == "partial"


def test_player_normalization_changes_source_order_without_fuzzy_aliases():
    assert normalize_player_name("Brown Jr., Troy", source_order=True) == "troybrownjr"
    assert normalize_player_name("Troy Brown Jr.") == "troybrownjr"
    assert normalize_player_name("Jakob Poeltl") != normalize_player_name("Jakob Pöltl")
    assert normalize_player_name("Luka Doncic") == normalize_player_name("Luka Dončić")


def test_unique_next_day_game_is_allowed_but_timing_stays_unknown():
    next_day = CanonicalGameIdentity(
        **{**GAME.__dict__, "game_date": date(2021, 10, 20)}
    )
    result = _resolve(
        games_by_key={(date(2021, 10, 20), "BKN", "MIL"): (next_day,)}
    )

    assert result.identity_status == "resolved"
    assert result.details["game_method"] == "report_date_plus_one"
    assert result.cutoff_status == "unknown"


def test_missing_player_or_game_remains_partial_without_guessing():
    missing_player = _resolve(players_by_name={})
    missing_game = _resolve(games_by_key={})

    assert missing_player.identity_status == "partial"
    assert missing_player.resolved_player_id is None
    assert missing_game.identity_status == "partial"
    assert missing_game.resolved_game_id is None


def test_ambiguous_player_is_quarantined_as_conflict():
    result = _resolve(players_by_name={"kyrieirving": (10, 11)})

    assert result.identity_status == "conflict"
    assert result.completeness_status == "quarantined"
    assert result.details["conflict_reasons"] == ["ambiguous_player"]
