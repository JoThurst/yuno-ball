"""Add immutable and canonical Advanced V3 player-game facts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "e1f2g3h4i5j6"
down_revision = "d0e1f2g3h4i5"
branch_labels = None
depends_on = None


ADVANCED_COLUMNS = (
    "estimated_offensive_rating",
    "offensive_rating",
    "estimated_defensive_rating",
    "defensive_rating",
    "estimated_net_rating",
    "net_rating",
    "assist_percentage",
    "assist_to_turnover",
    "assist_ratio",
    "offensive_rebound_percentage",
    "defensive_rebound_percentage",
    "rebound_percentage",
    "turnover_ratio",
    "effective_field_goal_percentage",
    "true_shooting_percentage",
    "usage_percentage",
    "estimated_usage_percentage",
    "estimated_pace",
    "pace",
    "pace_per_40",
    "possessions",
    "pie",
)


def advanced_columns():
    return [
        sa.Column("minutes", sa.String(16), nullable=True),
        *(sa.Column(name, sa.Numeric(12, 6), nullable=True) for name in ADVANCED_COLUMNS),
    ]


def upgrade() -> None:
    op.create_table(
        "player_game_advanced_fact_revisions",
        sa.Column("revision_id", sa.String(36), primary_key=True),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("source_row_key", sa.String(255), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("source_game_id", sa.String(32), nullable=False),
        sa.Column("source_player_id", sa.BigInteger(), nullable=False),
        sa.Column("source_team_id", sa.Integer(), nullable=False),
        sa.Column("canonical_game_id", sa.String(32), nullable=True),
        sa.Column("canonical_player_id", sa.BigInteger(), nullable=True),
        sa.Column("canonical_team_id", sa.Integer(), nullable=True),
        sa.Column("source_row_sha256", sa.String(64), nullable=False),
        sa.Column("source_run_id", sa.String(36), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("season_type", sa.String(32), nullable=False),
        sa.Column("completeness_status", sa.String(16), nullable=False),
        sa.Column("participation_status", sa.String(16), nullable=False),
        *advanced_columns(),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source_row_sha256 ~ '^[0-9a-f]{64}$'", name="ck_player_game_advanced_revision_sha256"),
        sa.CheckConstraint("completeness_status IN ('complete', 'partial')", name="ck_player_game_advanced_revision_completeness"),
        sa.CheckConstraint("participation_status IN ('played', 'did_not_play', 'unknown')", name="ck_player_game_advanced_revision_participation"),
        sa.ForeignKeyConstraint(["canonical_player_id"], ["players.player_id"]),
        sa.ForeignKeyConstraint(["canonical_team_id"], ["teams.team_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.UniqueConstraint("source_name", "source_row_key", "parser_version", name="uq_player_game_advanced_revision_source_row"),
    )
    op.create_index("idx_player_game_advanced_revision_game", "player_game_advanced_fact_revisions", ["canonical_game_id"])
    op.create_index("idx_player_game_advanced_revision_player", "player_game_advanced_fact_revisions", ["canonical_player_id"])
    op.create_index("idx_player_game_advanced_revision_run", "player_game_advanced_fact_revisions", ["source_run_id"])

    op.create_table(
        "player_game_advanced_facts",
        sa.Column("fact_id", sa.String(36), primary_key=True),
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.Column("canonical_game_id", sa.String(32), nullable=False),
        sa.Column("canonical_player_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_team_id", sa.Integer(), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("season_type", sa.String(32), nullable=False),
        sa.Column("completeness_status", sa.String(16), nullable=False),
        sa.Column("participation_status", sa.String(16), nullable=False),
        *advanced_columns(),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("source_row_sha256", sa.String(64), nullable=False),
        sa.Column("source_run_id", sa.String(36), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("participation_status IN ('played', 'did_not_play', 'unknown')", name="ck_player_game_advanced_fact_participation"),
        sa.ForeignKeyConstraint(["revision_id"], ["player_game_advanced_fact_revisions.revision_id"]),
        sa.ForeignKeyConstraint(["canonical_game_id", "canonical_team_id"], ["game_schedule.game_id", "game_schedule.team_id"], name="fk_player_game_advanced_fact_schedule"),
        sa.ForeignKeyConstraint(["canonical_player_id"], ["players.player_id"]),
        sa.ForeignKeyConstraint(["canonical_team_id"], ["teams.team_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.UniqueConstraint("canonical_game_id", "canonical_player_id", "canonical_team_id", name="uq_player_game_advanced_fact_canonical_grain"),
    )
    op.create_index("idx_player_game_advanced_fact_player_date", "player_game_advanced_facts", ["canonical_player_id", "game_date"])
    op.create_index("idx_player_game_advanced_fact_game", "player_game_advanced_facts", ["canonical_game_id"])


def downgrade() -> None:
    op.drop_index("idx_player_game_advanced_fact_game", table_name="player_game_advanced_facts")
    op.drop_index("idx_player_game_advanced_fact_player_date", table_name="player_game_advanced_facts")
    op.drop_table("player_game_advanced_facts")
    op.drop_index("idx_player_game_advanced_revision_run", table_name="player_game_advanced_fact_revisions")
    op.drop_index("idx_player_game_advanced_revision_player", table_name="player_game_advanced_fact_revisions")
    op.drop_index("idx_player_game_advanced_revision_game", table_name="player_game_advanced_fact_revisions")
    op.drop_table("player_game_advanced_fact_revisions")
