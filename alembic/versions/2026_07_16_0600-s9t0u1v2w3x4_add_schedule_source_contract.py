"""Add explicit schedule event, score, precision, and provenance fields.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-07-16 06:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_schedule", sa.Column("season_type", sa.String(32)))
    op.add_column(
        "game_schedule", sa.Column("game_date_precision", sa.String(16))
    )
    op.add_column("game_schedule", sa.Column("team_score", sa.Integer()))
    op.add_column("game_schedule", sa.Column("opponent_score", sa.Integer()))
    op.add_column("game_schedule", sa.Column("source_name", sa.String(64)))
    op.add_column("game_schedule", sa.Column("source_import_id", sa.String(36)))
    op.add_column("game_schedule", sa.Column("source_run_id", sa.String(36)))
    op.add_column("game_schedule", sa.Column("source_row_number", sa.BigInteger()))
    op.add_column(
        "game_schedule", sa.Column("source_row_sha256", sa.String(64))
    )
    op.add_column(
        "game_schedule", sa.Column("source_parser_version", sa.String(64))
    )

    op.execute(
        sa.text(
            """
            UPDATE game_schedule
            SET season_type = CASE substring(game_id FROM 1 FOR 3)
                    WHEN '001' THEN 'Pre Season'
                    WHEN '002' THEN 'Regular Season'
                    WHEN '003' THEN 'All-Star'
                    WHEN '004' THEN 'Playoffs'
                    WHEN '005' THEN 'Play-In'
                    WHEN '006' THEN 'NBA Cup'
                    ELSE 'Unknown'
                END,
                game_date_precision = CASE
                    WHEN game_date::time = TIME '00:00:00' THEN 'date_only'
                    ELSE 'exact'
                END,
                source_name = 'legacy_nba_pipeline'
            """
        )
    )

    op.alter_column("game_schedule", "season_type", nullable=False)
    op.alter_column("game_schedule", "game_date_precision", nullable=False)
    op.alter_column("game_schedule", "source_name", nullable=False)

    op.create_foreign_key(
        "fk_game_schedule_source_import",
        "game_schedule",
        "external_dataset_imports",
        ["source_import_id"],
        ["import_id"],
    )
    op.create_foreign_key(
        "fk_game_schedule_source_run",
        "game_schedule",
        "ingestion_runs",
        ["source_run_id"],
        ["run_id"],
    )
    op.create_check_constraint(
        "ck_game_schedule_season_type",
        "game_schedule",
        "season_type IN ('Pre Season', 'Regular Season', 'All-Star', "
        "'Playoffs', 'Play-In', 'NBA Cup', 'Unknown')",
    )
    op.create_check_constraint(
        "ck_game_schedule_date_precision",
        "game_schedule",
        "game_date_precision IN ('exact', 'date_only')",
    )
    op.create_check_constraint(
        "ck_game_schedule_score_pair",
        "game_schedule",
        "(team_score IS NULL) = (opponent_score IS NULL)",
    )
    op.create_check_constraint(
        "ck_game_schedule_scores_nonnegative",
        "game_schedule",
        "team_score IS NULL OR (team_score >= 0 AND opponent_score >= 0)",
    )
    op.create_check_constraint(
        "ck_game_schedule_result_scores",
        "game_schedule",
        "team_score IS NULL OR "
        "(result = 'W' AND team_score > opponent_score) OR "
        "(result = 'L' AND team_score < opponent_score)",
    )
    op.create_check_constraint(
        "ck_game_schedule_source_row",
        "game_schedule",
        "source_row_number IS NULL OR source_row_number >= 2",
    )
    op.create_check_constraint(
        "ck_game_schedule_source_row_sha256",
        "game_schedule",
        "source_row_sha256 IS NULL OR source_row_sha256 ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_game_schedule_external_lineage",
        "game_schedule",
        "source_name <> 'kaggle-uploaded-pack' OR "
        "(source_import_id IS NOT NULL AND source_run_id IS NOT NULL AND "
        "source_row_number IS NOT NULL AND source_row_sha256 IS NOT NULL AND "
        "source_parser_version IS NOT NULL AND team_score IS NOT NULL AND "
        "opponent_score IS NOT NULL)",
    )


def downgrade() -> None:
    for constraint_name in (
        "ck_game_schedule_external_lineage",
        "ck_game_schedule_source_row_sha256",
        "ck_game_schedule_source_row",
        "ck_game_schedule_result_scores",
        "ck_game_schedule_scores_nonnegative",
        "ck_game_schedule_score_pair",
        "ck_game_schedule_date_precision",
        "ck_game_schedule_season_type",
    ):
        op.drop_constraint(constraint_name, "game_schedule", type_="check")
    op.drop_constraint(
        "fk_game_schedule_source_run", "game_schedule", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_game_schedule_source_import", "game_schedule", type_="foreignkey"
    )
    for column_name in (
        "source_parser_version",
        "source_row_sha256",
        "source_row_number",
        "source_run_id",
        "source_import_id",
        "source_name",
        "opponent_score",
        "team_score",
        "game_date_precision",
        "season_type",
    ):
        op.drop_column("game_schedule", column_name)
