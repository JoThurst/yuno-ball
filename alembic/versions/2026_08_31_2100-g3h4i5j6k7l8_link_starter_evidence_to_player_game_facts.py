"""Link canonical starter projections to immutable starter evidence."""

from alembic import op
import sqlalchemy as sa


revision = "g3h4i5j6k7l8"
down_revision = "f2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "player_game_facts",
        sa.Column("starter_position", sa.String(8), nullable=True),
    )
    op.add_column(
        "player_game_facts",
        sa.Column("starter_evidence_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_player_game_fact_starter_evidence",
        "player_game_facts",
        "player_game_starter_evidence",
        ["starter_evidence_id"],
        ["evidence_id"],
    )
    op.create_index(
        "idx_player_game_fact_starter_evidence",
        "player_game_facts",
        ["starter_evidence_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_player_game_fact_starter_evidence",
        table_name="player_game_facts",
    )
    op.drop_constraint(
        "fk_player_game_fact_starter_evidence",
        "player_game_facts",
        type_="foreignkey",
    )
    op.drop_column("player_game_facts", "starter_evidence_id")
    op.drop_column("player_game_facts", "starter_position")
