"""Bounded dry-run/apply collector for NBA game-market observations."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
import uuid
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import get_db_context
from app.services.ingestion_run_service import IngestionRunTracker
from app.services.market_observation_service import (
    register_market_observation,
    validate_market_observation,
)
from app.services.nba_live_market_observation_adapter import (
    build_market_observations,
)
from app.utils.season_utils import get_current_season
from app.utils.fetch.odds_fetcher import OddsFetcher


EASTERN = ZoneInfo("America/New_York")
MAX_GAMES = 30
MAX_OBSERVATIONS = 500
SEASON_TYPE = "Regular Season"
PROVIDER = "nba_api.live.nba.endpoints.odds"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", default=None)
    parser.add_argument("--target-date", default=None, help="Eastern date; live endpoint is today-only")
    parser.add_argument("--observation-batch-id", default=None)
    parser.add_argument("--max-games", type=int, default=MAX_GAMES)
    parser.add_argument("--max-observations", type=int, default=MAX_OBSERVATIONS)
    parser.add_argument("--all-countries", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def _parse_target_date(value: str | None) -> date:
    target_date = date.fromisoformat(value) if value else datetime.now(EASTERN).date()
    if target_date != datetime.now(EASTERN).date():
        raise ValueError("NBA live odds collection only permits the current Eastern date")
    return target_date


def _validate_limits(args: argparse.Namespace) -> None:
    if not 1 <= args.max_games <= MAX_GAMES:
        raise ValueError(f"--max-games must be between 1 and {MAX_GAMES}")
    if not 1 <= args.max_observations <= MAX_OBSERVATIONS:
        raise ValueError(
            f"--max-observations must be between 1 and {MAX_OBSERVATIONS}"
        )


def collect(
    games: Sequence[Mapping[str, Any]],
    *,
    season: str,
    target_date: date,
    source_run_id: str,
    observation_batch_id: str,
    retrieved_at: datetime,
    max_games: int,
    max_observations: int,
    country_filter: str | None,
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    if len(games) > max_games:
        raise ValueError(f"Provider returned {len(games)} games; limit is {max_games}")
    payloads = build_market_observations(
        games,
        season=season,
        game_date=target_date,
        source_run_id=source_run_id,
        observation_batch_id=observation_batch_id,
        retrieved_at=retrieved_at,
        season_type=SEASON_TYPE,
        country_filter=country_filter,
    )
    if len(payloads) > max_observations:
        raise ValueError(
            f"Provider response produced {len(payloads)} observations; "
            f"limit is {max_observations}"
        )
    for header, selections in payloads:
        validate_market_observation(header, selections)
    return payloads


def _summary(
    *,
    mode: str,
    run_id: str,
    target_date: date,
    observation_batch_id: str,
    games_read: int,
    payloads: Sequence[tuple[Mapping[str, Any], Sequence[Mapping[str, Any]]]],
    rows_written: int,
) -> dict[str, Any]:
    by_market: dict[str, int] = {}
    for header, _ in payloads:
        market_type = str(header["market_type"])
        by_market[market_type] = by_market.get(market_type, 0) + 1
    return {
        "mode": mode,
        "database_write": mode == "apply",
        "run_id": run_id,
        "target_date": target_date.isoformat(),
        "observation_batch_id": observation_batch_id,
        "games_read": games_read,
        "observations": len(payloads),
        "selections": sum(len(selections) for _, selections in payloads),
        "rows_written": rows_written,
        "by_market": by_market,
        "provider": PROVIDER,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    _validate_limits(args)
    season = args.season or get_current_season()
    target_date = _parse_target_date(args.target_date)
    observation_batch_id = args.observation_batch_id or str(uuid.uuid4())
    country_filter = None if args.all_countries else "US"
    fetcher = OddsFetcher()

    if args.dry_run:
        run_id = str(uuid.uuid4())
        retrieved_at = datetime.now(timezone.utc)
        games = fetcher._fetch_raw_odds()
        if games is None:
            raise RuntimeError("NBA live odds provider returned no response")
        payloads = collect(
            games,
            season=season,
            target_date=target_date,
            source_run_id=run_id,
            observation_batch_id=observation_batch_id,
            retrieved_at=retrieved_at,
            max_games=args.max_games,
            max_observations=args.max_observations,
            country_filter=country_filter,
        )
        return _summary(
            mode="dry-run",
            run_id=run_id,
            target_date=target_date,
            observation_batch_id=observation_batch_id,
            games_read=len(games),
            payloads=payloads,
            rows_written=0,
        )

    with IngestionRunTracker(
        run_type="market_observation_collection",
        source="nba_live_odds",
        season=season,
        season_type=SEASON_TYPE,
        target_date=target_date,
        provider=PROVIDER,
        details={"observation_batch_id": observation_batch_id},
    ) as tracker:
        try:
            retrieved_at = datetime.now(timezone.utc)
            games = fetcher._fetch_raw_odds()
            if games is None:
                tracker.finish(
                    "failed",
                    rows_read=0,
                    rows_written=0,
                    error_summary="NBA live odds provider returned no response",
                )
                raise RuntimeError("NBA live odds provider returned no response")
            payloads = collect(
                games,
                season=season,
                target_date=target_date,
                source_run_id=tracker.run_id,
                observation_batch_id=observation_batch_id,
                retrieved_at=retrieved_at,
                max_games=args.max_games,
                max_observations=args.max_observations,
                country_filter=country_filter,
            )
            rows_written = 0
            with get_db_context() as db:
                for header, selections in payloads:
                    registration = register_market_observation(
                        header, selections, db=db
                    )
                    if registration.header_created:
                        rows_written += 1
                db.commit()
            tracker.finish(
                "success",
                validation_status="passed",
                rows_read=len(games),
                rows_written=rows_written,
                details={
                    "observation_batch_id": observation_batch_id,
                    "observations_seen": len(payloads),
                    "selections_seen": sum(len(s) for _, s in payloads),
                },
            )
            return _summary(
                mode="apply",
                run_id=tracker.run_id,
                target_date=target_date,
                observation_batch_id=observation_batch_id,
                games_read=len(games),
                payloads=payloads,
                rows_written=rows_written,
            )
        except Exception:
            raise


def main() -> int:
    args = build_parser().parse_args()
    try:
        print(json.dumps(run(args), indent=2, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
