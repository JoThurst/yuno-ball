"""Authoritative player-dimension resolution for daily and historical ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.player_sqlalchemy import PlayerORM
from app.utils.fetch.api_utils import create_api_endpoint
from app.utils.season_utils import normalize_season


class PlayerIdentityResolutionError(ValueError):
    """Raised when an NBA player ID cannot be resolved authoritatively."""


@dataclass(frozen=True)
class PlayerIdentityRecord:
    player_id: int
    name: str
    position: str | None
    weight: int | None
    born_date: date | None
    age: int | None
    exp: int | None
    school: str | None
    available_seasons: list[str]


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value).split("T", 1)[0], "%Y-%m-%d").date()
    except ValueError:
        return None


def _season_range(from_year: int | None, to_year: int | None) -> list[str]:
    if from_year is None or to_year is None or to_year < from_year:
        return []
    return [f"{year}-{(year + 1) % 100:02d}" for year in range(from_year, to_year + 1)]


def fetch_player_identity_record(
    player_id: int,
    *,
    season: str,
    require_active_season: bool = True,
) -> PlayerIdentityRecord:
    """Fetch one player identity from NBA CommonPlayerInfo without writing.

    ``require_active_season`` may be disabled only for a source-listed DNP-only
    row. This preserves an authoritative DNP fact when CommonPlayerInfo
    identifies a G League-only or otherwise inactive player without claiming
    that the player was NBA-active in the requested season.
    """
    from nba_api.stats.endpoints import commonplayerinfo

    endpoint = create_api_endpoint(
        commonplayerinfo.CommonPlayerInfo,
        player_id=int(player_id),
    )
    payload = endpoint.get_dict()
    result_sets = payload.get("resultSets", [])
    player_set = next(
        (result for result in result_sets if result.get("name") == "CommonPlayerInfo"),
        None,
    )
    if not player_set or not player_set.get("rowSet"):
        raise PlayerIdentityResolutionError(
            f"CommonPlayerInfo returned no identity for player {player_id}"
        )
    row = dict(zip(player_set.get("headers", []), player_set["rowSet"][0]))
    name = str(row.get("DISPLAY_FIRST_LAST") or "").strip()
    if not name:
        raise PlayerIdentityResolutionError(
            f"CommonPlayerInfo returned no player name for player {player_id}"
        )
    from_year = _safe_int(row.get("FROM_YEAR"))
    to_year = _safe_int(row.get("TO_YEAR"))
    canonical_season = normalize_season(season)
    available_seasons = _season_range(from_year, to_year)
    if require_active_season and canonical_season not in available_seasons:
        raise PlayerIdentityResolutionError(
            f"Player {player_id} ({name}) is not active in requested season {canonical_season}"
        )
    born_date = _parse_date(row.get("BIRTHDATE"))
    age = datetime.now().year - born_date.year if born_date else None
    return PlayerIdentityRecord(
        player_id=int(player_id),
        name=name,
        position=str(row.get("POSITION") or "").strip() or None,
        weight=_safe_int(row.get("WEIGHT")),
        born_date=born_date,
        age=age,
        exp=_safe_int(row.get("SEASON_EXP")),
        school=str(row.get("SCHOOL") or "").strip() or None,
        available_seasons=available_seasons,
    )


def missing_player_ids(db: Session, player_ids: Iterable[int]) -> list[int]:
    normalized = sorted({int(player_id) for player_id in player_ids})
    if not normalized:
        return []
    existing = {
        int(player_id)
        for (player_id,) in db.query(PlayerORM.player_id)
        .filter(PlayerORM.player_id.in_(normalized))
        .all()
    }
    return [player_id for player_id in normalized if player_id not in existing]


def upsert_player_identity_records(
    db: Session,
    records: Iterable[PlayerIdentityRecord],
) -> dict[str, int]:
    created = 0
    updated = 0
    for record in records:
        existing = PlayerORM.get_by_id(record.player_id, db=db)
        seasons = list(dict.fromkeys((existing.available_seasons if existing else []) or []))
        seasons.extend(season for season in record.available_seasons if season not in seasons)
        PlayerORM.create(
            player_id=record.player_id,
            name=record.name,
            position=record.position,
            weight=record.weight,
            born_date=record.born_date,
            age=record.age,
            exp=record.exp,
            school=record.school,
            available_seasons=seasons,
            db=db,
        )
        if existing is None:
            created += 1
        else:
            updated += 1
    db.flush()
    return {"created": created, "updated": updated}
