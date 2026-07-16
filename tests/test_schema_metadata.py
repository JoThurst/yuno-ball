"""Regression checks for ORM metadata that Alembic compares to PostgreSQL."""

from app.models.consecutive_streak_sqlalchemy import ConsecutiveStreakORM
from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
from app.models.game_odds_sqlalchemy import GameOddsORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.external_dataset_import_sqlalchemy import ExternalDatasetImportORM
from app.models.external_staging_sqlalchemy import (
    ExternalRowRejectionORM,
    ExternalMarketAnomalyORM,
    KaggleGameStagingORM,
    KaggleMoneylineStagingORM,
    KaggleSpreadStagingORM,
    KaggleTotalStagingORM,
    StatsurgeAvailabilityStagingORM,
)
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
        ExternalDatasetImportORM: {
            "created_at": "now()",
            "updated_at": "now()",
        },
        StatsurgeAvailabilityStagingORM: {"created_at": "now()"},
        ExternalRowRejectionORM: {"created_at": "now()"},
        KaggleGameStagingORM: {"created_at": "now()"},
        KaggleMoneylineStagingORM: {"created_at": "now()"},
        KaggleSpreadStagingORM: {"created_at": "now()"},
        KaggleTotalStagingORM: {"created_at": "now()"},
        ExternalMarketAnomalyORM: {"created_at": "now()"},
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


def test_external_dataset_manifest_has_immutable_grain_and_run_lineage():
    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in ExternalDatasetImportORM.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert unique_constraints["uq_external_dataset_import_artifact"] == (
        "source_name",
        "dataset_name",
        "dataset_version",
        "sha256",
        "transformation_version",
    )


def test_game_schedule_declares_event_score_and_external_lineage_contract():
    required_columns = {
        "season_type",
        "game_date_precision",
        "team_score",
        "opponent_score",
        "source_name",
        "source_import_id",
        "source_run_id",
        "source_row_number",
        "source_row_sha256",
        "source_parser_version",
    }
    assert required_columns <= set(GameScheduleORM.__table__.c.keys())
    assert GameScheduleORM.__table__.c.season_type.nullable is False
    assert GameScheduleORM.__table__.c.game_date_precision.nullable is False
    assert GameScheduleORM.__table__.c.source_name.nullable is False

    foreign_key_targets = {
        element.target_fullname
        for constraint in GameScheduleORM.__table__.foreign_key_constraints
        for element in constraint.elements
    }
    assert "external_dataset_imports.import_id" in foreign_key_targets
    assert "ingestion_runs.run_id" in foreign_key_targets

    check_names = {
        constraint.name
        for constraint in GameScheduleORM.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }
    assert "ck_game_schedule_season_type" in check_names
    assert "ck_game_schedule_result_scores" in check_names
    assert "ck_game_schedule_external_lineage" in check_names

    foreign_key_targets = {
        element.target_fullname
        for constraint in ExternalDatasetImportORM.__table__.foreign_key_constraints
        for element in constraint.elements
    }
    assert "ingestion_runs.run_id" in foreign_key_targets

    check_names = {
        constraint.name
        for constraint in ExternalDatasetImportORM.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }
    assert "ck_external_dataset_import_sha256" in check_names
    assert "ck_external_dataset_import_download_value" in check_names
    assert "ck_external_dataset_import_license_status" in check_names


