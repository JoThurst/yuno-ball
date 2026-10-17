"""Add immutable external dataset import manifests.

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-07-16 01:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_dataset_imports",
        sa.Column("import_id", sa.String(length=36), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("dataset_version", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "downloaded_at_precision",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column("storage_locator", sa.Text(), nullable=False),
        sa.Column("license_identifier", sa.String(length=255), nullable=True),
        sa.Column("license_status", sa.String(length=32), nullable=False),
        sa.Column("commercial_use_status", sa.String(length=32), nullable=False),
        sa.Column("transformation_version", sa.String(length=64), nullable=False),
        sa.Column("source_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_row_count", sa.BigInteger(), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("manifest_details", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_external_dataset_import_sha256",
        ),
        sa.CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_external_dataset_import_file_size",
        ),
        sa.CheckConstraint(
            "source_row_count IS NULL OR source_row_count >= 0",
            name="ck_external_dataset_import_row_count",
        ),
        sa.CheckConstraint(
            "downloaded_at_precision IN ('exact', 'file_mtime', 'unknown')",
            name="ck_external_dataset_import_download_precision",
        ),
        sa.CheckConstraint(
            "(downloaded_at IS NULL AND downloaded_at_precision = 'unknown') OR "
            "(downloaded_at IS NOT NULL AND downloaded_at_precision IN "
            "('exact', 'file_mtime'))",
            name="ck_external_dataset_import_download_value",
        ),
        sa.CheckConstraint(
            "license_status IN "
            "('unknown', 'needs_review', 'approved_internal', "
            "'approved_public', 'rejected')",
            name="ck_external_dataset_import_license_status",
        ),
        sa.CheckConstraint(
            "commercial_use_status IN ('unknown', 'permitted', 'prohibited')",
            name="ck_external_dataset_import_commercial_status",
        ),
        sa.CheckConstraint(
            "validation_status IN ('registered', 'profiled', 'failed', 'rejected')",
            name="ck_external_dataset_import_validation_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ingestion_runs.run_id"],
            name="fk_external_dataset_import_source_run",
        ),
        sa.PrimaryKeyConstraint("import_id"),
        sa.UniqueConstraint(
            "source_name",
            "dataset_name",
            "dataset_version",
            "sha256",
            "transformation_version",
            name="uq_external_dataset_import_artifact",
        ),
    )
    op.create_index(
        "idx_external_dataset_import_sha256",
        "external_dataset_imports",
        ["sha256"],
    )
    op.create_index(
        "idx_external_dataset_import_source_status",
        "external_dataset_imports",
        ["source_name", "validation_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_external_dataset_import_source_status",
        table_name="external_dataset_imports",
    )
    op.drop_index(
        "idx_external_dataset_import_sha256",
        table_name="external_dataset_imports",
    )
    op.drop_table("external_dataset_imports")
