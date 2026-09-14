"""Fetch starter evidence with a provenance-preserving fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from typing import Any, Mapping

import requests

from app.services.live_boxscore_starter_adapter import (
    LiveBoxScoreStarterAdapter,
    PARSER_VERSION as LIVE_PARSER_VERSION,
    SOURCE_NAME as LIVE_SOURCE_NAME,
    transform_payload as transform_live_payload,
)
from app.services.traditional_boxscore_v2_starter_adapter import (
    PARSER_VERSION as V2_PARSER_VERSION,
    SOURCE_NAME as V2_SOURCE_NAME,
    transform_payload as transform_v2_payload,
)
from app.utils.fetch.api_utils import create_api_endpoint


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StarterEvidenceFetch:
    """Evidence rows plus the source that actually produced them."""

    rows: list[dict[str, Any]]
    source_name: str
    parser_version: str
    fallback_reason: str | None = None


def _fetch_traditional_v2(game_id: str) -> Mapping[str, Any]:
    from nba_api.stats.endpoints import boxscoretraditionalv2

    endpoint = create_api_endpoint(
        boxscoretraditionalv2.BoxScoreTraditionalV2,
        game_id=game_id,
    )
    return endpoint.get_dict()


def _fallback_enabled() -> bool:
    return os.getenv(
        "STARTER_EVIDENCE_FALLBACK_SOURCE", "traditional_v2"
    ).strip().casefold() == "traditional_v2"


def _v2_fallback(
    *,
    game_id: str,
    season: str,
    season_type: str,
    run_id: str,
    retrieved_at: datetime,
    reason: str,
) -> StarterEvidenceFetch:
    payload = _fetch_traditional_v2(game_id)
    rows = transform_v2_payload(
        payload,
        game_id=game_id,
        season=season,
        season_type=season_type,
        run_id=run_id,
        retrieved_at=retrieved_at,
    )
    logger.warning(
        "Starter evidence used Traditional V2 fallback for %s: %s",
        game_id,
        reason,
    )
    return StarterEvidenceFetch(
        rows=rows,
        source_name=V2_SOURCE_NAME,
        parser_version=V2_PARSER_VERSION,
        fallback_reason=reason,
    )


def fetch_starter_evidence(
    *,
    game_id: str,
    season: str,
    season_type: str,
    run_id: str,
    retrieved_at: datetime,
    preferred_source: str = "live_boxscore",
) -> StarterEvidenceFetch:
    """Fetch explicit starter rows, falling back only to reviewed V2.

    Live BoxScore remains the preferred forward source.  A CDN transport error
    or a live payload without any explicit starter flags may use Traditional V2
    when ``STARTER_EVIDENCE_FALLBACK_SOURCE=traditional_v2``.  Each parser
    retains its own source name and hash contract; rows are never relabeled as
    Live evidence after fallback.
    """
    if preferred_source == "traditional_v2":
        payload = _fetch_traditional_v2(game_id)
        rows = transform_v2_payload(
            payload,
            game_id=game_id,
            season=season,
            season_type=season_type,
            run_id=run_id,
            retrieved_at=retrieved_at,
        )
        return StarterEvidenceFetch(
            rows=rows,
            source_name=V2_SOURCE_NAME,
            parser_version=V2_PARSER_VERSION,
        )

    if preferred_source != "live_boxscore":
        raise ValueError(f"unsupported starter evidence source: {preferred_source}")

    try:
        payload = LiveBoxScoreStarterAdapter().fetch_game(game_id)
    except requests.RequestException as live_error:
        if not _fallback_enabled():
            raise
        return _v2_fallback(
            game_id=game_id,
            season=season,
            season_type=season_type,
            run_id=run_id,
            retrieved_at=retrieved_at,
            reason=str(live_error),
        )

    rows = transform_live_payload(
        payload,
        game_id=game_id,
        season=season,
        season_type=season_type,
        run_id=run_id,
        retrieved_at=retrieved_at,
    )
    if not any(row["starter_status"] == "starter" for row in rows):
        if not _fallback_enabled():
            raise ValueError("Live BoxScore payload contains no explicit starters")
        return _v2_fallback(
            game_id=game_id,
            season=season,
            season_type=season_type,
            run_id=run_id,
            retrieved_at=retrieved_at,
            reason="Live BoxScore payload contains no explicit starters",
        )
    return StarterEvidenceFetch(
        rows=rows,
        source_name=LIVE_SOURCE_NAME,
        parser_version=LIVE_PARSER_VERSION,
    )
