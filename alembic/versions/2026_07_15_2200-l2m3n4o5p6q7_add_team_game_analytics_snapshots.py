"""Add leakage-safe team-game and game-environment snapshots.

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-07-15 22:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "l2m3n4o5p6q7"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def _provenance_columns(check_name: str):
    return (
        sa.Column("season", sa.String(length=7), nullable=False),
        sa.Column("season_type", sa.String(length=32), nullable=False),
        sa.Column("feature_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculation_version", sa.String(length=64), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("completeness_status", sa.String(length=16), nullable=False),
        sa.Column(
            "missing_input_flags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
        ),
        sa.CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name=check_name,
        ),
    )


def upgrade():
    op.create_table(
        "team_game_feature_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(length=20), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("opponent_team_id", sa.Integer(), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("scheduled_tipoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_home", sa.Boolean(), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("source_latest_game_id", sa.String(length=20), nullable=True),
        sa.Column("source_latest_game_date", sa.Date(), nullable=True),
        sa.Column("season_games_played", sa.Integer(), nullable=False),
        sa.Column("season_games_used", sa.Integer(), nullable=False),
        sa.Column("window_games_played", sa.Integer(), nullable=False),
        sa.Column("window_games_used", sa.Integer(), nullable=False),
        *(
            sa.Column(f"{metric}_{scope}", sa.Float(), nullable=True)
            for scope in ("season", "lastn", "delta")
            for metric in (
                "off_rtg",
                "def_rtg",
                "net_rtg",
                "pace",
                "efg",
                "tov_pct",
                "orb_pct",
                "ftr",
                "pct_pts_3pt",
            )
        ),
        sa.Column("sos_net_season", sa.Float(), nullable=True),
        sa.Column("sos_net_lastn", sa.Float(), nullable=True),
        sa.Column("sos_net_delta", sa.Float(), nullable=True),
        sa.Column("days_rest", sa.Integer(), nullable=True),
        sa.Column("is_b2b", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_3_in_4", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_4_in_5", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_5_in_7", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("games_last_4_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("games_last_7_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("flags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_provenance_columns("ck_team_feature_snapshot_completeness"),
        sa.ForeignKeyConstraint(
            ["game_id", "team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_team_feature_snapshot_schedule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"]),
        sa.ForeignKeyConstraint(["opponent_team_id"], ["teams.team_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "team_id",
            "window_size",
            "feature_as_of",
            "calculation_version",
            name="uq_team_feature_snapshot_natural_key",
        ),
        sa.CheckConstraint(
            "window_games_played <= season_games_played",
            name="ck_team_feature_snapshot_window_lte_season",
        ),
        sa.CheckConstraint(
            "season_games_used <= season_games_played AND "
            "window_games_used <= window_games_played",
            name="ck_team_feature_snapshot_used_lte_played",
        ),
    )
    op.create_index(
        "idx_team_feature_snapshot_latest",
        "team_game_feature_snapshots",
        ["season", "season_type", "calculation_version", "completeness_status", "feature_as_of"],
    )
    op.create_index(
        "idx_team_feature_snapshot_team",
        "team_game_feature_snapshots",
        ["team_id", "feature_as_of"],
    )

    op.create_table(
        "game_environment_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.String(length=20), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("scheduled_tipoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("home_off_rtg_lastn", sa.Float(), nullable=True),
        sa.Column("home_def_rtg_lastn", sa.Float(), nullable=True),
        sa.Column("home_pace_lastn", sa.Float(), nullable=True),
        sa.Column("away_off_rtg_lastn", sa.Float(), nullable=True),
        sa.Column("away_def_rtg_lastn", sa.Float(), nullable=True),
        sa.Column("away_pace_lastn", sa.Float(), nullable=True),
        sa.Column("pace_projection", sa.Float(), nullable=True),
        sa.Column("scoring_env_index", sa.Float(), nullable=True),
        sa.Column("three_env_index", sa.Float(), nullable=True),
        sa.Column("chaos_index", sa.Float(), nullable=True),
        sa.Column("pace_up_for_home", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pace_up_for_away", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_provenance_columns("ck_game_environment_snapshot_completeness"),
        sa.ForeignKeyConstraint(
            ["game_id", "home_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_game_environment_snapshot_home_schedule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "away_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_game_environment_snapshot_away_schedule",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.team_id"]),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.team_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "window_size",
            "feature_as_of",
            "calculation_version",
            name="uq_game_environment_snapshot_natural_key",
        ),
    )
    op.create_index(
        "idx_game_environment_snapshot_latest",
        "game_environment_snapshots",
        ["season", "season_type", "calculation_version", "completeness_status", "feature_as_of"],
    )
    op.create_index(
        "idx_game_environment_snapshot_date",
        "game_environment_snapshots",
        ["game_date", "feature_as_of"],
    )


def downgrade():
    op.drop_index("idx_game_environment_snapshot_date", table_name="game_environment_snapshots")
    op.drop_index("idx_game_environment_snapshot_latest", table_name="game_environment_snapshots")
    op.drop_table("game_environment_snapshots")
    op.drop_index("idx_team_feature_snapshot_team", table_name="team_game_feature_snapshots")
    op.drop_index("idx_team_feature_snapshot_latest", table_name="team_game_feature_snapshots")
    op.drop_table("team_game_feature_snapshots")
