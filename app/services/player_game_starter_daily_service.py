"""Bounded daily publication of explicit Live BoxScore starter evidence."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_starter_evidence_sqlalchemy import (
    PlayerGameStarterEvidenceORM,
)
from app.models.player_sqlalchemy import PlayerORM
from app.services.starter_evidence_fetch_service import fetch_starter_evidence
from app.services.player_game_starter_evidence_service import publish_starter_evidence


DAILY_STARTER_BATCH_SIZE = 25
REGULAR_SEASON = "Regular Season"


def _eligible_games(db, *, season: str, season_type: str) -> list[str]:
    rows = (
        db.query(GameScheduleORM)
        .filter(
            GameScheduleORM.season == season,
            GameScheduleORM.season_type == season_type,
            GameScheduleORM.result.isnot(None),
        )
        .order_by(GameScheduleORM.game_date, GameScheduleORM.game_id)
        .all()
    )
    by_game: dict[str, list[GameScheduleORM]] = defaultdict(list)
    for row in rows:
        by_game[str(row.game_id)].append(row)
    live_evidence = db.query(
        PlayerGameStarterEvidenceORM.canonical_game_id,
        PlayerGameStarterEvidenceORM.canonical_team_id,
        PlayerGameStarterEvidenceORM.starter_status,
    ).filter(
        PlayerGameStarterEvidenceORM.season == season,
        PlayerGameStarterEvidenceORM.season_type == season_type,
    ).all()
    evidence_by_game: dict[str, list[Any]] = defaultdict(list)
    for evidence_game_id, evidence_team_id, starter_status in live_evidence:
        if evidence_game_id:
            evidence_by_game[str(evidence_game_id)].append(
                (evidence_team_id, starter_status)
            )
    existing = {
        game_id
        for game_id, evidence_rows in evidence_by_game.items()
        if len({team_id for team_id, _ in evidence_rows}) == 2
        and sum(status == "starter" for _, status in evidence_rows) == 10
    }
    eligible = []
    for game_id, game_rows in by_game.items():
        if game_id in existing or len(game_rows) != 2:
            continue
        first, second = game_rows
        if (
            first.team_id == second.opponent_team_id
            and second.team_id == first.opponent_team_id
            and first.result in {"W", "L"}
            and second.result in {"W", "L"}
        ):
            eligible.append(game_id)
    return eligible


def collect_daily_starter_evidence(
    *,
    season: str,
    run_id: str | None,
    season_type: str = REGULAR_SEASON,
    max_games_per_batch: int = DAILY_STARTER_BATCH_SIZE,
    pause_seconds: float = 1.0,
) -> dict[str, Any]:
    """Collect at most one reviewed-size batch for the current daily run."""
    if not 1 <= max_games_per_batch <= DAILY_STARTER_BATCH_SIZE:
        raise ValueError(
            f"max_games_per_batch must be between 1 and {DAILY_STARTER_BATCH_SIZE}"
        )
    if pause_seconds < 0:
        raise ValueError("pause_seconds must not be negative")
    if not run_id:
        return {
            "status": "skipped",
            "reason": "starter evidence requires a parent ingestion run for lineage",
            "pending_games": 0,
            "batches": [],
        }

    with get_db_context() as db:
        pending = _eligible_games(db, season=season, season_type=season_type)
    selected = pending[:max_games_per_batch]
    if not selected:
        return {
            "status": "no_op",
            "season": season,
            "season_type": season_type,
            "pending_games": 0,
            "batches": [],
        }

    with get_db_context() as db:
        schedules = {
            (str(row.game_id), int(row.team_id)): row
            for row in db.query(GameScheduleORM).filter(
                GameScheduleORM.season == season,
                GameScheduleORM.season_type == season_type,
                GameScheduleORM.game_id.in_(selected),
            ).all()
        }
        player_ids = {
            int(player_id)
            for (player_id,) in db.query(PlayerORM.player_id).all()
        }

    evidence: list[dict[str, Any]] = []
    effective_sources: set[str] = set()
    fallback_count = 0
    for index, game_id in enumerate(selected):
        fetched = fetch_starter_evidence(
            game_id=game_id,
            season=season,
            season_type=season_type,
            run_id=run_id,
            retrieved_at=datetime.now(timezone.utc),
        )
        rows = fetched.rows
        effective_sources.add(fetched.source_name)
        fallback_count += bool(fetched.fallback_reason)
        for row in rows:
            schedule = schedules.get((game_id, int(row["source_team_id"])))
            if schedule is None:
                raise ValueError(
                    f"Missing exact schedule identity for {game_id}/{row['source_team_id']}"
                )
            row["game_date"] = (
                schedule.game_date.date()
                if hasattr(schedule.game_date, "date")
                else schedule.game_date
            )
            row["canonical_game_id"] = game_id
            row["canonical_team_id"] = int(row["source_team_id"])
            source_player_id = int(row["source_player_id"])
            row["canonical_player_id"] = (
                source_player_id if source_player_id in player_ids else None
            )
        evidence.extend(rows)
        if pause_seconds and index < len(selected) - 1:
            import time

            time.sleep(pause_seconds)

    with get_db_context() as db:
        counts = publish_starter_evidence(evidence, db=db)
    return {
        "status": "completed",
        "season": season,
        "season_type": season_type,
        "pending_games": len(pending),
        "processed_games": len(selected),
        "evidence_rows": len(evidence),
        "starter_rows": sum(row["starter_status"] == "starter" for row in evidence),
        "unknown_rows": sum(row["starter_status"] == "unknown" for row in evidence),
        "effective_sources": sorted(effective_sources),
        "fallback_count": fallback_count,
        "counts": counts,
    }
