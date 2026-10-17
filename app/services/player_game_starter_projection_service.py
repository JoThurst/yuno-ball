"""Project reviewed starter evidence onto canonical player-game facts."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM
# Import the model so Base.metadata can resolve the runtime foreign key.
from app.models.player_game_starter_evidence_sqlalchemy import (
    PlayerGameStarterEvidenceORM,
)


class StarterProjectionConflict(ValueError):
    """Raised when canonical starter lineage conflicts with evidence."""


def project_starter_evidence(
    evidence_rows: list[Mapping[str, object]],
    *,
    db: Session,
) -> dict[str, int]:
    """Project only explicit starter rows; leave unknown rows untouched."""
    counts = {
        "evidence_rows": len(evidence_rows),
        "starter_rows": 0,
        "facts_updated": 0,
        "facts_unchanged": 0,
    }
    for evidence in evidence_rows:
        if evidence.get("starter_status") != "starter":
            continue
        counts["starter_rows"] += 1
        evidence_id = str(evidence["evidence_id"])
        key = {
            "canonical_game_id": str(evidence["canonical_game_id"]),
            "canonical_player_id": int(evidence["canonical_player_id"]),
            "canonical_team_id": int(evidence["canonical_team_id"]),
        }
        fact = db.query(PlayerGameFactORM).filter_by(**key).one_or_none()
        if fact is None:
            raise StarterProjectionConflict(
                f"No canonical player-game fact for starter evidence {evidence_id}"
            )
        position = evidence.get("start_position")
        if fact.starter_status not in {"unknown", "starter"}:
            raise StarterProjectionConflict(
                f"Canonical starter status conflicts for {key}: {fact.starter_status}"
            )
        if fact.starter_evidence_id not in (None, evidence_id):
            raise StarterProjectionConflict(
                f"Canonical starter evidence conflicts for {key}: "
                f"{fact.starter_evidence_id}"
            )
        if fact.starter_position not in (None, position):
            raise StarterProjectionConflict(
                f"Canonical starter position conflicts for {key}: "
                f"{fact.starter_position}"
            )
        if (
            fact.starter_status == "starter"
            and fact.starter_evidence_id == evidence_id
            and fact.starter_position == position
        ):
            counts["facts_unchanged"] += 1
            continue
        fact.starter_status = "starter"
        fact.starter_position = position
        fact.starter_evidence_id = evidence_id
        counts["facts_updated"] += 1
    db.flush()
    return counts