def test_statsurge_staging_preserves_source_grain_and_lineage():
    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in StatsurgeAvailabilityStagingORM.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert unique_constraints["uq_statsurge_availability_source_row"] == (
        "source_import_id",
        "source_row_number",
        "parser_version",
    )
    assert unique_constraints["uq_statsurge_availability_natural_grain"] == (
        "source_import_id",
        "source_dataset_version",
        "report_date",
        "matchup_text",
        "reported_team_name",
        "reported_player_name",
        "parser_version",
    )

    foreign_key_targets = {
        element.target_fullname
        for constraint in StatsurgeAvailabilityStagingORM.__table__.foreign_key_constraints
        for element in constraint.elements
    }
    assert foreign_key_targets == {
        "external_dataset_imports.import_id",
        "ingestion_runs.run_id",
    }

    rejection_targets = {
        element.target_fullname
        for constraint in ExternalRowRejectionORM.__table__.foreign_key_constraints
        for element in constraint.elements
    }
    assert rejection_targets == foreign_key_targets

    check_names = {
        constraint.name
        for constraint in StatsurgeAvailabilityStagingORM.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }
    assert "ck_statsurge_availability_no_published_at" in check_names
    assert "ck_statsurge_availability_time_precision" in check_names
    assert "ck_statsurge_availability_identity_status" in check_names
    assert "ck_statsurge_availability_resolution_lineage" in check_names
    assert StatsurgeAvailabilityStagingORM.__table__.c.identity_resolution_version.nullable is True
    assert StatsurgeAvailabilityStagingORM.__table__.c.identity_resolution_run_id.nullable is True
    assert StatsurgeAvailabilityStagingORM.__table__.c.identity_resolution_details.nullable is True
    resolution_targets = {
        element.target_fullname
        for constraint in StatsurgeAvailabilityStagingORM.__table__.foreign_key_constraints
        for element in constraint.elements
    }
    assert "ingestion_runs.run_id" in resolution_targets


def test_kaggle_game_staging_preserves_pair_grain_and_missingness_states():
    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in KaggleGameStagingORM.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert unique_constraints["uq_kaggle_games_source_row"] == (
        "source_import_id",
        "source_row_number",
        "parser_version",
    )
    assert unique_constraints["uq_kaggle_games_natural_grain"] == (
        "source_import_id",
        "game_id",
        "team_id",
        "parser_version",
    )
    assert KaggleGameStagingORM.__table__.c.game_date.nullable is True
    assert KaggleGameStagingORM.__table__.c.wl.nullable is True
    assert KaggleGameStagingORM.__table__.c.fg3_pct.nullable is True

    check_names = {
        constraint.name
        for constraint in KaggleGameStagingORM.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }
    assert "ck_kaggle_games_result_value" in check_names
    assert "ck_kaggle_games_promotion_eligibility" in check_names
    assert "ck_kaggle_games_canonical_match_status" in check_names


def test_kaggle_market_staging_links_to_source_game_and_preserves_semantics():
    for model, constraint_name in (
        (KaggleMoneylineStagingORM, "uq_kaggle_moneylines_natural_grain"),
        (KaggleSpreadStagingORM, "uq_kaggle_spreads_natural_grain"),
        (KaggleTotalStagingORM, "uq_kaggle_totals_natural_grain"),
    ):
        unique_constraints = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in model.__table__.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert unique_constraints[constraint_name] == (
            "source_import_id",
            "game_id",
            "book_id",
            "team_id",
            "opponent_team_id",
            "parser_version",
        )
        foreign_key_names = {
            constraint.name
            for constraint in model.__table__.foreign_key_constraints
            if constraint.name is not None
        }
        assert any(name.endswith("_source_game") for name in foreign_key_names)
        assert not any(
            tuple(element.parent.name for element in constraint.elements)
            == ("source_game_import_id",)
            for constraint in model.__table__.foreign_key_constraints
        )
        check_names = {
            constraint.name
            for constraint in model.__table__.constraints
            if constraint.__class__.__name__ == "CheckConstraint"
        }
        assert any(name.endswith("_timing_precision") for name in check_names)
        assert any(name.endswith("_snapshot_type") for name in check_names)

    assert KaggleSpreadStagingORM.__table__.c.line_pair_status.nullable is False
    assert KaggleTotalStagingORM.__table__.c.line_pair_status.nullable is False
    anomaly_targets = {
        element.target_fullname
        for constraint in ExternalMarketAnomalyORM.__table__.foreign_key_constraints
        for element in constraint.elements
    }
    assert "external_dataset_imports.import_id" in anomaly_targets
    assert "ingestion_runs.run_id" in anomaly_targets
