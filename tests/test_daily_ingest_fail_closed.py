"""Fixture-only checks for unattended daily ingestion failure publication."""

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import daily_ingest
from app.services.ingestion_run_service import IngestionRunAlreadyActive
from app.utils.fetch.team_fetcher import TeamFetcher, TeamSeasonStatsFetchResult

# daily_fetch initializes its database pool at import time; these tests never open it.
with patch("db_config.init_db"):
    import daily_fetch


def _args():
    return SimpleNamespace(
        list=False,
        date=None,
        season="2026-27",
        validate_only=False,
        calc_only=False,
        fetch_only=False,
        proxy=False,
        local=False,
        force_gamelogs=False,
        fetch_tasks=None,
        exclude_fetch=None,
        force_calc=False,
        calc_tasks=None,
        exclude_calc=None,
        skip_validate=False,
    )


@pytest.fixture
def october_21_stale_player_index():
    return {
        "game_id": "0022600090",
        "participants": [
            {
                "player_id": player_id,
                "participation_status": "played",
                "available_seasons": ["2025-26"],
            }
            for player_id in range(1001, 1020)
        ],
    }


@pytest.mark.parametrize(
    ("outcome", "failed_tasks", "expected_status", "expected_exit"),
    [
        ({"fetch_success": False, "calc_success": True, "validate_success": True,
          "validation_status": "skipped", "skipped_calc": True, "overall_ok": False},
         True, "failed", 1),
        ({"fetch_success": True, "calc_success": True, "validate_success": False,
          "validation_status": "failed", "skipped_calc": False, "overall_ok": False},
         True, "failed", 1),
        ({"fetch_success": True, "calc_success": True, "validate_success": True,
          "validation_status": "passed", "skipped_calc": False, "overall_ok": True},
         True, "partial", 0),
    ],
)
def test_failed_or_partial_run_never_advances_success_marker(
    outcome, failed_tasks, expected_status, expected_exit
):
    tracker = SimpleNamespace(run_id="fixture-run")
    finished = []
    tracker.finish = lambda *args, **kwargs: finished.append((args, kwargs))

    @contextmanager
    def fake_tracker(**_kwargs):
        yield tracker

    with patch.object(daily_ingest, "parse_args", return_value=_args()), patch.object(
        daily_ingest, "IngestionRunTracker", side_effect=fake_tracker
    ), patch.object(daily_ingest, "execute_pipeline", return_value=outcome), patch.object(
        daily_ingest, "run_has_failed_tasks", return_value=failed_tasks
    ), patch.object(daily_ingest, "write_success_marker") as marker:
        result = daily_ingest.main()

    assert result == expected_exit
    assert finished[0][0] == (expected_status,)
    marker.assert_not_called()


def test_lock_collision_exits_three_without_pipeline_or_marker():
    with patch.object(daily_ingest, "parse_args", return_value=_args()), patch.object(
        daily_ingest, "IngestionRunTracker", side_effect=IngestionRunAlreadyActive("fixture lock")
    ), patch.object(daily_ingest, "execute_pipeline") as pipeline, patch.object(
        daily_ingest, "write_success_marker"
    ) as marker:
        result = daily_ingest.main()

    assert result == 3
    pipeline.assert_not_called()
    marker.assert_not_called()


@pytest.mark.parametrize("failed_phase", ["fetch", "validate"])
def test_critical_failure_skips_or_blocks_downstream_publication(failed_phase):
    args = _args()
    if failed_phase == "fetch":
        script_results = [False]
        validation_ok = True
    else:
        script_results = [True, True]
        validation_ok = False

    with patch.object(daily_ingest, "run_script", side_effect=script_results) as run_script, patch.object(
        daily_ingest, "_run_validation", return_value=validation_ok
    ) as validator:
        outcome = daily_ingest.execute_pipeline(args, "2026-27", date(2026, 10, 21), "fixture-run")

    assert outcome["overall_ok"] is False
    if failed_phase == "fetch":
        assert outcome["skipped_calc"] is True
        assert run_script.call_count == 1
        validator.assert_not_called()
    else:
        assert outcome["validation_status"] == "failed"
        assert run_script.call_count == 2
        validator.assert_called_once()


