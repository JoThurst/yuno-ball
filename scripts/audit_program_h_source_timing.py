"""Read-only audit of source timing needed by Program H1 strict cutoffs."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import timezone

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM


def _tipoff(row: GameScheduleORM):
    if row.game_date_precision != "exact" or row.game_date is None:
        return None
    value = row.game_date
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def summarize_source_timing(*, facts: list, schedules: list, season: str, season_type: str) -> dict:
    schedules_by_game_team = {
        (str(row.game_id), int(row.team_id)): row for row in schedules
    }
    source_event_order = Counter()
    source_order_verified_fact_ids = set()
    facts_by_team = defaultdict(list)
    for fact in facts:
        facts_by_team[int(fact.canonical_team_id)].append(fact)
        source_schedule = schedules_by_game_team.get(
            (str(fact.canonical_game_id), int(fact.canonical_team_id))
        )
        if fact.data_available_at is None:
            source_event_order["missing_availability_timestamp"] += 1
        elif source_schedule is None:
            source_event_order["missing_source_schedule"] += 1
        elif (source_tipoff := _tipoff(source_schedule)) is None:
            source_event_order["date_only_source_schedule"] += 1
        elif _as_utc(fact.data_available_at) < source_tipoff:
            source_event_order["availability_before_source_tipoff"] += 1
        else:
            source_event_order["availability_at_or_after_source_tipoff"] += 1
            source_order_verified_fact_ids.add(id(fact))
    for rows in facts_by_team.values():
        rows.sort(key=lambda row: (row.game_date, str(row.canonical_game_id), str(row.fact_id)))

    schedule_precision = Counter(row.game_date_precision or "unknown" for row in schedules)
    exact_target_team_rows = 0
    exact_targets_with_any_eligible_history = 0
    eligible_prior_fact_rows = 0
    exact_target_team_rows_with_timestamped_history = 0
    for schedule in schedules:
        tipoff = _tipoff(schedule)
        if tipoff is None:
            continue
        exact_target_team_rows += 1
        eligible = [
            fact
            for fact in facts_by_team.get(int(schedule.team_id), ())
            if id(fact) in source_order_verified_fact_ids
            and fact.game_date < schedule.game_date.date()
            and _as_utc(fact.data_available_at) <= tipoff
        ]
        if eligible:
            exact_targets_with_any_eligible_history += 1
            eligible_prior_fact_rows += len(eligible)
            exact_target_team_rows_with_timestamped_history += 1

    data_available_values = [_as_utc(fact.data_available_at) for fact in facts if fact.data_available_at is not None]
    source_event_order_check_passed = not any(
        source_event_order[key]
        for key in (
            "availability_before_source_tipoff",
            "date_only_source_schedule",
            "missing_source_schedule",
            "missing_availability_timestamp",
        )
    )
    return {
        "season": season,
        "season_type": season_type,
        "fact_rows_read": len(facts),
        "schedule_rows_read": len(schedules),
        "schedule_precision": dict(sorted(schedule_precision.items())),
        "facts_with_data_available_at": len(data_available_values),
        "facts_without_data_available_at": len(facts) - len(data_available_values),
        "source_event_order": {
            key: source_event_order[key]
            for key in (
                "availability_at_or_after_source_tipoff",
                "availability_before_source_tipoff",
                "date_only_source_schedule",
                "missing_source_schedule",
                "missing_availability_timestamp",
            )
        },
        "source_event_order_check_passed": source_event_order_check_passed,
        "data_available_at_min": min(data_available_values).isoformat() if data_available_values else None,
        "data_available_at_max": max(data_available_values).isoformat() if data_available_values else None,
        "exact_target_team_rows": exact_target_team_rows,
        "exact_targets_with_any_strictly_eligible_history": exact_targets_with_any_eligible_history,
        "exact_target_team_rows_with_timestamped_history": exact_target_team_rows_with_timestamped_history,
        "eligible_prior_fact_rows": eligible_prior_fact_rows,
        "strict_source_timing_ready": (
            exact_target_team_rows > 0
            and exact_targets_with_any_eligible_history == exact_target_team_rows
            and source_event_order_check_passed
        ),
        "writes_performed": False,
    }


def run_audit(*, season: str, season_type: str) -> dict:
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
    return summarize_source_timing(
        facts=facts,
        schedules=schedules,
        season=season,
        season_type=season_type,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    args = parser.parse_args()
    print(json.dumps(run_audit(season=args.season, season_type=args.season_type), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
