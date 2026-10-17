"""Add append-only market observation headers and selections."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "c9d0e1f2g3h4"
down_revision = "b8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_observation_headers",
        sa.Column("observation_id", sa.String(36), primary_key=True),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("source_observation_key", sa.String(255), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("snapshot_type", sa.String(32), nullable=False),
        sa.Column("timing_precision", sa.String(16), nullable=False),
        sa.Column("market_type", sa.String(16), nullable=False),
        sa.Column("source_import_id", sa.String(36), nullable=True),
        sa.Column("source_run_id", sa.String(36), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=True),
        sa.Column("source_game_id", sa.String(64), nullable=False),
        sa.Column("canonical_game_id", sa.String(32), nullable=False),
        sa.Column("source_row_sha256", sa.String(64), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("season", sa.String(10), nullable=False),
        sa.Column("season_type", sa.String(32), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("sportsbook_id", sa.String(64), nullable=False),
        sa.Column("sportsbook_name", sa.Text(), nullable=True),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "market_type IN ('moneyline', 'spread', 'total')",
            name="ck_market_observation_market_type",
        ),
        sa.CheckConstraint(
            "snapshot_type IN ('historical_static', 'forward')",
            name="ck_market_observation_snapshot_type",
        ),
        sa.CheckConstraint(
            "timing_precision IN ('unknown', 'date', 'minute', 'second')",
            name="ck_market_observation_timing_precision",
        ),
        sa.CheckConstraint(
            "source_row_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_market_observation_sha256",
        ),
        sa.CheckConstraint(
            "home_team_id <> away_team_id",
            name="ck_market_observation_distinct_teams",
        ),
        sa.ForeignKeyConstraint(["source_import_id"], ["external_dataset_imports.import_id"]),
        sa.ForeignKeyConstraint(["source_run_id"], ["ingestion_runs.run_id"]),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.team_id"]),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.team_id"]),
        sa.UniqueConstraint(
            "source_name",
            "source_observation_key",
            "parser_version",
            name="uq_market_observation_source_key",
        ),
    )
    op.create_index(
        "idx_market_observation_game_time",
        "market_observation_headers",
        ["canonical_game_id", "observed_at"],
    )
    op.create_index(
        "idx_market_observation_as_of",
        "market_observation_headers",
        ["canonical_game_id", "data_available_at"],
    )
    op.create_index(
        "idx_market_observation_market",
        "market_observation_headers",
        ["market_type", "snapshot_type"],
    )
    op.create_index(
        "idx_market_observation_source_run",
        "market_observation_headers",
        ["source_run_id"],
    )

    op.create_table(
        "market_observation_selections",
        sa.Column("selection_id", sa.String(36), primary_key=True),
        sa.Column("observation_id", sa.String(36), nullable=False),
        sa.Column("selection_key", sa.String(16), nullable=False),
        sa.Column("selection_label", sa.Text(), nullable=False),
        sa.Column("selection_team_id", sa.Integer(), nullable=True),
        sa.Column("line_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("price_american", sa.Integer(), nullable=True),
        sa.Column("price_decimal", sa.Numeric(12, 6), nullable=True),
        sa.Column("pair_status", sa.String(24), nullable=False),
        sa.Column("raw_selection", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "selection_key IN ('home', 'away', 'over', 'under')",
            name="ck_market_selection_key",
        ),
        sa.CheckConstraint(
            "pair_status IN ('inverse', 'selection_specific', 'not_applicable', 'unknown')",
            name="ck_market_selection_pair_status",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["market_observation_headers.observation_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["selection_team_id"], ["teams.team_id"]),
        sa.UniqueConstraint(
            "observation_id",
            "selection_key",
            name="uq_market_selection_observation_key",
        ),
    )
    op.create_index(
        "idx_market_selection_team",
        "market_observation_selections",
        ["selection_team_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_market_selection_team", table_name="market_observation_selections")
    op.drop_table("market_observation_selections")
    op.drop_index("idx_market_observation_source_run", table_name="market_observation_headers")
    op.drop_index("idx_market_observation_market", table_name="market_observation_headers")
    op.drop_index("idx_market_observation_as_of", table_name="market_observation_headers")
    op.drop_index("idx_market_observation_game_time", table_name="market_observation_headers")
    op.drop_table("market_observation_headers")
