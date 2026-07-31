"""Adapt one NBA live-odds response into immutable game-market observations."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence


SOURCE_NAME = "nba_live_odds"
PARSER_VERSION = "nba-live-odds-adapter-v1"


def build_market_observations(
    games: Sequence[Mapping[str, Any]],
    *,
    season: str,
    game_date: date,
    source_run_id: str,
    observation_batch_id: str,
    retrieved_at: datetime,
    season_type: str = "Regular Season",
    country_filter: str | None = "US",
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Build immutable registration payloads from one bounded provider response.

    The NBA live endpoint is a current-state feed. When it does not provide a
    provider line timestamp, the collector retrieval time is recorded as the
    observation time. That makes the result safe for *observed-by* queries but
    does not claim to be the line's creation or opening time.
    """
    retrieved_at = _require_aware(retrieved_at)
    payloads: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []

    for game in games:
        game_id = str(game.get("gameId") or "")
        home_team_id = _int_or_none(game.get("homeTeamId"))
        away_team_id = _int_or_none(game.get("awayTeamId"))
        if not game_id or not home_team_id or not away_team_id or home_team_id == away_team_id:
            continue

        for market in game.get("markets") or []:
            market_type = _market_type(market.get("name"))
            if market_type is None:
                continue
            for book in market.get("books") or []:
                sportsbook_id = str(book.get("id") or "")
                if not sportsbook_id or (country_filter and book.get("countryCode") != country_filter):
                    continue
                selections = _selections(market_type, book, home_team_id, away_team_id)
                if not selections:
                    continue
                raw_row = {"game": game, "market": market, "book": book}
                payloads.append(
                    (
                        {
                            "source_name": SOURCE_NAME,
                            "source_observation_key": (
                                f"{observation_batch_id}:{game_id}:{sportsbook_id}:{market_type}"
                            ),
                            "parser_version": PARSER_VERSION,
                            "snapshot_type": "forward",
                            "timing_precision": "second",
                            "market_type": market_type,
                            "source_run_id": source_run_id,
                            "source_game_id": game_id,
                            "canonical_game_id": game_id,
                            "source_row_sha256": _sha256(raw_row),
                            "game_date": game_date,
                            "season": season,
                            "season_type": season_type,
                            "home_team_id": home_team_id,
                            "away_team_id": away_team_id,
                            "sportsbook_id": sportsbook_id,
                            "sportsbook_name": book.get("name"),
                            "observed_at": retrieved_at,
                            "retrieved_at": retrieved_at,
                            "data_available_at": retrieved_at,
                            "raw_payload": raw_row,
                        },
                        selections,
                    )
                )
    return payloads


def _market_type(name: Any) -> str | None:
    normalized = str(name or "").strip().lower()
    if normalized == "2way":
        return "moneyline"
    if normalized == "spread":
        return "spread"
    if normalized in {"total", "totals"}:
        return "total"
    return None


def _selections(
    market_type: str,
    book: Mapping[str, Any],
    home_team_id: int,
    away_team_id: int,
) -> list[dict[str, Any]]:
    result = []
    pair_status = "selection_specific" if market_type == "total" else "inverse"
    for outcome in book.get("outcomes") or []:
        key = str(outcome.get("type") or "").strip().lower()
        if key not in {"home", "away", "over", "under"}:
            continue
        decimal_price = _float_or_none(outcome.get("odds"))
        if decimal_price is None or decimal_price <= 1:
            continue
        line = None
        if market_type == "spread":
            line = _first_float(outcome, "spread", "line")
        elif market_type == "total":
            line = _first_float(outcome, "total", "points", "line")
        result.append(
            {
                "selection_key": key,
                "selection_label": key.title(),
                "selection_team_id": (
                    home_team_id if key == "home" else away_team_id if key == "away" else None
                ),
                "line_value": line,
                "price_american": _american(decimal_price),
                "price_decimal": decimal_price,
                "pair_status": pair_status,
                "raw_selection": dict(outcome),
            }
        )
    return result


def _first_float(value: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        parsed = _float_or_none(value.get(key))
        if parsed is not None:
            return parsed
    return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed or None


def _american(decimal_price: float) -> int:
    if decimal_price >= 2:
        return round((decimal_price - 1) * 100)
    return round(-100 / (decimal_price - 1))


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
