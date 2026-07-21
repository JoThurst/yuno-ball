"""Tests for source-preserving official injury-report PDF parsing."""

from datetime import datetime

from app.utils.parse.official_injury_report_parser import (
    parse_official_injury_report_layout,
)


def _layout_line(
    *,
    game_date: str = "",
    game_time: str = "",
    matchup: str = "",
    team: str = "",
    player: str = "",
    status: str = "",
    reason: str = "",
    reason_start: int = 94,
) -> str:
    fields = [(3, game_date), (16, game_time), (28, matchup), (36, team),
              (59, player), (81, status), (reason_start, reason)]
    width = max(116, *(start + len(value) for start, value in fields))
    chars = [" "] * width
    for start, value in fields:
        chars[start:start + len(value)] = value
    return "".join(chars)


def test_parser_preserves_wrapped_reasons_and_submission_state():
    page = "\n".join(
        [
            "Injury Report: 03/03/26 11:30 AM",
            "   Game Date    Game Time   Matchup Team                   Player Name           Current Status Reason",
            _layout_line(
                game_date="03/03/2026",
                game_time="07:00 (ET)",
                matchup="DAL@CHA",
                team="Dallas Mavericks",
            ),
            _layout_line(reason="Injury/Illness - Right Finger;", reason_start=92),
            _layout_line(player="Marshall, Naji", status="Out"),
            _layout_line(reason="Contusion", reason_start=92),
            _layout_line(player="Cisse, Moussa", status="Questionable", reason="G League - Two-Way"),
            _layout_line(matchup="WAS@ORL", team="Washington Wizards", status="NOT YET SUBMITTED"),
            _layout_line(team="Orlando Magic", player="Black, Anthony", status="Questionable", reason="Injury/Illness - Right Quad; Contusion"),
            "Page 1 of 1",
        ]
    )

    result = parse_official_injury_report_layout([page])

    assert result.parse_status == "parsed"
    assert result.report_published_at == datetime(
        2026, 3, 3, 11, 30, tzinfo=result.report_published_at.tzinfo
    )
    assert len(result.observations) == 3
    assert result.observations[0].game_time_text == "07:00 (ET)"
    assert result.team_submission_statuses[0].game_time_text == "07:00 (ET)"
    assert result.observations[0].reported_player_name == "Marshall, Naji"
    assert result.observations[0].raw_reason == "Injury/Illness - Right Finger; Contusion"
    assert result.observations[0].reason_category == "Injury/Illness"
    assert result.observations[0].reason_detail == "Right Finger; Contusion"
    assert result.observations[1].reason_category == "G League"
    assert result.observations[1].reason_detail == "Two-Way"
    assert result.team_submission_statuses[0].reported_team_name == "Washington Wizards"
    assert result.team_submission_statuses[0].submission_status == "NOT YET SUBMITTED"


def test_parser_carries_game_context_across_page_boundaries():
    first_page = "\n".join(
        [
            "Injury Report: 04/13/25 05:30 PM",
            _layout_line(
                game_date="04/13/2025",
                game_time="01:00 (ET)",
                matchup="CHA@BOS",
                team="Charlotte Hornets",
                player="Ball, LaMelo",
                status="Out",
                reason="Injury/Illness - Right Ankle; Impingement",
            ),
            "Page 1 of 2",
        ]
    )
    second_page = _layout_line(
        player="Brown, Jaylen",
        status="Out",
        reason="Injury/Illness - Right Knee; Impingement",
    )

    result = parse_official_injury_report_layout([first_page, second_page])

    assert len(result.observations) == 2
    assert result.observations[1].matchup == "CHA@BOS"
    assert result.observations[1].reported_team_name == "Charlotte Hornets"
