"""
Daily Fetch Script - Handles all NBA API data fetching tasks.

Fetches data from external APIs and stores in database.
Run this first, then run daily_calculate.py for analysis.

Usage:
    python daily_fetch.py                    # Run all fetch tasks
    python daily_fetch.py --tasks players rosters gamelogs
    python daily_fetch.py --list             # List available tasks
    python daily_fetch.py --exclude injury odds  # Run all except specified

See docs/INGESTION_RUNBOOK.md for full documentation.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to Python path FIRST
project_root = Path(__file__).parent.absolute()
project_root_str = str(project_root)
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

import logging
import traceback
import time
import socket
from dotenv import load_dotenv
from datetime import date, datetime

load_dotenv()

# Parse early CLI flags BEFORE importing fetchers / config (affects proxy + workers)
if "--proxy" in sys.argv:
    os.environ["FORCE_PROXY"] = "true"
    os.environ["FORCE_LOCAL"] = "false"
    sys.argv.remove("--proxy")

if "--local" in sys.argv:
    os.environ["FORCE_LOCAL"] = "true"
    os.environ["FORCE_PROXY"] = "false"
    sys.argv.remove("--local")

# Direct stats.nba.com cannot sustain parallel workers — throttle hard in local mode
_force_local = os.getenv("FORCE_LOCAL", "").lower() == "true"
_force_proxy = os.getenv("FORCE_PROXY", "").lower() == "true"
if _force_local and not _force_proxy:
    os.environ["MAX_WORKERS"] = "1"

# Set up logging
logging.basicConfig(
    filename="daily_fetch.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

if _force_proxy:
    logging.info("Forcing proxy usage for API calls")
elif _force_local:
    logging.info("Forcing local (direct) connection for API calls")
    logging.info("Local mode: MAX_WORKERS=1 to avoid stats.nba.com rate limits")

# Initialize database
from db_config import init_db
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
init_db(DATABASE_URL)
logging.info("Database connection pool initialized")

# Environment adjustments
def is_running_on_aws():
    try:
        socket.getaddrinfo('instance-data.ec2.internal', 80)
        return True
    except socket.gaierror:
        return False

if is_running_on_aws():
    os.environ["MAX_WORKERS"] = "1"
    logging.info("Running on AWS - Using single worker")

# Import app modules
try:
    import app
    from app.database import get_db_context
    from app.utils.fetch.team_fetcher import TeamFetcher
    from app.utils.fetch.player_fetcher import PlayerFetcher
    from app.utils.fetch.schedule_fetcher import ScheduleFetcher
    from app.utils.fetch.smart_gamelog_fetcher import SmartGameLogFetcher
    from app.utils.fetch.injury_fetcher import InjuryFetcher
    from app.utils.fetch.odds_fetcher import OddsFetcher
except Exception as e:
    logging.error(f"Import error: {e}")
    logging.error(traceback.format_exc())
    raise


from app.services.ingestion_run_service import IngestionRunTracker, finish_task, start_task
from app.services.schedule_result_reconciliation_service import (
    reconcile_schedule_results_from_team_stats,
)
from app.services.season_context_service import resolve_active_ingestion_season
from app.utils.season_utils import InvalidSeason, normalize_season, season_year_range

# Tasks whose failure should fail the overall fetch (blocks calculate in daily_ingest).
# `future` is non-critical: offseason CDN often has no upcoming games / 403s, and
# schedule already covers past+future when it succeeds.
CRITICAL_FETCH_TASKS = frozenset({
    'players', 'rosters', 'schedule', 'teamstats', 'schedule_reconcile',
    'gamelogs', 'leagueteam', 'leagueplayer',
})


def run_task(task_name, task_function, *args, **kwargs):
    """Run a task with timing and error handling."""
    start_time = time.perf_counter()
    logging.info(f"Starting task: {task_name}")
    try:
        result = task_function(*args, **kwargs)
        duration = time.perf_counter() - start_time
        logging.info(f"✓ Completed: {task_name} in {duration:.1f}s")
        return True, result, None
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.error(f"✗ Failed: {task_name} after {duration:.1f}s - {str(e)}")
        logging.error(traceback.format_exc())
        return False, None, e


# ============================================================================
# TASK DEFINITIONS
# ============================================================================

FETCH_TASKS = {
    'players': {
        'name': 'Sync active players',
        'description': 'Sync active players and update available_seasons',
        'delay_after': 10
    },
    'rosters': {
        'name': 'Update current rosters',
        'description': 'Fetch and update current team rosters',
        'delay_after': 10
    },
    'schedule': {
        'name': 'Update game schedule',
        'description': 'Update game schedule with results',
        'delay_after': 10
    },
    'future': {
        'name': 'Update future games',
        'description': 'Fetch upcoming game schedule',
        'delay_after': 60
    },
    'teamstats': {
        'name': 'Update team stats',
        'description': 'Fetch team game stats for season',
        'delay_after': 20
    },
    'schedule_reconcile': {
        'name': 'Reconcile schedule results',
        'description': 'Repair null final schedule results from paired team game stats',
        'delay_after': 0
    },
    'gamelogs': {
        'name': 'Fetch game logs',
        'description': 'Fetch player game logs for current season',
        'delay_after': 15
    },
    'leagueteam': {
        'name': 'Update league dash team stats',
        'description': 'Fetch league-wide team statistics',
        'delay_after': 10
    },
    'leagueplayer': {
        'name': 'Update league dash player stats',
        'description': 'Fetch league-wide player statistics',
        'delay_after': 10
    },
    'injury': {
        'name': 'Fetch injury data',
        'description': 'Fetch player injury/status from boxscores (batch)',
        'delay_after': 0  # Fetcher handles rate limiting
    },
    'odds': {
        'name': 'Fetch game odds',
        'description': "Fetch today's game betting odds",
        'delay_after': 0
    },
}


def _reconcile_schedule_results(season: str) -> dict[str, int]:
    """Run the local result repair in the same fetch phase transaction boundary."""
    with get_db_context() as db:
        return reconcile_schedule_results_from_team_stats(db, season=season)


def run_fetch_tasks(tasks_to_run: list, current_season: str, run_id: str = None):
    """Run specified fetch tasks.

    Returns:
        (tasks_completed, tasks_failed, critical_failed)
        critical_failed is True if any CRITICAL_FETCH_TASKS failed.
    """
    team_fetcher = TeamFetcher()
    player_fetcher = PlayerFetcher()
    schedule_fetcher = ScheduleFetcher()
    gamelog_fetcher = SmartGameLogFetcher()
    injury_fetcher = InjuryFetcher()
    odds_fetcher = OddsFetcher()

    season_from, season_to = season_year_range(current_season)

    tasks_completed = 0
    tasks_failed = 0
    critical_failed = False
    failed_task_keys = []

    for task_key in tasks_to_run:
        task_info = FETCH_TASKS.get(task_key)
        if not task_info:
            logging.warning(f"Unknown task: {task_key}")
            continue

        task_run_id = None
        if run_id:
            task_source = "derived" if task_key == "schedule_reconcile" else "nba"
            task_provider = (
                "team_game_stats"
                if task_key == "schedule_reconcile"
                else "stats.nba.com/nba-cdn"
            )
            task_run_id = start_task(
                run_id,
                f"fetch.{task_key}",
                source=task_source,
                provider=task_provider,
            )

        success = False
        result = None
        error = None

        if task_key == 'players':
            success, result, error = run_task(
                task_info['name'],
                player_fetcher.sync_active_players,
                current_season=current_season
            )

        elif task_key == 'rosters':
            success, result, error = run_task(
                task_info['name'],
                team_fetcher.fetch_current_rosters
            )

        elif task_key == 'schedule':
            success, result, error = run_task(
                task_info['name'],
                schedule_fetcher.fetch_and_store_schedule,
                current_season
            )

        elif task_key == 'future':
            success, result, error = run_task(
                task_info['name'],
                schedule_fetcher.fetch_and_store_future_games,
                current_season
            )

        elif task_key == 'teamstats':
            success, result, error = run_task(
                task_info['name'],
                team_fetcher.fetch_team_game_stats_for_season,
                season=current_season
            )

        elif task_key == 'schedule_reconcile':
            success, result, error = run_task(
                task_info['name'],
                _reconcile_schedule_results,
                current_season,
            )

        elif task_key == 'gamelogs':
            success, result, error = run_task(
                task_info['name'],
                gamelog_fetcher.fetch_game_logs_tiered,
                tier="current",
                current_season=current_season,
            )

        elif task_key == 'leagueteam':
            success, result, error = run_task(
                task_info['name'],
                team_fetcher.fetch_league_dash_team_stats,
                season=current_season
            )

        elif task_key == 'leagueplayer':
            success, result, error = run_task(
                task_info['name'],
                player_fetcher.fetch_league_dash_player_stats,
                season_from=season_from,
                season_to=season_to,
            )

        elif task_key == 'injury':
            # Daily path: last 14 days (wider than prior 7 for reliability).
            # Full-season backfill: pass start_date/end_date explicitly to InjuryFetcher.
            success, result, error = run_task(
                task_info['name'],
                lambda: injury_fetcher.fetch_injury_data(
                    season=current_season,
                    lookback_days=14,
                )
            )

        elif task_key == 'odds':
            success, result, error = run_task(
                task_info['name'],
                lambda: odds_fetcher.fetch_todays_odds(season=current_season)
            )

        if task_run_id:
            finish_task(
                task_run_id,
                "success" if success else "failed",
                result=result,
                error=error,
                error_summary=None if success else str(error),
            )

        if success:
            tasks_completed += 1
        else:
            tasks_failed += 1
            failed_task_keys.append(task_key)
            if task_key in CRITICAL_FETCH_TASKS:
                critical_failed = True

        if task_info['delay_after'] > 0:
            time.sleep(task_info['delay_after'])

    if failed_task_keys:
        logging.warning(f"Failed tasks: {', '.join(failed_task_keys)}")
    if critical_failed:
        logging.error("One or more critical fetch tasks failed")

    return tasks_completed, tasks_failed, critical_failed


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Daily NBA data fetch script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daily_fetch.py                          # Run all tasks
  python daily_fetch.py --tasks players rosters  # Run specific tasks
  python daily_fetch.py --exclude injury odds    # Run all except specified
  python daily_fetch.py --list                   # List available tasks
  python daily_fetch.py --proxy                  # Force proxy usage
  python daily_fetch.py --local                  # Force local/direct connection
        """
    )
    parser.add_argument('--tasks', nargs='+', choices=list(FETCH_TASKS.keys()),
                       help='Specific tasks to run')
    parser.add_argument('--exclude', nargs='+', choices=list(FETCH_TASKS.keys()),
                       help='Tasks to exclude from run')
    parser.add_argument('--list', action='store_true',
                       help='List available tasks and exit')
    parser.add_argument('--season', type=str, default=None,
                       help='Override season (e.g., "2024-25")')
    parser.add_argument('--force-gamelogs', action='store_true',
                       help='Re-fetch all gamelogs (skip cache optimization)')
    return parser.parse_args()


