"""Database-backed operational season selection.

The underlying policy lives in :mod:`app.utils.season_utils`; this module only
collects the available durable and future schedule seasons.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.utils.season_utils import active_ingestion_season, normalize_season


def resolve_active_ingestion_season(
    on_date: date,
    *,
    override: Optional[str] = None,
    db: Optional[Session] = None,
) -> str:
    """Resolve the active season using schedule evidence and an optional override."""
    if override is not None:
        return normalize_season(override)

    if db is None:
        with get_db_context() as session:
            return _resolve_active_ingestion_season(on_date, session)
    return _resolve_active_ingestion_season(on_date, db)


def _resolve_active_ingestion_season(on_date: date, db: Session) -> str:
    known_schedule = [
        row[0]
        for row in db.query(GameScheduleORM.season)
        .filter(GameScheduleORM.season.isnot(None))
        .distinct()
        .all()
    ]
    known_gamelogs = [
        row[0]
        for row in db.query(GameLogORM.season)
        .filter(GameLogORM.season.isnot(None))
        .distinct()
        .all()
    ]
    future_start = datetime.combine(on_date, datetime.min.time())
    scheduled = [
        row[0]
        for row in db.query(GameScheduleORM.season)
        .filter(
            GameScheduleORM.season.isnot(None),
            GameScheduleORM.game_date >= future_start,
        )
        .distinct()
        .all()
    ]
    return active_ingestion_season(
        on_date,
        scheduled_seasons=scheduled,
        known_seasons=[*known_schedule, *known_gamelogs],
    )
