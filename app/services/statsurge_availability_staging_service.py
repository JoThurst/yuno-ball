"""Transactional persistence for Stat Surge availability staging rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.external_dataset_import_sqlalchemy import ExternalDatasetImportORM
from app.models.external_staging_sqlalchemy import (
    ExternalRowRejectionORM,
    StatsurgeAvailabilityStagingORM,
)


STATSURGE_STAGING_LOCK_NAME = "yunoball:statsurge_availability_staging"
STATSURGE_PARSER_VERSION = "statsurge-availability-v1"
EXPECTED_SOURCE_NAME = "stat-surge"
EXPECTED_DATASET_NAME = "nba-injury-daily-checkpoints"
_BATCH_SIZE = 500


@dataclass(frozen=True)
class StatsurgeStagingResult:
    """Counts and lineage returned by one staging transaction."""

    source_import_id: str
    parser_version: str
    source_rows: int
    staged_rows: int
    rejected_rows: int
    inserted_staged_rows: int
    inserted_rejected_rows: int


def _batches(values: Sequence[Mapping[str, Any]]) -> Iterable[Sequence[Mapping[str, Any]]]:
    for start in range(0, len(values), _BATCH_SIZE):
        yield values[start : start + _BATCH_SIZE]


def _manifest_for_staging(
    db: Session,
    *,
    source_import_id: str,
    file_name: str,
    file_sha256: str,
    source_row_count: int,
) -> ExternalDatasetImportORM:
    manifest = db.get(ExternalDatasetImportORM, source_import_id)
    if manifest is None:
        raise ValueError(f"Unknown external dataset manifest: {source_import_id}")

    mismatches = []
    expected = {
        "source_name": EXPECTED_SOURCE_NAME,
        "dataset_name": EXPECTED_DATASET_NAME,
        "file_name": file_name,
        "sha256": file_sha256,
        "source_row_count": source_row_count,
        "license_status": "approved_public",
        "commercial_use_status": "permitted",
    }
    for field, expected_value in expected.items():
        if getattr(manifest, field) != expected_value:
            mismatches.append(field)
    if manifest.validation_status not in {"registered", "profiled"}:
        mismatches.append("validation_status")
    if mismatches:
        raise ValueError(
            "Manifest is not eligible for Stat Surge staging: "
            + ", ".join(sorted(set(mismatches)))
        )
    return manifest


def _insert_staged_rows(
    db: Session,
    rows: Sequence[Mapping[str, Any]],
    *,
    source_import_id: str,
    source_run_id: str,
    manifest: ExternalDatasetImportORM,
) -> int:
    inserted = 0
    payloads: List[Dict[str, Any]] = []
    for row in rows:
        payloads.append(
            {
                "staging_row_id": str(uuid.uuid4()),
                "source_import_id": source_import_id,
                "source_run_id": source_run_id,
                "source_dataset_version": manifest.dataset_version,
                "source_file_name": manifest.file_name,
                "parser_version": STATSURGE_PARSER_VERSION,
                **dict(row),
            }
        )
    for batch in _batches(payloads):
        statement = (
            pg_insert(StatsurgeAvailabilityStagingORM)
            .values(list(batch))
            .on_conflict_do_nothing(
                constraint="uq_statsurge_availability_source_row"
            )
        )
        inserted += int(db.execute(statement).rowcount or 0)
    return inserted


def _insert_rejections(
    db: Session,
    rejections: Sequence[Mapping[str, Any]],
    *,
    source_import_id: str,
    source_run_id: str,
    manifest: ExternalDatasetImportORM,
) -> int:
    inserted = 0
    payloads: List[Dict[str, Any]] = []
    for rejection in rejections:
        payloads.append(
            {
                "rejection_id": str(uuid.uuid4()),
                "source_import_id": source_import_id,
                "source_run_id": source_run_id,
                "source_file_name": manifest.file_name,
                "parser_version": STATSURGE_PARSER_VERSION,
                **dict(rejection),
            }
        )
    for batch in _batches(payloads):
        statement = (
            pg_insert(ExternalRowRejectionORM)
            .values(list(batch))
            .on_conflict_do_nothing(
                constraint="uq_external_row_rejection_source_row"
            )
        )
        inserted += int(db.execute(statement).rowcount or 0)
    return inserted


def _verify_persisted_partition(
    db: Session,
    *,
    source_import_id: str,
    expected_rows: Mapping[int, str],
    expected_rejections: Mapping[int, str],
) -> Tuple[int, int]:
    staged = dict(
        db.query(
            StatsurgeAvailabilityStagingORM.source_row_number,
            StatsurgeAvailabilityStagingORM.row_sha256,
        )
        .filter(
            StatsurgeAvailabilityStagingORM.source_import_id == source_import_id,
            StatsurgeAvailabilityStagingORM.parser_version
            == STATSURGE_PARSER_VERSION,
        )
        .all()
    )
    rejected = dict(
        db.query(
            ExternalRowRejectionORM.source_row_number,
            ExternalRowRejectionORM.row_sha256,
        )
        .filter(
            ExternalRowRejectionORM.source_import_id == source_import_id,
            ExternalRowRejectionORM.parser_version == STATSURGE_PARSER_VERSION,
        )
        .all()
    )
    overlap = set(staged).intersection(rejected)
    if overlap:
        raise ValueError(
            "Source rows exist in both staged and rejected partitions: "
            + ", ".join(str(value) for value in sorted(overlap)[:10])
        )
    if staged != dict(expected_rows):
        raise ValueError("Persisted staged rows do not match the parsed artifact")
    if rejected != dict(expected_rejections):
        raise ValueError("Persisted rejected rows do not match the parsed artifact")
    return len(staged), len(rejected)


def stage_statsurge_availability(
    *,
    source_import_id: str,
    source_run_id: str,
    file_name: str,
    file_sha256: str,
    source_row_count: int,
    rows: Sequence[Mapping[str, Any]],
    rejections: Sequence[Mapping[str, Any]],
    db: Optional[Session] = None,
) -> StatsurgeStagingResult:
    """Stage one hash-verified artifact and quarantine invalid rows atomically."""
    if source_row_count != len(rows) + len(rejections):
        raise ValueError("Parsed staged and rejected rows do not cover the source file")

    try:
        uuid.UUID(source_import_id)
        uuid.UUID(source_run_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("source_import_id and source_run_id must be UUIDs") from exc

    staged_numbers = [int(row["source_row_number"]) for row in rows]
    rejected_numbers = [int(row["source_row_number"]) for row in rejections]
    if len(staged_numbers) != len(set(staged_numbers)):
        raise ValueError("Parsed staged rows contain duplicate source row numbers")
    if len(rejected_numbers) != len(set(rejected_numbers)):
        raise ValueError("Parsed rejected rows contain duplicate source row numbers")
    if set(staged_numbers).intersection(rejected_numbers):
        raise ValueError("A source row cannot be both staged and rejected")

    def persist(session: Session) -> StatsurgeStagingResult:
        manifest = _manifest_for_staging(
            session,
            source_import_id=source_import_id,
            file_name=file_name,
            file_sha256=file_sha256,
            source_row_count=source_row_count,
        )
        inserted_staged = _insert_staged_rows(
            session,
            rows,
            source_import_id=source_import_id,
            source_run_id=source_run_id,
            manifest=manifest,
        )
        inserted_rejected = _insert_rejections(
            session,
            rejections,
            source_import_id=source_import_id,
            source_run_id=source_run_id,
            manifest=manifest,
        )
        expected_rows = {
            int(row["source_row_number"]): str(row["row_sha256"])
            for row in rows
        }
        expected_rejections = {
            int(row["source_row_number"]): str(row["row_sha256"])
            for row in rejections
        }
        staged_count, rejected_count = _verify_persisted_partition(
            session,
            source_import_id=source_import_id,
            expected_rows=expected_rows,
            expected_rejections=expected_rejections,
        )
        return StatsurgeStagingResult(
            source_import_id=source_import_id,
            parser_version=STATSURGE_PARSER_VERSION,
            source_rows=source_row_count,
            staged_rows=staged_count,
            rejected_rows=rejected_count,
            inserted_staged_rows=inserted_staged,
            inserted_rejected_rows=inserted_rejected,
        )

    if db is not None:
        return persist(db)
    with get_db_context() as session:
        return persist(session)