def main():
    """Main entry point. Exit 0 on success, 1 if any critical task failed."""
    args = parse_args()

    # List tasks and exit
    if args.list:
        print("\nAvailable Fetch Tasks:")
        print("-" * 60)
        for key, info in FETCH_TASKS.items():
            print(f"  {key:15} - {info['description']}")
        print("\nDefault order:", ', '.join(FETCH_TASKS.keys()))
        print("\nCritical tasks (block calculate on failure):",
              ', '.join(sorted(CRITICAL_FETCH_TASKS)))
        return 0

    # Determine which tasks to run
    if args.tasks:
        tasks_to_run = args.tasks
    else:
        tasks_to_run = list(FETCH_TASKS.keys())

    # Apply exclusions
    if args.exclude:
        tasks_to_run = [t for t in tasks_to_run if t not in args.exclude]

    try:
        current_season = (
            normalize_season(args.season)
            if args.season
            else resolve_active_ingestion_season(date.today())
        )
    except InvalidSeason as exc:
        logging.error(str(exc))
        return 2
    except Exception as exc:
        logging.error("Could not resolve the active ingestion season: %s", exc)
        return 1

    if args.force_gamelogs:
        os.environ["FORCE_GAMELOG_REFRESH"] = "true"

    logging.info("=" * 70)
    logging.info("Starting Daily Fetch")
    logging.info(f"Season: {current_season}")
    logging.info(f"Tasks to run: {', '.join(tasks_to_run)}")
    logging.info("=" * 70)

    parent_run_id = os.getenv("YUNOBALL_INGESTION_RUN_ID")
    if parent_run_id:
        completed, failed, critical_failed = run_fetch_tasks(
            tasks_to_run,
            current_season,
            run_id=parent_run_id,
        )
    else:
        try:
            with IngestionRunTracker(
                run_type="daily_fetch",
                source="nba",
                season=current_season,
                target_date=date.today(),
                provider="stats.nba.com/nba-cdn",
                details={"tasks": tasks_to_run},
            ) as tracker:
                completed, failed, critical_failed = run_fetch_tasks(
                    tasks_to_run,
                    current_season,
                    run_id=tracker.run_id,
                )
                run_status = (
                    "failed"
                    if critical_failed
                    else "partial"
                    if failed
                    else "success"
                )
                tracker.finish(
                    run_status,
                    validation_status="not_run",
                    details={
                        "tasks": tasks_to_run,
                        "tasks_completed": completed,
                        "tasks_failed": failed,
                        "critical_failed": critical_failed,
                    },
                )
        except Exception as exc:
            logging.error("Fetch run tracking failed: %s", exc)
            logging.error(traceback.format_exc())
            return 1

    logging.info("=" * 70)
    logging.info(f"Daily Fetch Complete: {completed} succeeded, {failed} failed")
    if critical_failed:
        logging.error("CRITICAL FAILURES present — exit code 1")
    logging.info("=" * 70)

    return 1 if critical_failed else 0


if __name__ == "__main__":
    sys.exit(main())

