"""Add durable ingestion run and task tracking.

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-07-15 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("parent_run_id", sa.String(length=36), nullable=True),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("season", sa.String(length=7), nullable=True),
        sa.Column("season_type", sa.String(length=32), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("feature_cutoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_read", sa.Integer(), nullable=True),
        sa.Column("rows_written", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("code_version", sa.String(length=128), nullable=True),
        sa.Column("calculation_version", sa.String(length=128), nullable=True),
        sa.Column("error_class", sa.String(length=255), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')",
            name="ck_ingestion_runs_status",
        ),
        sa.CheckConstraint(
            "validation_status IN ('not_run', 'passed', 'failed', 'skipped')",
            name="ck_ingestion_runs_validation_status",
        ),
        sa.ForeignKeyConstraint(["parent_run_id"], ["ingestion_runs.run_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("idx_ingestion_runs_started_at", "ingestion_runs", ["started_at"])
    op.create_index("idx_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index(
        "idx_ingestion_runs_season_date",
        "ingestion_runs",
        ["season", "target_date"],
    )

    op.create_table(
        "ingestion_task_runs",
        sa.Column("task_run_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_read", sa.Integer(), nullable=True),
        sa.Column("rows_written", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("error_class", sa.String(length=255), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'skipped', 'failed')",
            name="ck_ingestion_task_runs_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_run_id"),
        sa.UniqueConstraint("run_id", "task_name", name="uq_ingestion_task_run_name"),
    )
    op.create_index(
        "idx_ingestion_task_runs_run_status",
        "ingestion_task_runs",
        ["run_id", "status"],
    )
    op.create_index(
        "idx_ingestion_task_runs_source",
        "ingestion_task_runs",
        ["source"],
    )


def downgrade():
    op.drop_index("idx_ingestion_task_runs_source", table_name="ingestion_task_runs")
    op.drop_index("idx_ingestion_task_runs_run_status", table_name="ingestion_task_runs")
    op.drop_table("ingestion_task_runs")
    op.drop_index("idx_ingestion_runs_season_date", table_name="ingestion_runs")
    op.drop_index("idx_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index("idx_ingestion_runs_started_at", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
