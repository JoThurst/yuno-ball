"""Database-only idempotency replay for published C7 player-game facts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameAdvancedFactRevisionORM,
    PlayerGameFactORM,
    PlayerGameFactRevisionORM,
)
from app.services.player_game_advanced_fact_service import publish_advanced_facts
from app.services.player_game_fact_ingestion_service import publish_player_game_facts
from app.services.player_game_fact_reconciliation_service import build_reconciliation_report
from app.services.player_role_baseline_service import (
    publish_role_history,
    role_history_records_from_facts,
)


def _revision_values(revision: Any) -> dict[str, Any]:
    return {
        column.name: getattr(revision, column.name)
        for column in revision.__table__.columns
    }


def source_row_set_sha256(facts: list[dict[str, Any]], game_id: str) -> str:
    """Fingerprint the exact canonical player/team keys and source rows for a game."""
    rows = [
        (
            str(fact["canonical_game_id"]),
            int(fact["canonical_player_id"]),
            int(fact["canonical_team_id"]),
            str(fact["source_row_sha256"]),
        )
        for fact in facts
        if str(fact["canonical_game_id"]) == str(game_id)
    ]
    if not rows or len(rows) != len({row[:3] for row in rows}) or any(
        len(row[3]) != 64 for row in rows
    ):
        raise ValueError(f"Missing or ambiguous source rows for game {game_id}")
    return hashlib.sha256(
        json.dumps(sorted(rows), separators=(",", ":")).encode()
    ).hexdigest()


def replay_published_player_game_facts(
    db: Session,
    *,
    game_ids: list[str],
    season: str | None = None,
    season_type: str | None = None,
    max_games: int = 25,
    expected_response_hashes: dict[str, dict[str, str]] | None = None,
    expected_source_row_set_hashes: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Replay canonical source revisions without contacting an external provider."""
    traditional_rows = (
        db.query(PlayerGameFactORM)
        .filter(PlayerGameFactORM.canonical_game_id.in_(game_ids))
        .all()
    )
    advanced_rows = (
        db.query(PlayerGameAdvancedFactORM)
        .filter(PlayerGameAdvancedFactORM.canonical_game_id.in_(game_ids))
        .all()
    )
    traditional_facts = [
        _revision_values(db.get(PlayerGameFactRevisionORM, row.revision_id))
        for row in traditional_rows
    ]
    advanced_facts = [
        _revision_values(db.get(PlayerGameAdvancedFactRevisionORM, row.revision_id))
        for row in advanced_rows
    ]
    if expected_response_hashes:
        for family, facts in (
            ("traditional", traditional_facts),
            ("advanced", advanced_facts),
        ):
            actual: dict[str, set[str]] = {}
            for fact in facts:
                payload = fact.get("raw_payload") or {}
                response_hash = payload.get("response_sha256")
                actual.setdefault(str(fact["canonical_game_id"]), set()).add(str(response_hash))
            normalized = {game_id: hashes for game_id, hashes in actual.items()}
            expected = expected_response_hashes.get(family, {})
            if any(len(hashes) != 1 for hashes in normalized.values()) or {
                game_id: next(iter(hashes)) for game_id, hashes in normalized.items()
            } != expected:
                raise ValueError(f"{family} database source hash differs from the replay manifest")
    if expected_source_row_set_hashes:
        for family, facts in (
            ("traditional", traditional_facts),
            ("advanced", advanced_facts),
        ):
            expected = expected_source_row_set_hashes.get(family, {})
            actual = {
                str(game_id): source_row_set_sha256(facts, str(game_id))
                for game_id in game_ids
            }
            if actual != expected:
                raise ValueError(
                    f"{family} database source rows differ from the replay manifest"
                )
    if {str(row.canonical_game_id) for row in traditional_rows} != set(game_ids):
        raise ValueError("Database replay is missing Traditional coverage for the manifest")
    if {str(row.canonical_game_id) for row in advanced_rows} != set(game_ids):
        raise ValueError("Database replay is missing Advanced coverage for the manifest")

    traditional_counts = publish_player_game_facts(traditional_facts, db=db)
    advanced_counts = publish_advanced_facts(advanced_facts, db=db)
    reconciliation = None
    if season and season_type:
        reconciliation = build_reconciliation_report(
            db,
            season=season,
            game_ids=game_ids,
            max_games=max_games,
        )
        if reconciliation["status"] != "passed":
            raise ValueError(f"C5 reconciliation failed during database replay: {reconciliation}")
    role_history_rows = publish_role_history(
        role_history_records_from_facts(traditional_facts), db=db
    )
    return {
        "traditional_counts": traditional_counts,
        "advanced_counts": advanced_counts,
        "role_history_rows": role_history_rows,
        "reconciliation": reconciliation,
    }
