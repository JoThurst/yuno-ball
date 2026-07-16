"""Reconcile intentional schema metadata and remove unused indexes.

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-07-15 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    orphan_count = bind.scalar(
        sa.text(
            """
            SELECT COUNT(*)
            FROM team_schedule_factors AS tsf
            LEFT JOIN game_schedule AS gs
              ON gs.game_id = tsf.game_id
             AND gs.team_id = tsf.team_id
            WHERE gs.game_id IS NULL
            """
        )
    )
    if orphan_count:
        raise RuntimeError(
            "Cannot add team_schedule_factors schedule foreign key: "
            f"found {orphan_count} orphan row(s)"
        )

    op.drop_index("idx_team_game_stats_oreb", table_name="team_game_stats")
    op.drop_index("idx_team_game_stats_dreb", table_name="team_game_stats")
    op.drop_index("idx_team_game_stats_wl", table_name="team_game_stats")

    op.create_foreign_key(
        "fk_team_schedule_factors_game_schedule",
        "team_schedule_factors",
        "game_schedule",
        ["game_id", "team_id"],
        ["game_id", "team_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_team_schedule_factors_game_schedule",
        "team_schedule_factors",
        type_="foreignkey",
    )

    op.create_index(
        "idx_team_game_stats_oreb", "team_game_stats", ["oreb"]
    )
    op.create_index(
        "idx_team_game_stats_dreb", "team_game_stats", ["dreb"]
    )
    op.create_index("idx_team_game_stats_wl", "team_game_stats", ["wl"])
