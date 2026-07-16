"""Expand market pair-status columns for explicit selection semantics.

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-07-16 05:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name, constraint_name, base_value in (
        (
            "stg_kaggle_spreads",
            "ck_kaggle_spreads_line_pair_status",
            "inverse",
        ),
        (
            "stg_kaggle_totals",
            "ck_kaggle_totals_line_pair_status",
            "same",
        ),
    ):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.alter_column(
            table_name,
            "line_pair_status",
            existing_type=sa.String(length=16),
            type_=sa.String(length=24),
            existing_nullable=False,
        )
        op.execute(
            sa.text(
                f"UPDATE {table_name} SET line_pair_status = "
                "'selection_specific' WHERE line_pair_status = 'selection_pair'"
            )
        )
        op.create_check_constraint(
            constraint_name,
            table_name,
            f"line_pair_status IN ('{base_value}', 'selection_specific')",
        )


def downgrade() -> None:
    for table_name, constraint_name, base_value in (
        (
            "stg_kaggle_totals",
            "ck_kaggle_totals_line_pair_status",
            "same",
        ),
        (
            "stg_kaggle_spreads",
            "ck_kaggle_spreads_line_pair_status",
            "inverse",
        ),
    ):
        op.drop_constraint(constraint_name, table_name, type_="check")
        op.execute(
            sa.text(
                f"UPDATE {table_name} SET line_pair_status = "
                "'selection_pair' WHERE line_pair_status = 'selection_specific'"
            )
        )
        op.alter_column(
            table_name,
            "line_pair_status",
            existing_type=sa.String(length=24),
            type_=sa.String(length=16),
            existing_nullable=False,
        )
        op.create_check_constraint(
            constraint_name,
            table_name,
            f"line_pair_status IN ('{base_value}', 'selection_pair')",
        )
