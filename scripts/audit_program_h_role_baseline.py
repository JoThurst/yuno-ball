"""Read-only backtest of the H1 descriptive role band against actual minutes."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import timezone
from statistics import median

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM
from app.services.player_role_baseline_service import (
    build_pregame_role_baseline,
    build_role_history_observation,
    parse_minutes,
)


def _tipoff(row):
    if row.game_date_precision != "exact" or row.game_date is None:
        return None
    value = row.game_date
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bucket(played_games_used: int, window_size: int) -> str:
    if played_games_used == 0:
        return "0"
    if played_games_used < min(5, window_size):
        return "1-4"
    if played_games_used < window_size:
        return "5-9"
    return str(window_size)


def run_audit(
    *,
    season: str,
    season_type: str,
    window_size: int,
    low_percentile: float = 0.25,
    high_percentile: float = 0.75,
) -> dict:
    with get_db_context() as db:
        facts = (
            db.query(PlayerGameFactORM)
            .filter(
                PlayerGameFactORM.season == season,
                PlayerGameFactORM.season_type == season_type,
            )
            .all()
        )
        schedules = (
            db.query(GameScheduleORM)
            .filter(
                GameScheduleORM.season == season,
                GameScheduleORM.season_type == season_type,
            )
            .all()
        )

    history = [build_role_history_observation(fact) for fact in facts]
    schedules_by_key = {
        (str(row.game_id), int(row.team_id)): row
        for row in schedules
        if row.game_date is not None
    }
    history_by_player_team: dict[tuple[int, int], list] = defaultdict(list)
    for row in history:
        history_by_player_team[(row.canonical_player_id, row.canonical_team_id)].append(row)
    errors: list[float] = []
    coverage: list[bool] = []
    cohorts: dict[str, list[dict]] = defaultdict(list)
    evaluated = 0
    for fact in facts:
        actual = parse_minutes(fact.minutes)
        schedule = schedules_by_key.get((str(fact.canonical_game_id), int(fact.canonical_team_id)))
        if actual is None or fact.participation_status != "played" or schedule is None:
            continue
        tipoff = _tipoff(schedule)
        feature_as_of = tipoff or schedule.game_date.replace(tzinfo=timezone.utc)
        result = build_pregame_role_baseline(
            history_by_player_team[(int(fact.canonical_player_id), int(fact.canonical_team_id))],
            canonical_game_id=str(fact.canonical_game_id),
            canonical_player_id=int(fact.canonical_player_id),
            canonical_team_id=int(fact.canonical_team_id),
            target_game_date=schedule.game_date.date(),
            season=season,
            season_type=season_type,
            feature_as_of=feature_as_of,
            scheduled_tipoff=tipoff,
            source_run_id="audit-only",
            window_size=window_size,
            timing_policy="historical_game_date_proxy",
            low_percentile=low_percentile,
            high_percentile=high_percentile,
        )
        median_minutes = result["baseline_minutes_median"]
        if median_minutes is None:
            continue
        evaluated += 1
        error = abs(float(actual) - float(median_minutes))
        inside_band = (
            result["baseline_minutes_low"] <= actual <= result["baseline_minutes_high"]
        )
        errors.append(error)
        coverage.append(inside_band)
        cohorts[_bucket(result["played_games_used"], window_size)].append(
            {"error": error, "inside_band": inside_band}
        )

    return {
        "season": season,
        "season_type": season_type,
        "window_size": window_size,
        "low_percentile": low_percentile,
        "high_percentile": high_percentile,
        "fact_rows_read": len(facts),
        "exact_schedule_team_rows": len(schedules_by_key),
        "evaluated_player_games": evaluated,
        "median_absolute_error_minutes": round(float(median(errors)), 2) if errors else None,
        "role_band_coverage": round(sum(coverage) / len(coverage), 4) if coverage else None,
        "cohorts": {
            key: {
                "n": len(rows),
                "median_absolute_error_minutes": round(float(median(row["error"] for row in rows)), 2),
                "role_band_coverage": round(sum(row["inside_band"] for row in rows) / len(rows), 4),
            }
            for key, rows in sorted(cohorts.items())
        },
        "writes_performed": False,
        "timing_policy": "historical_game_date_proxy",
        "production_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--window-size", type=int, default=10)
    parser.add_argument("--low-percentile", type=float, default=0.25)
    parser.add_argument("--high-percentile", type=float, default=0.75)
    args = parser.parse_args()
    if args.window_size < 1 or not 0 <= args.low_percentile < 0.5 < args.high_percentile <= 1:
        parser.error("invalid window or band percentiles")
    print(run_audit(
        season=args.season,
        season_type=args.season_type,
        window_size=args.window_size,
        low_percentile=args.low_percentile,
        high_percentile=args.high_percentile,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
