"""Bounded repair of null historical schedule results from local team-game facts."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import get_db_context
from app.services.ingestion_run_service import IngestionRunTracker
from app.services.schedule_result_reconciliation_service import (
    ScheduleResultPlan,
    apply_schedule_result_plan,
    build_schedule_result_plan,
    load_schedule_result_sources,
)
from app.utils.season_utils import normalize_season


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile null Regular Season game_schedule results from paired "
            "team_game_stats rows"
        )
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--from-date", required=True, type=_parse_date)
    parser.add_argument("--to-date", required=True, type=_parse_date)
    parser.add_argument(
        "--max-days",
        type=int,
        default=62,
        help="Maximum inclusive calendar span (default: 62)",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=500,
        help="Maximum scheduled games inspected (default: 500)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def _print_plan(plan: ScheduleResultPlan) -> None:
    print(
        "PLAN "
        f"inspected_games={plan.inspected_games} "
        f"eligible_games={plan.eligible_games} "
        f"already_complete_games={plan.already_complete_games} "
        f"candidate_rows={len(plan.updates)} "
        f"issues={len(plan.issues)}"
    )
    for issue in plan.issues[:25]:
        print(f"  BLOCKED game={issue.game_id}: {issue.reason}")
    if len(plan.issues) > 25:
        print(f"  ... {len(plan.issues) - 25} additional issue(s) omitted")
    for candidate in plan.updates[:10]:
        print(
            "  CANDIDATE "
            f"game={candidate.game_id} team={candidate.team_id} "
            f"result={candidate.result} score={candidate.score}"
        )
    if len(plan.updates) > 10:
        print(f"  ... {len(plan.updates) - 10} additional candidate row(s) omitted")


def main() -> int:
    args = parse_args()
    season = normalize_season(args.season)
    if args.from_date > args.to_date:
        raise SystemExit("--from-date must be on or before --to-date")
    if args.max_days < 1 or args.max_games < 1:
        raise SystemExit("--max-days and --max-games must be positive")
    inclusive_days = (args.to_date - args.from_date).days + 1
    if inclusive_days > args.max_days:
        raise SystemExit(
            f"Refusing {inclusive_days} calendar days; split the range or raise --max-days"
        )

    with get_db_context() as db:
        schedule_rows, team_game_rows = load_schedule_result_sources(
            db,
            season=season,
            from_date=args.from_date,
            to_date=args.to_date,
        )
    inspected_games = len({row.game_id for row in schedule_rows})
    if inspected_games > args.max_games:
        raise SystemExit(
            f"Refusing {inspected_games} scheduled games; split the range or raise --max-games"
        )

    plan = build_schedule_result_plan(schedule_rows, team_game_rows)
    _print_plan(plan)
    if plan.issues:
        print("REFUSED: resolve every blocked game before applying this range.")
        return 1
    if args.dry_run:
        print("DRY RUN: no schedule rows changed.")
        return 0
    if not plan.updates:
        print("APPLIED rows=0 (range already reconciled or empty).")
        return 0

    with IngestionRunTracker(
        run_type="schedule_result_reconciliation",
        source="derived",
        season=season,
        season_type="Regular Season",
        target_date=args.to_date,
        provider="team_game_stats",
        details={
            "from_date": args.from_date.isoformat(),
            "to_date": args.to_date.isoformat(),
            "inspected_games": plan.inspected_games,
            "eligible_games": plan.eligible_games,
        },
    ) as tracker:
        with get_db_context() as db:
            updated_rows = apply_schedule_result_plan(db, plan)
        tracker.finish(
            "success",
            validation_status="not_run",
            rows_written=updated_rows,
            details={
                "from_date": args.from_date.isoformat(),
                "to_date": args.to_date.isoformat(),
                "eligible_games": plan.eligible_games,
                "updated_rows": updated_rows,
            },
        )
    print(f"APPLIED games={plan.eligible_games} rows={updated_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