@pytest.mark.parametrize(
    ("task_key", "failure"),
    [
        ("teamstats", "provider timeout"),
        ("teamstats", "No rows returned"),
        ("schedule_reconcile", "incomplete reciprocal team pair"),
        ("player_facts", "C5 reconciliation failed"),
    ],
)
def test_required_fetch_failure_records_failed_task(task_key, failure):
    with patch.object(daily_fetch, "TeamFetcher") as team_fetcher, patch.object(
        daily_fetch, "PlayerFetcher"
    ), patch.object(daily_fetch, "ScheduleFetcher"), patch.object(
        daily_fetch, "SmartGameLogFetcher"
    ), patch.object(daily_fetch, "InjuryFetcher"), patch.object(
        daily_fetch, "OddsFetcher"
    ), patch.object(daily_fetch, "start_task", return_value="fixture-task"), patch.object(
        daily_fetch, "finish_task"
    ) as finish_task, patch.object(daily_fetch.time, "sleep"), patch.object(
        daily_fetch, "_reconcile_schedule_results", side_effect=RuntimeError(failure)
    ), patch(
        "app.services.player_game_fact_daily_service.collect_daily_player_game_facts",
        side_effect=RuntimeError(failure),
    ):
        team_fetcher.return_value.fetch_team_game_stats_for_season.side_effect = RuntimeError(failure)
        completed, failed, critical_failed = daily_fetch.run_fetch_tasks(
            [task_key], "2026-27", run_id="fixture-run"
        )

    assert (completed, failed, critical_failed) == (0, 1, True)
    assert finish_task.call_args.args[:2] == ("fixture-task", "failed")
    assert failure in finish_task.call_args.kwargs["error_summary"]


def test_supervised_fetch_stops_before_dependent_task_after_critical_failure():
    with patch.object(daily_fetch, "TeamFetcher"), patch.object(
        daily_fetch, "PlayerFetcher"
    ), patch.object(daily_fetch, "ScheduleFetcher"), patch.object(
        daily_fetch, "SmartGameLogFetcher"
    ), patch.object(daily_fetch, "InjuryFetcher"), patch.object(
        daily_fetch, "OddsFetcher"
    ), patch.object(daily_fetch, "start_task", return_value="fixture-task"), patch.object(
        daily_fetch, "finish_task"
    ) as finish_task, patch.object(daily_fetch.time, "sleep"), patch.object(
        daily_fetch, "_reconcile_schedule_results",
        side_effect=RuntimeError("incomplete reciprocal team pair"),
    ), patch(
        "app.services.player_game_fact_daily_service.collect_daily_player_game_facts"
    ) as player_facts:
        completed, failed, critical_failed = daily_fetch.run_fetch_tasks(
            ["schedule_reconcile", "player_facts"], "2026-27",
            run_id="fixture-run", fail_fast=True,
        )

    assert (completed, failed, critical_failed) == (0, 1, True)
    finish_task.assert_called_once()
    player_facts.assert_not_called()


def test_gamelogs_fail_closed_when_players_prerequisite_is_omitted(
    october_21_stale_player_index,
):
    # Before the dependency guard, this October 21 shape selected zero players:
    # all 19 played participants lacked 2026-27 in available_seasons, so the
    # current-tier query returned an empty set and gamelogs could report success.
    from app.models.player_sqlalchemy import PlayerORM

    assert october_21_stale_player_index["game_id"] == "0022600090"
    assert len(october_21_stale_player_index["participants"]) == 19
    assert all(
        participant["participation_status"] == "played"
        and "2026-27" not in participant["available_seasons"]
        for participant in october_21_stale_player_index["participants"]
    )
    with patch("app.utils.fetch.smart_gamelog_fetcher.get_db_context") as db_context, patch.object(
        PlayerORM,
        "get_active_for_season",
        side_effect=lambda season, db=None: [
            SimpleNamespace(player_id=participant["player_id"])
            for participant in october_21_stale_player_index["participants"]
            if season in participant["available_seasons"]
        ],
    ):
        db_context.return_value.__enter__.return_value = object()
        seasons, selected_ids = daily_fetch.SmartGameLogFetcher()._resolve_seasons_and_players(
            "current", 2026, 2026, current_season="2026-27"
        )
    assert seasons == ["2026-27"]
    assert selected_ids == []

    with patch.object(daily_fetch, "TeamFetcher"), patch.object(
        daily_fetch, "PlayerFetcher"
    ), patch.object(daily_fetch, "ScheduleFetcher"), patch.object(
        daily_fetch, "SmartGameLogFetcher"
    ) as gamelog_fetcher, patch.object(daily_fetch, "InjuryFetcher"), patch.object(
        daily_fetch, "OddsFetcher"
    ), patch.object(daily_fetch, "start_task", return_value="fixture-gamelog-task") as start_task, patch.object(
        daily_fetch, "finish_task"
    ) as finish_task, patch.object(daily_fetch.time, "sleep"):
        completed, failed, critical_failed = daily_fetch.run_fetch_tasks(
            ["gamelogs"], "2026-27", run_id="fixture-run"
        )

    assert (completed, failed, critical_failed) == (0, 1, True)
    start_task.assert_called_once_with(
        "fixture-run", "fetch.gamelogs",
        source="nba", provider="stats.nba.com/nba-cdn", details=None,
    )
    finish_task.assert_called_once()
    assert finish_task.call_args.args[:2] == ("fixture-gamelog-task", "failed")
    assert "fetch.players" in finish_task.call_args.kwargs["error_summary"]
    assert "before fetch.gamelogs" in finish_task.call_args.kwargs["error_summary"]
    gamelog_fetcher.return_value.fetch_game_logs_tiered.assert_not_called()


