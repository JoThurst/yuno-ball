"""Season-safe roster normalization and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from sqlalchemy.orm import Session

from app.models.team_sqlalchemy import RosterORM
from app.utils.season_utils import normalize_season


class EmptyRosterPayload(ValueError):
    """Raised when an empty/invalid provider response would erase a roster."""


@dataclass(frozen=True)
class RosterReconciliationResult:
    season: str
    received: int
    inserted: int
    updated: int
    removed: int


def _jersey_number(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_roster_payload(
    rows: Iterable[Mapping[str, Any]],
    *,
    season: str,
) -> list[dict]:
    """Normalize CommonTeamRoster rows without trusting its legacy SEASON field."""

    canonical_season = normalize_season(season)
    normalized: list[dict] = []
    seen = set()
    for row in rows:
        player_id = row.get("PLAYER_ID")
        player_name = str(row.get("PLAYER") or "").strip()
        if player_id is None or not player_name:
            continue
        player_id = int(player_id)
        if player_id in seen:
            continue
        seen.add(player_id)
        normalized.append(
            {
                "player_id": player_id,
                "player_name": player_name,
                "player_number": _jersey_number(row.get("NUM")),
                "position": str(row.get("POSITION") or "").strip() or None,
                "how_acquired": str(row.get("HOW_ACQUIRED") or "").strip() or None,
                "season": canonical_season,
            }
        )
    if not normalized:
        raise EmptyRosterPayload(
            f"Refusing to reconcile an empty roster for season {canonical_season}"
        )
    return normalized


def reconcile_team_roster(
    db: Session,
    *,
    team_id: int,
    season: str,
    entries: Iterable[Mapping[str, Any]],
) -> RosterReconciliationResult:
    """Upsert one team-season roster and remove only absent rows in that season."""

    canonical_season = normalize_season(season)
    values = [dict(entry) for entry in entries]
    if not values:
        raise EmptyRosterPayload(
            f"Refusing to reconcile an empty roster for team {team_id}"
        )

    existing = {
        row.player_id: row
        for row in db.query(RosterORM).filter(
            RosterORM.team_id == team_id,
            RosterORM.season == canonical_season,
        )
    }
    incoming_ids = {int(entry["player_id"]) for entry in values}
    inserted = sum(player_id not in existing for player_id in incoming_ids)
    updated = len(incoming_ids) - inserted

    for entry in values:
        RosterORM.create(
            team_id=team_id,
            player_id=int(entry["player_id"]),
            season=canonical_season,
            player_name=entry["player_name"],
            player_number=entry.get("player_number"),
            position=entry.get("position"),
            how_acquired=entry.get("how_acquired"),
            db=db,
        )

    stale_ids = set(existing) - incoming_ids
    removed = 0
    if stale_ids:
        removed = (
            db.query(RosterORM)
            .filter(
                RosterORM.team_id == team_id,
                RosterORM.season == canonical_season,
                RosterORM.player_id.in_(stale_ids),
            )
            .delete(synchronize_session=False)
        )
    db.flush()
    return RosterReconciliationResult(
        season=canonical_season,
        received=len(values),
        inserted=inserted,
        updated=updated,
        removed=removed,
    )
