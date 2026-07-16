"""Atomic persistence for the three-file Kaggle historical market pack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_db_context
from app.models.external_dataset_import_sqlalchemy import ExternalDatasetImportORM
from app.models.external_staging_sqlalchemy import (
    ExternalMarketAnomalyORM,
    ExternalRowRejectionORM,
    KaggleGameStagingORM,
    KaggleMoneylineStagingORM,
    KaggleSpreadStagingORM,
    KaggleTotalStagingORM,
)


KAGGLE_MARKET_STAGING_LOCK_NAME = "yunoball:kaggle_market_staging"
MARKET_PARSER_VERSION = "kaggle-markets-v1"
GAME_PARSER_VERSION = "kaggle-games-v1"
EXPECTED_SOURCE_NAME = "kaggle-uploaded-pack"
MARKET_MODELS = {
    "moneyline": KaggleMoneylineStagingORM,
    "spread": KaggleSpreadStagingORM,
    "total": KaggleTotalStagingORM,
}
MARKET_DATASETS = {
    "moneyline": "nba-moneyline-observations",
    "spread": "nba-spread-observations",
    "total": "nba-total-observations",
}
MARKET_CONSTRAINTS = {
    "moneyline": "uq_kaggle_moneylines_source_row",
    "spread": "uq_kaggle_spreads_source_row",
    "total": "uq_kaggle_totals_source_row",
}
_BATCH_SIZE = 500


@dataclass(frozen=True)
class MarketCounts:
    source_rows: int
    staged_rows: int
    anomaly_rows: int
    rejected_rows: int
    inserted_staged_rows: int
    inserted_anomaly_rows: int
    inserted_rejected_rows: int


@dataclass(frozen=True)
class KaggleMarketStagingResult:
    markets: Mapping[str, MarketCounts]

    @property
    def total_source_rows(self) -> int:
        return sum(value.source_rows for value in self.markets.values())

    @property
    def total_anomalies(self) -> int:
        return sum(value.anomaly_rows for value in self.markets.values())

    @property
    def total_rejections(self) -> int:
        return sum(value.rejected_rows for value in self.markets.values())

    @property
    def total_inserted_rows(self) -> int:
        return sum(
            value.inserted_staged_rows
            + value.inserted_anomaly_rows
            + value.inserted_rejected_rows
            for value in self.markets.values()
        )

    def details(self) -> Dict[str, Any]:
        return {
            "total_source_rows": self.total_source_rows,
            "total_anomaly_rows": self.total_anomalies,
            "total_rejected_rows": self.total_rejections,
            "total_inserted_rows": self.total_inserted_rows,
            "market_counts": {
                market: value.__dict__ for market, value in self.markets.items()
            },
        }


def _batches(values: Sequence[Mapping[str, Any]]) -> Iterable[Sequence[Mapping[str, Any]]]:
    for start in range(0, len(values), _BATCH_SIZE):
        yield values[start : start + _BATCH_SIZE]


def _insert(session, model, constraint: str, payloads) -> int:
    inserted = 0
    for batch in _batches(payloads):
        statement = (
            pg_insert(model)
            .values(list(batch))
            .on_conflict_do_nothing(constraint=constraint)
        )
        inserted += int(session.execute(statement).rowcount or 0)
    return inserted


def _manifest(session, import_id: str) -> ExternalDatasetImportORM:
    manifest = session.get(ExternalDatasetImportORM, import_id)
    if manifest is None:
        raise ValueError(f"Unknown external dataset manifest: {import_id}")
    return manifest


def _validate_manifest(
    manifest: ExternalDatasetImportORM,
    artifact,
    *,
    expected_dataset: str,
) -> None:
    expected = {
        "source_name": EXPECTED_SOURCE_NAME,
        "dataset_name": expected_dataset,
        "file_name": artifact.file_name,
        "sha256": artifact.sha256,
        "source_row_count": artifact.source_row_count,
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
            f"Manifest is not eligible for {expected_dataset} staging: "
            + ", ".join(sorted(set(mismatches)))
        )


def _source_game_keys(session, game_manifest_id: str):
    manifest = _manifest(session, game_manifest_id)
    _expected = {
        "source_name": EXPECTED_SOURCE_NAME,
        "dataset_name": "nba-team-game-facts",
        "license_status": "approved_public",
        "commercial_use_status": "permitted",
    }
    mismatches = [
        field
        for field, expected_value in _expected.items()
        if getattr(manifest, field) != expected_value
    ]
    if mismatches:
        raise ValueError(
            "Game manifest is not eligible for market staging: "
            + ", ".join(sorted(mismatches))
        )
    rows = (
        session.query(
            KaggleGameStagingORM.game_id,
            KaggleGameStagingORM.team_id,
            KaggleGameStagingORM.opponent_team_id,
        )
        .filter(
            KaggleGameStagingORM.source_import_id == game_manifest_id,
            KaggleGameStagingORM.parser_version == GAME_PARSER_VERSION,
        )
        .all()
    )
    if len(rows) != manifest.source_row_count:
        raise ValueError("Verified Kaggle game staging is incomplete")
    return {(game_id, team_id, opponent_id) for game_id, team_id, opponent_id in rows}


def _validate_source_game_membership(artifacts, game_keys) -> None:
    missing = []
    for market, artifact in artifacts.items():
        for partition in (artifact.rows, artifact.anomalies):
            for row in partition:
                key = (row["game_id"], row["team_id"], row["opponent_team_id"])
                if key not in game_keys:
                    missing.append((market, row["source_row_number"], key))
                    if len(missing) >= 10:
                        break
            if len(missing) >= 10:
                break
        if len(missing) >= 10:
            break
    if missing:
        raise ValueError(f"Market rows do not match staged source games: {missing}")


def _verify_partition(session, market, import_id, artifact):
    model = MARKET_MODELS[market]
    staged = dict(
        session.query(model.source_row_number, model.row_sha256)
        .filter(
            model.source_import_id == import_id,
            model.parser_version == MARKET_PARSER_VERSION,
        )
        .all()
    )
    anomalies = dict(
        session.query(
            ExternalMarketAnomalyORM.source_row_number,
            ExternalMarketAnomalyORM.row_sha256,
        )
        .filter(
            ExternalMarketAnomalyORM.source_import_id == import_id,
            ExternalMarketAnomalyORM.parser_version == MARKET_PARSER_VERSION,
        )
        .all()
    )
    rejected = dict(
        session.query(
            ExternalRowRejectionORM.source_row_number,
            ExternalRowRejectionORM.row_sha256,
        )
        .filter(
            ExternalRowRejectionORM.source_import_id == import_id,
            ExternalRowRejectionORM.parser_version == MARKET_PARSER_VERSION,
        )
        .all()
    )
    expected = [
        {
            int(row["source_row_number"]): str(row["row_sha256"])
            for row in partition
        }
        for partition in (artifact.rows, artifact.anomalies, artifact.rejections)
    ]
    if set(staged) & set(anomalies) or set(staged) & set(rejected) or set(anomalies) & set(rejected):
        raise ValueError(f"Persisted {market} partitions overlap")
    if [staged, anomalies, rejected] != expected:
        raise ValueError(f"Persisted {market} partitions do not match the artifact")
    return len(staged), len(anomalies), len(rejected)


def stage_kaggle_markets(
    *,
    source_run_id: str,
    game_manifest_id: str,
    market_manifests: Mapping[str, str],
    artifacts: Mapping[str, Any],
) -> KaggleMarketStagingResult:
    """Validate and persist all three market artifacts in one transaction."""
    try:
        uuid.UUID(source_run_id)
        uuid.UUID(game_manifest_id)
        for value in market_manifests.values():
            uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("All manifest and run IDs must be UUIDs") from exc
    if set(artifacts) != set(MARKET_MODELS) or set(market_manifests) != set(MARKET_MODELS):
        raise ValueError("moneyline, spread, and total must be staged together")

    with get_db_context() as session:
        game_keys = _source_game_keys(session, game_manifest_id)
        manifests = {}
        for market, artifact in artifacts.items():
            if artifact.source_row_count != (
                len(artifact.rows) + len(artifact.anomalies) + len(artifact.rejections)
            ):
                raise ValueError(f"{market} partitions do not cover the source file")
            manifest = _manifest(session, market_manifests[market])
            _validate_manifest(
                manifest, artifact, expected_dataset=MARKET_DATASETS[market]
            )
            manifests[market] = manifest
        _validate_source_game_membership(artifacts, game_keys)

        results = {}
        for market, artifact in artifacts.items():
            import_id = market_manifests[market]
            manifest = manifests[market]
            common = {
                "source_import_id": import_id,
                "source_game_import_id": game_manifest_id,
                "source_game_parser_version": GAME_PARSER_VERSION,
                "source_run_id": source_run_id,
                "source_dataset_version": manifest.dataset_version,
                "source_file_name": manifest.file_name,
                "parser_version": MARKET_PARSER_VERSION,
            }
            staged_payloads = [
                {"staging_row_id": str(uuid.uuid4()), **common, **dict(row)}
                for row in artifact.rows
            ]
            anomaly_payloads = [
                {
                    "anomaly_id": str(uuid.uuid4()),
                    "source_import_id": import_id,
                    "source_game_import_id": game_manifest_id,
                    "source_run_id": source_run_id,
                    "source_file_name": manifest.file_name,
                    "source_row_number": row["source_row_number"],
                    "row_sha256": row["row_sha256"],
                    "game_id": row["game_id"],
                    "market": row["market"],
                    "reason_code": row["reason_code"],
                    "reason_detail": row["reason_detail"],
                    "raw_values": row["raw_values"],
                    "parser_version": MARKET_PARSER_VERSION,
                }
                for row in artifact.anomalies
            ]
            rejection_payloads = [
                {
                    "rejection_id": str(uuid.uuid4()),
                    "source_import_id": import_id,
                    "source_run_id": source_run_id,
                    "source_file_name": manifest.file_name,
                    "parser_version": MARKET_PARSER_VERSION,
                    **dict(row),
                }
                for row in artifact.rejections
            ]
            inserted_staged = _insert(
                session,
                MARKET_MODELS[market],
                MARKET_CONSTRAINTS[market],
                staged_payloads,
            )
            inserted_anomalies = _insert(
                session,
                ExternalMarketAnomalyORM,
                "uq_external_market_anomaly_source_row",
                anomaly_payloads,
            )
            inserted_rejections = _insert(
                session,
                ExternalRowRejectionORM,
                "uq_external_row_rejection_source_row",
                rejection_payloads,
            )
            staged, anomalies, rejected = _verify_partition(
                session, market, import_id, artifact
            )
            results[market] = MarketCounts(
                source_rows=artifact.source_row_count,
                staged_rows=staged,
                anomaly_rows=anomalies,
                rejected_rows=rejected,
                inserted_staged_rows=inserted_staged,
                inserted_anomaly_rows=inserted_anomalies,
                inserted_rejected_rows=inserted_rejections,
            )
        return KaggleMarketStagingResult(markets=results)
