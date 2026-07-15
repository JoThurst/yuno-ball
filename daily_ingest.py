"""Daily NBA ingestion orchestrator.

This is the authoritative operational entry point. It runs fetch, calculation,
and validation phases under one durable run record and one advisory job lock.

See docs/INGESTION_RUNBOOK.md for the operating contract.
"""

import argparse
from datetime import date, datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import traceback


project_root = Path(__file__).parent.absolute()
project_root_str = str(project_root)
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename="daily_ingest.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logging.getLogger("").addHandler(console)

FETCH_TASKS = [
    "players",
    "rosters",
    "schedule",
    "future",
    "teamstats",
    "schedule_reconcile",
    "gamelogs",
    "leagueteam",
    "leagueplayer",
    "injury",
    "odds",
]
CALC_TASKS = [
    "streaks",
    "heat",
    "consistency",
    "player_snapshots",
    "schedule",
    "metrics",
    "flags",
    "environment",
]

from app.services.ingestion_run_service import (
    IngestionRunAlreadyActive,
    IngestionRunTracker,
    finish_task,
    run_has_failed_tasks,
    start_task,
)
from app.services.season_context_service import resolve_active_ingestion_season
from app.services.player_snapshot_service import feature_cutoff_for_slate
from app.utils.season_utils import InvalidSeason, normalize_season


