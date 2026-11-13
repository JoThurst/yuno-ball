from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.matchup_player_context_service import build_player_context

CUTOFF = datetime(2026, 10, 26, 14, tzinfo=timezone.utc)


def row(day=25, **changes):
    values = dict(game_date=date(2026, 10, day), data_available_at=CUTOFF,
                  selected_at=CUTOFF, canonical_player_id=1, canonical_team_id=10,
                  canonical_game_id=str(day), participation_status="played",
                  points=20, rebounds_total=5, assists=0, minutes="30:30",
                  source_name="official")
    return SimpleNamespace(**(values | changes))


def build(rows):
    return build_player_context(rows, target_date=date(2026, 10, 26), cutoff=CUTOFF,
                                team_ids={10, 20})


def test_ordinary_players_have_averages_recent_lines_and_real_denominators():
    result = build([row(25), row(24), row(23), row(22, points=None),
                    row(21, participation_status="did_not_play", points=0)])
    player = result[10][0]
    assert player["player_name"] == "Player 1"
    assert player["appearances"] == 4
    assert player["averages"]["points"] == {"value": 20.0, "sample_size": 3, "appearances": 4}
    assert player["averages"]["assists"]["value"] == 0
    assert player["averages"]["minutes"]["value"] == 30.5
    assert len(player["recent_lines"]) == 3
    assert {"stat": "points", "threshold": 20, "length": 3} in player["streaks"]
    assert {"stat": "points", "threshold": 20, "hits": 3, "denominator": 3, "appearances": 4} in player["frequencies"]


def test_target_later_and_late_selected_or_available_rows_are_excluded():
    later = datetime(2026, 10, 27, tzinfo=timezone.utc)
    assert build([row(26), row(27), row(selected_at=later), row(data_available_at=later),
                  row(canonical_player_id=None)]) == {10: [], 20: []}


def test_late_selected_game_withholds_whole_player_history_to_avoid_false_streak():
    later = datetime(2026, 10, 27, tzinfo=timezone.utc)
    assert not build([row(25, selected_at=later), row(24), row(23), row(22)])[10]


def test_latest_observed_team_and_conflicting_membership_are_conservative():
    assert not build([row(24), row(25, canonical_team_id=30)])[10]
    assert not build([row(25), row(25, canonical_team_id=20)])[10]
    player = build([row(24), row(25, canonical_team_id=20)])[20][0]
    assert player["appearances"] == 2
    assert player["membership_status"] == "last_observed_only"


def test_empty_dnp_and_missing_values_do_not_become_zero():
    assert build([]) == {10: [], 20: []}
    assert not build([row(participation_status="did_not_play")])[10]
    player = build([row(points=None, minutes=None)])[10][0]
    assert player["averages"]["points"]["value"] is None
    assert player["frequencies"][0]["denominator"] == 0
    assert player["streaks"] == []


def test_hour_minute_second_minutes_are_valid_canonical_values():
    player = build([row(minutes="1:02:30")])[10][0]
    assert player["averages"]["minutes"]["value"] == 62.5
    assert player["recent_lines"][0]["minutes"] == 62.5


def test_same_day_games_withhold_order_dependent_context():
    player = build([row(25, canonical_game_id="1"), row(25, canonical_game_id="2"),
                    row(24), row(23)])[10][0]
    assert player["appearances"] == 4
    assert player["averages"]["points"]["value"] == 20.0
    assert player["recent_lines"] == []
    assert player["frequencies"] == []
    assert player["streaks"] == []
    assert player["recent_history_reason"] == "same_day_game_order_unknown"
