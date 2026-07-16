"""Transactional persistence for source-specific Kaggle game staging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.external_dataset_import_sqlalchemy import ExternalDatasetImportORM
from app.models.external_staging_sqlalchemy import (
    ExternalRowRejectionORM,
    KaggleGameStagingORM,
)


KAGGLE_GAME_STAGING_LOCK_NAME = "yunoball:kaggle_game_staging"
KAGGLE_GAME_PARSER_VERSION = "kaggle-games-v1"
EXPECTED_SOURCE_NAME = "kaggle-uploaded-pack"
EXPECTED_DATASET_NAME = "nba-team-game-facts"
_BATCH_SIZE = 500


@dataclass(frozen=True)
class KaggleGameStagingResult:
    source_rows: int
    staged_rows: int
    rejected_rows: int
    inserted_staged_rows: int
    inserted_rejected_rows: int


def _batches(values: Sequence[Mapping[str, Any]]) -> Iterable[Sequence[Mapping[str, Any]]]:
    for start in range(0, len(values), _BATCH_SIZE):
        yield values[start : start + _BATCH_SIZE]


def _eligible_manifest(
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
    expected = {
        "source_name": EXPECTED_SOURCE_NAME,
        "dataset_name": EXPECTED_DATASET_NAME,
        "file_name": file_name,
        "sha256": file_sha256,
        "source_row_count": source_row_count,
        "license_status": "approved_public",
        "commercial_use_status": "permitted",
    }
    mismatches = [
        field
        for field, expected_value in expected.items()
        if getattr(manifest, field) != expected_value
    ]
    if manifest.validation_status not in {"registered", "profiled"}:
        mismatches.append("validation_status")
    if mismatches:
        raise ValueError(
            "Manifest is not eligible for Kaggle game staging: "
            + ", ".join(sorted(set(mismatches)))
        )
    return manifest


def _insert_rows(
    db: Session,
    *,
    model: type,
    constraint: str,
    payloads: Sequence[Mapping[str, Any]],
) -> int:
    inserted = 0
    for batch in _batches(payloads):
        statement = (
            pg_insert(model)
            .values(list(batch))
            .on_conflict_do_nothing(constraint=constraint)
        )
        inserted += int(db.execute(statement).rowcount or 0)
    return inserted


def stage_kaggle_games(
    *,
    source_import_id: str,
    source_run_id: str,
    file_name: str,
    file_sha256: str,
    source_row_count: int,
    rows: Sequence[Mapping[str, Any]],
    rejections: Sequence[Mapping[str, Any]],
    db: Optional[Session] = None,
) -> KaggleGameStagingResult:
    """Stage the complete game artifact, with an exact persisted partition."""
    if source_row_count != len(rows) + len(rejections):
        raise ValueError("Staged and rejected rows do not cover the source file")
    try:
        uuid.UUID(source_import_id)
        uuid.UUID(source_run_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("source_import_id and source_run_id must be UUIDs") from exc

    staged_numbers = [int(row["source_row_number"]) for row in rows]
    rejected_numbers = [int(row["source_row_number"]) for row in rejections]
    if len(staged_numbers) != len(set(staged_numbers)):
        raise ValueError("Staged rows contain duplicate source row numbers")
    if len(rejected_numbers) != len(set(rejected_numbers)):
        raise ValueError("Rejected rows contain duplicate source row numbers")
    if set(staged_numbers).intersection(rejected_numbers):
        raise ValueError("A source row cannot be both staged and rejected")

    def persist(session: Session) -> KaggleGameStagingResult:
        manifest = _eligible_manifest(
            session,
            source_import_id=source_import_id,
            file_name=file_name,
            file_sha256=file_sha256,
            source_row_count=source_row_count,
        )
        staged_payloads: List[Dict[str, Any]] = [
            {
                "staging_row_id": str(uuid.uuid4()),
                "source_import_id": source_import_id,
                "source_run_id": source_run_id,
                "source_dataset_version": manifest.dataset_version,
                "source_file_name": manifest.file_name,
                "parser_version": KAGGLE_GAME_PARSER_VERSION,
                **dict(row),
            }
            for row in rows
        ]
        rejected_payloads: List[Dict[str, Any]] = [
            {
                "rejection_id": str(uuid.uuid4()),
                "source_import_id": source_import_id,
                "source_run_id": source_run_id,
                "source_file_name": manifest.file_name,
                "parser_version": KAGGLE_GAME_PARSER_VERSION,
                **dict(row),
            }
            for row in rejections
        ]
        inserted_staged = _insert_rows(
            session,
            model=KaggleGameStagingORM,
            constraint="uq_kaggle_games_source_row",
            payloads=staged_payloads,
        )
        inserted_rejected = _insert_rows(
            session,
            model=ExternalRowRejectionORM,
            constraint="uq_external_row_rejection_source_row",
            payloads=rejected_payloads,
        )

        persisted_staged = dict(
            session.query(
                KaggleGameStagingORM.source_row_number,
                KaggleGameStagingORM.row_sha256,
            )
            .filter(
                KaggleGameStagingORM.source_import_id == source_import_id,
                KaggleGameStagingORM.parser_version == KAGGLE_GAME_PARSER_VERSION,
            )
            .all()
        )
        persisted_rejected = dict(
            session.query(
                ExternalRowRejectionORM.source_row_number,
                ExternalRowRejectionORM.row_sha256,
            )
            .filter(
                ExternalRowRejectionORM.source_import_id == source_import_id,
                ExternalRowRejectionORM.parser_version == KAGGLE_GAME_PARSER_VERSION,
            )
            .all()
        )
        expected_staged = {
            int(row["source_row_number"]): str(row["row_sha256"])
            for row in rows
        }
        expected_rejected = {
            int(row["source_row_number"]): str(row["row_sha256"])
            for row in rejections
        }
        if set(persisted_staged).intersection(persisted_rejected):
            raise ValueError("Persisted game partitions overlap")
        if persisted_staged != expected_staged:
            raise ValueError("Persisted game rows do not match the parsed artifact")
        if persisted_rejected != expected_rejected:
            raise ValueError("Persisted game rejections do not match the parsed artifact")
        return KaggleGameStagingResult(
            source_rows=source_row_count,
            staged_rows=len(persisted_staged),
            rejected_rows=len(persisted_rejected),
            inserted_staged_rows=inserted_staged,
            inserted_rejected_rows=inserted_rejected,
        )

    if db is not None:
        return persist(db)
    with get_db_context() as session:
        return persist(session)
