"""Parse player-level starter flags from the NBA Live BoxScore source."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from typing import Any, Mapping

import requests

from app.utils.fetch.proxy_manager import ProxyManager


logger = logging.getLogger(__name__)


SOURCE_NAME = "nba_live_boxscore_starter"
PARSER_VERSION = "live-boxscore-starter-v1"
LIVE_BOX_SCORE_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _game(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    value = payload.get("game")
    return value if isinstance(value, Mapping) else payload


def transform_payload(
    payload: Mapping[str, Any],
    *,
    game_id: str,
    season: str,
    season_type: str,
    run_id: str,
    retrieved_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return immutable starter evidence without publishing canonical facts.

    The live source has an explicit ``starter`` flag.  Only ``"1"`` is
    promoted to ``starter``; every other value remains ``unknown`` because
    absence of an explicit flag is not proof of a bench role.
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    game = _game(payload)
    response_game_id = game.get("gameId") or payload.get("gameId")
    if response_game_id not in (None, "") and str(response_game_id) != str(game_id):
        raise ValueError(
            f"Live BoxScore response game mismatch: {response_game_id!r} != {game_id!r}"
        )

    payload_hash = _sha(payload)
    evidence: list[dict[str, Any]] = []
    for team_key in ("homeTeam", "awayTeam"):
        team = game.get(team_key) or {}
        team_id = team.get("teamId")
        if team_id is None:
            continue
        for player in team.get("players") or []:
            player_id = player.get("personId")
            if player_id is None:
                continue
            raw = dict(player)
            starter_status = "starter" if str(player.get("starter")) == "1" else "unknown"
            start_position = player.get("position") if starter_status == "starter" else None
            evidence.append({
                "source_name": SOURCE_NAME,
                "parser_version": PARSER_VERSION,
                "source_game_id": str(game_id),
                "source_player_id": int(player_id),
                "source_team_id": int(team_id),
                "source_row_key": f"{game_id}:{int(player_id)}:{int(team_id)}",
                "source_row_sha256": _sha(raw),
                "source_response_sha256": payload_hash,
                "season": season,
                "season_type": season_type,
                "starter_status": starter_status,
                "start_position": str(start_position) if start_position else None,
                "source_run_id": run_id,
                "retrieved_at": retrieved_at,
                "data_available_at": retrieved_at,
                "raw_payload": {"row": raw, "response_sha256": payload_hash},
            })
    if not evidence:
        raise ValueError("Live BoxScore response contains no player rows")
    return evidence


class LiveBoxScoreStarterAdapter:
    """Fetch bounded completed-game starter evidence through the CDN provider."""

    def fetch_game(self, game_id: str) -> Mapping[str, Any]:
        """Fetch one completed-game payload through the shared CDN/proxy path.

        ``nba_api.live`` constructs a direct CDN request and does not accept the
        project's proxy-aware endpoint factory. Keep the provider boundary here
        while applying the runtime proxy policy used by schedule CDN fetches.
        """
        attempts = max(1, min(int(os.getenv("NBA_API_PROXY_ATTEMPTS", "3")), 3))
        last_error: Exception | None = None
        manager = ProxyManager()

        for attempt in range(attempts):
            proxy = self._select_proxy(manager)
            request_kwargs = {
                "headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/145.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": "https://www.nba.com/",
                    "Origin": "https://www.nba.com",
                },
                "timeout": 45,
            }
            if proxy:
                request_kwargs["proxies"] = {"http": proxy, "https": proxy}
            try:
                response = requests.get(
                    LIVE_BOX_SCORE_URL.format(game_id=str(game_id)),
                    **request_kwargs,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, Mapping):
                    raise ValueError("Live BoxScore response is not a JSON object")
                if proxy:
                    manager.mark_success(proxy)
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if proxy:
                    manager.mark_failed(proxy)
                if attempt + 1 < attempts:
                    logger.warning(
                        "Live BoxScore transport failure; rotating proxy (%s/%s): %s",
                        attempt + 1,
                        attempts,
                        exc,
                    )

        raise last_error or RuntimeError("Live BoxScore request failed")

    @staticmethod
    def _select_proxy(manager: ProxyManager) -> str | None:
        force_proxy = os.getenv("FORCE_PROXY", "false").lower() == "true"
        force_local = os.getenv("FORCE_LOCAL", "false").lower() == "true"
        if force_local or not force_proxy:
            return None
        return manager.get_healthy_proxy()
