"""Add versioned identity-resolution lineage to official observations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "b8c9d0e1f2g3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def _add_lineage(table: str, prefix: str) -> None:
    op.add_column(table, sa.Column("identity_resolution_version", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("identity_resolution_run_id", sa.String(36), nullable=True))
    op.add_column(table, sa.Column("identity_resolution_details", JSONB(), nullable=True))
    op.create_foreign_key(
        f"fk_{prefix}_identity_run",
        table,
        "ingestion_runs",
        ["identity_resolution_run_id"],
        ["run_id"],
    )
    op.create_check_constraint(
        f"ck_{prefix}_resolution_lineage",
        table,
        "identity_resolution_version IS NULL OR "
        "(identity_resolution_run_id IS NOT NULL AND "
        "identity_resolution_details IS NOT NULL)",
    )


def upgrade() -> None:
    _add_lineage("availability_observations", "availability_observation")
    _add_lineage("team_report_submission_status", "team_report_submission")


def _drop_lineage(table: str, prefix: str) -> None:
    op.drop_constraint(f"ck_{prefix}_resolution_lineage", table, type_="check")
    op.drop_constraint(f"fk_{prefix}_identity_run", table, type_="foreignkey")
    op.drop_column(table, "identity_resolution_details")
    op.drop_column(table, "identity_resolution_run_id")
    op.drop_column(table, "identity_resolution_version")


def downgrade() -> None:
    _drop_lineage("team_report_submission_status", "team_report_submission")
    _drop_lineage("availability_observations", "availability_observation")
