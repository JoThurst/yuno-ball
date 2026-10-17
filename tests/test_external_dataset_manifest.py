"""Contract tests for local external source-file inspection."""

from __future__ import annotations

from datetime import timezone
import hashlib
import json

import pytest

import scripts.register_external_dataset as manifest_cli
from scripts.register_external_dataset import (
    ManifestInspectionError,
    inspect_external_dataset_file,
    main,
    parse_downloaded_at,
)


def test_csv_inspection_hashes_and_counts_logical_records(tmp_path):
    source = tmp_path / "sample.csv"
    content = 'name,reason\n"Doe, Jane","line one\nline two"\nSmith,Rest\n'
    source.write_text(content, encoding="utf-8")

    result = inspect_external_dataset_file(source)

    assert result.file_name == "sample.csv"
    assert result.source_row_count == 2
    assert result.column_names == ("name", "reason")
    assert result.blank_rows == 0
    assert result.row_width_mismatches == 0
    assert result.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_csv_inspection_reports_blank_and_width_mismatch_rows(tmp_path):
    source = tmp_path / "shape.csv"
    source.write_text("a,b\n\n1\n2,3\n", encoding="utf-8")

    result = inspect_external_dataset_file(source)

    assert result.source_row_count == 3
    assert result.blank_rows == 1
    assert result.row_width_mismatches == 2


@pytest.mark.parametrize("header", ["", "a,,b\n", "A,a\n"])
def test_csv_inspection_rejects_invalid_headers(tmp_path, header):
    source = tmp_path / "invalid.csv"
    source.write_text(header, encoding="utf-8")

    with pytest.raises(ManifestInspectionError):
        inspect_external_dataset_file(source)


def test_non_csv_manifest_preserves_hash_without_inventing_rows(tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.7\nfixture")

    result = inspect_external_dataset_file(source)

    assert result.media_type == "application/pdf"
    assert result.source_row_count is None
    assert result.column_names == ()


def test_inspection_rejects_a_file_changed_during_scan(tmp_path, monkeypatch):
    source = tmp_path / "changing.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    original_sha256 = manifest_cli._sha256

    def hash_then_change(path):
        digest = original_sha256(path)
        path.write_text("a,b\n3,4\n5,6\n", encoding="utf-8")
        return digest

    monkeypatch.setattr(manifest_cli, "_sha256", hash_then_change)

    with pytest.raises(ManifestInspectionError, match="changed"):
        inspect_external_dataset_file(source)


def test_download_timestamp_requires_explicit_timezone():
    with pytest.raises(ManifestInspectionError, match="timezone"):
        parse_downloaded_at("2026-07-15T12:00:00", "exact")

    with pytest.raises(ManifestInspectionError, match="exact or file_mtime"):
        parse_downloaded_at("2026-07-15T16:00:00Z", "unknown")

    parsed, precision = parse_downloaded_at("2026-07-15T16:00:00Z", "exact")
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    assert precision == "exact"


def test_dry_run_uses_no_database_and_rejects_temporary_storage(tmp_path, capsys):
    source = tmp_path / "sample.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    common = [
        "--file",
        str(source),
        "--source-name",
        "fixture",
        "--dataset-name",
        "fixture-data",
        "--dataset-version",
        "v1",
        "--storage-locator",
        "s3://private-yunoball-fixtures/sample.csv",
        "--dry-run",
    ]

    assert main(common) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["database_write"] is False
    assert output["inspection"]["source_row_count"] == 1

    rejected = list(common)
    rejected[rejected.index("s3://private-yunoball-fixtures/sample.csv")] = (
        "C:/Code/sports_analytics/dataSource/archive/sample.csv"
    )
    assert main(rejected) == 1
    assert "durable preserved copy" in capsys.readouterr().err
