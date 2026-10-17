"""add immutable official availability report documents

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-07-16 08:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "availability_report_documents",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "report_published_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("source_time_precision", sa.String(length=16), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("raw_storage_locator", sa.Text(), nullable=False),
        sa.Column("http_etag", sa.Text(), nullable=True),
        sa.Column("http_last_modified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collector_version", sa.String(length=64), nullable=False),
        sa.Column("completeness_status", sa.String(length=16), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("parse_status", sa.String(length=16), nullable=False),
        sa.Column("parse_error_summary", sa.Text(), nullable=True),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_name = 'official_nba'",
            name="ck_availability_report_document_source",
        ),
        sa.CheckConstraint(
            "raw_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_availability_report_document_sha256",
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0",
            name="ck_availability_report_document_file_size",
        ),
        sa.CheckConstraint(
            "media_type = 'application/pdf'",
            name="ck_availability_report_document_media_type",
        ),
        sa.CheckConstraint(
            "source_time_precision = 'minute'",
            name="ck_availability_report_document_time_precision",
        ),
        sa.CheckConstraint(
            "completeness_status IN ('complete', 'partial')",
            name="ck_availability_report_document_completeness",
        ),
        sa.CheckConstraint(
            "parse_status IN ('not_parsed', 'parsed', 'partial', 'failed')",
            name="ck_availability_report_document_parse_status",
        ),
        sa.CheckConstraint(
            "(parse_status = 'not_parsed' AND parser_version IS NULL AND "
            "parse_error_summary IS NULL) OR "
            "(parse_status IN ('parsed', 'partial') AND parser_version IS NOT NULL) OR "
            "(parse_status = 'failed' AND parser_version IS NOT NULL AND "
            "parse_error_summary IS NOT NULL)",
            name="ck_availability_report_document_parse_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_availability_report_document_source_run",
        ),
        sa.PrimaryKeyConstraint(
            "document_id",
            name="availability_report_documents_pkey",
        ),
        sa.UniqueConstraint(
            "source_name",
            "source_url",
            "raw_sha256",
            name="uq_availability_report_document_revision",
        ),
    )
    op.create_index(
        "idx_availability_report_document_published",
        "availability_report_documents",
        ["report_published_at"],
        unique=False,
    )
    op.create_index(
        "idx_availability_report_document_sha256",
        "availability_report_documents",
        ["raw_sha256"],
        unique=False,
    )
    op.create_index(
        "idx_availability_report_document_source_run",
        "availability_report_documents",
        ["source_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_availability_report_document_source_run",
        table_name="availability_report_documents",
    )
    op.drop_index(
        "idx_availability_report_document_sha256",
        table_name="availability_report_documents",
    )
    op.drop_index(
        "idx_availability_report_document_published",
        table_name="availability_report_documents",
    )
    op.drop_table("availability_report_documents")
