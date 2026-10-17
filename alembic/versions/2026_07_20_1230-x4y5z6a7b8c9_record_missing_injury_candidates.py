"""Retain confirmed missing official injury-report candidates."""

from alembic import op


revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_availability_download_status",
        "availability_report_download_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_availability_download_status",
        "availability_report_download_attempts",
        "status IN ('pending', 'succeeded', 'not_found')",
    )
    op.drop_constraint(
        "ck_availability_download_terminal_state",
        "availability_report_download_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_availability_download_terminal_state",
        "availability_report_download_attempts",
        "(status = 'pending' AND document_id IS NULL) OR "
        "(status = 'succeeded' AND document_id IS NOT NULL AND "
        "last_error_class IS NULL AND last_error_summary IS NULL AND next_retry_at IS NULL) OR "
        "(status = 'not_found' AND document_id IS NULL AND next_retry_at IS NULL AND "
        "last_error_class IS NOT NULL AND last_error_summary IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_availability_download_terminal_state",
        "availability_report_download_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_availability_download_terminal_state",
        "availability_report_download_attempts",
        "(status = 'pending' AND document_id IS NULL) OR "
        "(status = 'succeeded' AND document_id IS NOT NULL AND "
        "last_error_class IS NULL AND last_error_summary IS NULL AND next_retry_at IS NULL)",
    )
    op.drop_constraint(
        "ck_availability_download_status",
        "availability_report_download_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_availability_download_status",
        "availability_report_download_attempts",
        "status IN ('pending', 'succeeded')",
    )
