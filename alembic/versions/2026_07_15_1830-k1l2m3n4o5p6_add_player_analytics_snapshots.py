"""Add versioned player analytical snapshot tables.

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-07-15 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def _provenance_columns():
    # Return new Column instances because one instance cannot belong to more
    # than one table.
    return (
        sa.Column("season", sa.String(length=7), nullable=False),
        sa.Column("season_type", sa.String(length=32), nullable=False),
        sa.Column("feature_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=False),
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
    )


def upgrade():
    op.create_table(
        "player_consecutive_streak_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("stat", sa.String(length=16), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("streak_games", sa.Integer(), nullable=False),
        sa.Column("start_game_id", sa.String(), nullable=False),
        sa.Column("end_game_id", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("streak_kind", sa.String(length=16), nullable=False),
        *_provenance_columns(),
        sa.CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_streak_snapshot_completeness",
        ),
        sa.CheckConstraint(
            "streak_kind IN ('current', 'season_max')",
            name="ck_player_streak_snapshot_kind",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.player_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id", "stat", "threshold", "season", "season_type",
            "feature_as_of", "calculation_version", "streak_kind",
            name="uq_player_streak_snapshot_natural_key",
        ),
    )
    op.create_index(
        "idx_player_streak_snapshot_latest",
        "player_consecutive_streak_snapshots",
        ["season", "season_type", "calculation_version", "completeness_status", "feature_as_of"],
    )
    op.create_index(
        "idx_player_streak_snapshot_player",
        "player_consecutive_streak_snapshots",
        ["player_id", "feature_as_of"],
    )

    op.create_table(
        "player_stat_window_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("stat", sa.String(length=16), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("games_played", sa.Integer(), nullable=False),
        sa.Column("games_hit", sa.Integer(), nullable=False),
        sa.Column("last_game_id", sa.String(), nullable=False),
        sa.Column("last_game_date", sa.Date(), nullable=False),
        *_provenance_columns(),
        sa.CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_window_snapshot_completeness",
        ),
        sa.CheckConstraint("games_hit <= games_played", name="ck_player_window_hits_lte_games"),
        sa.ForeignKeyConstraint(["player_id"], ["players.player_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id", "stat", "threshold", "season", "season_type",
            "window_size", "feature_as_of", "calculation_version",
            name="uq_player_window_snapshot_natural_key",
        ),
    )
    op.create_index(
        "idx_player_window_snapshot_latest",
        "player_stat_window_snapshots",
        ["season", "season_type", "calculation_version", "completeness_status", "feature_as_of"],
    )
    op.create_index(
        "idx_player_window_snapshot_player",
        "player_stat_window_snapshots",
        ["player_id", "feature_as_of"],
    )

    op.create_table(
        "player_heat_index_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("stat", sa.String(length=16), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("games_played", sa.Integer(), nullable=False),
        sa.Column("recent_games_played", sa.Integer(), nullable=False),
        sa.Column("season_avg", sa.Float(), nullable=False),
        sa.Column("season_std", sa.Float(), nullable=False),
        sa.Column("recent_avg", sa.Float(), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        *_provenance_columns(),
        sa.CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_heat_snapshot_completeness",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.player_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id", "stat", "season", "season_type", "window_size",
            "feature_as_of", "calculation_version",
            name="uq_player_heat_snapshot_natural_key",
        ),
    )
    op.create_index(
        "idx_player_heat_snapshot_latest",
        "player_heat_index_snapshots",
        ["season", "season_type", "calculation_version", "completeness_status", "feature_as_of"],
    )
    op.create_index(
        "idx_player_heat_snapshot_player",
        "player_heat_index_snapshots",
        ["player_id", "feature_as_of"],
    )

    op.create_table(
        "player_consistency_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("stat_name", sa.String(length=16), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("games_played", sa.Integer(), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("stddev", sa.Float(), nullable=False),
        sa.Column("cv", sa.Float(), nullable=False),
        sa.Column("min_val", sa.Float(), nullable=False),
        sa.Column("max_val", sa.Float(), nullable=False),
        sa.Column("median", sa.Float(), nullable=False),
        sa.Column("consistency_tier", sa.String(length=16), nullable=False),
        *_provenance_columns(),
        sa.CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_player_consistency_snapshot_completeness",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.player_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id", "season", "season_type", "stat_name", "window_size",
            "feature_as_of", "calculation_version",
            name="uq_player_consistency_snapshot_natural_key",
        ),
    )
    op.create_index(
        "idx_player_consistency_snapshot_latest",
        "player_consistency_snapshots",
        ["season", "season_type", "calculation_version", "completeness_status", "feature_as_of"],
    )
    op.create_index(
        "idx_player_consistency_snapshot_player",
        "player_consistency_snapshots",
        ["player_id", "feature_as_of"],
    )


def downgrade():
    for table, indexes in (
        ("player_consistency_snapshots", ["idx_player_consistency_snapshot_player", "idx_player_consistency_snapshot_latest"]),
        ("player_heat_index_snapshots", ["idx_player_heat_snapshot_player", "idx_player_heat_snapshot_latest"]),
        ("player_stat_window_snapshots", ["idx_player_window_snapshot_player", "idx_player_window_snapshot_latest"]),
        ("player_consecutive_streak_snapshots", ["idx_player_streak_snapshot_player", "idx_player_streak_snapshot_latest"]),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
