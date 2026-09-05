"""Daily, bounded bridge from completed games to canonical player facts.

The historical C7 script remains useful for reviewed backfills.  This service
owns the smaller operational path: select completed games that are missing a
canonical source, fetch Traditional before Advanced, publish atomically per
batch, and require C5 reconciliation before moving to the next batch.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import uuid
from typing import Any, Iterable, Mapping, Sequence

from app.database import get_db_context
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
from app.services.player_identity_service import (
    fetch_player_identity_record,
    missing_player_ids,
    upsert_player_identity_records,
)


DAILY_FACT_BATCH_SIZE = 25
REGULAR_SEASON = "Regular Season"


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
        db.commit()

    with get_db_context() as db:
        reconciliation = build_reconciliation_report(
            db,
            season=season,
            game_ids=game_ids,
            max_games=max_games,
        )
    if reconciliation["status"] != "passed":
        raise ValueError(f"C5 reconciliation failed for daily batch: {reconciliation}")
    return {
        "identity_resolution": identity,
        "traditional_counts": traditional_counts,
        "advanced_counts": advanced_counts,
        "reconciliation": reconciliation,
        "traditional": collected["traditional_games"],
        "advanced": collected["advanced_games"],
    }


def collect_daily_player_game_facts(
    *,
    season: str,
    run_id: str | None,
    season_type: str = REGULAR_SEASON,
    max_games_per_batch: int = DAILY_FACT_BATCH_SIZE,
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
    results: list[dict[str, Any]] = []
    for batch_number, game_ids in enumerate(batches, start=1):
        with get_db_context() as db:
            specs = resolve_completed_game_specs(
                db,
                game_ids,
                season=season,
                season_type=season_type,
            )
        collected = collect_player_game_batch(
            specs,
            run_id=lineage_run_id,
            max_games=max_games_per_batch,
        )
        batch_result = _publish_and_reconcile(
            collected,
            season=season,
            game_ids=game_ids,
            max_games=max_games_per_batch,
        )
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
    }
