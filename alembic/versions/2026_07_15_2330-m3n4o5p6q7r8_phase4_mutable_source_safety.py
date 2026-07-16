"""Phase 4 mutable-source safety and canonical roster seasons.

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-07-15 23:30:00
"""

from alembic import op


revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove a legacy four-digit duplicate only when its canonical row already
    # exists, then convert every remaining legacy season in place.
    op.execute(
        """
        DELETE FROM roster AS legacy
        USING roster AS canonical
        WHERE legacy.season ~ '^[0-9]{4}$'
          AND canonical.team_id = legacy.team_id
          AND canonical.player_id = legacy.player_id
          AND canonical.season = legacy.season || '-' ||
              lpad(((legacy.season::integer + 1) % 100)::text, 2, '0')
        """
    )
    op.execute(
        """
        UPDATE roster
        SET season = season || '-' ||
            lpad(((season::integer + 1) % 100)::text, 2, '0')
        WHERE season ~ '^[0-9]{4}$'
        """
    )

    op.create_check_constraint(
        "ck_roster_season_canonical",
        "roster",
        "season ~ '^[0-9]{4}-[0-9]{2}$'",
    )
    op.create_check_constraint(
        "ck_gamelogs_season_canonical",
        "gamelogs",
        "season ~ '^[0-9]{4}-[0-9]{2}$'",
    )
    op.create_foreign_key(
        "fk_gamelogs_player",
        "gamelogs",
        "players",
        ["player_id"],
        ["player_id"],
    )
    op.create_foreign_key(
        "fk_gamelogs_game_schedule",
        "gamelogs",
        "game_schedule",
        ["game_id", "team_id"],
        ["game_id", "team_id"],
        ondelete="CASCADE",
    )
    op.create_primary_key("player_z_scores_pkey", "player_z_scores", ["player_id"])
    op.execute(
        "COMMENT ON TABLE player_z_scores IS "
        "'Deprecated read-only legacy data; use player_heat_index_snapshots'"
    )


def downgrade() -> None:
    op.execute("COMMENT ON TABLE player_z_scores IS NULL")
    op.drop_constraint("player_z_scores_pkey", "player_z_scores", type_="primary")
    op.drop_constraint("fk_gamelogs_game_schedule", "gamelogs", type_="foreignkey")
    op.drop_constraint("fk_gamelogs_player", "gamelogs", type_="foreignkey")
    op.drop_constraint("ck_gamelogs_season_canonical", "gamelogs", type_="check")
    op.drop_constraint("ck_roster_season_canonical", "roster", type_="check")
    # Canonical season values are intentionally retained during downgrade.
