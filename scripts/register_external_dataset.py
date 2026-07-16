"""Inspect and optionally register one immutable external source artifact.

Dry-run mode uses only the Python standard library and does not require database
configuration. Apply mode records one ingestion run and one manifest row; it
never imports source rows or changes canonical basketball tables.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import mimetypes
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

HASH_CHUNK_BYTES = 1024 * 1024
DEFAULT_TRANSFORMATION_VERSION = "external-manifest-v1"


class ManifestInspectionError(ValueError):
    """Raised when a local source artifact cannot be safely inspected."""


@dataclass(frozen=True)
class ManifestInspection:
    """Named, serializable result of a bounded source-file inspection."""

    local_path: str
    file_name: str
    file_size_bytes: int
    sha256: str
    media_type: str
    source_row_count: Optional[int]
    column_names: Tuple[str, ...]
    encoding: Optional[str]
    blank_rows: int
    row_width_mismatches: int

    def manifest_details(self) -> Dict[str, Any]:
        """Return non-sensitive parser metadata persisted with the manifest."""
        return {
            "inspection_version": DEFAULT_TRANSFORMATION_VERSION,
            "column_names": list(self.column_names),
            "encoding": self.encoding,
            "blank_rows": self.blank_rows,
            "row_width_mismatches": self.row_width_mismatches,
        }

    def display_dict(self) -> Dict[str, Any]:
        """Return a dry-run display payload, including the local inspection path."""
        payload = asdict(self)
        payload["column_names"] = list(self.column_names)
        return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_csv(path: Path, encoding: str) -> Tuple[int, Tuple[str, ...], int, int]:
    try:
        with path.open("r", encoding=encoding, newline="") as source:
            reader = csv.reader(source)
            try:
                raw_header = next(reader)
            except StopIteration as exc:
                raise ManifestInspectionError("CSV file is empty") from exc

            header = tuple(value.strip() for value in raw_header)
            if not header or any(not value for value in header):
                raise ManifestInspectionError("CSV header contains an empty column name")
            folded = [value.casefold() for value in header]
            if len(folded) != len(set(folded)):
                raise ManifestInspectionError("CSV header contains duplicate column names")

            row_count = 0
            blank_rows = 0
            width_mismatches = 0
            for row in reader:
                row_count += 1
                if not row or all(not value.strip() for value in row):
                    blank_rows += 1
                if len(row) != len(header):
                    width_mismatches += 1
            return row_count, header, blank_rows, width_mismatches
    except (UnicodeError, csv.Error, OSError) as exc:
        raise ManifestInspectionError(f"Could not parse CSV: {exc}") from exc


def inspect_external_dataset_file(
    raw_path: str | Path,
    *,
    encoding: str = "utf-8-sig",
) -> ManifestInspection:
    """Hash one file and stream CSV shape metadata without retaining source rows."""
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise ManifestInspectionError(f"Source file does not exist: {path}")
    if not path.is_file():
        raise ManifestInspectionError(f"Source path is not a file: {path}")

    before = path.stat()
    sha256 = _sha256(path)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    source_row_count: Optional[int] = None
    column_names: Tuple[str, ...] = ()
    inspected_encoding: Optional[str] = None
    blank_rows = 0
    row_width_mismatches = 0
    if path.suffix.casefold() == ".csv":
        (
            source_row_count,
            column_names,
            blank_rows,
            row_width_mismatches,
        ) = _inspect_csv(path, encoding)
        inspected_encoding = encoding

    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ManifestInspectionError(
            "Source file changed while it was being inspected; retry with an "
            "unchanged artifact"
        )

    return ManifestInspection(
        local_path=str(path),
        file_name=path.name,
        file_size_bytes=before.st_size,
        sha256=sha256,
        media_type=media_type,
        source_row_count=source_row_count,
        column_names=column_names,
        encoding=inspected_encoding,
        blank_rows=blank_rows,
        row_width_mismatches=row_width_mismatches,
    )


def parse_downloaded_at(
    raw_value: Optional[str],
    precision: str,
) -> Tuple[Optional[datetime], str]:
    """Parse an aware ISO timestamp while preserving declared precision."""
    if not raw_value:
        if precision != "unknown":
            raise ManifestInspectionError(
                "downloaded-at-precision must be unknown without --downloaded-at"
            )
        return None, "unknown"

    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestInspectionError("--downloaded-at must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestInspectionError("--downloaded-at must include a timezone")
    if precision == "unknown":
        raise ManifestInspectionError(
            "--downloaded-at-precision must be exact or file_mtime when "
            "--downloaded-at is supplied"
        )
    return parsed, precision


def _validate_storage_locator(storage_locator: str) -> str:
    normalized = storage_locator.strip()
    if not normalized:
        raise ManifestInspectionError("--storage-locator is required")
    comparable = normalized.replace("\\", "/").casefold()
    if "datasource/archive" in comparable:
        raise ManifestInspectionError(
            "--storage-locator must reference the durable preserved copy, not "
            "temporary dataSource/archive"
        )
    return normalized


def validate_cli_metadata(args: argparse.Namespace) -> None:
    """Reject incomplete or oversized contract fields before reading a large file."""
    required_lengths = {
        "source_name": 64,
        "dataset_name": 128,
        "dataset_version": 128,
        "transformation_version": 64,
    }
    for field, max_length in required_lengths.items():
        value = str(getattr(args, field, "")).strip()
        if not value:
            raise ManifestInspectionError(f"--{field.replace('_', '-')} is required")
        if len(value) > max_length:
            raise ManifestInspectionError(
                f"--{field.replace('_', '-')} exceeds {max_length} characters"
            )
    if args.license_identifier and len(args.license_identifier.strip()) > 255:
        raise ManifestInspectionError("--license-identifier exceeds 255 characters")
    parse_downloaded_at(args.downloaded_at, args.downloaded_at_precision)
    _validate_storage_locator(args.storage_locator)


def build_manifest_values(
    args: argparse.Namespace,
    inspection: ManifestInspection,
    *,
    source_run_id: str,
) -> Dict[str, Any]:
    """Build the persistence payload without retaining the temporary local path."""
    downloaded_at, precision = parse_downloaded_at(
        args.downloaded_at,
        args.downloaded_at_precision,
    )
    return {
        "source_name": args.source_name.strip(),
        "dataset_name": args.dataset_name.strip(),
        "dataset_version": args.dataset_version.strip(),
        "source_url": args.source_url,
        "file_name": inspection.file_name,
        "file_size_bytes": inspection.file_size_bytes,
        "sha256": inspection.sha256,
        "media_type": inspection.media_type,
        "downloaded_at": downloaded_at,
        "downloaded_at_precision": precision,
        "storage_locator": _validate_storage_locator(args.storage_locator),
        "license_identifier": args.license_identifier,
        "license_status": args.license_status,
        "commercial_use_status": args.commercial_use_status,
        "transformation_version": args.transformation_version.strip(),
        "source_run_id": source_run_id,
        "source_row_count": inspection.source_row_count,
        "validation_status": "registered",
        "manifest_details": inspection.manifest_details(),
    }


def _apply_manifest(
    args: argparse.Namespace,
    inspection: ManifestInspection,
) -> Dict[str, Any]:
    # Lazy imports keep --dry-run independent of database configuration.
    from app.services.external_dataset_manifest_service import (
        EXTERNAL_MANIFEST_LOCK_NAME,
        register_external_dataset_import,
    )
    from app.services.ingestion_run_service import IngestionRunTracker

    run_details = {
        "dataset_name": args.dataset_name.strip(),
        "dataset_version": args.dataset_version.strip(),
        "file_name": inspection.file_name,
        "sha256": inspection.sha256,
        "validation_scope": "hash_header_row_count",
    }
    with IngestionRunTracker(
        run_type="external_dataset_manifest",
        source=args.source_name.strip(),
        season=None,
        target_date=None,
        provider=args.source_name.strip(),
        calculation_version=args.transformation_version.strip(),
        details=run_details,
        lock_name=EXTERNAL_MANIFEST_LOCK_NAME,
    ) as tracker:
        values = build_manifest_values(
            args,
            inspection,
            source_run_id=tracker.run_id,
        )
        result = register_external_dataset_import(values)
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=inspection.source_row_count,
            rows_written=1 if result.created else 0,
            details={
                **run_details,
                "import_id": result.import_id,
                "created": result.created,
            },
        )
    return {
        "mode": "apply",
        "run_id": tracker.run_id,
        "import_id": result.import_id,
        "created": result.created,
        "manifest": result.manifest.to_dict(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Hash and register one external source artifact without importing rows"
        )
    )
    parser.add_argument("--file", required=True, help="Temporary local file to inspect")
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--source-url")
    parser.add_argument(
        "--storage-locator",
        required=True,
        help="Durable preserved-copy locator; dataSource/archive is rejected",
    )
    parser.add_argument(
        "--downloaded-at",
        help="Timezone-aware ISO timestamp; requires an explicit non-unknown precision",
    )
    parser.add_argument(
        "--downloaded-at-precision",
        choices=("exact", "file_mtime", "unknown"),
        default="unknown",
    )
    parser.add_argument("--license-identifier")
    parser.add_argument(
        "--license-status",
        choices=(
            "unknown",
            "needs_review",
            "approved_internal",
            "approved_public",
            "rejected",
        ),
        default="needs_review",
    )
    parser.add_argument(
        "--commercial-use-status",
        choices=("unknown", "permitted", "prohibited"),
        default="unknown",
    )
    parser.add_argument(
        "--transformation-version",
        default=DEFAULT_TRANSFORMATION_VERSION,
    )
    parser.add_argument("--encoding", default="utf-8-sig")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_cli_metadata(args)
        inspection = inspect_external_dataset_file(args.file, encoding=args.encoding)
        # Validate timestamp and durable-storage semantics in both modes.
        downloaded_at, precision = parse_downloaded_at(
            args.downloaded_at,
            args.downloaded_at_precision,
        )
        storage_locator = _validate_storage_locator(args.storage_locator)
        if args.dry_run:
            output = {
                "mode": "dry-run",
                "database_write": False,
                "source_name": args.source_name.strip(),
                "dataset_name": args.dataset_name.strip(),
                "dataset_version": args.dataset_version.strip(),
                "source_url": args.source_url,
                "storage_locator": storage_locator,
                "downloaded_at": (
                    downloaded_at.isoformat() if downloaded_at else None
                ),
                "downloaded_at_precision": precision,
                "license_identifier": args.license_identifier,
                "license_status": args.license_status,
                "commercial_use_status": args.commercial_use_status,
                "transformation_version": args.transformation_version.strip(),
                "inspection": inspection.display_dict(),
            }
        else:
            output = _apply_manifest(args, inspection)
    except Exception as exc:
        print(f"External dataset manifest failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1

    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
