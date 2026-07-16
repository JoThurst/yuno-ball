"""Add source-specific Stat Surge availability staging.

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-07-16 02:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stg_statsurge_availability",
        sa.Column("staging_row_id", sa.String(length=36), nullable=False),
        sa.Column("source_import_id", sa.String(length=36), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("source_dataset_version", sa.String(length=128), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("row_sha256", sa.String(length=64), nullable=False),
        sa.Column("reported_player_name", sa.Text(), nullable=False),
        sa.Column("reported_status", sa.String(length=32), nullable=False),
        sa.Column("reported_reason", sa.Text(), nullable=False),
        sa.Column("reported_team_name", sa.Text(), nullable=False),
        sa.Column("matchup_text", sa.String(length=32), nullable=False),
        sa.Column("report_date_raw", sa.String(length=32), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("season", sa.String(length=7), nullable=False),
        sa.Column("source_checkpoint", sa.String(length=32), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_time_precision", sa.String(length=32), nullable=False),
        sa.Column("source_time_confidence", sa.String(length=32), nullable=False),
        sa.Column("resolved_player_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_team_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_game_id", sa.String(length=20), nullable=True),
        sa.Column("identity_status", sa.String(length=32), nullable=False),
        sa.Column("cutoff_status", sa.String(length=32), nullable=False),
        sa.Column("completeness_status", sa.String(length=32), nullable=False),
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
            name="ck_statsurge_availability_source_row",
        ),
        sa.CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_statsurge_availability_row_sha256",
        ),
        sa.CheckConstraint(
            "reported_status IN "
            "('Available', 'Probable', 'Questionable', 'Doubtful', 'Out')",
            name="ck_statsurge_availability_status",
        ),
        sa.CheckConstraint(
            "season ~ '^[0-9]{4}-[0-9]{2}$'",
            name="ck_statsurge_availability_season",
        ),
        sa.CheckConstraint(
            "source_checkpoint = 'daily_2pm_report'",
            name="ck_statsurge_availability_checkpoint",
        ),
        sa.CheckConstraint(
            "source_published_at IS NULL",
            name="ck_statsurge_availability_no_published_at",
        ),
        sa.CheckConstraint(
            "source_time_precision = 'report_checkpoint'",
            name="ck_statsurge_availability_time_precision",
        ),
        sa.CheckConstraint(
            "source_time_confidence = 'methodology_level'",
            name="ck_statsurge_availability_time_confidence",
        ),
        sa.CheckConstraint(
            "identity_status IN ('unresolved', 'partial', 'resolved', 'conflict')",
            name="ck_statsurge_availability_identity_status",
        ),
        sa.CheckConstraint(
            "cutoff_status IN ('not_evaluated', 'pregame', 'after_cutoff', 'unknown')",
            name="ck_statsurge_availability_cutoff_status",
        ),
        sa.CheckConstraint(
            "completeness_status IN "
            "('identity_unresolved', 'partial', 'complete', 'quarantined')",
            name="ck_statsurge_availability_completeness",
        ),
        sa.CheckConstraint(
            "validation_status IN ('staged', 'rejected', 'promoted')",
            name="ck_statsurge_availability_validation_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_import_id"],
            ["external_dataset_imports.import_id"],
            name="fk_statsurge_availability_source_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_statsurge_availability_source_run",
        ),
        sa.PrimaryKeyConstraint("staging_row_id"),
        sa.UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_statsurge_availability_source_row",
        ),
        sa.UniqueConstraint(
            "source_import_id",
            "source_dataset_version",
            "report_date",
            "matchup_text",
            "reported_team_name",
            "reported_player_name",
            "parser_version",
            name="uq_statsurge_availability_natural_grain",
        ),
    )
    op.create_index(
        "idx_statsurge_availability_date_team",
        "stg_statsurge_availability",
        ["report_date", "reported_team_name"],
    )
    op.create_index(
        "idx_statsurge_availability_import_status",
        "stg_statsurge_availability",
        ["source_import_id", "validation_status"],
    )

    op.create_table(
        "external_row_rejections",
        sa.Column("rejection_id", sa.String(length=36), nullable=False),
        sa.Column("source_import_id", sa.String(length=36), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("row_sha256", sa.String(length=64), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column("raw_values", JSONB(), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "source_row_number >= 2",
            name="ck_external_row_rejection_source_row",
        ),
        sa.CheckConstraint(
            "row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_external_row_rejection_sha256",
        ),
        sa.ForeignKeyConstraint(
            ["source_import_id"],
            ["external_dataset_imports.import_id"],
            name="fk_external_row_rejection_source_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_external_row_rejection_source_run",
        ),
        sa.PrimaryKeyConstraint("rejection_id"),
        sa.UniqueConstraint(
            "source_import_id",
            "source_row_number",
            "parser_version",
            name="uq_external_row_rejection_source_row",
        ),
    )
    op.create_index(
        "idx_external_row_rejection_import_reason",
        "external_row_rejections",
        ["source_import_id", "reason_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_external_row_rejection_import_reason",
        table_name="external_row_rejections",
    )
    op.drop_table("external_row_rejections")
    op.drop_index(
        "idx_statsurge_availability_import_status",
        table_name="stg_statsurge_availability",
    )
    op.drop_index(
        "idx_statsurge_availability_date_team",
        table_name="stg_statsurge_availability",
    )
    op.drop_table("stg_statsurge_availability")