def run_script(script_name: str, args: list = None, run_id: str = None) -> bool:
    """Run one child command and preserve its exit status."""
    command = [sys.executable, script_name]
    if args:
        command.extend(args)
    logging.info("Running: %s", " ".join(command))

    child_env = os.environ.copy()
    if run_id:
        child_env["YUNOBALL_INGESTION_RUN_ID"] = run_id
    try:
        result = subprocess.run(
            command,
            check=True,
            cwd=project_root,
            env=child_env,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as exc:
        logging.error("Script failed: %s with code %s", script_name, exc.returncode)
        return False
    except Exception as exc:
        logging.error("Error running %s: %s", script_name, exc)
        return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Daily NBA data ingestion pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daily_ingest.py
  python daily_ingest.py --fetch-only
  python daily_ingest.py --calc-only
  python daily_ingest.py --fetch-tasks players rosters --calc-tasks streaks
  python daily_ingest.py --validate-only --date 2026-03-03
  python daily_ingest.py --list
        """,
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--fetch-only", action="store_true", help="Only run fetch tasks"
    )
    mode_group.add_argument(
        "--calc-only", action="store_true", help="Only run calculation tasks"
    )

    parser.add_argument("--fetch-tasks", nargs="+", choices=FETCH_TASKS)
    parser.add_argument("--calc-tasks", nargs="+", choices=CALC_TASKS)
    parser.add_argument("--exclude-fetch", nargs="+", choices=FETCH_TASKS)
    parser.add_argument("--exclude-calc", nargs="+", choices=CALC_TASKS)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--season", type=str, default=None, help="Season in YYYY-YY format")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Operational date in YYYY-MM-DD format; historical dates are validation-only until snapshot v2",
    )
    network_group = parser.add_mutually_exclusive_group()
    network_group.add_argument("--proxy", action="store_true")
    network_group.add_argument("--local", action="store_true")
    parser.add_argument(
        "--force-calc",
        action="store_true",
        help="Run calculations even if critical fetch tasks fail",
    )
    parser.add_argument(
        "--force-gamelogs",
        action="store_true",
        help="Re-fetch all gamelogs instead of using the smart refresh cache",
    )
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run read-only validation without fetch or calculation",
    )
    return parser.parse_args()


def write_success_marker(
    season: str,
    target_date: date,
    run_id: str,
    fetch_ok: bool,
    calc_ok: bool,
    validate_ok: bool,
) -> None:
    """Publish the last fully successful and validated operational run."""
    marker_dir = project_root / "data"
    marker_dir.mkdir(exist_ok=True)
    marker_path = marker_dir / "last_ingest_success.json"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "season": season,
        "target_date": target_date.isoformat(),
        "fetch_success": fetch_ok,
        "calc_success": calc_ok,
        "validation_success": validate_ok,
        "status": "success",
    }
    temporary_path = marker_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(marker_path)
    logging.info("Wrote success marker: %s", marker_path)


def _run_validation(run_id: str, season: str, target_date: date) -> bool:
    task_run_id = start_task(run_id, "validate.daily_data", source="database")
    success = run_script(
        "scripts/validate_daily_data.py",
        ["--season", season, "--date", target_date.isoformat()],
        run_id=run_id,
    )
    finish_task(
        task_run_id,
        "success" if success else "failed",
        error_summary=None if success else "Daily validation failed; see validator output",
    )
    return success


def execute_pipeline(args, current_season: str, target_date: date, run_id: str) -> dict:
    """Execute child phases and return their publication state."""
    if args.validate_only:
        validation_ok = _run_validation(run_id, current_season, target_date)
        return {
            "fetch_success": True,
            "calc_success": True,
            "validate_success": validation_ok,
            "validation_status": "passed" if validation_ok else "failed",
            "skipped_calc": False,
            "overall_ok": validation_ok,
        }

    fetch_success = True
    calc_success = True
    validate_success = True
    validation_status = "skipped"
    skipped_calc = False
    common_args = ["--season", current_season]

    if not args.calc_only:
        fetch_args = common_args.copy()
        if args.proxy:
            fetch_args.append("--proxy")
        if args.local:
            fetch_args.append("--local")
        if args.force_gamelogs:
            fetch_args.append("--force-gamelogs")
        if args.fetch_tasks:
            fetch_args.extend(["--tasks"] + args.fetch_tasks)
        if args.exclude_fetch:
            fetch_args.extend(["--exclude"] + args.exclude_fetch)

        logging.info("-" * 70)
        logging.info("PHASE 1: DATA FETCHING")
        logging.info("-" * 70)
        fetch_success = run_script("daily_fetch.py", fetch_args, run_id=run_id)
        if not fetch_success:
            logging.error("Fetch phase failed (critical tasks)!")
            if not args.fetch_only and not args.force_calc:
                logging.error(
                    "Skipping calculations to avoid stale derived metrics. "
                    "Use --force-calc to override."
                )
                skipped_calc = True

    if not args.fetch_only and not skipped_calc:
        if fetch_success or args.calc_only or args.force_calc:
            calc_args = common_args.copy()
            calc_args.extend(["--date", target_date.isoformat()])
            if args.calc_tasks:
                calc_args.extend(["--tasks"] + args.calc_tasks)
            if args.exclude_calc:
                calc_args.extend(["--exclude"] + args.exclude_calc)

            logging.info("-" * 70)
            logging.info("PHASE 2: CALCULATIONS")
            logging.info("-" * 70)
            calc_success = run_script("daily_calculate.py", calc_args, run_id=run_id)
        else:
            calc_success = False

    if not args.skip_validate and not args.fetch_only:
        if fetch_success and calc_success:
            logging.info("-" * 70)
            logging.info("PHASE 3: VALIDATION")
            logging.info("-" * 70)
            validate_success = _run_validation(run_id, current_season, target_date)
            validation_status = "passed" if validate_success else "failed"
        elif skipped_calc:
            logging.warning("Skipping validation because calculations were skipped")

    overall_ok = fetch_success and calc_success and validate_success and not skipped_calc

    logging.info("=" * 70)
    logging.info("DAILY INGEST SUMMARY")
    logging.info("  Fetch: %s", "SUCCESS" if fetch_success else "FAILED")
    if skipped_calc:
        logging.info("  Calculate: SKIPPED (critical fetch failure)")
    else:
        logging.info("  Calculate: %s", "SUCCESS" if calc_success else "FAILED")
    if not args.skip_validate and not args.fetch_only:
        logging.info("  Validate: %s", "SUCCESS" if validate_success else "FAILED")
    logging.info("=" * 70)

    return {
        "fetch_success": fetch_success,
        "calc_success": calc_success,
        "validate_success": validate_success,
        "validation_status": validation_status,
        "skipped_calc": skipped_calc,
        "overall_ok": overall_ok,
    }


def _print_task_list() -> None:
    print("\n" + "=" * 60)
    print("DAILY INGEST - Available Tasks")
    print("=" * 60)
    print("\nFetch Tasks (daily_fetch.py):")
    print("-" * 40)
    for task in FETCH_TASKS:
        print(f"  {task}")
    print("\nCalculation Tasks (daily_calculate.py):")
    print("-" * 40)
    for task in CALC_TASKS:
        print(f"  {task}")
    print("\nFor detailed task descriptions, run:")
    print("  python daily_fetch.py --list")
    print("  python daily_calculate.py --list")


def main():
    args = parse_args()
    if args.list:
        _print_task_list()
        return 0

    if args.validate_only and args.skip_validate:
        logging.error("--validate-only cannot be combined with --skip-validate")
        return 2

    try:
        target_date = (
            datetime.strptime(args.date, "%Y-%m-%d").date()
            if args.date
            else date.today()
        )
    except ValueError:
        logging.error("Invalid --date value %r; expected YYYY-MM-DD", args.date)
        return 2

    if target_date != date.today() and not args.validate_only:
        logging.error(
            "Historical --date is validation-only until versioned, leakage-safe snapshots exist"
        )
        return 2

    try:
        current_season = (
            normalize_season(args.season)
            if args.season
            else resolve_active_ingestion_season(target_date)
        )
    except InvalidSeason as exc:
        logging.error(str(exc))
        return 2
    except Exception as exc:
        logging.error("Could not resolve the active ingestion season: %s", exc)
        return 1

    logging.info("=" * 70)
    logging.info("DAILY INGEST PIPELINE")
    logging.info("Season: %s", current_season)
    logging.info("Date: %s", target_date)
    logging.info("=" * 70)

    selected_fetch_tasks = list(args.fetch_tasks or FETCH_TASKS)
    if args.exclude_fetch:
        selected_fetch_tasks = [
            task for task in selected_fetch_tasks if task not in args.exclude_fetch
        ]
    selected_calc_tasks = list(args.calc_tasks or CALC_TASKS)
    if args.exclude_calc:
        selected_calc_tasks = [
            task for task in selected_calc_tasks if task not in args.exclude_calc
        ]
    if args.calc_only or args.validate_only:
        selected_fetch_tasks = []
    if args.fetch_only or args.validate_only:
        selected_calc_tasks = []

    run_details = {
        "fetch_tasks": selected_fetch_tasks,
        "calc_tasks": selected_calc_tasks,
        "fetch_only": args.fetch_only,
        "calc_only": args.calc_only,
        "validate_only": args.validate_only,
    }
    try:
        with IngestionRunTracker(
            run_type="daily_ingest",
            source="orchestrator",
            season=current_season,
            season_type="Regular Season",
            target_date=target_date,
            feature_cutoff=feature_cutoff_for_slate(target_date),
            provider="stats.nba.com/nba-cdn",
            calculation_version="daily-v2",
            details=run_details,
        ) as tracker:
            outcome = execute_pipeline(args, current_season, target_date, tracker.run_id)
            has_failed_tasks = run_has_failed_tasks(tracker.run_id)
            run_status = (
                "failed"
                if not outcome["overall_ok"]
                else "partial"
                if has_failed_tasks
                else "success"
            )
            tracker.finish(
                run_status,
                validation_status=outcome["validation_status"],
                details={**run_details, **outcome, "has_failed_tasks": has_failed_tasks},
            )

            if (
                run_status == "success"
                and not args.validate_only
                and not args.fetch_only
                and outcome["validation_status"] == "passed"
            ):
                write_success_marker(
                    current_season,
                    target_date,
                    tracker.run_id,
                    outcome["fetch_success"],
                    outcome["calc_success"],
                    outcome["validate_success"],
                )
            return 0 if outcome["overall_ok"] else 1
    except IngestionRunAlreadyActive as exc:
        logging.error(str(exc))
        return 3
    except Exception as exc:
        logging.error("Ingestion run tracking failed: %s", exc)
        logging.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
