"""Bounded Traditional V3 adapter with deterministic source lineage."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from typing import Any, Mapping

from app.services.player_game_fact_service import PARSER_VERSION
from app.utils.fetch.api_utils import create_api_endpoint

SOURCE_NAME = "nba_boxscore_traditional_v3"
SUPPORTED_FIELDS = {
    "MIN": "minutes", "FGM": "field_goals_made", "FGA": "field_goals_attempted",
    "FG_PCT": "field_goals_percentage", "FG3M": "three_pointers_made",
    "FG3A": "three_pointers_attempted", "FG3_PCT": "three_pointers_percentage",
    "FTM": "free_throws_made", "FTA": "free_throws_attempted",
    "FT_PCT": "free_throws_percentage", "OREB": "rebounds_offensive",
    "DREB": "rebounds_defensive", "REB": "rebounds_total", "AST": "assists",
    "STL": "steals", "BLK": "blocks", "TO": "turnovers", "PF": "fouls_personal",
    "PTS": "points", "PLUS_MINUS": "plus_minus_points",
}

CAMEL_TO_V3 = {
    "minutes": "MIN", "fieldGoalsMade": "FGM", "fieldGoalsAttempted": "FGA",
    "fieldGoalsPercentage": "FG_PCT", "threePointersMade": "FG3M",
    "threePointersAttempted": "FG3A", "threePointersPercentage": "FG3_PCT",
    "freeThrowsMade": "FTM", "freeThrowsAttempted": "FTA", "freeThrowsPercentage": "FT_PCT",
    "reboundsOffensive": "OREB", "reboundsDefensive": "DREB", "reboundsTotal": "REB",
    "assists": "AST", "steals": "STL", "blocks": "BLK", "turnovers": "TO",
    "foulsPersonal": "PF", "points": "PTS", "plusMinusPoints": "PLUS_MINUS",
}


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _rows(dataset: Any) -> list[dict[str, Any]]:
    if not dataset:
        return []
    if hasattr(dataset, "get_dict"):
        dataset = dataset.get_dict()
    if isinstance(dataset, dict) and "data" in dataset:
        return [dict(zip(dataset.get("headers", []), row)) for row in dataset["data"]]
    if isinstance(dataset, list):
        return [dict(row) for row in dataset]
    return []


def extract_player_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Accept endpoint get_dict output or a fixture containing player_stats."""
    for key in ("player_stats", "PlayerStats", "playerStats"):
        if key in payload:
            return _rows(payload[key])
    for value in payload.values():
        rows = _rows(value)
        if rows and any("PLAYER_ID" in row for row in rows):
            return rows
    box = payload.get("boxScoreTraditional")
    if isinstance(box, Mapping):
        rows = []
        for team_key in ("homeTeam", "awayTeam"):
            team = box.get(team_key) or {}
            for player in team.get("players", []):
                stats = player.get("statistics") or {}
                row = {"PLAYER_ID": player.get("personId"), "TEAM_ID": team.get("teamId"),
                       "PLAYER_STATUS": player.get("comment")}
                row.update({CAMEL_TO_V3[key]: value for key, value in stats.items() if key in CAMEL_TO_V3})
                rows.append(row)
        return rows
    return []


def extract_team_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the endpoint's reciprocal team-stat rows, if present."""
    for key in ("team_stats", "TeamStats", "teamStats"):
        if key in payload:
            return _rows(payload[key])
    for value in payload.values():
        rows = _rows(value)
        if rows and any("TEAM_ID" in row for row in rows) and not any("PLAYER_ID" in row for row in rows):
            return rows
    box = payload.get("boxScoreTraditional")
    if isinstance(box, Mapping):
        rows = []
        for team_key in ("homeTeam", "awayTeam"):
            team = box.get(team_key) or {}
            stats = team.get("statistics") or {}
            rows.append({"TEAM_ID": team.get("teamId"), "PTS": stats.get("points")})
        return rows
    return []


def response_sha256(payload: Mapping[str, Any]) -> str:
    """Hash the complete normalized response for replay/provenance evidence."""
    return _sha(payload)


def validate_payload_identity(
    payload: Mapping[str, Any], *, game_id: str, season: str, season_type: str,
) -> None:
    """Fail closed when a response identifies a different game or competition."""
    response_game_id = payload.get("GAME_ID") or payload.get("game_id") or payload.get("GameID")
    box = payload.get("boxScoreTraditional")
    if isinstance(box, Mapping):
        response_game_id = response_game_id or box.get("gameId")
    if response_game_id not in (None, "") and str(response_game_id) != str(game_id):
        raise ValueError(f"Traditional V3 response game mismatch: {response_game_id!r} != {game_id!r}")
    payload_season = payload.get("SEASON") or payload.get("season") or payload.get("Season")
    if payload_season not in (None, "") and str(payload_season) != season:
        raise ValueError(f"Traditional V3 response season mismatch: {payload_season!r} != {season!r}")
    payload_type = payload.get("SEASON_TYPE") or payload.get("season_type") or payload.get("SeasonType")
    if payload_type not in (None, "") and str(payload_type) != season_type:
        raise ValueError(f"Traditional V3 response season type mismatch: {payload_type!r} != {season_type!r}")


