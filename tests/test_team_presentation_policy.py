from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.team_presentation_policy import qualified_environment, qualified_small_sample, team_readout


CUTOFF = datetime(2026, 10, 26, 14, tzinfo=timezone.utc)


def team(team_id, opponent, home, games):
    return SimpleNamespace(
        game_id="0022600001", team_id=team_id, opponent_team_id=opponent, is_home=home,
        game_date=date(2026, 10, 26), scheduled_tipoff=CUTOFF + timedelta(hours=5),
        feature_as_of=CUTOFF, data_available_at=CUTOFF - timedelta(hours=1),
        calculation_version="team-v2.1", season="2026-27", season_type="Regular Season",
        source_run_id="run", source_latest_game_id="0022600000", source_latest_game_date=date(2026, 10, 25),
        window_size=10, window_games_used=min(games, 10), window_games_played=min(games, 10),
        season_games_used=games, season_games_played=games,
        missing_input_flags={"insufficient_window_games": {"required": 10, "available": games}},
        completeness_status="partial", pace_lastn=100.0, off_rtg_lastn=110.0,
        def_rtg_lastn=110.0, net_rtg_season=0.0, net_rtg_delta=0.0,
    )


@pytest.mark.parametrize("games,qualifies", [(0, False), (1, True), (2, True), (3, True), (10, False), (11, False)])
def test_qualified_partial_requires_a_real_short_window(games, qualifies):
    assert qualified_small_sample(team(1, 2, True, games), CUTOFF) is qualifies


def test_missing_inputs_conflicting_counts_and_future_lineage_fail_closed():
    row = team(1, 2, True, 2)
    row.missing_input_flags["excluded_window_games"] = ["bad"]
    assert not qualified_small_sample(row, CUTOFF)
    row.missing_input_flags.pop("excluded_window_games")
    row.window_games_used = 1
    assert not qualified_small_sample(row, CUTOFF)
    row.window_games_used = 2
    row.data_available_at = CUTOFF + timedelta(seconds=1)
    assert not qualified_small_sample(row, CUTOFF)
    row.data_available_at = CUTOFF
    row.pace_lastn = float("nan")
    assert not qualified_small_sample(row, CUTOFF)


def test_short_window_cannot_hide_larger_season_sample():
    row = team(1, 2, True, 2)
    row.season_games_used = row.season_games_played = 11
    assert not qualified_small_sample(row, CUTOFF)


def test_environment_requires_same_paired_source_and_preserves_zero():
    home, away = team(1, 2, True, 2), team(2, 1, False, 3)
    environment = SimpleNamespace(**{key: getattr(home, key) for key in (
        "game_id", "feature_as_of", "calculation_version", "window_size", "source_run_id",
        "season", "season_type", "scheduled_tipoff", "data_available_at")},
        home_team_id=1, away_team_id=2, missing_input_flags={"partial_team_snapshots": True},
        pace_projection=0.0, scoring_env_index=0.0)
    teams = {(home.game_id, 1): home, (away.game_id, 2): away}
    assert qualified_environment(environment, teams, CUTOFF)
    away.source_run_id = "different"
    assert not qualified_environment(environment, teams, CUTOFF)
    away.source_run_id = "run"
    away.is_home = True
    assert not qualified_environment(environment, teams, CUTOFF)


def test_team_readout_only_uses_delta_after_season_exceeds_window():
    assert team_readout(team(1, 2, True, 10))["label"] == "Season net rating"
    readout = team_readout(team(1, 2, True, 11))
    assert readout["label"] == "Recent minus season net rating"
    assert readout["value"] == 0.0
