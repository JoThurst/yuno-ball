"""Add source-specific Kaggle team-game staging.

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-07-16 03:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stg_kaggle_games",
        sa.Column("staging_row_id", sa.String(length=36), nullable=False),
        sa.Column("source_import_id", sa.String(length=36), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("source_dataset_version", sa.String(length=128), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("row_sha256", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=20), nullable=False),
        sa.Column("game_date_raw", sa.String(length=32), nullable=True),
        sa.Column("game_date", sa.Date(), nullable=True),
        sa.Column("matchup", sa.Text(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("is_home", sa.Boolean(), nullable=False),
        sa.Column("wl", sa.String(length=1), nullable=True),
        sa.Column("wins_to_date", sa.Integer(), nullable=True),
        sa.Column("losses_to_date", sa.Integer(), nullable=True),
        sa.Column("win_pct_to_date", sa.Numeric(precision=8, scale=5), nullable=True),
        sa.Column("minutes", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("fgm", sa.Integer(), nullable=True),
        sa.Column("fga", sa.Integer(), nullable=True),
        sa.Column("fg_pct", sa.Numeric(precision=8, scale=5), nullable=True),
        sa.Column("fg3m", sa.Integer(), nullable=True),
        sa.Column("fg3a", sa.Integer(), nullable=True),
        sa.Column("fg3_pct", sa.Numeric(precision=8, scale=5), nullable=True),
        sa.Column("ftm", sa.Integer(), nullable=True),
        sa.Column("fta", sa.Integer(), nullable=True),
        sa.Column("ft_pct", sa.Numeric(precision=8, scale=5), nullable=True),
        sa.Column("oreb", sa.Integer(), nullable=True),
        sa.Column("dreb", sa.Integer(), nullable=True),
        sa.Column("reb", sa.Integer(), nullable=True),
        sa.Column("ast", sa.Integer(), nullable=True),
        sa.Column("stl", sa.Integer(), nullable=True),
        sa.Column("blk", sa.Integer(), nullable=True),
        sa.Column("tov", sa.Integer(), nullable=True),
        sa.Column("pf", sa.Integer(), nullable=True),
        sa.Column("pts", sa.Integer(), nullable=True),
        sa.Column("opponent_team_id", sa.BigInteger(), nullable=False),
        sa.Column("season_start_year", sa.Integer(), nullable=False),
        sa.Column("season_type", sa.String(length=32), nullable=False),
        sa.Column("season", sa.String(length=7), nullable=False),
        sa.Column("date_status", sa.String(length=16), nullable=False),
        sa.Column("result_status", sa.String(length=16), nullable=False),
        sa.Column("promotion_eligibility", sa.String(length=40), nullable=False),
        sa.Column("canonical_match_status", sa.String(length=32), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("raw_values", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "source_row_number >= 2",
            name="ck_kaggle_games_source_row",
        ),
        sa.CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_kaggle_games_row_sha256",
        ),
        sa.CheckConstraint(
            "game_id ~ '^[0-9]{10}$'",
            name="ck_kaggle_games_game_id",
        ),
        sa.CheckConstraint(
            "team_id <> opponent_team_id",
            name="ck_kaggle_games_distinct_teams",
        ),
        sa.CheckConstraint(
            "wl IS NULL OR wl IN ('W', 'L')",
            name="ck_kaggle_games_wl",
        ),
        sa.CheckConstraint(
            "season ~ '^[0-9]{4}-[0-9]{2}$'",
            name="ck_kaggle_games_season",
        ),
        sa.CheckConstraint(
            "season_type IN ('Regular Season', 'Playoffs', 'Pre Season', 'All Star')",
            name="ck_kaggle_games_season_type",
        ),
        sa.CheckConstraint(
            "date_status IN ('parsed', 'missing')",
            name="ck_kaggle_games_date_status",
        ),
        sa.CheckConstraint(
            "(game_date IS NULL AND date_status = 'missing') OR "
            "(game_date IS NOT NULL AND date_status = 'parsed')",
            name="ck_kaggle_games_date_value",
        ),
        sa.CheckConstraint(
            "result_status IN ('final', 'missing')",
            name="ck_kaggle_games_result_status",
        ),
        sa.CheckConstraint(
            "(wl IS NULL AND result_status = 'missing') OR "
            "(wl IS NOT NULL AND result_status = 'final')",
            name="ck_kaggle_games_result_value",
        ),
        sa.CheckConstraint(
            "promotion_eligibility IN "
            "('eligible_market_range', 'deferred_pre_2006', "
            "'excluded_incomplete_2018_19', 'excluded_unsupported_event_type', "
            "'excluded_incomplete_result')",
            name="ck_kaggle_games_promotion_eligibility",
        ),
        sa.CheckConstraint(
            "canonical_match_status IN "
            "('not_evaluated', 'matched', 'canonical_missing', 'conflict')",
            name="ck_kaggle_games_canonical_match_status",
        ),
        sa.CheckConstraint(
            "validation_status IN ('staged', 'rejected', 'promoted')",
            name="ck_kaggle_games_validation_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_import_id"],
            ["external_dataset_imports.import_id"],
            name="fk_kaggle_games_source_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_kaggle_games_source_run",
        ),
        sa.PrimaryKeyConstraint("staging_row_id"),
        sa.UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_kaggle_games_source_row",
        ),
        sa.UniqueConstraint(
            "source_import_id",
            "game_id",
            "team_id",
            "parser_version",
            name="uq_kaggle_games_natural_grain",
        ),
    )
    op.create_index(
        "idx_kaggle_games_game_id",
        "stg_kaggle_games",
        ["game_id"],
    )
    op.create_index(
        "idx_kaggle_games_season_type",
        "stg_kaggle_games",
        ["season", "season_type"],
    )
    op.create_index(
        "idx_kaggle_games_import_status",
        "stg_kaggle_games",
        ["source_import_id", "validation_status"],
    )


def downgrade() -> None:
    op.drop_index("idx_kaggle_games_import_status", table_name="stg_kaggle_games")
    op.drop_index("idx_kaggle_games_season_type", table_name="stg_kaggle_games")
    op.drop_index("idx_kaggle_games_game_id", table_name="stg_kaggle_games")
    op.drop_table("stg_kaggle_games")
