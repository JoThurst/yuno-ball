"""Preserve the official report's raw game-time text."""

from alembic import op
import sqlalchemy as sa


revision = "z6a7b8c9d0e1"
down_revision = "y5z6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "availability_observations",
        sa.Column("reported_game_time_text", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "team_report_submission_status",
        sa.Column("reported_game_time_text", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("team_report_submission_status", "reported_game_time_text")
    op.drop_column("availability_observations", "reported_game_time_text")
