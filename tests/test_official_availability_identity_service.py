from datetime import date

from app.services.official_availability_identity_service import (
    CanonicalGame,
    _player_index,
    _resolve_row,
)
from app.services.statsurge_identity_reconciliation_service import normalize_player_name


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
