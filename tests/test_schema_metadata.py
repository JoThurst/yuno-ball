"""Regression checks for ORM metadata that Alembic compares to PostgreSQL."""

from app.models.consecutive_streak_sqlalchemy import ConsecutiveStreakORM
from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
from app.models.game_odds_sqlalchemy import GameOddsORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.ingestion_run_sqlalchemy import IngestionRunORM, IngestionTaskRunORM
from app.models.player_consistency_sqlalchemy import PlayerConsistencyORM
from app.models.player_game_status_sqlalchemy import PlayerGameStatusORM
from app.models.player_heat_index_sqlalchemy import PlayerHeatIndexORM
from app.models.player_stat_window_sqlalchemy import PlayerStatWindowORM
from app.models.player_z_scores_sqlalchemy import PlayerZScoresORM
from app.models.team_sqlalchemy import RosterORM
from app.models.team_daily_flags_sqlalchemy import TeamDailyFlagsORM
from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
from app.models.team_analytics_snapshot_sqlalchemy import (
    GameEnvironmentSnapshotORM,
    TeamGameFeatureSnapshotORM,
)


def _server_default(model, column_name: str) -> str:
    default = model.__table__.c[column_name].server_default
    assert default is not None
    return str(default.arg).lower()


def test_intentional_postgres_defaults_are_declared_in_metadata():
    expected = {
        GameEnvironmentDailyORM: {
            "pace_up_for_home": "false",
            "pace_up_for_away": "false",
            "three_point_fest": "false",
            "paint_battle": "false",
            "glass_war": "false",
            "whistle_heavy": "false",
            "created_at": "now()",
        },
        GameOddsORM: {"recorded_at": "now()", "updated_at": "now()"},
        IngestionRunORM: {
            "started_at": "now()",
            "created_at": "now()",
            "updated_at": "now()",
        },
        IngestionTaskRunORM: {
            "started_at": "now()",
            "created_at": "now()",
            "updated_at": "now()",
        },
        ConsecutiveStreakORM: {"is_active": "true", "created_at": "now()"},
        PlayerConsistencyORM: {"window_size": "0", "created_at": "now()"},
        PlayerGameStatusORM: {
            "played": "false",
            "recorded_at": "now()",
            "updated_at": "now()",
        },
        PlayerHeatIndexORM: {"created_at": "now()"},
        PlayerStatWindowORM: {"created_at": "now()"},
        TeamDailyFlagsORM: {"created_at": "now()"},
        TeamDailyMetricsORM: {"window_size": "10", "created_at": "now()"},
        TeamScheduleFactorsORM: {
            "is_b2b": "false",
            "is_3_in_4": "false",
            "is_4_in_5": "false",
            "is_5_in_7": "false",
            "created_at": "now()",
        },
        TeamGameFeatureSnapshotORM: {
            "is_b2b": "false",
            "is_3_in_4": "false",
            "is_4_in_5": "false",
            "is_5_in_7": "false",
            "games_last_4_days": "0",
            "games_last_7_days": "0",
            "flags": "'[]'::jsonb",
            "missing_input_flags": "'{}'::jsonb",
            "created_at": "now()",
        },
        GameEnvironmentSnapshotORM: {
            "pace_up_for_home": "false",
            "pace_up_for_away": "false",
            "tags": "'[]'::jsonb",
            "missing_input_flags": "'{}'::jsonb",
            "created_at": "now()",
        },
    }

    for model, defaults in expected.items():
        for column_name, value in defaults.items():
            assert _server_default(model, column_name) == value


def test_team_game_stats_comments_are_preserved_without_unused_indexes():
    expected_comments = {
        "oreb": "Offensive Rebounds",
        "dreb": "Defensive Rebounds",
        "pf": "Personal Fouls",
        "matchup": "Matchup string (e.g., LAL @ BOS)",
        "wl": "Win/Loss (W or L)",
        "w": "Season wins after this game",
        "l": "Season losses after this game",
        "w_pct": "Win percentage after this game",
    }
    for column_name, comment in expected_comments.items():
        assert TeamGameStatsORM.__table__.c[column_name].comment == comment

    index_names = {index.name for index in TeamGameStatsORM.__table__.indexes}
    assert "idx_team_game_stats_oreb" not in index_names
    assert "idx_team_game_stats_dreb" not in index_names
    assert "idx_team_game_stats_wl" not in index_names


def test_schedule_factors_uses_composite_schedule_foreign_key():
    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in TeamScheduleFactorsORM.__table__.foreign_key_constraints
    }

    assert (
        ("game_id", "team_id"),
        ("game_schedule.game_id", "game_schedule.team_id"),
        "CASCADE",
    ) in foreign_keys
    assert not any(
        columns == ("game_id",) and targets == ("game_schedule.game_id",)
        for columns, targets, _ in foreign_keys
    )


def test_team_snapshot_tables_use_composite_schedule_foreign_keys():
    team_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in TeamGameFeatureSnapshotORM.__table__.foreign_key_constraints
    }
    environment_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in GameEnvironmentSnapshotORM.__table__.foreign_key_constraints
    }

    assert ("game_schedule.game_id", "game_schedule.team_id") in team_targets
    assert sum(
        targets == ("game_schedule.game_id", "game_schedule.team_id")
        for targets in environment_targets
    ) == 1
    environment_fk_names = {
        constraint.name
        for constraint in GameEnvironmentSnapshotORM.__table__.foreign_key_constraints
    }
    assert "fk_game_environment_snapshot_home_schedule" in environment_fk_names
    assert "fk_game_environment_snapshot_away_schedule" in environment_fk_names


def test_phase4_mutable_source_constraints_are_declared_in_metadata():
    gamelog_fk_targets = {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in GameLogORM.__table__.foreign_key_constraints
    }
    assert ("players.player_id",) in gamelog_fk_targets
    assert ("game_schedule.game_id", "game_schedule.team_id") in gamelog_fk_targets

    gamelog_checks = {constraint.name for constraint in GameLogORM.__table__.constraints}
    roster_checks = {constraint.name for constraint in RosterORM.__table__.constraints}
    assert "ck_gamelogs_season_canonical" in gamelog_checks
    assert "ck_roster_season_canonical" in roster_checks
    assert [column.name for column in PlayerZScoresORM.__table__.primary_key] == [
        "player_id"
    ]
