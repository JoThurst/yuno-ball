from datetime import date, datetime

import pytest

from app.services.official_availability_identity_service import (
    CanonicalGame,
    _game_index,
    _player_index,
    _resolve_row,
)
from app.services.statsurge_identity_reconciliation_service import normalize_player_name


def _schedule_pair(game_id="0022600220", *, scheduled_at=datetime(2026, 11, 10), precision="exact"):
    return [
        {"game_id": game_id, "game_date": scheduled_at, "game_date_precision": precision,
         "season": "2026-27", "home_or_away": side, "team_id": team_id,
         "opponent_team_id": opponent_id, "away_abbreviation": "BOS", "home_abbreviation": "NYK"}
        for side, team_id, opponent_id in (("A", 1, 2), ("H", 2, 1))
    ]


@pytest.mark.parametrize("scheduled_at,precision,lookup_dates", [
    (datetime(2026, 11, 10), "exact", (date(2026, 11, 9), date(2026, 11, 10))),
    (datetime(2026, 11, 1), "exact", (date(2026, 10, 31), date(2026, 11, 1))),
    (datetime(2026, 11, 10, 1), "exact", (date(2026, 11, 9),)),
    (datetime(2026, 11, 10), "date_only", (date(2026, 11, 10),)),
])
def test_game_index_has_one_candidate_per_game_and_lookup_date(scheduled_at, precision, lookup_dates):
    games = _game_index(_schedule_pair(scheduled_at=scheduled_at, precision=precision))
    assert set(games) == {(day, "BOS", "NYK") for day in lookup_dates}
    for candidates in games.values():
        assert [game.game_id for game in candidates] == ["0022600220"]


@pytest.mark.parametrize("second_game,expected_status", [(False, "resolved"), (True, "partial")])
def test_midnight_schedule_resolves_only_when_game_identity_is_unique(second_game, expected_status):
    rows = _schedule_pair()
    if second_game:
        rows += _schedule_pair("0022600221")
    update = _resolve_row(
        {"table_name": "availability_observations", "observation_id": "obs-midnight",
         "game_id": None, "team_id": None, "player_id": None,
         "game_date": date(2026, 11, 10), "matchup_text": "BOS@NYK",
         "reported_team_name": "Boston Celtics", "reported_player_name": "Example Player"},
        teams={"bostonceltics": (1,)}, players={}, games=_game_index(rows), resolve_player=False,
    )
    assert update.details["identity_status"] == expected_status
    assert update.details["game_candidate_count"] == (2 if second_game else 1)
    assert update.game_id == (None if second_game else "0022600220")


def test_precise_back_to_back_tipoffs_match_only_their_eastern_game_dates():
    games = _game_index(
        _schedule_pair("0022600216", scheduled_at=datetime(2026, 11, 11, 4))
        + _schedule_pair("0022600226", scheduled_at=datetime(2026, 11, 12, 3))
    )
    assert [g.game_id for g in games[(date(2026, 11, 10), "BOS", "NYK")]] == ["0022600216"]
    assert [g.game_id for g in games[(date(2026, 11, 11), "BOS", "NYK")]] == ["0022600226"]
    assert (date(2026, 11, 12), "BOS", "NYK") not in games


def _game():
    return CanonicalGame(
        game_id="0042600101",
        game_date=date(2026, 4, 18),
        season="2025-26",
        away_team_id=1,
        away_abbreviation="BOS",
        home_team_id=2,
        home_abbreviation="NYK",
    )


def test_identity_resolves_exact_report_date_matchup_and_team():
    update = _resolve_row(
        {
            "table_name": "availability_observations",
            "observation_id": "obs-1",
            "game_id": None,
            "team_id": None,
            "player_id": None,
            "game_date": date(2026, 4, 18),
            "matchup_text": "BOS@NYK",
            "reported_team_name": "Boston Celtics",
            "reported_player_name": "Example Player",
        },
        teams={"bostonceltics": (1,)},
        players={},
        games={(date(2026, 4, 18), "BOS", "NYK"): (_game(),)},
        resolve_player=False,
    )
    assert update.team_id == 1
    assert update.game_id == "0042600101"
    assert update.details["identity_status"] == "resolved"


def test_identity_preserves_null_on_team_game_conflict():
    update = _resolve_row(
        {
            "table_name": "team_report_submission_status",
            "submission_id": "sub-1",
            "game_id": None,
            "team_id": None,
            "player_id": None,
            "game_date": date(2026, 4, 18),
            "matchup_text": "BOS@NYK",
            "reported_team_name": "Chicago Bulls",
            "reported_player_name": None,
        },
        teams={"chicagobulls": (3,)},
        players={},
        games={(date(2026, 4, 18), "BOS", "NYK"): (_game(),)},
        resolve_player=False,
    )
    assert update.team_id == 3
    assert update.game_id is None
    assert update.details["identity_status"] == "conflict"


def test_player_normalization_handles_unicode_and_transliteration_variants():
    assert normalize_player_name("Poeltl, Jakob", source_order=True) == normalize_player_name(
        "Jakob Pöltl"
    )
    assert normalize_player_name("Djurisic, Nikola", source_order=True) == normalize_player_name(
        "Nikola Đurišić"
    )


def test_suffix_order_alias_resolves_only_to_unique_canonical_player():
    players = _player_index([{"player_id": 1643640, "name": "Ernest Udeh, Jr."}])
    assert players[normalize_player_name("Udeh, Jr., Ernest", source_order=True)] == (1643640,)


def test_morez_johnson_report_suffix_resolves_only_to_unique_player():
    players = _player_index([{"player_id": 1643516, "name": "Morez Johnson"}])
    key = normalize_player_name("Johnson Jr., Morez", source_order=True)
    assert players[key] == (1643516,)
    ambiguous = _player_index([
        {"player_id": 1643516, "name": "Morez Johnson"},
        {"player_id": 9999999, "name": "Morez Johnson"},
    ])
    assert len(ambiguous[key]) == 2


def test_christopher_cenac_report_name_resolves_to_unique_chris_cenac():
    key = normalize_player_name("Cenac Jr., Christopher", source_order=True)
    players = _player_index([{"player_id": 1643416, "name": "Chris Cenac Jr."}])
    assert players[key] == (1643416,)
    ambiguous = _player_index([
        {"player_id": 1643416, "name": "Chris Cenac Jr."},
        {"player_id": 9999999, "name": "Chris Cenac Jr."},
    ])
    assert len(ambiguous[key]) == 2
