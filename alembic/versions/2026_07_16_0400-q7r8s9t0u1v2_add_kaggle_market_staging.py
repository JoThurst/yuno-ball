"""Add atomic Kaggle moneyline, spread, and totals staging.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-07-16 04:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("staging_row_id", sa.String(length=36), nullable=False),
        sa.Column("source_import_id", sa.String(length=36), nullable=False),
        sa.Column("source_game_import_id", sa.String(length=36), nullable=False),
        sa.Column("source_game_parser_version", sa.String(length=64), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("source_dataset_version", sa.String(length=128), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("row_sha256", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=20), nullable=False),
        sa.Column("book_name", sa.Text(), nullable=False),
        sa.Column("book_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("opponent_team_id", sa.BigInteger(), nullable=False),
        sa.Column("timing_precision", sa.String(length=16), nullable=False),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
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
    ]


def _common_constraints(prefix: str, natural_name: str) -> list[sa.Constraint]:
    return [
        sa.CheckConstraint(
            "source_row_number >= 2", name=f"ck_{prefix}_source_row"
        ),
        sa.CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'", name=f"ck_{prefix}_row_sha256"
        ),
        sa.CheckConstraint(
            "game_id ~ '^[0-9]{10}$'", name=f"ck_{prefix}_game_id"
        ),
        sa.CheckConstraint(
            "team_id <> opponent_team_id", name=f"ck_{prefix}_distinct_teams"
        ),
        sa.CheckConstraint(
            "timing_precision = 'unknown'", name=f"ck_{prefix}_timing_precision"
        ),
        sa.CheckConstraint(
            "snapshot_type = 'historical_static'", name=f"ck_{prefix}_snapshot_type"
        ),
        sa.CheckConstraint(
            "canonical_match_status IN "
            "('not_evaluated', 'matched', 'canonical_missing', 'conflict')",
            name=f"ck_{prefix}_canonical_match_status",
        ),
        sa.CheckConstraint(
            "validation_status IN ('staged', 'rejected', 'promoted')",
            name=f"ck_{prefix}_validation_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_import_id"],
            ["external_dataset_imports.import_id"],
            name=f"fk_{prefix}_source_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
            name=f"fk_{prefix}_source_run",
        ),
        sa.ForeignKeyConstraint(
            [
                "source_game_import_id",
                "game_id",
                "team_id",
                "source_game_parser_version",
            ],
            [
                "stg_kaggle_games.source_import_id",
                "stg_kaggle_games.game_id",
                "stg_kaggle_games.team_id",
                "stg_kaggle_games.parser_version",
            ],
            name=f"fk_{prefix}_source_game",
        ),
        sa.PrimaryKeyConstraint("staging_row_id"),
        sa.UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name=f"uq_{prefix}_source_row",
        ),
        sa.UniqueConstraint(
            "source_import_id",
            "game_id",
            "book_id",
            "team_id",
            "opponent_team_id",
            "parser_version",
            name=natural_name,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "stg_kaggle_moneylines",
        *_common_columns(),
        sa.Column("team_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "opponent_price", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        *_common_constraints(
            "kaggle_moneylines", "uq_kaggle_moneylines_natural_grain"
        ),
    )
    op.create_index(
        "idx_kaggle_moneylines_game_book",
        "stg_kaggle_moneylines",
        ["game_id", "book_id"],
    )

    op.create_table(
        "stg_kaggle_spreads",
        *_common_columns(),
        sa.Column("team_spread", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "opponent_spread", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("team_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "opponent_price", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("line_pair_status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "line_pair_status IN ('inverse', 'selection_pair')",
            name="ck_kaggle_spreads_line_pair_status",
        ),
        *_common_constraints("kaggle_spreads", "uq_kaggle_spreads_natural_grain"),
    )
    op.create_index(
        "idx_kaggle_spreads_game_book",
        "stg_kaggle_spreads",
        ["game_id", "book_id"],
    )

    op.create_table(
        "stg_kaggle_totals",
        *_common_columns(),
        sa.Column("over_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("under_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("over_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("under_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("line_pair_status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "line_pair_status IN ('same', 'selection_pair')",
            name="ck_kaggle_totals_line_pair_status",
        ),
        *_common_constraints("kaggle_totals", "uq_kaggle_totals_natural_grain"),
    )
    op.create_index(
        "idx_kaggle_totals_game_book",
        "stg_kaggle_totals",
        ["game_id", "book_id"],
    )

    op.create_table(
        "external_market_anomalies",
        sa.Column("anomaly_id", sa.String(length=36), nullable=False),
        sa.Column("source_import_id", sa.String(length=36), nullable=False),
        sa.Column("source_game_import_id", sa.String(length=36), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("row_sha256", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=20), nullable=True),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("reason_detail", sa.Text(), nullable=False),
        sa.Column("raw_values", JSONB(), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "source_row_number >= 2", name="ck_external_market_anomaly_source_row"
        ),
        sa.CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_external_market_anomaly_sha256",
        ),
        sa.CheckConstraint(
            "market IN ('moneyline', 'spread', 'total')",
            name="ck_external_market_anomaly_market",
        ),
        sa.ForeignKeyConstraint(
            ["source_import_id"],
            ["external_dataset_imports.import_id"],
            name="fk_external_market_anomaly_source_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_game_import_id"],
            ["external_dataset_imports.import_id"],
            name="fk_external_market_anomaly_game_import",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_external_market_anomaly_source_run",
        ),
        sa.PrimaryKeyConstraint("anomaly_id"),
        sa.UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_external_market_anomaly_source_row",
        ),
    )
    op.create_index(
        "idx_external_market_anomaly_import_reason",
        "external_market_anomalies",
        ["source_import_id", "reason_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_external_market_anomaly_import_reason",
        table_name="external_market_anomalies",
    )
    op.drop_table("external_market_anomalies")
    op.drop_index("idx_kaggle_totals_game_book", table_name="stg_kaggle_totals")
    op.drop_table("stg_kaggle_totals")
    op.drop_index("idx_kaggle_spreads_game_book", table_name="stg_kaggle_spreads")
    op.drop_table("stg_kaggle_spreads")
    op.drop_index(
        "idx_kaggle_moneylines_game_book", table_name="stg_kaggle_moneylines"
    )
    op.drop_table("stg_kaggle_moneylines")
