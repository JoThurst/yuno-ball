"""add durable official availability download retry queue

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
"""

from alembic import op
import sqlalchemy as sa

revision = "v2w3x4y5z6a7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "availability_report_download_attempts",
        sa.Column("download_attempt_id", sa.String(36), nullable=False),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("report_published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_class", sa.String(128), nullable=True),
        sa.Column("last_error_summary", sa.Text(), nullable=True),
        sa.Column("first_discovered_run_id", sa.String(36), nullable=False),
        sa.Column("last_attempt_run_id", sa.String(36), nullable=True),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_name = 'official_nba'", name="ck_availability_download_source"),
        sa.CheckConstraint("status IN ('pending', 'succeeded')", name="ck_availability_download_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_availability_download_attempt_count"),
        sa.CheckConstraint("(status = 'pending' AND document_id IS NULL) OR (status = 'succeeded' AND document_id IS NOT NULL AND last_error_class IS NULL AND last_error_summary IS NULL AND next_retry_at IS NULL)", name="ck_availability_download_terminal_state"),
        sa.ForeignKeyConstraint(["first_discovered_run_id"], ["ingestion_runs.run_id"], name="fk_availability_download_first_run"),
        sa.ForeignKeyConstraint(["last_attempt_run_id"], ["ingestion_runs.run_id"], name="fk_availability_download_last_run"),
        sa.ForeignKeyConstraint(["document_id"], ["availability_report_documents.document_id"], name="fk_availability_download_document"),
        sa.PrimaryKeyConstraint("download_attempt_id", name="availability_report_download_attempts_pkey"),
        sa.UniqueConstraint("source_name", "source_url", name="uq_availability_download_source_url"),
    )
    op.create_index("idx_availability_download_due", "availability_report_download_attempts", ["status", "next_retry_at"])
    op.create_index("idx_availability_download_report_date", "availability_report_download_attempts", ["report_date"])


def downgrade() -> None:
    op.drop_index("idx_availability_download_report_date", table_name="availability_report_download_attempts")
    op.drop_index("idx_availability_download_due", table_name="availability_report_download_attempts")
    op.drop_table("availability_report_download_attempts")