def reconcile_player_totals(payload: Mapping[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconcile player points to both reciprocal team rows before publication."""
    team_rows = extract_team_rows(payload)
    if len(team_rows) != 2:
        raise ValueError(f"Expected exactly two reciprocal team rows, found {len(team_rows)}")
    player_totals: dict[int, int] = {}
    for fact in facts:
        points = fact.get("points")
        if points is not None:
            player_totals[fact["source_team_id"]] = player_totals.get(fact["source_team_id"], 0) + int(points)
    team_totals = {}
    for row in team_rows:
        team_id = row.get("TEAM_ID")
        if team_id is None or row.get("PTS") is None:
            raise ValueError("Traditional V3 team rows require TEAM_ID and PTS")
        team_totals[int(team_id)] = int(row["PTS"])
    if set(player_totals) != set(team_totals) or any(player_totals.get(k) != v for k, v in team_totals.items()):
        raise ValueError(f"Player/team points mismatch: players={player_totals}, teams={team_totals}")
    return {"team_ids": sorted(team_totals), "team_points": team_totals, "total_points": sum(team_totals.values())}


def transform_payload(payload: Mapping[str, Any], *, game_id: str, game_date: date,
                      season: str, season_type: str, run_id: str,
                      retrieved_at: datetime | None = None) -> list[dict[str, Any]]:
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    validate_payload_identity(payload, game_id=game_id, season=season, season_type=season_type)
    rows = extract_player_rows(payload)
    payload_hash = response_sha256(payload)
    facts = []
    for row in rows:
        player_id = row.get("PLAYER_ID")
        team_id = row.get("TEAM_ID")
        if player_id is None or team_id is None:
            raise ValueError("Traditional V3 player rows require PLAYER_ID and TEAM_ID")
        raw = {key: row.get(key) for key in sorted(row)}
        minutes = row.get("MIN")
        status = str(row.get("PLAYER_STATUS") or row.get("STATUS") or "").strip().upper()
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
        starter = {1: "starter", True: "starter", 0: "bench", False: "bench"}.get(row.get("START_POSITION"), "unknown")
        if row.get("START_POSITION") in (None, "") and row.get("STARTER") is not None:
            starter = {1: "starter", True: "starter", 0: "bench", False: "bench"}.get(row["STARTER"], "unknown")
        fact = {
            "source_name": SOURCE_NAME, "source_row_key": f"{game_id}:{int(player_id)}:{int(team_id)}",
            "parser_version": PARSER_VERSION, "source_game_id": str(game_id),
            "source_player_id": int(player_id), "source_team_id": int(team_id),
            "canonical_game_id": str(game_id), "canonical_player_id": int(player_id),
            "canonical_team_id": int(team_id), "source_row_sha256": _sha(raw),
            "source_run_id": run_id, "game_date": game_date, "season": season,
            "season_type": season_type, "completeness_status": "complete",
            "participation_status": participation, "starter_status": starter,
            "retrieved_at": retrieved_at, "data_available_at": retrieved_at,
            "source_response_sha256": payload_hash,
            "data_available_at_basis": "retrieved_proxy",
            "raw_payload": {"row": raw, "response_sha256": payload_hash},
        }
        fact.update({target: row.get(source) for source, target in SUPPORTED_FIELDS.items()})
        facts.append(fact)
    return facts


class TraditionalBoxScoreV3Adapter:
    """Fetch exactly the requested bounded game IDs through nba_api's shared path."""
    def __init__(self, endpoint_factory=create_api_endpoint):
        self.endpoint_factory = endpoint_factory

    def fetch_game(self, game_id: str) -> Mapping[str, Any]:
        from nba_api.stats.endpoints import boxscoretraditionalv3
        endpoint = self.endpoint_factory(boxscoretraditionalv3.BoxScoreTraditionalV3, game_id=game_id)
        return endpoint.get_dict()

    def collect(self, game_ids: list[str], *, max_games: int, **kwargs: Any) -> list[dict[str, Any]]:
        if max_games < 1 or len(game_ids) > max_games:
            raise ValueError("game_ids must be non-empty and within max_games")
        result = []
        for game_id in game_ids:
            result.extend(transform_payload(self.fetch_game(game_id), game_id=game_id, **kwargs))
        return result
