"""Support legacy hourly official injury-report filenames."""

from alembic import op
import sqlalchemy as sa


revision = "w3x4y5z6a7b8"
down_revision = "v2w3x4y5z6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_availability_report_document_time_precision",
        "availability_report_documents",
        type_="check",
    )
    op.create_check_constraint(
        "ck_availability_report_document_time_precision",
        "availability_report_documents",
        "source_time_precision IN ('hour', 'minute')",
    )

    op.add_column(
        "availability_report_download_attempts",
        sa.Column("source_time_precision", sa.String(length=16), nullable=True),
    )
    op.execute(
        "UPDATE availability_report_download_attempts "
        "SET source_time_precision = 'minute' "
        "WHERE source_time_precision IS NULL"
    )
    op.alter_column(
        "availability_report_download_attempts",
        "source_time_precision",
        existing_type=sa.String(length=16),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_availability_download_time_precision",
        "availability_report_download_attempts",
        "source_time_precision IN ('hour', 'minute')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_availability_download_time_precision",
        "availability_report_download_attempts",
        type_="check",
    )
    op.drop_column(
        "availability_report_download_attempts",
        "source_time_precision",
    )
    op.drop_constraint(
        "ck_availability_report_document_time_precision",
        "availability_report_documents",
        type_="check",
    )
    op.create_check_constraint(
        "ck_availability_report_document_time_precision",
        "availability_report_documents",
        "source_time_precision = 'minute'",
    )
