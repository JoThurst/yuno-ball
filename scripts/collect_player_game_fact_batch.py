"""Run one deterministic Program C7 Traditional -> Advanced batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db_context
from app.models.ingestion_run_sqlalchemy import IngestionRunORM, IngestionTaskRunORM
from app.services.ingestion_run_service import IngestionRunTracker, PIPELINE_LOCK_NAME
from app.services.player_game_advanced_fact_service import publish_advanced_facts
from app.services.player_game_fact_batch_service import collect_player_game_batch
from app.services.player_game_fact_collection_service import (
    resolve_completed_game_specs,
)
from app.services.player_game_fact_coverage_service import (
    build_player_game_fact_coverage_report,
)
from app.services.player_game_fact_ingestion_service import publish_player_game_facts
from app.services.player_game_fact_reconciliation_service import (
    build_reconciliation_report,
)
from app.services.player_game_fact_replay_service import (
    replay_published_player_game_facts,
)
from app.services.player_identity_service import (
    fetch_player_identity_record,
    missing_player_ids,
    upsert_player_identity_records,
)


C7_BACKFILL_LOCK = "yunoball:program_c7_player_game_fact_backfill"


def _load_game_ids(db, args) -> tuple[list[str], int | None]:
    if args.replay_task_id:
        task = db.get(IngestionTaskRunORM, args.replay_task_id)
        if task is None:
            raise ValueError(f"Unknown ingestion task: {args.replay_task_id}")
        details = task.details or {}
        manifest = details.get("replay_manifest")
        from app.services.player_game_fact_daily_service import (
            validate_daily_player_fact_replay_manifest,
        )

        validate_daily_player_fact_replay_manifest(manifest or {}, max_games=args.max_games)
        if manifest.get("task_run_id") != task.task_run_id or manifest.get("run_id") != task.run_id:
            raise ValueError("Daily task manifest identity does not match its durable task row")
        candidates = [
            batch for batch in manifest["batches"]
            if batch.get("batch") == args.batch_number
        ]
        if len(candidates) != 1:
            raise ValueError("Daily task manifest does not identify exactly one requested batch")
        batch = candidates[0]
        if batch.get("status") != "completed":
            raise ValueError("Only an atomically completed daily batch can be replayed")
        for family in ("traditional", "advanced"):
            entries = batch.get(family)
            if not isinstance(entries, list) or {str(row.get("game_id")) for row in entries} != set(map(str, batch["game_ids"])):
                raise ValueError(f"Daily manifest has ambiguous {family} evidence for the requested batch")
            if any(
                not isinstance(row.get("response_sha256"), str)
                or len(row["response_sha256"]) != 64
                or not row.get("retrieved_at")
                for row in entries
            ):
                raise ValueError(f"Daily manifest is missing {family} response hash or retrieval time")
        args.season = manifest["season"]
        args.season_type = manifest["season_type"]
        args.expected_response_hashes = {
            family: {
                str(row["game_id"]): row["response_sha256"]
                for row in batch[family]
            }
            for family in ("traditional", "advanced")
        }
        return [str(game_id) for game_id in batch["game_ids"]], args.batch_number

    if args.replay_run_id:
        run = db.get(IngestionRunORM, args.replay_run_id)
        if run is None:
            raise ValueError(f"Unknown ingestion run: {args.replay_run_id}")
        game_ids = (run.details or {}).get("game_ids")
        if not isinstance(game_ids, list) or not game_ids:
            raise ValueError("The ingestion run does not contain a replayable game_ids manifest")
        return [str(game_id) for game_id in game_ids], None

    report = build_player_game_fact_coverage_report(
        db,
        season=args.season,
        season_type=args.season_type,
        max_batch_size=args.max_games,
    )
    batches = report["traditional_backfill_batches"]
    if args.batch < 1 or args.batch > len(batches):
        raise ValueError(f"batch must be between 1 and {len(batches)}")
    return batches[args.batch - 1], args.batch


def main() -> int:
    parser = argparse.ArgumentParser()
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--batch", type=int, help="1-based pending batch from the coverage inventory")
    selector.add_argument("--replay-run-id", help="replay the exact game manifest stored by a prior run")
    selector.add_argument("--replay-task-id", help="replay one completed batch from a daily player-facts task manifest")
    parser.add_argument("--batch-number", type=int, help="1-based batch number required with --replay-task-id")
    parser.add_argument(
        "--network-replay",
        action="store_true",
        help="refetch the replay manifest from NBA endpoints; default replay is database-only",
    )
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--max-games", type=int, default=25)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.replay_task_id and not args.batch_number:
        parser.error("--batch-number is required with --replay-task-id")
    if args.batch_number and not args.replay_task_id:
        parser.error("--batch-number requires --replay-task-id")
    if not 1 <= args.max_games <= 25:
        parser.error("--max-games must be between 1 and 25")

    from app.services.player_game_fact_collection_service import validate_game_bound

    with get_db_context() as db:
        game_ids, batch_number = _load_game_ids(db, args)
        game_ids = validate_game_bound(game_ids, max_games=args.max_games)
        specs = resolve_completed_game_specs(
            db,
            game_ids,
            season=args.season,
            season_type=args.season_type,
        )

    run_id = str(uuid.uuid4())
    if args.dry_run:
        collected = collect_player_game_batch(
            specs,
            run_id=run_id,
            max_games=args.max_games,
        )
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "batch": batch_number,
                    "game_ids": game_ids,
                    "run_id": run_id,
                    "traditional": collected["traditional_games"],
                    "advanced": collected["advanced_games"],
                    "traditional_player_rows": len(collected["traditional_facts"]),
                    "advanced_player_rows": len(collected["advanced_facts"]),
                },
                default=str,
                sort_keys=True,
            )
        )
        return 0

    target_date = min(spec.game_date for spec in specs)
    details = {
        "batch": batch_number,
        "replay_run_id": args.replay_run_id,
        "replay_task_id": args.replay_task_id,
        "game_ids": game_ids,
        "max_games": args.max_games,
        "stages": ["traditional", "advanced", "reconciliation"],
    }
    with IngestionRunTracker(
        run_type="program_c7_player_game_fact_batch",
        source="nba_boxscore_traditional_v3+advanced_v3",
        season=args.season,
        target_date=target_date,
        season_type=args.season_type,
        provider="nba_api",
        details=details,
        lock_name=PIPELINE_LOCK_NAME if args.replay_task_id else C7_BACKFILL_LOCK,
    ) as tracker:
        replay = None
        if (args.replay_run_id or args.replay_task_id) and not args.network_replay:
            with get_db_context() as db:
                replay = replay_published_player_game_facts(
                    db,
                    game_ids=game_ids,
                    season=args.season,
                    season_type=args.season_type,
                    max_games=args.max_games,
                    expected_response_hashes=getattr(args, "expected_response_hashes", None),
                )
                traditional_counts = replay["traditional_counts"]
                advanced_counts = replay["advanced_counts"]
                collected = {
                    "traditional_games": [],
                    "advanced_games": [],
                }
        else:
            # Keep external calls outside database transactions. A slow proxy
            # or provider failure must not hold a DB transaction open.
            collected = collect_player_game_batch(
                specs,
                run_id=tracker.run_id,
                max_games=args.max_games,
            )
            expected_hashes = getattr(args, "expected_response_hashes", None)
            if expected_hashes:
                for family in ("traditional", "advanced"):
                    actual = {
                        str(row["game_id"]): row["response_sha256"]
                        for row in collected[f"{family}_games"]
                    }
                    if actual != expected_hashes[family]:
                        raise ValueError(
                            f"{family} provider response hash changed; stop for correction review"
                        )
            facts_by_player: dict[int, list[dict]] = {}
            for fact in collected["traditional_facts"]:
                facts_by_player.setdefault(int(fact["canonical_player_id"]), []).append(fact)
            player_ids = sorted(facts_by_player)
            with get_db_context() as db:
                missing_ids = missing_player_ids(db, player_ids)
            source_only_dnp_ids = [
                player_id
                for player_id in missing_ids
                if all(
                    fact["participation_status"] == "did_not_play"
                    for fact in facts_by_player[player_id]
                )
            ]
            identity_records = []
            for player_id in missing_ids:
                identity_records.append(
                    fetch_player_identity_record(
                        player_id,
                        season=args.season,
                        require_active_season=player_id not in source_only_dnp_ids,
                    )
                )
            identity_counts = {
                "requested": len(missing_ids),
                "created": 0,
                "updated": 0,
                "source_only_dnp_ids": source_only_dnp_ids,
            }
            with get_db_context() as db:
                if identity_records:
                    identity_counts.update(upsert_player_identity_records(db, identity_records))
                    db.commit()
                traditional_counts = publish_player_game_facts(
                    collected["traditional_facts"], db=db
                )
                advanced_counts = publish_advanced_facts(
                    collected["advanced_facts"], db=db
                )
            details["identity_resolution"] = identity_counts
        if (args.replay_run_id or args.replay_task_id) and not args.network_replay:
            details["identity_resolution"] = {"requested": 0, "created": 0, "updated": 0}
        with get_db_context() as db:
            reconciliation = (
                replay["reconciliation"]
                if replay is not None
                else build_reconciliation_report(
                    db,
                    season=args.season,
                    game_ids=game_ids,
                    max_games=args.max_games,
                )
            )
            if reconciliation["status"] != "passed":
                raise ValueError(
                    f"C5 reconciliation failed for batch: {reconciliation}"
                )
        result = {
            **details,
            "run_id": tracker.run_id,
            "traditional_counts": traditional_counts,
            "advanced_counts": advanced_counts,
            "traditional": collected["traditional_games"],
            "advanced": collected["advanced_games"],
            "reconciliation": reconciliation,
        }
        tracker.finish(
            "success",
            validation_status="passed",
            rows_read=(
                len(collected.get("traditional_facts", []))
                + len(collected.get("advanced_facts", []))
            ),
            rows_written=(
                traditional_counts["revisions_created"]
                + traditional_counts["facts_created"]
                + traditional_counts["facts_updated"]
                + advanced_counts["revisions_created"]
                + advanced_counts["facts_created"]
                + advanced_counts["facts_updated"]
            ),
            details=result,
        )
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
