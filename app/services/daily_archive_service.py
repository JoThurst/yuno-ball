"""Read-only builders for Daily Intelligence historical destinations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional
from zoneinfo import ZoneInfo

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_sqlalchemy import TeamORM
from app.services.daily_intelligence_service import build_daily_intelligence_v1
from app.utils.date_utils import current_eastern_date
from app.utils.season_utils import season_for_date


EASTERN = ZoneInfo("America/New_York")


def _eastern_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        current = value
    else:
        try:
            current = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(EASTERN).date()


def _team_name_map(db, team_ids: Iterable[int]) -> Dict[int, Mapping[str, Any]]:
    ids = {team_id for team_id in team_ids if team_id is not None}
    if not ids:
        return {}
    return {
        team.team_id: {
            "team_id": team.team_id,
            "name": team.name,
            "abbreviation": team.abbreviation,
        }
        for team in db.query(TeamORM).filter(TeamORM.team_id.in_(ids)).all()
    }


def _summarize_schedule_rows(rows: Iterable[Any], team_names: Mapping[int, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse schedule rows into date-level archive entries."""
    grouped: Dict[tuple, Dict[str, Any]] = {}
    for row in rows:
        target_date = _eastern_date(getattr(row, "game_date", None))
        if target_date is None:
            continue
        season = getattr(row, "season", None) or season_for_date(target_date)
        key = (target_date, season)
        entry = grouped.setdefault(
            key,
            {
                "date": target_date,
                "season": season,
                "game_ids": set(),
                "completed_game_ids": set(),
                "matchups": {},
            },
        )
        game_id = str(getattr(row, "game_id", ""))
        if not game_id:
            continue
        entry["game_ids"].add(game_id)
        if getattr(row, "result", None) is not None:
            entry["completed_game_ids"].add(game_id)

        home_id = getattr(row, "team_id", None)
        away_id = getattr(row, "opponent_team_id", None)
        if getattr(row, "home_or_away", None) == "A":
            home_id, away_id = away_id, home_id
        home = team_names.get(home_id, {"team_id": home_id, "abbreviation": "HOME", "name": "Home"})
        away = team_names.get(away_id, {"team_id": away_id, "abbreviation": "AWAY", "name": "Away"})
        entry["matchups"][game_id] = {
            "game_id": game_id,
            "home": home,
            "away": away,
            "completed": game_id in entry["completed_game_ids"],
        }

    output = []
    for entry in grouped.values():
        matchups = sorted(
            (
                {
                    **item,
                    "completed": item["game_id"] in entry["completed_game_ids"],
                }
                for item in entry["matchups"].values()
            ),
            key=lambda item: item["game_id"],
        )
        output.append(
            {
                "date": entry["date"],
                "season": entry["season"],
                "game_count": len(entry["game_ids"]),
                "completed_count": len(entry["completed_game_ids"]),
                "matchups": matchups,
            }
        )
    return sorted(output, key=lambda item: item["date"], reverse=True)


def build_daily_archive_index(
    *,
    season: Optional[str] = None,
    limit: int = 60,
    offset: int = 0,
) -> Dict[str, Any]:
    """Build a bounded archive index from durable Regular Season schedules."""
    limit = max(1, min(int(limit), 120))
    offset = max(0, int(offset))
    today = current_eastern_date()
    with get_db_context() as db:
        rows = (
            db.query(GameScheduleORM)
            .filter(GameScheduleORM.season_type == "Regular Season")
            .all()
        )
        rows = [
            row
            for row in rows
            if (_eastern_date(getattr(row, "game_date", None)) or today) <= today
            and (season is None or getattr(row, "season", None) == season)
        ]
        team_names = _team_name_map(
            db,
            (
                team_id
                for row in rows
                for team_id in (
                    getattr(row, "team_id", None),
                    getattr(row, "opponent_team_id", None),
                )
            ),
        )

    entries = _summarize_schedule_rows(rows, team_names)
    page = entries[offset: offset + limit]
    return {
        "entries": page,
        "season": season,
        "limit": limit,
        "offset": offset,
        "has_previous": offset > 0,
        "has_next": offset + limit < len(entries),
        "total_dates": len(entries),
    }


def build_historical_matchup(
    target_date: date,
    *,
    away_abbreviation: str,
    home_abbreviation: str,
    season: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve one canonical Daily game and its date-scoped insights."""
    package = build_daily_intelligence_v1(
        target_date=target_date,
        season=season or season_for_date(target_date),
    ).to_dict()
    away_token = away_abbreviation.upper()
    home_token = home_abbreviation.upper()
    game = next(
        (
            candidate
            for candidate in package.get("games", [])
            if str(candidate.get("away", {}).get("abbreviation", "")).upper() == away_token
            and str(candidate.get("home", {}).get("abbreviation", "")).upper() == home_token
        ),
        None,
    )
    if game is None:
        raise LookupError(
            f"No Daily Intelligence matchup found for {away_token} at {home_token} on {target_date.isoformat()}"
        )
    return {
        "package": package,
        "game": game,
        "insights": [item for item in package.get("insights", []) if item.get("game_id") == game.get("game_id")],
        "season": package.get("season") or season or season_for_date(target_date),
    }
