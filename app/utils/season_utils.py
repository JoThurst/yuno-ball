"""Canonical, season-agnostic NBA season helpers.

The calendar-membership rule is intentionally separate from operational ingestion
selection. NBA seasons use ``YYYY-YY`` and start in October; during July through
September an ingestion process may remain on the completed season until an
upcoming schedule is actually available.
"""

from __future__ import annotations

import re
import warnings
from datetime import date, datetime
from typing import Iterable, Optional, Tuple, Union


SEASON_PATTERN = re.compile(r"^(?P<start>\d{4})-(?P<end>\d{2})$")
OFFSEASON_START_MONTH = 7
SEASON_START_MONTH = 10

CANONICAL_SEASON_TYPES = {
    "pre season": "Pre Season",
    "preseason": "Pre Season",
    "regular season": "Regular Season",
    "regular": "Regular Season",
    "all-star": "All-Star",
    "all star": "All-Star",
    "playoffs": "Playoffs",
    "postseason": "Playoffs",
}


class InvalidSeason(ValueError):
    """Raised when a value is not a canonical NBA season."""


def format_season(start_year: int) -> str:
    """Format a starting calendar year as a canonical NBA season."""
    if isinstance(start_year, bool) or not isinstance(start_year, int):
        raise InvalidSeason("Season start year must be an integer")
    if start_year < 1946 or start_year > 9998:
        raise InvalidSeason(f"Season start year is outside the supported range: {start_year}")
    return f"{start_year:04d}-{(start_year + 1) % 100:02d}"


def parse_season(season: str) -> Tuple[int, int]:
    """Return ``(start_year, end_year)`` after strict canonical validation."""
    if not isinstance(season, str):
        raise InvalidSeason("Season must be a string in YYYY-YY format")

    match = SEASON_PATTERN.fullmatch(season.strip())
    if not match:
        raise InvalidSeason(f"Invalid NBA season {season!r}; expected YYYY-YY")

    start_year = int(match.group("start"))
    if start_year < 1946 or start_year > 9998:
        raise InvalidSeason(f"NBA season is outside the supported range: {season!r}")
    end_year = start_year + 1
    expected_suffix = f"{end_year % 100:02d}"
    if match.group("end") != expected_suffix:
        raise InvalidSeason(
            f"Invalid NBA season {season!r}; expected {format_season(start_year)!r}"
        )
    return start_year, end_year


def normalize_season(season: str) -> str:
    """Validate and return the canonical representation of ``season``."""
    start_year, _ = parse_season(season)
    return format_season(start_year)


def season_for_date(value: Union[date, datetime]) -> str:
    """Return the NBA season containing a calendar date.

    This function expresses calendar membership only. Use
    :func:`active_ingestion_season` for offseason ingestion policy.
    """
    if not isinstance(value, (date, datetime)):
        raise TypeError("season_for_date requires a date or datetime")
    start_year = value.year if value.month >= SEASON_START_MONTH else value.year - 1
    return format_season(start_year)


def get_current_season(now: Optional[Union[date, datetime]] = None) -> str:
    """Return the calendar-membership season for ``now``."""
    return season_for_date(now or datetime.now())


# Alias used by fetch utilities and routes.
get_current_season_str = get_current_season


def season_start_year(season: Optional[str] = None) -> int:
    """Return the starting calendar year of a canonical season."""
    start_year, _ = parse_season(season or get_current_season())
    return start_year


def season_end_year(season: Optional[str] = None) -> int:
    """Return the ending calendar year of a canonical season."""
    _, end_year = parse_season(season or get_current_season())
    return end_year


def season_year_range(season: Optional[str] = None) -> Tuple[int, int]:
    """Return ``(start_year, end_year)`` for league-dash endpoint arguments."""
    return parse_season(season or get_current_season())


def previous_season(season: str) -> str:
    """Return the season immediately preceding ``season``."""
    return format_season(season_start_year(season) - 1)


def next_season(season: str) -> str:
    """Return the season immediately following ``season``."""
    return format_season(season_start_year(season) + 1)


def latest_known_season(seasons: Iterable[str]) -> Optional[str]:
    """Return the newest valid canonical season from an iterable.

    Invalid values are ignored so legacy values such as roster ``2025`` do not
    silently become canonical season identifiers.
    """
    valid = []
    for value in seasons:
        try:
            valid.append(normalize_season(value))
        except (InvalidSeason, TypeError):
            continue
    return max(valid, key=season_start_year) if valid else None


def active_ingestion_season(
    on_date: Union[date, datetime],
    *,
    scheduled_seasons: Iterable[str] = (),
    known_seasons: Iterable[str] = (),
    override: Optional[str] = None,
) -> str:
    """Choose the operational season for an ingestion run.

    An explicit override always wins after validation. From October through June,
    the calendar-membership season is used. During July through September, the
    upcoming season is selected only when it appears in the supplied future
    schedule; otherwise the latest known season remains active.
    """
    if override is not None:
        return normalize_season(override)
    if not isinstance(on_date, (date, datetime)):
        raise TypeError("active_ingestion_season requires a date or datetime")

    calendar_season = season_for_date(on_date)
    if not OFFSEASON_START_MONTH <= on_date.month < SEASON_START_MONTH:
        return calendar_season

    upcoming_season = format_season(on_date.year)
    scheduled = {value for value in _valid_seasons(scheduled_seasons)}
    if upcoming_season in scheduled:
        return upcoming_season

    return latest_known_season(known_seasons) or calendar_season


def default_display_season(
    on_date: Union[date, datetime],
    *,
    known_seasons: Iterable[str] = (),
    scheduled_seasons: Iterable[str] = (),
    override: Optional[str] = None,
) -> str:
    """Choose a truthful default season for current user-facing pages."""
    return active_ingestion_season(
        on_date,
        scheduled_seasons=scheduled_seasons,
        known_seasons=known_seasons,
        override=override,
    )


def normalize_season_type(season_type: str) -> str:
    """Normalize a supported NBA season type without conflating it with season."""
    if not isinstance(season_type, str):
        raise ValueError("Season type must be a string")
    normalized = CANONICAL_SEASON_TYPES.get(season_type.strip().lower())
    if not normalized:
        allowed = ", ".join(sorted(set(CANONICAL_SEASON_TYPES.values())))
        raise ValueError(f"Unsupported NBA season type {season_type!r}; expected one of {allowed}")
    return normalized


def roster_season_year(season: Optional[Union[str, int]] = None) -> str:
    """Return the legacy four-digit roster season key.

    The current database stores roster season as the starting year. This helper is
    retained only for read compatibility until the Phase 4 canonical roster
    migration. New writes must use a canonical ``YYYY-YY`` season.
    """
    warnings.warn(
        "roster_season_year is a legacy compatibility helper; use canonical seasons for new writes",
        DeprecationWarning,
        stacklevel=2,
    )
    if isinstance(season, int):
        return str(season)
    if season:
        text = str(season)
        if "-" in text:
            return str(season_start_year(text))
        return text
    return str(season_start_year())


def _valid_seasons(seasons: Iterable[str]) -> Iterable[str]:
    for value in seasons:
        try:
            yield normalize_season(value)
        except (InvalidSeason, TypeError):
            continue
