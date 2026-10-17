"""Add immutable player-game starter evidence."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "f2g3h4i5j6k7"
down_revision = "e1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_game_starter_evidence",
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("source_row_key", sa.String(255), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("source_game_id", sa.String(32), nullable=False),
        sa.Column("source_player_id", sa.BigInteger(), nullable=False),
        sa.Column("source_team_id", sa.Integer(), nullable=False),
        sa.Column("canonical_game_id", sa.String(32), nullable=True),
        sa.Column("canonical_player_id", sa.BigInteger(), nullable=True),
        sa.Column("canonical_team_id", sa.Integer(), nullable=True),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("season_type", sa.String(32), nullable=False),
        sa.Column("starter_status", sa.String(16), nullable=False),
        sa.Column("start_position", sa.String(8), nullable=True),
        sa.Column("source_row_sha256", sa.String(64), nullable=False),
        sa.Column("source_response_sha256", sa.String(64), nullable=False),
        sa.Column("source_run_id", sa.String(36), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "starter_status IN ('starter', 'unknown')",
            name="ck_player_game_starter_evidence_status",
        ),
        sa.CheckConstraint(
            "source_row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_starter_evidence_row_sha256",
        ),
        sa.CheckConstraint(
            "source_response_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_player_game_starter_evidence_response_sha256",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_game_id", "canonical_team_id"],
            ["game_schedule.game_id", "game_schedule.team_id"],
            name="fk_player_game_starter_evidence_schedule",
        ),
        sa.ForeignKeyConstraint(["canonical_player_id"], ["players.player_id"]),
        sa.ForeignKeyConstraint(["canonical_team_id"], ["teams.team_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.UniqueConstraint(
            "source_name",
            "source_row_key",
            "parser_version",
            name="uq_player_game_starter_evidence_source_row",
        ),
    )
    op.create_index(
        "idx_player_game_starter_evidence_game",
        "player_game_starter_evidence",
        ["canonical_game_id"],
    )
    op.create_index(
        "idx_player_game_starter_evidence_player",
        "player_game_starter_evidence",
        ["canonical_player_id"],
    )
    op.create_index(
        "idx_player_game_starter_evidence_date",
        "player_game_starter_evidence",
        ["game_date"],
    )
    op.create_index(
        "idx_player_game_starter_evidence_run",
        "player_game_starter_evidence",
        ["source_run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_player_game_starter_evidence_run", table_name="player_game_starter_evidence")
    op.drop_index("idx_player_game_starter_evidence_date", table_name="player_game_starter_evidence")
    op.drop_index("idx_player_game_starter_evidence_player", table_name="player_game_starter_evidence")
    op.drop_index("idx_player_game_starter_evidence_game", table_name="player_game_starter_evidence")
    op.drop_table("player_game_starter_evidence")
