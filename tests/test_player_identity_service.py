from datetime import date

import pytest

from app.services.player_identity_service import (
    PlayerIdentityResolutionError,
    PlayerIdentityRecord,
    _season_range,
    fetch_player_identity_record,
)


def test_season_range_includes_requested_nba_season_format():
    assert _season_range(2025, 2025) == ["2025-26"]


def test_player_identity_record_is_explicit_and_typed():
    record = PlayerIdentityRecord(
        player_id=1642955,
        name="Kadary Richmond",
        position="Guard",
        weight=205,
        born_date=date(2001, 8, 25),
        age=24,
        exp=0,
        school="St. John's, N.Y.",
        available_seasons=["2025-26"],
    )
    assert record.player_id == 1642955
    assert record.available_seasons == ["2025-26"]


def test_source_only_dnp_identity_can_be_resolved_without_claiming_season(monkeypatch):
    payload = {
        "resultSets": [
            {
                "name": "CommonPlayerInfo",
                "headers": [
                    "PERSON_ID", "DISPLAY_FIRST_LAST", "FROM_YEAR", "TO_YEAR",
                    "POSITION", "WEIGHT", "BIRTHDATE", "SEASON_EXP", "SCHOOL",
                ],
                "rowSet": [[
                    1641907, "Erik Stevenson", None, None, "", "",
                    "1999-04-28T00:00:00", 0, "West Virginia",
                ]],
            }
        ]
    }

    class FakeEndpoint:
        def get_dict(self):
            return payload

    monkeypatch.setattr(
        "app.services.player_identity_service.create_api_endpoint",
        lambda *args, **kwargs: FakeEndpoint(),
    )

    with pytest.raises(PlayerIdentityResolutionError):
        fetch_player_identity_record(1641907, season="2024-25")

    record = fetch_player_identity_record(
        1641907,
        season="2024-25",
        require_active_season=False,
    )
    assert record.name == "Erik Stevenson"
    assert record.available_seasons == []
