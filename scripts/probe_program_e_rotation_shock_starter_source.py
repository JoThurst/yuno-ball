"""Probe a bounded box-score source for starter fields without database writes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.fetch.api_utils import create_api_endpoint


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe BoxScoreTraditionalV2 for starter fields without persistence"
    )
    parser.add_argument("--game-id", action="append", required=True)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    return parser.parse_args()


def _datasets(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        headers = value.get("headers")
        row_set = value.get("rowSet", value.get("data"))
        if isinstance(headers, list) and isinstance(row_set, list):
            yield {
                "name": value.get("name"),
                "headers": [str(header) for header in headers],
                "row_count": sum(isinstance(row, list) for row in row_set),
                "rows": [dict(zip(headers, row)) for row in row_set if isinstance(row, list)],
            }
        for child in value.values():
            yield from _datasets(child)
    elif isinstance(value, list):
        for child in value:
            yield from _datasets(child)


def _player_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for dataset in _datasets(payload):
        rows = dataset["rows"]
        headers = dataset["headers"]
        if "PLAYER_ID" in headers:
            return rows
    return []


def probe_game(game_id: str) -> dict[str, Any]:
    from nba_api.stats.endpoints import boxscoretraditionalv2

    endpoint = create_api_endpoint(boxscoretraditionalv2.BoxScoreTraditionalV2, game_id=game_id)
    payload = endpoint.get_dict()
    datasets = list(_datasets(payload))
    player_dataset = next(
        (dataset for dataset in datasets if "PLAYER_ID" in dataset["headers"]),
        None,
    )
    rows = _player_rows(payload)
    headers = player_dataset["headers"] if player_dataset else sorted({key for row in rows for key in row})
    starter_position_rows = [
        row for row in rows if row.get("START_POSITION") not in (None, "")
    ]
    starter_flag_rows = [row for row in rows if row.get("STARTER") not in (None, "")]
    return {
        "game_id": str(game_id),
        "response_shape": "result_sets" if datasets else "unrecognized",
        "dataset_count": len(datasets),
        "datasets": [
            {
                "name": dataset["name"],
                "headers": dataset["headers"],
                "row_count": dataset["row_count"],
            }
            for dataset in datasets
        ],
        "player_dataset_found": player_dataset is not None,
        "player_dataset_row_count": player_dataset["row_count"] if player_dataset else 0,
        "player_rows": len(rows),
        "headers": headers,
        "starter_fields_declared": any(
            field in headers for field in ("START_POSITION", "STARTER")
        ),
        "starter_position_rows": len(starter_position_rows),
        "starter_flag_rows": len(starter_flag_rows),
        "starter_fields_present": bool(starter_position_rows or starter_flag_rows),
        "starter_position_values": sorted(
            {str(row.get("START_POSITION")) for row in starter_position_rows}
        ),
    }


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    if not 1 <= len(args.game_id) <= 25:
        raise ValueError("provide between 1 and 25 game IDs")
    if args.pause_seconds < 0:
        raise ValueError("pause seconds must not be negative")
    results = []
    errors = []
    for index, game_id in enumerate(args.game_id):
        try:
            results.append(probe_game(game_id))
        except Exception as exc:  # noqa: BLE001 - report bounded source failures
            errors.append({"game_id": str(game_id), "error_type": type(exc).__name__, "error": str(exc)})
        if index < len(args.game_id) - 1 and args.pause_seconds:
            time.sleep(args.pause_seconds)
    return {
        "mode": "read-only-source-probe",
        "source": "BoxScoreTraditionalV2",
        "game_count": len(args.game_id),
        "results": results,
        "errors": errors,
        "writes_performed": False,
    }


def main() -> int:
    print(json.dumps(run_probe(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
