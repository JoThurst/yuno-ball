"""Bounded multi-game collection helpers shared by Program C collectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import sys
from typing import Any, Callable, Iterable, Mapping, Sequence

from sqlalchemy.orm import Session

from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.services.traditional_boxscore_v3_adapter import (
    TraditionalBoxScoreV3Adapter,
    reconcile_player_totals,
    response_sha256,
    transform_payload,
)


MAX_BOUNDED_GAMES = 25


@dataclass(frozen=True)
class CompletedGameSpec:
    game_id: str
    game_date: date
    season: str
    season_type: str
    team_ids: tuple[int, int]


def validate_game_bound(game_ids: Sequence[str], *, max_games: int) -> list[str]:
    normalized = list(dict.fromkeys(str(game_id).strip() for game_id in game_ids if str(game_id).strip()))
    if not 1 <= max_games <= MAX_BOUNDED_GAMES:
        raise ValueError(f"max_games must be between 1 and {MAX_BOUNDED_GAMES}")
    if not normalized or len(normalized) > max_games:
        raise ValueError("game_ids must be non-empty, unique, and within max_games")
    return normalized


def resolve_completed_game_specs(
    db: Session,
    game_ids: Sequence[str],
    *,
    season: str,
    season_type: str,
) -> list[CompletedGameSpec]:
    """Resolve exact reciprocal completed schedule identities."""
    normalized = list(dict.fromkeys(game_ids))
    rows = (
        db.query(GameScheduleORM)
        .filter(GameScheduleORM.game_id.in_(normalized))
        .order_by(GameScheduleORM.game_id, GameScheduleORM.team_id)
        .all()
    )
    by_game: dict[str, list[GameScheduleORM]] = {game_id: [] for game_id in normalized}
    for row in rows:
        by_game.setdefault(str(row.game_id), []).append(row)

    specs: list[CompletedGameSpec] = []
    for game_id in normalized:
        pair = by_game.get(game_id, [])
        if len(pair) != 2:
            raise ValueError(f"Game {game_id} requires exactly two schedule rows; found {len(pair)}")
        first, second = pair
        if first.team_id != second.opponent_team_id or second.team_id != first.opponent_team_id:
            raise ValueError(f"Game {game_id} schedule rows are not reciprocal")
        if any(row.result not in {"W", "L"} for row in pair):
            raise ValueError(f"Game {game_id} is not completed")
        if any(row.season != season or row.season_type != season_type for row in pair):
            raise ValueError(f"Game {game_id} season identity mismatch")
        dates = {
            row.game_date.date() if hasattr(row.game_date, "date") else row.game_date
            for row in pair
        }
        if len(dates) != 1:
            raise ValueError(f"Game {game_id} reciprocal rows disagree on date")
        specs.append(
            CompletedGameSpec(
                game_id=game_id,
                game_date=dates.pop(),
                season=season,
                season_type=season_type,
                team_ids=tuple(sorted((int(first.team_id), int(second.team_id)))),
            )
        )
    return specs


def collect_traditional_games(
    specs: Sequence[CompletedGameSpec],
    *,
    run_id: str,
    max_games: int,
    adapter: TraditionalBoxScoreV3Adapter | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch and reconcile every game before returning any publishable facts."""
    validate_game_bound([spec.game_id for spec in specs], max_games=max_games)
    adapter = adapter or TraditionalBoxScoreV3Adapter()
    all_facts: list[dict[str, Any]] = []
    game_results: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        print(
            f"[{index}/{len(specs)}] Traditional V3 {spec.game_id}",
            file=sys.stderr,
            flush=True,
        )
        payload = adapter.fetch_game(spec.game_id)
        retrieved_at = datetime.now(timezone.utc)
        if progress_callback:
            progress_callback(
                {
                    "game_id": spec.game_id,
                    "response_sha256": response_sha256(payload),
                    "retrieved_at": retrieved_at.isoformat(),
                }
            )
        facts = transform_payload(
            payload,
            game_id=spec.game_id,
            game_date=spec.game_date,
            season=spec.season,
            season_type=spec.season_type,
            run_id=run_id,
            retrieved_at=retrieved_at,
        )
        if not facts:
            raise ValueError(f"Traditional V3 returned zero player rows for {spec.game_id}")
        source_team_ids = {int(fact["source_team_id"]) for fact in facts}
        if source_team_ids != set(spec.team_ids):
            raise ValueError(
                f"Traditional V3 team identity mismatch for {spec.game_id}: "
                f"{sorted(source_team_ids)} != {list(spec.team_ids)}"
            )
        reconciliation = reconcile_player_totals(payload, facts)
        all_facts.extend(facts)
        game_results.append(
            {
                "game_id": spec.game_id,
                "game_date": spec.game_date.isoformat(),
                "player_rows": len(facts),
                "dnp_rows": sum(
                    fact["participation_status"] == "did_not_play" for fact in facts
                ),
                "unknown_participation_rows": sum(
                    fact["participation_status"] == "unknown" for fact in facts
                ),
                "response_sha256": facts[0]["raw_payload"]["response_sha256"],
                "retrieved_at": facts[0]["retrieved_at"].isoformat(),
                "reconciliation": reconciliation,
            }
        )
    canonical_keys = {
        (
            fact["canonical_game_id"],
            fact["canonical_player_id"],
            fact["canonical_team_id"],
        )
        for fact in all_facts
    }
    if len(canonical_keys) != len(all_facts):
        raise ValueError("Traditional V3 collection contains duplicate canonical player rows")
    return all_facts, game_results
