from datetime import datetime

from app.services.player_game_fact_read_service import (
    PlayerGameFactReadRow,
    PlayerGameFactReadService,
)


def _row(source, game_id="g", player_id=1, status="played"):
    return PlayerGameFactReadRow(
        player_id=player_id,
        game_id=game_id,
        team_id=10,
        points=5,
        assists=2,
        rebounds=3,
        steals=1,
        blocks=0,
        turnovers=1,
        minutes="12:30",
        season="2025-26",
        season_type="Regular Season",
        game_date=datetime(2026, 3, 3),
        participation_status=status,
        completeness_status="complete",
        source_name=source,
    )


def test_canonical_rows_override_legacy_at_same_grain():
    rows = PlayerGameFactReadService._merge(
        [_row("nba_boxscore_traditional_v3")],
        [_row("legacy_gamelogs")],
        played_only=True,
    )
    assert len(rows) == 1
    assert rows[0].source_name == "nba_boxscore_traditional_v3"


def test_legacy_fills_only_uncovered_history():
    rows = PlayerGameFactReadService._merge(
        [_row("nba_boxscore_traditional_v3")],
        [_row("legacy_gamelogs", game_id="older")],
        played_only=True,
    )
    assert {row.game_id for row in rows} == {"g", "older"}


def test_played_compatibility_excludes_dnp_but_preserves_source_row():
    dnp = _row("nba_boxscore_traditional_v3", status="did_not_play")
    assert PlayerGameFactReadService._merge([dnp], [], played_only=True) == []
    assert PlayerGameFactReadService._merge([dnp], [], played_only=False) == [dnp]


def test_minutes_exposes_legacy_decimal_compatibility():
    assert _row("source").minutes_played == "12.5"
