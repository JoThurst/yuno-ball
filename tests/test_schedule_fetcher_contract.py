"""Pure contract tests for the season-aware schedule source boundary."""

from datetime import date

import pytest

from app.utils.fetch.schedule_fetcher import ScheduleFetcher, ScheduleSourceError


def _record(
    *,
    game_id="0042500101",
    game_status=3,
    game_datetime="2026-04-15T23:30:00Z",
    season="2025-26",
):
    return {
        "seasonYear": season,
        "gameId": game_id,
        "gameStatus": game_status,
        "gameDateTimeUTC": game_datetime,
        "homeTeam_teamId": 1610612738,
        "awayTeam_teamId": 1610612751,
        "homeTeam_score": 110,
        "awayTeam_score": 105,
    }


def test_scheduleleaguev2_records_emit_reciprocal_provenance_rows():
    entries = ScheduleFetcher._entries_from_records(
        [_record()],
        season="2025-26",
        source_name="nba-stats-scheduleleaguev2",
        source_parser_version="scheduleleaguev2-v1",
        start_date=date(2026, 4, 15),
        end_date=date(2026, 4, 15),
    )

    assert len(entries) == 2
    assert {entry["home_or_away"] for entry in entries} == {"H", "A"}
    assert {entry["season_type"] for entry in entries} == {"Playoffs"}
    assert {entry["source_name"] for entry in entries} == {
        "nba-stats-scheduleleaguev2"
    }
    assert {entry["team_score"] for entry in entries} == {105, 110}
    assert {entry["opponent_score"] for entry in entries} == {105, 110}


def test_scheduleleaguev2_records_preserve_play_in_type_and_date_filter():
    entries = ScheduleFetcher._entries_from_records(
        [
            _record(game_id="0052500001", game_datetime="2026-04-14T23:30:00Z"),
            _record(game_id="0052500002", game_datetime="2026-04-15T23:30:00Z"),
        ],
        season="2025-26",
        source_name="nba-stats-scheduleleaguev2",
        source_parser_version="scheduleleaguev2-v1",
        start_date=date(2026, 4, 15),
        end_date=date(2026, 4, 15),
        season_types=("Play-In",),
    )

    assert {entry["game_id"] for entry in entries} == {"0052500002"}
    assert {entry["season_type"] for entry in entries} == {"Play-In"}


def test_future_mode_excludes_final_stats_api_rows():
    entries = ScheduleFetcher._entries_from_records(
        [_record(game_status=3), _record(game_id="0042500102", game_status=1)],
        season="2025-26",
        source_name="nba-stats-scheduleleaguev2",
        source_parser_version="scheduleleaguev2-v1",
        mode="future",
    )

    assert {entry["game_id"] for entry in entries} == {"0042500102"}


def test_stats_api_records_skip_tbd_matchups_without_discarding_season():
    tbd = _record(game_id="0022601201")
    tbd["seasonYear"] = "2026-27"
    tbd["homeTeam_teamId"] = 0
    tbd["awayTeam_teamId"] = 0

    valid = _record(game_id="0022600001", game_datetime="2026-10-21T23:30:00Z", game_status=1, season="2026-27")
    entries = ScheduleFetcher._entries_from_records(
        [tbd, valid],
        season="2026-27",
        source_name="nba-stats-scheduleleaguev2",
        source_parser_version="scheduleleaguev2-v1",
        mode="future",
    )

    assert {entry["game_id"] for entry in entries} == {"0022600001"}
    assert all(entry["team_score"] is None for entry in entries)
    assert all(entry["opponent_score"] is None for entry in entries)


def test_schedule_source_rejects_mismatched_or_empty_cdn_payload():
    with pytest.raises(ScheduleSourceError):
        ScheduleFetcher._validate_payload_season(
            {"seasonYear": "2024-25", "gameDates": [{}]}, "2025-26"
        )
    with pytest.raises(ScheduleSourceError):
        ScheduleFetcher._validate_payload_season(
            {"seasonYear": "2025-26", "gameDates": []}, "2025-26"
        )
