"""Add a nullable, pair-derived team-game plus/minus field."""

from alembic import op
import sqlalchemy as sa


revision = "h4i5j6k7l8"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "team_game_stats",
        sa.Column(
            "plus_minus",
            sa.Integer(),
            nullable=True,
            comment=(
                "Derived team points minus reciprocal opponent points; "
                "NULL when the exact pair is incomplete"
            ),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE team_game_stats AS team
               SET plus_minus = team.pts - opponent.pts
              FROM team_game_stats AS opponent
             WHERE opponent.game_id = team.game_id
               AND opponent.team_id = team.opponent_team_id
               AND opponent.opponent_team_id = team.team_id
               AND team.team_id <> opponent.team_id
               AND team.pts IS NOT NULL
               AND opponent.pts IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("team_game_stats", "plus_minus")
