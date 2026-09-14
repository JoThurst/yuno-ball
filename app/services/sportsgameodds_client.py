"""Fail-closed SportsGameOdds client and provider-shape normalizer.

The odds pilot is intentionally separate from the durable market-observation
writer.  This module can describe a request without network access, and a
live request requires an explicit opt-in from the caller.  API keys are sent
in a header so they do not appear in URLs, browser history, or request logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Mapping, Sequence

import requests


BASE_URL = "https://api.sportsgameodds.com/v2"
SOURCE_NAME = "sportsgameodds"
PARSER_VERSION = "sportsgameodds-events-v1"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_PROBE_REQUESTS = 1
MAX_PROBE_EVENTS = 25


class SportsGameOddsSafetyError(RuntimeError):
    """Raised when the bounded odds pilot is asked to exceed its guardrails."""


@dataclass(frozen=True)
class SportsGameOddsRequest:
    """A redacted request plan; it never contains the API key."""

    url: str
    params: Mapping[str, str | int | bool]
    headers: Mapping[str, str]
    timeout_seconds: float


@dataclass(frozen=True)
class SportsGameOddsResponse:
    """Small, redacted response envelope for probe/reporting code."""

    status_code: int
    events: tuple[Mapping[str, Any], ...]
    next_cursor_present: bool
    content_type: str | None
    retrieved_at: datetime


def api_key_from_environment(environ: Mapping[str, str] | None = None) -> str:
    """Read the provider key without ever printing it."""

    values = environ if environ is not None else os.environ
    key = str(values.get("SPORTSGAMEODDS_API_KEY") or "").strip()
    if not key:
        raise SportsGameOddsSafetyError(
            "SPORTSGAMEODDS_API_KEY is not configured in the process environment"
        )
    return key


def build_events_request(
    *,
    api_key: str,
    league_id: str = "NBA",
    limit: int = 1,
    finalized: bool = False,
    odds_available: bool = True,
    base_url: str = BASE_URL,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> SportsGameOddsRequest:
    """Build a single bounded request while keeping the secret in headers."""

    if not api_key.strip():
        raise SportsGameOddsSafetyError("An API key is required to build a request")
    if limit < 1 or limit > MAX_PROBE_EVENTS:
        raise SportsGameOddsSafetyError(
            f"The bounded odds probe allows 1-{MAX_PROBE_EVENTS} events"
        )
    if timeout_seconds <= 0:
        raise SportsGameOddsSafetyError("timeout_seconds must be positive")
    return SportsGameOddsRequest(
        url=f"{base_url.rstrip('/')}/events",
        params={
            "leagueID": league_id,
            "finalized": str(finalized).lower(),
            "oddsAvailable": str(odds_available).lower(),
            "limit": limit,
        },
        headers={"x-api-key": api_key},
        timeout_seconds=timeout_seconds,
    )


def fetch_events(
    request: SportsGameOddsRequest,
    *,
    allow_live_probe: bool = False,
    session: requests.Session | None = None,
) -> SportsGameOddsResponse:
    """Perform exactly one GET only when the caller opts into a live probe."""

    if not allow_live_probe:
        raise SportsGameOddsSafetyError(
            "Network access is disabled; pass allow_live_probe=True for one probe"
        )
    client = session or requests.Session()
    retrieved_at = datetime.now(timezone.utc)
    response = client.get(
        request.url,
        params=dict(request.params),
        headers=dict(request.headers),
        timeout=request.timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise SportsGameOddsSafetyError("SportsGameOdds response must be a JSON object")
    data = payload.get("data") or []
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)):
        raise SportsGameOddsSafetyError("SportsGameOdds response data must be a list")
    return SportsGameOddsResponse(
        status_code=response.status_code,
        events=tuple(item for item in data if isinstance(item, Mapping)),
        next_cursor_present=bool(payload.get("nextCursor")),
        content_type=response.headers.get("content-type"),
        retrieved_at=retrieved_at,
    )


def normalize_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize documented event/odd/bookmaker shape without claiming identity.

    Provider team IDs remain strings here.  A later identity-resolution step
    must map them to Yuno Ball integer team IDs before durable registration.
    Player props and non-game periods are deliberately excluded from this
    first game-market pilot.
    """

    normalized: list[dict[str, Any]] = []
    for event in events:
        teams = event.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        event_id = str(event.get("eventID") or "").strip()
        home_id = str(home.get("teamID") or "").strip()
        away_id = str(away.get("teamID") or "").strip()
        if not event_id or not home_id or not away_id or home_id == away_id:
            continue
        markets: list[dict[str, Any]] = []
        odds = event.get("odds") or {}
        if isinstance(odds, Mapping):
            for odd_id, odd in odds.items():
                if not isinstance(odd, Mapping) or odd.get("periodID") not in {None, "game"}:
                    continue
                if str(odd.get("statID") or "points").strip().lower() != "points":
                    continue
                market_type = _market_type(odd.get("betTypeID"))
                selection_key = _selection_key(odd.get("sideID"))
                if market_type is None or selection_key is None:
                    continue
                bookmakers = []
                by_bookmaker = odd.get("byBookmaker") or {}
                if isinstance(by_bookmaker, Mapping):
                    for bookmaker_id, bookmaker in by_bookmaker.items():
                        if not isinstance(bookmaker, Mapping) or bookmaker.get("available") is False:
                            continue
                        price = _american(bookmaker.get("odds") or odd.get("bookOdds"))
                        if price is None:
                            continue
                        bookmakers.append(
                            {
                                "bookmaker_id": str(bookmaker_id),
                                "price_american": price,
                                "line_value": _number(
                                    bookmaker.get("overUnder") or odd.get("bookOverUnder")
                                ),
                                "provider_updated_at": _timestamp(
                                    bookmaker.get("lastUpdatedAt")
                                ),
                            }
                        )
                if bookmakers:
                    markets.append(
                        {
                            "odd_id": str(odd_id),
                            "market_type": market_type,
                            "selection_key": selection_key,
                            "selection_label": selection_key.title(),
                            "bookmakers": bookmakers,
                        }
                    )
        normalized.append(
            {
                "source_name": SOURCE_NAME,
                "parser_version": PARSER_VERSION,
                "source_event_id": event_id,
                "league_id": event.get("leagueID"),
                "starts_at": _timestamp(
                    (event.get("status") or {}).get("startsAt")
                    if isinstance(event.get("status"), Mapping)
                    else event.get("startTime")
                ),
                "home_provider_team_id": home_id,
                "home_name": _team_name(home),
                "away_provider_team_id": away_id,
                "away_name": _team_name(away),
                "status": dict(event.get("status") or {})
                if isinstance(event.get("status"), Mapping)
                else {},
                "markets": markets,
            }
        )
    return normalized


def _market_type(value: Any) -> str | None:
    return {"ml": "moneyline", "sp": "spread", "ou": "total"}.get(
        str(value or "").strip().lower()
    )


def _selection_key(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"home", "away", "over", "under"} else None


def _team_name(team: Mapping[str, Any]) -> str | None:
    names = team.get("names") or {}
    if isinstance(names, Mapping):
        return str(names.get("long") or names.get("medium") or "").strip() or None
    return None


def _american(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace("+", ""))
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)
