"""Canonical NBA season string helpers.

NBA seasons start in October. Rule (everywhere):
  month >= 10  ->  YYYY-(YY+1)
  otherwise    ->  (YYYY-1)-YY
"""

from datetime import datetime
from typing import Optional, Tuple, Union


def get_current_season(now: Optional[datetime] = None) -> str:
    """Return current NBA season string (e.g. '2025-26')."""
    now = now or datetime.now()
    if now.month >= 10:
        start_year = now.year
    else:
        start_year = now.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def season_for_date(d) -> str:
    """Return the NBA season string that contains the given date."""
    if hasattr(d, "month"):
        month, year = d.month, d.year
    else:
        return get_current_season()
    if month >= 10:
        start_year = year
    else:
        start_year = year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


# Alias used by fetch_utils / routes
get_current_season_str = get_current_season


def season_start_year(season: Optional[str] = None) -> int:
    """Return the starting calendar year of a season string, or current season."""
    season = season or get_current_season()
    return int(season.split("-")[0])


def season_year_range(season: Optional[str] = None) -> Tuple[int, int]:
    """Return (start_year, end_year) for league-dash style season_from/season_to."""
    start = season_start_year(season)
    return start, start + 1


def roster_season_year(season: Optional[Union[str, int]] = None) -> str:
    """Roster tables store season as a 4-digit year (e.g. '2025' for 2025-26)."""
    if isinstance(season, int):
        return str(season)
    if season and "-" in str(season):
        return str(season).split("-")[0]
    if season:
        return str(season)
    return str(season_start_year())
