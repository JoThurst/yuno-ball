"""Add source-preserving official availability observations."""

from alembic import op
import sqlalchemy as sa


revision = "y5z6a7b8c9d0"
down_revision = "x4y5z6a7b8c9"
branch_labels = None
depends_on = None


SOURCE_CHECKS = (
    "source_name = 'official_nba'",
    "raw_sha256 ~ '^[0-9a-f]{64}$'",
    "source_time_precision IN ('hour', 'minute')",
)


def upgrade() -> None:
    op.create_table(
        "availability_observations",
        sa.Column("observation_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "report_document_id",
            sa.String(length=36),
            sa.ForeignKey("availability_report_documents.document_id"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("report_published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_time_precision", sa.String(length=16), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("source_row_key", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=32), nullable=True),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("scheduled_tipoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matchup_text", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("reported_team_name", sa.Text(), nullable=False),
        sa.Column("reported_player_name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_reason", sa.Text(), nullable=True),
        sa.Column("reason_category", sa.Text(), nullable=True),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source_name = 'official_nba'",
            name="ck_availability_observation_source",
        ),
        sa.CheckConstraint(
            "raw_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_availability_observation_sha256",
        ),
        sa.CheckConstraint(
            "source_time_precision IN ('hour', 'minute')",
            name="ck_availability_observation_time_precision",
        ),
        sa.CheckConstraint(
            "status IN ('Available', 'Probable', 'Questionable', 'Doubtful', 'Out')",
            name="ck_availability_observation_status",
        ),
        sa.UniqueConstraint(
            "report_document_id",
            "parser_version",
            "source_row_key",
            name="uq_availability_observation_parse_row",
        ),
    )
    op.create_index(
        "idx_availability_observation_game",
        "availability_observations",
        ["game_id"],
    )
    op.create_index(
        "idx_availability_observation_team_date",
        "availability_observations",
        ["team_id", "game_date"],
    )
    op.create_index(
        "idx_availability_observation_report_time",
        "availability_observations",
        ["report_published_at"],
    )
    op.create_index(
        "idx_availability_observation_player",
        "availability_observations",
        ["player_id"],
    )

    op.create_table(
        "team_report_submission_status",
        sa.Column("submission_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "report_document_id",
            sa.String(length=36),
            sa.ForeignKey("availability_report_documents.document_id"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("report_published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_time_precision", sa.String(length=16), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("source_row_key", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=32), nullable=True),
        sa.Column("game_date", sa.Date(), nullable=False),
        sa.Column("scheduled_tipoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matchup_text", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("reported_team_name", sa.Text(), nullable=False),
        sa.Column("submission_status", sa.String(length=32), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source_name = 'official_nba'",
            name="ck_team_report_submission_source",
        ),
        sa.CheckConstraint(
            "raw_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_team_report_submission_sha256",
        ),
        sa.CheckConstraint(
            "source_time_precision IN ('hour', 'minute')",
            name="ck_team_report_submission_time_precision",
        ),
        sa.CheckConstraint(
            "submission_status = 'NOT YET SUBMITTED'",
            name="ck_team_report_submission_status_value",
        ),
        sa.UniqueConstraint(
            "report_document_id",
            "parser_version",
            "source_row_key",
            name="uq_team_report_submission_parse_row",
        ),
    )
    op.create_index(
        "idx_team_report_submission_game",
        "team_report_submission_status",
        ["game_id"],
    )
    op.create_index(
        "idx_team_report_submission_report_time",
        "team_report_submission_status",
        ["report_published_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_team_report_submission_report_time",
        table_name="team_report_submission_status",
    )
    op.drop_index(
        "idx_team_report_submission_game",
        table_name="team_report_submission_status",
    )
    op.drop_table("team_report_submission_status")
    op.drop_index(
        "idx_availability_observation_player",
        table_name="availability_observations",
    )
    op.drop_index(
        "idx_availability_observation_report_time",
        table_name="availability_observations",
    )
    op.drop_index(
        "idx_availability_observation_team_date",
        table_name="availability_observations",
    )
    op.drop_index(
        "idx_availability_observation_game",
        table_name="availability_observations",
    )
    op.drop_table("availability_observations")
