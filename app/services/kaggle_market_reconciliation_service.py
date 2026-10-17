"""Pure rules for staged historical market identity reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple


@dataclass(frozen=True)
class MarketIdentityEvidence:
    game_id: str
    team_id: int
    opponent_team_id: int
    season: str
    season_type: str
    game_date: Optional[date]
    is_home: bool


@dataclass(frozen=True)
class CanonicalMarketGameEvidence:
    row_count: int
    team_ids: Tuple[int, ...]
    opponent_team_ids: Tuple[int, ...]
    seasons: Tuple[str, ...]
    season_types: Tuple[str, ...]
    game_dates: Tuple[date, ...]


@dataclass(frozen=True)
class MarketIdentityResult:
    status: str
    conflict_reasons: Tuple[str, ...]


def classify_market_identity(
    market: MarketIdentityEvidence,
    canonical: Optional[CanonicalMarketGameEvidence],
) -> MarketIdentityResult:
    """Classify one market row through its exact NBA game/team identity."""
    if canonical is None or canonical.row_count == 0:
        return MarketIdentityResult("canonical_missing", ())
    if canonical.row_count != 2:
        return MarketIdentityResult(
            "canonical_incomplete", ("canonical_row_count",)
        )

    reasons = []
    if market.is_home:
        reasons.append("market_team_not_away")
    if market.team_id not in canonical.team_ids:
        reasons.append("team_id")
    if market.opponent_team_id not in canonical.team_ids:
        reasons.append("opponent_team_id")
    perspective = dict(zip(canonical.team_ids, canonical.opponent_team_ids))
    if perspective.get(market.team_id) != market.opponent_team_id:
        reasons.append("team_opponent_pair")
    if set(canonical.seasons) != {market.season}:
        reasons.append("season")
    if set(canonical.season_types) != {market.season_type}:
        reasons.append("season_type")
    if market.game_date is not None and set(canonical.game_dates) != {
        market.game_date
    }:
        reasons.append("game_date")
    return MarketIdentityResult(
        "conflict" if reasons else "matched",
        tuple(sorted(set(reasons))),
    )