def test_players_then_gamelogs_selects_current_season_participants_on_rerun():
    from app.models.player_sqlalchemy import PlayerORM
    from app.utils.fetch.smart_gamelog_fetcher import SmartGameLogFetcher

    participant_ids = list(range(1001, 1020))
    player_rows = {
        player_id: SimpleNamespace(
            player_id=player_id,
            name=f"Fixture Player {player_id}",
            position=None,
            weight=None,
            born_date=None,
            age=None,
            exp=None,
            school=None,
            available_seasons=["2025-26"],
        )
        for player_id in participant_ids
    }

    @contextmanager
    def fake_db_context():
        yield SimpleNamespace(flush=lambda: None, commit=lambda: None, rollback=lambda: None)

    def get_or_create(player_id, name, available_seasons, **_kwargs):
        row = player_rows.get(player_id)
        if row is None:
            row = SimpleNamespace(
                player_id=player_id, name=name, position=None, weight=None,
                born_date=None, age=None, exp=None, school=None,
                available_seasons=list(available_seasons),
            )
            player_rows[player_id] = row
        else:
            row.available_seasons = list(available_seasons)
        return row

    selected_each_run = []

    def resolve_after_sync(_self, tier, start_year, end_year, current_season=None):
        seasons, ids = SmartGameLogFetcher._resolve_seasons_and_players(
            _self, tier, start_year, end_year, current_season=current_season
        )
        selected_each_run.append(ids)
        return seasons, ids

    def observe_selection(**kwargs):
        return resolve_after_sync(
            daily_fetch.SmartGameLogFetcher(), "current", 2026, 2026,
            kwargs["current_season"],
        )

    with patch("app.utils.fetch.player_fetcher.players.get_active_players", return_value=[
        {"id": player_id, "full_name": f"Fixture Player {player_id}"}
        for player_id in participant_ids
    ]), patch("app.utils.fetch.player_fetcher.get_db_context", side_effect=fake_db_context), patch.object(
        PlayerORM, "get_by_id", side_effect=lambda player_id, db=None: player_rows.get(player_id)
    ), patch.object(PlayerORM, "create", side_effect=get_or_create), patch.object(
        PlayerORM, "get_active_for_season", side_effect=lambda season, db=None: [
            row for row in player_rows.values() if season in (row.available_seasons or [])
        ]
    ), patch("app.utils.fetch.smart_gamelog_fetcher.get_db_context", side_effect=fake_db_context), patch.object(
        daily_fetch, "TeamFetcher"
    ), patch.object(daily_fetch, "ScheduleFetcher"), patch.object(
        daily_fetch, "SmartGameLogFetcher"
    ) as gamelog_fetcher, patch.object(daily_fetch, "InjuryFetcher"), patch.object(
        daily_fetch, "OddsFetcher"
    ), patch.object(daily_fetch.time, "sleep"), patch.object(daily_fetch, "start_task", return_value=None), patch.object(
        daily_fetch, "finish_task"
    ):
        gamelog_fetcher.return_value.fetch_game_logs_tiered.side_effect = observe_selection
        first = daily_fetch.run_fetch_tasks(["players", "gamelogs"], "2026-27")
        second = daily_fetch.run_fetch_tasks(["players", "gamelogs"], "2026-27")

    assert first == (2, 0, False)
    assert second == (2, 0, False)
    assert selected_each_run == [participant_ids, participant_ids]
    assert all(
        player_rows[player_id].available_seasons.count("2026-27") == 1
        for player_id in participant_ids
    )


def test_empty_team_response_fails_season_task_without_database_writes():
    teams = [SimpleNamespace(team_id=1)]
    with patch("app.utils.fetch.team_fetcher.get_db_context") as db_context, patch(
        "app.utils.fetch.team_fetcher.TeamORM.get_all", return_value=teams
    ), patch.object(
        TeamFetcher,
        "_fetch_team_season_stats",
        return_value=TeamSeasonStatsFetchResult(
            1, "2026-27", False, error="No rows returned for team 1"
        ),
    ):
        db_context.return_value.__enter__.return_value = object()
        with pytest.raises(RuntimeError, match="No rows returned"):
            TeamFetcher().fetch_team_game_stats_for_season("2026-27")
