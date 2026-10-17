"""Parse Traditional V2 starter evidence without publishing canonical facts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping


SOURCE_NAME = "nba_boxscore_traditional_v2_starter_trial"
PARSER_VERSION = "boxscore-traditional-v2-starter-trial-v1"


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _datasets(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        headers = payload.get("headers")
        row_set = payload.get("rowSet", payload.get("data"))
        if isinstance(headers, list) and isinstance(row_set, list):
            return [{
                "name": payload.get("name"),
                "headers": [str(header) for header in headers],
                "rows": [dict(zip(headers, row)) for row in row_set if isinstance(row, list)],
            }]
        result_sets = payload.get("resultSets", payload.get("resultSet"))
        if result_sets is not None:
            return _datasets(result_sets)
        datasets: list[dict[str, Any]] = []
        for child in payload.values():
            datasets.extend(_datasets(child))
        return datasets
    if isinstance(payload, list):
        datasets: list[dict[str, Any]] = []
        for child in payload:
            datasets.extend(_datasets(child))
        return datasets
    return []


def extract_player_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract V2 PlayerStats rows, including empty-response detection."""
    for dataset in _datasets(payload):
        if dataset["name"] == "PlayerStats" or "PLAYER_ID" in dataset["headers"]:
            return dataset["rows"]
    return []


def transform_payload(
    payload: Mapping[str, Any],
    *,
    game_id: str,
    season: str,
    season_type: str,
    run_id: str,
    retrieved_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return trial-only starter evidence; never return a full player fact."""
    retrieved_at = retrieved_at or datetime.now(timezone.utc)
    rows = extract_player_rows(payload)
    if not rows:
        raise ValueError("Traditional V2 response contains no PlayerStats rows")

    payload_hash = _sha(payload)
    evidence = []
    for row in rows:
        player_id = row.get("PLAYER_ID")
        team_id = row.get("TEAM_ID")
        if player_id is None or team_id is None:
            raise ValueError("Traditional V2 starter rows require PLAYER_ID and TEAM_ID")
        response_game_id = row.get("GAME_ID")
        if response_game_id not in (None, "") and str(response_game_id) != str(game_id):
            raise ValueError(
                f"Traditional V2 response game mismatch: {response_game_id!r} != {game_id!r}"
            )
        start_position = row.get("START_POSITION")
        starter_status = "starter" if start_position not in (None, "") else "unknown"
        raw = {key: row.get(key) for key in sorted(row)}
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
            "start_position": str(start_position) if start_position not in (None, "") else None,
            "source_run_id": run_id,
            "retrieved_at": retrieved_at,
            "data_available_at": retrieved_at,
            "raw_payload": {"row": raw, "response_sha256": payload_hash},
        })
    if not any(row["starter_status"] == "starter" for row in evidence):
        raise ValueError("Traditional V2 response contains no populated START_POSITION values")
    return evidence
