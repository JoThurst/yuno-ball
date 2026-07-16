"""Dry-run or apply the exact staged Kaggle playoff schedule promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _plan_payload(plan) -> dict:
    return {
        "source_games": plan.source_games,
        "already_matched_games": plan.already_matched_games,
        "candidate_games": plan.candidate_games,
        "candidate_rows": plan.candidate_row_count,
        "conflict_count": len(plan.conflicts),
        "conflict_samples": list(plan.conflicts[:20]),
    }


def _dry_run(source_import_id: str) -> dict:
    from sqlalchemy import text

    from app.database import engine
    from app.services.kaggle_playoff_promotion_service import (
        load_playoff_promotion_plan,
    )

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            plan = load_playoff_promotion_plan(
                connection,
                source_import_id=source_import_id,
            )
        finally:
            transaction.rollback()
    return {
        "mode": "dry-run",
        "database_write": False,
        "source_import_id": source_import_id,
        **_plan_payload(plan),
    }


def _apply(source_import_id: str) -> dict:
    from app.database import engine
    from app.services.ingestion_run_service import (
        IngestionRunTracker,
        PIPELINE_LOCK_NAME,
    )
    from app.services.kaggle_playoff_promotion_service import (
        apply_playoff_promotion,
    )

    details = {
        "source_import_id": source_import_id,
        "scope": "missing_playoff_schedule_only",
        "identity_policy": "exact_nba_game_id_and_reciprocal_teams",
    }
    with IngestionRunTracker(
        run_type="external_kaggle_playoff_schedule_promotion",
        source="kaggle-uploaded-pack",
        season=None,
        season_type="Playoffs",
        target_date=None,
        provider="registered_external_artifact",
        calculation_version="kaggle-playoff-promotion-v1",
        details=details,
        lock_name=PIPELINE_LOCK_NAME,
    ) as tracker:
        with engine.begin() as connection:
            result = apply_playoff_promotion(
                connection,
                source_import_id=source_import_id,
                source_run_id=tracker.run_id,
            )
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=result.source_games * 2,
            rows_written=(
                result.inserted_schedule_rows
                + result.updated_match_rows
                + result.updated_promoted_rows
            ),
            details={
                **details,
                "already_matched_games": result.already_matched_games,
                "promoted_games": result.promoted_games,
                "inserted_schedule_rows": result.inserted_schedule_rows,
                "updated_match_rows": result.updated_match_rows,
                "updated_promoted_rows": result.updated_promoted_rows,
                "persisted_external_games": result.persisted_external_games,
                "persisted_external_rows": result.persisted_external_rows,
            },
        )
    return {
        "mode": "apply",
        "database_write": True,
        "run_id": tracker.run_id,
        "source_import_id": source_import_id,
        **result.__dict__,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote validated staged Kaggle playoff schedules"
    )
    parser.add_argument("--manifest-id", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = (
            _dry_run(args.manifest_id)
            if args.dry_run
            else _apply(args.manifest_id)
        )
    except Exception as exc:
        print(f"Kaggle playoff promotion failed: {exc}", file=sys.stderr)
        return 3 if type(exc).__name__ == "IngestionRunAlreadyActive" else 1
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
