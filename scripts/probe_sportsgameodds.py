"""Plan or explicitly execute one read-only SportsGameOdds NBA probe.

Default execution is credential-free and network-free.  ``--live-probe`` is
required for the single request path and never writes to Yuno Ball storage.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MAX_PROBE_EVENTS = 25


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional local env file; its contents are never printed",
    )
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument(
        "--live-probe",
        action="store_true",
        help="Opt into exactly one read-only provider request",
    )
    return parser


def _load_env(path: Path | None) -> None:
    if path is not None:
        load_dotenv(path, override=False)
    else:
        load_dotenv()


def _plan(args: argparse.Namespace) -> dict[str, object]:
    return {
        "mode": "live_probe" if args.live_probe else "plan_only",
        "network_request_count": 1 if args.live_probe else 0,
        "writes_performed": False,
        "provider": "sportsgameodds",
        "endpoint": "/v2/events",
        "league_id": "NBA",
        "limit": args.limit,
        "max_allowed_limit": MAX_PROBE_EVENTS,
        "auth": "x-api-key header; never query parameter",
    }


def main() -> int:
    args = build_parser().parse_args()
    try:
        _load_env(args.env_file)
        # Import after dotenv loading: app/__init__.py validates the normal
        # application settings during import, while this script remains a
        # read-only provider probe.
        from app.services.sportsgameodds_client import (  # noqa: E402
            SportsGameOddsSafetyError,
            api_key_from_environment,
            build_events_request,
            fetch_events,
            normalize_events,
        )

        if args.limit < 1 or args.limit > MAX_PROBE_EVENTS:
            raise SportsGameOddsSafetyError(
                f"--limit must be between 1 and {MAX_PROBE_EVENTS}"
            )
        if not args.live_probe:
            print(json.dumps(_plan(args), indent=2))
            return 0

        key = api_key_from_environment()
        request = build_events_request(api_key=key, limit=args.limit)
        response = fetch_events(request, allow_live_probe=True)
        normalized = normalize_events(response.events)
        bookmaker_rows = [
            bookmaker
            for event in normalized
            for market in event["markets"]
            for bookmaker in market["bookmakers"]
        ]
        print(
            json.dumps(
                {
                    **_plan(args),
                    "http_status": response.status_code,
                    "events_received": len(response.events),
                    "events_normalized": len(normalized),
                    "next_cursor_present": response.next_cursor_present,
                    "content_type": response.content_type,
                    "retrieved_at": response.retrieved_at.isoformat(),
                    "quality_counts": {
                        "events_with_both_provider_teams": sum(
                            bool(
                                event["home_provider_team_id"]
                                and event["away_provider_team_id"]
                            )
                            for event in normalized
                        ),
                        "events_with_start_time": sum(
                            event["starts_at"] is not None for event in normalized
                        ),
                        "game_market_rows": sum(
                            len(event["markets"]) for event in normalized
                        ),
                        "bookmaker_rows": len(bookmaker_rows),
                        "bookmaker_rows_with_provider_timestamp": sum(
                            bookmaker["provider_updated_at"] is not None
                            for bookmaker in bookmaker_rows
                        ),
                    },
                    "market_counts": {
                        market_type: sum(
                            1
                            for event in normalized
                            for market in event["markets"]
                            if market["market_type"] == market_type
                        )
                        for market_type in ("moneyline", "spread", "total")
                    },
                },
                indent=2,
            )
        )
        return 0
    except SportsGameOddsSafetyError as exc:
        print(json.dumps({"error": "ODDS_PROBE_BLOCKED", "message": str(exc)}))
        return 2
    except Exception as exc:  # pragma: no cover - CLI safety boundary
        print(json.dumps({"error": "ODDS_PROBE_FAILED", "message": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
