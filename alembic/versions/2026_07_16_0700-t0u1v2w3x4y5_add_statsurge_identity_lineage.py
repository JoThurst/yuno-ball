"""Add durable Stat Surge identity-resolution lineage.

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-07-16 07:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stg_statsurge_availability",
        sa.Column("identity_resolution_version", sa.String(64), nullable=True),
    )
    op.add_column(
        "stg_statsurge_availability",
        sa.Column("identity_resolution_run_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "stg_statsurge_availability",
        sa.Column("identity_resolution_details", JSONB(), nullable=True),
    )
    op.create_foreign_key(
        "fk_statsurge_availability_identity_run",
        "stg_statsurge_availability",
        "ingestion_runs",
        ["identity_resolution_run_id"],
        ["run_id"],
    )
    op.create_check_constraint(
        "ck_statsurge_availability_resolution_lineage",
        "stg_statsurge_availability",
        "identity_resolution_version IS NULL OR "
        "(identity_resolution_run_id IS NOT NULL AND "
        "identity_resolution_details IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_statsurge_availability_resolution_lineage",
        "stg_statsurge_availability",
        type_="check",
    )
    op.drop_constraint(
        "fk_statsurge_availability_identity_run",
        "stg_statsurge_availability",
        type_="foreignkey",
    )
    op.drop_column("stg_statsurge_availability", "identity_resolution_details")
    op.drop_column("stg_statsurge_availability", "identity_resolution_run_id")
    op.drop_column("stg_statsurge_availability", "identity_resolution_version")
