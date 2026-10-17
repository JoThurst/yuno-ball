"""Bounded Advanced V3 adapter with immutable source lineage."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from app.utils.fetch.api_utils import create_api_endpoint


SOURCE_NAME = "nba_boxscore_advanced_v3"
PARSER_VERSION = "boxscore-advanced-v3-fact-v1"
CAMEL_TO_FIELD = {
    "minutes": "minutes",
    "estimatedOffensiveRating": "estimated_offensive_rating",
    "offensiveRating": "offensive_rating",
    "estimatedDefensiveRating": "estimated_defensive_rating",
    "defensiveRating": "defensive_rating",
    "estimatedNetRating": "estimated_net_rating",
    "netRating": "net_rating",
    "assistPercentage": "assist_percentage",
    "assistToTurnover": "assist_to_turnover",
    "assistRatio": "assist_ratio",
    "offensiveReboundPercentage": "offensive_rebound_percentage",
    "defensiveReboundPercentage": "defensive_rebound_percentage",
    "reboundPercentage": "rebound_percentage",
    "turnoverRatio": "turnover_ratio",
    "effectiveFieldGoalPercentage": "effective_field_goal_percentage",
    "trueShootingPercentage": "true_shooting_percentage",
    "usagePercentage": "usage_percentage",
    "estimatedUsagePercentage": "estimated_usage_percentage",
    "estimatedPace": "estimated_pace",
    "pace": "pace",
    "pacePer40": "pace_per_40",
    "possessions": "possessions",
    "PIE": "pie",
}


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _is_present(value: Any) -> bool:
    return value not in (None, "")


def _row_quality(row: Mapping[str, Any]) -> tuple[int, int, int]:
    """Rank duplicate endpoint rows without treating missing values as zero."""
    minutes = row.get("minutes")
    has_played_minutes = int(minutes not in (None, "", "0:00", "00:00"))
    populated_statistics = sum(
        _is_present(value)
        for key, value in row.items()
        if key not in {"player_id", "team_id", "status", "duplicate_source_rows"}
    )
    has_status = int(bool(str(row.get("status") or "").strip()))
    return has_played_minutes, populated_statistics, has_status


def extract_advanced_player_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    box = payload.get("boxScoreAdvanced")
    if isinstance(box, Mapping):
        rows = []
        for team_key in ("homeTeam", "awayTeam"):
            team = box.get(team_key) or {}
            by_player: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
            for player in team.get("players", []):
                row = {
                    "player_id": player.get("personId"),
                    "team_id": team.get("teamId"),
                    "status": player.get("comment"),
                }
                row.update(player.get("statistics") or {})
                by_player.setdefault((row["player_id"], row["team_id"]), []).append(row)
            for player_rows in by_player.values():
                if len(player_rows) == 1:
                    rows.append(player_rows[0])
                    continue
                ranked = sorted(
                    player_rows,
                    key=_row_quality,
                    reverse=True,
                )
                if _row_quality(ranked[0]) == _row_quality(ranked[1]):
                    rows.extend(player_rows)
                    continue
                chosen = dict(ranked[0])
                chosen["duplicate_source_rows"] = [
                    dict(row) for row in ranked[1:]
                ]
                rows.append(chosen)
        return rows
    rows = payload.get("player_stats") or []
    return [dict(row) for row in rows]


def transform_advanced_payload(
    payload: Mapping[str, Any],
    *,
    game_id: str,
    game_date: date,
    season: str,
    season_type: str,
    run_id: str,
    retrieved_at: datetime | None = None,
) -> list[dict[str, Any]]:
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    box = payload.get("boxScoreAdvanced")
    response_game_id = box.get("gameId") if isinstance(box, Mapping) else payload.get("game_id")
    if response_game_id not in (None, "") and str(response_game_id) != str(game_id):
        raise ValueError(f"Advanced V3 response game mismatch: {response_game_id!r} != {game_id!r}")
    response_hash = _sha(payload)
    facts = []
    for row in extract_advanced_player_rows(payload):
        player_id = row.get("player_id")
        team_id = row.get("team_id")
        if player_id is None or team_id is None:
            raise ValueError("Advanced V3 player rows require player and team identity")
        raw = {key: row.get(key) for key in sorted(row)}
        minutes = row.get("minutes")
        status = str(row.get("status") or "").strip().upper()
        did_not_play = (
            status == "INACTIVE"
            or status.startswith("DNP")
            or status.startswith("DID NOT PLAY")
            or status.startswith("DND")
        )
        participation = (
            "did_not_play"
            if did_not_play
            else "played"
            if minutes not in (None, "", "0:00", "00:00")
            else "unknown"
        )
        fact = {
            "source_name": SOURCE_NAME,
            "source_row_key": f"{game_id}:{int(player_id)}:{int(team_id)}",
            "parser_version": PARSER_VERSION,
            "source_game_id": str(game_id),
            "source_player_id": int(player_id),
            "source_team_id": int(team_id),
            "canonical_game_id": str(game_id),
            "canonical_player_id": int(player_id),
            "canonical_team_id": int(team_id),
            "source_row_sha256": _sha(raw),
            "source_run_id": run_id,
            "game_date": game_date,
            "season": season,
            "season_type": season_type,
            "completeness_status": "complete",
            "participation_status": participation,
            "retrieved_at": retrieved_at,
            "data_available_at": retrieved_at,
            "raw_payload": {"row": raw, "response_sha256": response_hash},
        }
        fact.update(
            {target: row.get(source) for source, target in CAMEL_TO_FIELD.items()}
        )
        facts.append(fact)
    return facts


class AdvancedBoxScoreV3Adapter:
    def __init__(self, endpoint_factory=create_api_endpoint):
        self.endpoint_factory = endpoint_factory

    def fetch_game(self, game_id: str) -> Mapping[str, Any]:
        from nba_api.stats.endpoints import boxscoreadvancedv3

        endpoint = self.endpoint_factory(
            boxscoreadvancedv3.BoxScoreAdvancedV3,
            game_id=game_id,
        )
        return endpoint.get_dict()
