"""Daily, bounded bridge from completed games to canonical player facts.

The historical C7 script remains useful for reviewed backfills.  This service
owns the smaller operational path: select completed games that are missing a
canonical source, fetch Traditional before Advanced, publish atomically per
batch, and require C5 reconciliation before moving to the next batch.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import uuid
from typing import Any, Iterable, Mapping, Sequence

from app.database import get_db_context
from app.models.ingestion_run_sqlalchemy import IngestionTaskRunORM
from app.services.player_game_fact_batch_service import collect_player_game_batch
from app.services.player_game_fact_collection_service import (
    CompletedGameSpec,
    resolve_completed_game_specs,
)
from app.services.player_game_fact_coverage_service import (
    build_player_game_fact_coverage_report,
)
from app.services.player_game_fact_ingestion_service import publish_player_game_facts
from app.services.player_game_advanced_fact_service import publish_advanced_facts
from app.services.player_game_fact_reconciliation_service import (
    build_reconciliation_report,
)
from app.services.player_role_baseline_service import (
    publish_role_history,
    role_history_records_from_facts,
)
from app.services.player_identity_service import (
    fetch_player_identity_record,
    missing_player_ids,
    upsert_player_identity_records,
)


DAILY_FACT_BATCH_SIZE = 25
REGULAR_SEASON = "Regular Season"
DAILY_FACT_MANIFEST_VERSION = "daily-player-facts-v1"


def build_daily_player_fact_replay_manifest(
    *,
    run_id: str | None,
    task_run_id: str | None = None,
    season: str,
    season_type: str,
    batches: Sequence[Mapping[str, Any]],
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    """Build the durable, explicit scope for a daily player-fact replay.

    This is intentionally derived only from completed provider results.  A
    batch is a replay unit; its game IDs are never flattened into a wider
    season scope.
    """
    if status not in {"running", "completed", "partial", "failed"}:
        raise ValueError(f"Unsupported daily manifest status: {status}")
    manifest = {
        "manifest_version": DAILY_FACT_MANIFEST_VERSION,
        "run_id": run_id,
        "task_run_id": task_run_id,
        "season": season,
        "season_type": season_type,
        "provider": "nba_api",
        "endpoints": {
            "traditional": "BoxScoreTraditionalV3",
            "advanced": "BoxScoreAdvancedV3",
        },
        "status": status,
        "batches": [dict(batch) for batch in batches],
    }
    if error:
        manifest["error"] = error[:500]
    return manifest


def validate_daily_player_fact_replay_manifest(
    manifest: Mapping[str, Any], *, max_games: int = DAILY_FACT_BATCH_SIZE
) -> list[str]:
    """Return one exact manifest scope, rejecting absent or ambiguous scope."""
    if manifest.get("manifest_version") != DAILY_FACT_MANIFEST_VERSION:
        raise ValueError("Unsupported or absent daily player-fact manifest version")
    if manifest.get("status") not in {"completed", "partial", "failed", "running"}:
        raise ValueError("Daily player-fact manifest has an unsupported status")
    if not manifest.get("run_id") or not manifest.get("task_run_id"):
        raise ValueError("Daily player-fact manifest is missing run or task identity")
    if manifest.get("provider") != "nba_api" or manifest.get("endpoints") != {
        "traditional": "BoxScoreTraditionalV3",
        "advanced": "BoxScoreAdvancedV3",
    }:
        raise ValueError("Daily player-fact manifest has unsupported provider endpoints")
    if not manifest.get("season") or not manifest.get("season_type"):
        raise ValueError("Daily player-fact manifest is missing season scope")
    batches = manifest.get("batches")
    if not isinstance(batches, list):
        raise ValueError("Daily player-fact manifest batches must be a list")
    if not batches:
        raise ValueError("Daily player-fact manifest has no replayable batches")
    game_ids: list[str] = []
    batch_numbers: set[int] = set()
    attempt_ids: set[str] = set()
    for batch in batches:
        if not isinstance(batch, Mapping):
            raise ValueError("Daily player-fact manifest contains an invalid batch")
        batch_ids = batch.get("game_ids")
        if not isinstance(batch_ids, list) or not batch_ids:
            raise ValueError("Daily player-fact manifest contains an empty batch")
        if any(not isinstance(game_id, str) or not game_id.strip() for game_id in batch_ids):
            raise ValueError("Daily player-fact manifest contains an invalid game ID")
        if len(batch_ids) > max_games:
            raise ValueError("Daily player-fact manifest batch exceeds the replay bound")
        if batch.get("status") not in {"planned", "collecting", "collected", "publishing", "completed", "failed"}:
            raise ValueError("Daily player-fact manifest contains an unsupported batch status")
        batch_number = batch.get("batch")
        attempt_id = batch.get("attempt_id")
        if not isinstance(batch_number, int) or batch_number < 1 or batch_number in batch_numbers:
            raise ValueError("Daily player-fact manifest has ambiguous batch numbering")
        if not isinstance(attempt_id, str) or not attempt_id or attempt_id in attempt_ids:
            raise ValueError("Daily player-fact manifest has ambiguous attempt identity")
        batch_numbers.add(batch_number)
        attempt_ids.add(attempt_id)
        if batch.get("status") == "completed":
            expected_ids = set(map(str, batch_ids))
            for family in ("traditional", "advanced"):
                evidence = batch.get(family)
                if not isinstance(evidence, list) or len(evidence) != len(expected_ids := set(map(str, batch_ids))) or {
                    str(entry.get("game_id")) for entry in evidence
                } != expected_ids:
                    raise ValueError(f"Completed daily batch lacks exact {family} evidence")
                if any(
                    not isinstance(entry.get("response_sha256"), str)
                    or len(entry["response_sha256"]) != 64
                    or any(char not in "0123456789abcdef" for char in entry["response_sha256"])
                    or not entry.get("retrieved_at")
                    for entry in evidence
                ):
                    raise ValueError(f"Completed daily batch lacks {family} hash or retrieval time")
                for entry in evidence:
                    try:
                        retrieved_at = datetime.fromisoformat(
                            str(entry["retrieved_at"]).replace("Z", "+00:00")
                        )
                    except ValueError as exc:
                        raise ValueError(f"Completed daily batch has invalid {family} retrieval time") from exc
                    if retrieved_at.tzinfo is None:
                        raise ValueError(f"Completed daily batch has naive {family} retrieval time")
        normalized = [str(game_id) for game_id in batch_ids]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Daily player-fact manifest contains duplicate game IDs")
        game_ids.extend(normalized)
    if len(set(game_ids)) != len(game_ids):
        raise ValueError("Daily player-fact manifest overlaps multiple batches")
    if batch_numbers != set(range(1, len(batches) + 1)):
        raise ValueError("Daily player-fact manifest batch numbering is incomplete")
    if manifest["status"] == "completed" and any(
        batch.get("status") != "completed" for batch in batches
    ):
        raise ValueError("Completed daily manifest contains an incomplete batch")
    return game_ids


def _manifest_details(
    manifest: Mapping[str, Any], *, pending_games: int, blocked_games: int,
    eligible_completed_games: int,
) -> dict[str, Any]:
    return {
        "status": manifest["status"],
        "season": manifest["season"],
        "season_type": manifest["season_type"],
        "pending_games": pending_games,
        "blocked_games": blocked_games,
        "eligible_completed_games": eligible_completed_games,
        "replay_manifest": dict(manifest),
    }


def _persist_task_details(task_run_id: str, details: Mapping[str, Any]) -> None:
    with get_db_context() as db:
        task = db.get(IngestionTaskRunORM, task_run_id)
        if task is None or task.status != "running":
            raise ValueError(f"Daily player-fact task is not running: {task_run_id}")
        task.details = dict(details)


def select_pending_completed_game_ids(
    schedule_rows: Iterable[Any],
    traditional_game_ids: Iterable[str],
    advanced_game_ids: Iterable[str],
) -> list[str]:
    """Select completed reciprocal games missing either canonical source.

    This pure selector is deliberately small so the daily eligibility rule is
    testable without a database or network call.  Team-stat availability is
    checked by the coverage inventory before this selector is used in the
    operational path.
    """
    traditional = {str(game_id) for game_id in traditional_game_ids}
    advanced = {str(game_id) for game_id in advanced_game_ids}
    by_game: dict[str, list[Any]] = defaultdict(list)
    for row in schedule_rows:
        by_game[str(row.game_id)].append(row)

    pending: list[tuple[date, str]] = []
    for game_id, rows in by_game.items():
        if len(rows) != 2:
            continue
        first, second = rows
        first_date = first.game_date.date() if hasattr(first.game_date, "date") else first.game_date
        second_date = second.game_date.date() if hasattr(second.game_date, "date") else second.game_date
        completed_reciprocal = (
            first.team_id == second.opponent_team_id
            and second.team_id == first.opponent_team_id
            and first_date == second_date
            and first.result in {"W", "L"}
            and second.result in {"W", "L"}
        )
        if completed_reciprocal and (
            game_id not in traditional or game_id not in advanced
        ):
            pending.append((first_date, game_id))
    return [game_id for _, game_id in sorted(pending)]


def _inventory(db, *, season: str, season_type: str) -> dict[str, Any]:
    report = build_player_game_fact_coverage_report(
        db,
        season=season,
        season_type=season_type,
        max_batch_size=DAILY_FACT_BATCH_SIZE,
    )
    pending = [
        row["game_id"]
        for row in report["games"]
        if row["state"] in {"traditional_missing", "advanced_missing"}
    ]
    return {
        "report": report,
        "pending_game_ids": pending,
        "blocked_game_ids": [
            row["game_id"]
            for row in report["games"]
            if row["state"] == "blocked_team_stats"
        ],
    }


def _resolve_missing_players(
    facts: Sequence[Mapping[str, Any]],
    *,
    season: str,
) -> dict[str, Any]:
    facts_by_player: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for fact in facts:
        facts_by_player[int(fact["canonical_player_id"])].append(fact)
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
    records = [
        fetch_player_identity_record(
            player_id,
            season=season,
            require_active_season=player_id not in source_only_dnp_ids,
        )
        for player_id in missing_ids
    ]
    counts = {
        "requested": len(missing_ids),
        "created": 0,
        "updated": 0,
        "source_only_dnp_ids": source_only_dnp_ids,
    }
    with get_db_context() as db:
        if records:
            counts.update(upsert_player_identity_records(db, records))
            db.commit()
    return counts


def _publish_and_reconcile(
    collected: Mapping[str, Any],
    *,
    season: str,
    game_ids: Sequence[str],
    max_games: int,
    task_run_id: str | None = None,
    task_details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity = _resolve_missing_players(
        collected["traditional_facts"],
        season=season,
    )
    with get_db_context() as db:
        traditional_counts = publish_player_game_facts(
            collected["traditional_facts"],
            db=db,
        )
        advanced_counts = publish_advanced_facts(
            collected["advanced_facts"],
            db=db,
        )
        reconciliation = build_reconciliation_report(
            db,
            season=season,
            game_ids=game_ids,
            max_games=max_games,
        )
        if reconciliation["status"] != "passed":
            raise ValueError(f"C5 reconciliation failed for daily batch: {reconciliation}")
        role_history_rows = publish_role_history(
            role_history_records_from_facts(collected["traditional_facts"]),
            db=db,
        )
        if task_run_id and task_details is not None:
            task = db.get(IngestionTaskRunORM, task_run_id)
            if task is None or task.status != "running":
                raise ValueError(f"Daily player-fact task is not running: {task_run_id}")
            task.details = dict(task_details)
    return {
        "identity_resolution": identity,
        "traditional_counts": traditional_counts,
        "advanced_counts": advanced_counts,
        "reconciliation": reconciliation,
        "role_history_rows": role_history_rows,
        "traditional": collected["traditional_games"],
        "advanced": collected["advanced_games"],
    }


def collect_daily_player_game_facts(
    *,
    season: str,
    run_id: str | None,
    season_type: str = REGULAR_SEASON,
    max_games_per_batch: int = DAILY_FACT_BATCH_SIZE,
    task_run_id: str | None = None,
) -> dict[str, Any]:
    """Ingest all currently pending completed games in reviewed-size batches."""
    if not 1 <= max_games_per_batch <= DAILY_FACT_BATCH_SIZE:
        raise ValueError(
            f"max_games_per_batch must be between 1 and {DAILY_FACT_BATCH_SIZE}"
        )
    lineage_run_id = run_id or str(uuid.uuid4())

    with get_db_context() as db:
        inventory = _inventory(db, season=season, season_type=season_type)
    report = inventory["report"]
    pending_game_ids = inventory["pending_game_ids"]
    if not pending_game_ids:
        return {
            "status": "no_op",
            "season": season,
            "season_type": season_type,
            "pending_games": 0,
            "blocked_games": len(inventory["blocked_game_ids"]),
            "eligible_completed_games": report["eligible_completed_games"],
            "batches": [],
        }

    batches = [
        pending_game_ids[index : index + max_games_per_batch]
        for index in range(0, len(pending_game_ids), max_games_per_batch)
    ]
    planned_batches = [
        {
            "batch": index,
            "attempt_id": str(uuid.uuid4()),
            "status": "planned",
            "game_ids": list(game_ids),
            "traditional": [],
            "advanced": [],
        }
        for index, game_ids in enumerate(batches, start=1)
    ]
    manifest = build_daily_player_fact_replay_manifest(
        run_id=lineage_run_id,
        task_run_id=task_run_id,
        season=season,
        season_type=season_type,
        batches=planned_batches,
        status="running",
    )
    task_details = _manifest_details(
        manifest,
        pending_games=len(pending_game_ids),
        blocked_games=len(inventory["blocked_game_ids"]),
        eligible_completed_games=report["eligible_completed_games"],
    )
    if task_run_id:
        _persist_task_details(task_run_id, task_details)

    results: list[dict[str, Any]] = []
    for batch_number, game_ids in enumerate(batches, start=1):
        batch_manifest = planned_batches[batch_number - 1]
        batch_manifest["status"] = "collecting"
        task_details["replay_manifest"] = dict(manifest, batches=[dict(batch) for batch in planned_batches])
        if task_run_id:
            _persist_task_details(task_run_id, task_details)
        with get_db_context() as db:
            specs = resolve_completed_game_specs(
                db,
                game_ids,
                season=season,
                season_type=season_type,
            )
        try:
            def record_family(family: str, evidence: list[dict[str, Any]]) -> None:
                batch_manifest[family] = evidence
                batch_manifest[f"{family}_retrieved_at"] = datetime.now(timezone.utc).isoformat()
                task_details["replay_manifest"] = dict(
                    manifest,
                    batches=[dict(batch) for batch in planned_batches],
                )
                if task_run_id:
                    _persist_task_details(task_run_id, task_details)

            collected = collect_player_game_batch(
                specs,
                # Fact revisions reference the durable parent ingestion run;
                # attempt_id remains the per-batch identity in this manifest.
                run_id=lineage_run_id,
                max_games=max_games_per_batch,
                progress_callback=record_family,
            )
        except Exception as exc:
            batch_manifest["status"] = "failed"
            batch_manifest["error"] = str(exc)[:500]
            manifest = dict(manifest, status="partial" if results else "failed", batches=[dict(batch) for batch in planned_batches])
            task_details["replay_manifest"] = manifest
            if task_run_id:
                _persist_task_details(task_run_id, task_details)
            raise
        batch_manifest.update(
            {
                "status": "collected",
                "traditional": collected["traditional_games"],
                "advanced": collected["advanced_games"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        manifest = dict(manifest, batches=[dict(batch) for batch in planned_batches])
        task_details["replay_manifest"] = manifest
        if task_run_id:
            _persist_task_details(task_run_id, task_details)
        batch_manifest["status"] = "publishing"
        task_details["replay_manifest"] = dict(manifest, batches=[dict(batch) for batch in planned_batches])
        if task_run_id:
            _persist_task_details(task_run_id, task_details)
        final_manifest = dict(
            manifest,
            status="completed" if batch_number == len(batches) else "running",
            batches=[
                dict(batch, status="completed") if batch is batch_manifest else dict(batch)
                for batch in planned_batches
            ],
        )
        final_details = _manifest_details(
            final_manifest,
            pending_games=len(pending_game_ids),
            blocked_games=len(inventory["blocked_game_ids"]),
            eligible_completed_games=report["eligible_completed_games"],
        )
        batch_result = _publish_and_reconcile(
            collected,
            season=season,
            game_ids=game_ids,
            max_games=max_games_per_batch,
            task_run_id=task_run_id,
            task_details=final_details,
        )
        batch_manifest["status"] = "completed"
        results.append(
            {
                "batch": batch_number,
                "game_ids": list(game_ids),
                **batch_result,
            }
        )

    return {
        "status": "completed",
        "season": season,
        "season_type": season_type,
        "pending_games": len(pending_game_ids),
        "blocked_games": len(inventory["blocked_game_ids"]),
        "eligible_completed_games": report["eligible_completed_games"],
        "batches": results,
        "replay_manifest": dict(manifest, status="completed", batches=[dict(batch) for batch in planned_batches]),
    }
