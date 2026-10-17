"""Unit tests for immutable manifest registration semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid

import pytest

from app.models.external_dataset_import_sqlalchemy import ExternalDatasetImportORM
from app.services.external_dataset_manifest_service import (
    ExternalDatasetManifestConflict,
    normalize_manifest_values,
    register_external_dataset_import,
)


def _values():
    return {
        "source_name": "statsurge",
        "dataset_name": "nba-injury-checkpoints",
        "dataset_version": "2021-2024",
        "source_url": "https://example.test/injuries",
        "file_name": "injuries.csv",
        "file_size_bytes": 123,
        "sha256": "a" * 64,
        "media_type": "text/csv",
        "downloaded_at": datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc),
        "downloaded_at_precision": "exact",
        "storage_locator": "s3://private-yunoball/injuries.csv",
        "license_identifier": None,
        "license_status": "needs_review",
        "commercial_use_status": "unknown",
        "transformation_version": "external-manifest-v1",
        "source_run_id": str(uuid.uuid4()),
        "source_row_count": 35522,
        "validation_status": "registered",
        "manifest_details": {"column_names": ["PLAYER", "STATUS"]},
    }


def _session_with_existing(existing):
    session = MagicMock()
    session.query.return_value.filter_by.return_value.one_or_none.return_value = existing
    return session


def test_normalization_rejects_timestamp_without_precision():
    values = _values()
    values["downloaded_at_precision"] = "unknown"

    with pytest.raises(ValueError, match="cannot be unknown"):
        normalize_manifest_values(values)


def test_first_registration_creates_one_manifest():
    values = _values()
    session = _session_with_existing(None)

    result = register_external_dataset_import(values, db=session)

    assert result.created is True
    assert result.manifest.sha256 == "a" * 64
    session.add.assert_called_once_with(result.manifest)
    session.flush.assert_called_once_with()


def test_identical_registration_is_idempotent():
    values = _values()
    normalized = normalize_manifest_values(values)
    existing = ExternalDatasetImportORM(import_id=str(uuid.uuid4()), **normalized)
    session = _session_with_existing(existing)

    result = register_external_dataset_import(values, db=session)

    assert result.created is False
    assert result.import_id == existing.import_id
    session.add.assert_not_called()


def test_natural_key_rerun_rejects_changed_immutable_metadata():
    values = _values()
    normalized = normalize_manifest_values(values)
    existing = ExternalDatasetImportORM(import_id=str(uuid.uuid4()), **normalized)
    session = _session_with_existing(existing)
    values["storage_locator"] = "s3://another-location/injuries.csv"

    with pytest.raises(ExternalDatasetManifestConflict, match="storage_locator"):
        register_external_dataset_import(values, db=session)

    session.add.assert_not_called()
