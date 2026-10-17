"""Add derived actual-role history and pregame role bands."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "i5j6k7l8m9n0"
down_revision = "h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_role_history",
        sa.Column("role_history_id", sa.String(36), primary_key=True),
        sa.Column("canonical_game_id", sa.String(32), nullable=False),
        sa.Column("canonical_player_id", sa.BigInteger(), sa.ForeignKey("players.player_id"), nullable=False),
        sa.Column("canonical_team_id", sa.Integer(), sa.ForeignKey("teams.team_id"), nullable=False),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("season_type", sa.String(32), nullable=False),
        sa.Column("participation_status", sa.String(16), nullable=False),
        sa.Column("starter_status", sa.String(16), nullable=False),
        sa.Column("starter_position", sa.String(8), nullable=True),
        sa.Column("minutes", sa.String(16), nullable=True),
        sa.Column("minutes_decimal", sa.Numeric(8, 2), nullable=True),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("source_fact_id", sa.String(36), nullable=False),
        sa.Column("source_row_sha256", sa.String(64), nullable=False),
        sa.Column("source_run_id", sa.String(36), sa.ForeignKey("ingestion_runs.run_id"), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "participation_status IN ('played', 'did_not_play', 'unknown')",
            name="ck_player_role_history_participation",
        ),
        sa.CheckConstraint(
            "starter_status IN ('starter', 'bench', 'unknown')",
            name="ck_player_role_history_starter",
        ),
        sa.CheckConstraint(
            "minutes_decimal IS NULL OR minutes_decimal >= 0",
            name="ck_player_role_history_minutes",
        ),
        sa.UniqueConstraint(
            "canonical_game_id", "canonical_player_id", "canonical_team_id",
            "calculation_version", name="uq_player_role_history_grain",
        ),
    )
    op.create_index(
        "idx_player_role_history_player_date", "player_role_history",
        ["canonical_player_id", "game_date"],
    )
    op.create_index(
        "idx_player_role_history_team_date", "player_role_history",
        ["canonical_team_id", "game_date"],
    )
    op.create_index(
        "idx_player_role_history_season", "player_role_history",
        ["season", "season_type"],
    )

    op.create_table(
        "pregame_player_role_baselines",
        sa.Column("baseline_id", sa.String(36), primary_key=True),
        sa.Column("canonical_game_id", sa.String(32), nullable=False),
        sa.Column("canonical_player_id", sa.BigInteger(), sa.ForeignKey("players.player_id"), nullable=False),
        sa.Column("canonical_team_id", sa.Integer(), sa.ForeignKey("teams.team_id"), nullable=False),
        sa.Column("target_game_date", sa.Date(), nullable=False),
        sa.Column("scheduled_tipoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("season", sa.String(7), nullable=False),
        sa.Column("season_type", sa.String(32), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("history_games_seen", sa.Integer(), nullable=False),
        sa.Column("played_games_used", sa.Integer(), nullable=False),
        sa.Column("start_count", sa.Integer(), nullable=False),
        sa.Column("baseline_minutes_low", sa.Numeric(8, 2), nullable=True),
        sa.Column("baseline_minutes_median", sa.Numeric(8, 2), nullable=True),
        sa.Column("baseline_minutes_high", sa.Numeric(8, 2), nullable=True),
        sa.Column("latest_history_date", sa.Date(), nullable=True),
        sa.Column("completeness_status", sa.String(16), nullable=False),
        sa.Column("confidence_band", sa.String(16), nullable=False),
        sa.Column("timing_policy", sa.String(32), nullable=False),
        sa.Column("feature_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.Column("source_run_id", sa.String(36), sa.ForeignKey("ingestion_runs.run_id"), nullable=False),
        sa.Column("missing_input_flags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "completeness_status IN ('complete', 'partial', 'unknown', 'after_cutoff')",
            name="ck_pregame_role_baseline_completeness",
        ),
        sa.CheckConstraint(
            "confidence_band IN ('high', 'medium', 'low', 'none')",
            name="ck_pregame_role_baseline_confidence",
        ),
        sa.CheckConstraint(
            "timing_policy IN ('strict_source', 'historical_game_date_proxy')",
            name="ck_pregame_role_baseline_timing_policy",
        ),
        sa.CheckConstraint(
            "window_size > 0 AND history_games_seen >= 0 AND played_games_used >= 0",
            name="ck_pregame_role_baseline_counts",
        ),
        sa.UniqueConstraint(
            "canonical_game_id", "canonical_player_id", "canonical_team_id",
            "window_size", "feature_as_of", "calculation_version",
            name="uq_pregame_role_baseline_natural_key",
        ),
    )
    op.create_index("idx_pregame_role_baseline_game", "pregame_player_role_baselines", ["canonical_game_id"])
    op.create_index(
        "idx_pregame_role_baseline_player", "pregame_player_role_baselines",
        ["canonical_player_id", "feature_as_of"],
    )
    op.create_index(
        "idx_pregame_role_baseline_status", "pregame_player_role_baselines",
        ["season", "completeness_status"],
    )


def downgrade() -> None:
    op.drop_index("idx_pregame_role_baseline_status", table_name="pregame_player_role_baselines")
    op.drop_index("idx_pregame_role_baseline_player", table_name="pregame_player_role_baselines")
    op.drop_index("idx_pregame_role_baseline_game", table_name="pregame_player_role_baselines")
    op.drop_table("pregame_player_role_baselines")
    op.drop_index("idx_player_role_history_season", table_name="player_role_history")
    op.drop_index("idx_player_role_history_team_date", table_name="player_role_history")
    op.drop_index("idx_player_role_history_player_date", table_name="player_role_history")
    op.drop_table("player_role_history")
