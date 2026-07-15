"""
Daily Calculate Script - Handles all calculation/analysis tasks.

Runs analysis on data already in the database.
Run daily_fetch.py first to get fresh data.

Usage:
    python daily_calculate.py                     # Run all calculations
    python daily_calculate.py --tasks streaks heat consistency
    python daily_calculate.py --list              # List available tasks
    python daily_calculate.py --exclude flags     # Run all except specified

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
from dotenv import load_dotenv
from datetime import datetime, date

load_dotenv()

# Set up logging
logging.basicConfig(
    filename="daily_calculate.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Initialize database
from db_config import init_db
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
init_db(DATABASE_URL)
logging.info("Database connection pool initialized")

# Import app modules
try:
    import app
    from app.services.streak_calculation_service import StreakCalculationService
    from app.services.heat_index_service import HeatIndexService
    from app.services.consistency_service import ConsistencyService
    from app.services.schedule_analysis_service import ScheduleAnalysisService
    from app.services.team_metrics_service import TeamMetricsService
    from app.services.team_flags_service import TeamFlagsService
    from app.services.game_environment_service import GameEnvironmentService
    from app.services.player_snapshot_service import (
        build_snapshot_context,
        feature_cutoff_for_slate,
        publish_player_snapshots,
    )
    from app.services.team_snapshot_service import (
        build_team_snapshot_context,
        publish_team_game_snapshots,
    )
except Exception as e:
    logging.error(f"Import error: {e}")
    logging.error(traceback.format_exc())
    raise


from app.services.ingestion_run_service import (
    IngestionRunTracker,
    finish_task,
    start_task,
)
from app.services.season_context_service import resolve_active_ingestion_season
from app.utils.season_utils import InvalidSeason, normalize_season


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

CALC_TASKS = {
    'streaks': {
        'name': 'Calculate streak metrics',
        'description': 'Consecutive streaks and recent form windows',
        'delay_after': 10
    },
    'heat': {
        'name': 'Calculate heat index',
        'description': 'Hot/cold player identification (recent vs season)',
        'delay_after': 10
    },
    'consistency': {
        'name': 'Calculate consistency metrics',
        'description': 'Player volatility/CV for each stat',
        'delay_after': 10
    },
    'player_snapshots': {
        'name': 'Publish versioned player snapshots',
        'description': 'Leakage-safe player analytics at the target slate cutoff',
        'delay_after': 0
    },
    'schedule': {
        'name': 'Calculate schedule factors',
        'description': 'B2B, rest days, rest advantage analysis',
        'delay_after': 5
    },
    'team_snapshots': {
        'name': 'Publish versioned team/game snapshots',
        'description': 'Leakage-safe team features and game environments at the slate cutoff',
        'delay_after': 0
    },
    'metrics': {
        'name': 'Calculate team metrics',
        'description': 'Team performance + Strength of Schedule',
        'delay_after': 10
    },
    'flags': {
        'name': 'Generate team flags',
        'description': 'Qualitative performance tags',
        'delay_after': 5
    },
    'environment': {
        'name': 'Calculate game environments',
        'description': "Today's game context analysis",
        'delay_after': 5
    },
}


def run_calc_tasks(
    tasks_to_run: list,
    current_season: str,
    calculation_date: date,
    run_id: str = None,
):
    """Run specified calculation tasks."""
    streak_service = StreakCalculationService()
    heat_service = HeatIndexService()
    consistency_service = ConsistencyService()
    schedule_service = ScheduleAnalysisService()
    metrics_service = TeamMetricsService()
    flags_service = TeamFlagsService()
    env_service = GameEnvironmentService()
    
    tasks_completed = 0
    tasks_failed = 0
    
    for task_key in tasks_to_run:
        task_info = CALC_TASKS.get(task_key)
        if not task_info:
            logging.warning(f"Unknown task: {task_key}")
            continue

        task_run_id = None
        if run_id:
            task_run_id = start_task(
                run_id,
                f"calculate.{task_key}",
                source="derived",
                provider="yunoball",
                details={"calculation_date": calculation_date.isoformat()},
            )

        success = False
        result = None
        error = None
        
        if task_key == 'streaks':
            def calc_streaks():
                streaks, windows = streak_service.calculate_all_players(
                    season=current_season,
                    window_sizes=[5, 10]
                )
                logging.info(f"Streaks: {streaks} consecutive, {windows} windows")
                return streaks + windows
            success, result, error = run_task(task_info['name'], calc_streaks)
        
        elif task_key == 'heat':
            def calc_heat():
                indices = heat_service.calculate_all_players(
                    season=current_season,
                    window_sizes=[3, 5, 10]
                )
                logging.info(f"Heat index: {len(indices)} calculations")
                return len(indices)
            success, result, error = run_task(task_info['name'], calc_heat)
        
        elif task_key == 'consistency':
            def calc_consistency():
                count = consistency_service.calculate_all_players(
                    season=current_season,
                    window_sizes=[0, 10]
                )
                logging.info(f"Consistency: {count} records")
                return count
            success, result, error = run_task(task_info['name'], calc_consistency)

        elif task_key == 'player_snapshots':
            def calc_player_snapshots():
                if not run_id:
                    raise ValueError("A durable ingestion run is required for snapshot publication")
                context = build_snapshot_context(
                    season=current_season,
                    target_date=calculation_date,
                    source_run_id=run_id,
                )
                counts = publish_player_snapshots(context)
                logging.info("Player snapshots: %s", counts)
                return sum(counts.values())
            success, result, error = run_task(task_info['name'], calc_player_snapshots)
        
        elif task_key == 'schedule':
            def calc_schedule():
                factors = schedule_service.calculate_for_season(season=current_season)
                logging.info(f"Schedule factors: {len(factors)} records")
                return len(factors)
            success, result, error = run_task(task_info['name'], calc_schedule)

        elif task_key == 'team_snapshots':
            def calc_team_snapshots():
                if not run_id:
                    raise ValueError("A durable ingestion run is required for snapshot publication")
                context = build_team_snapshot_context(
                    season=current_season,
                    target_date=calculation_date,
                    source_run_id=run_id,
                )
                counts = publish_team_game_snapshots(context)
                logging.info("Team/game snapshots: %s", counts)
                return sum(counts.values())
            success, result, error = run_task(task_info['name'], calc_team_snapshots)
        
        elif task_key == 'metrics':
            def calc_metrics():
                metrics = metrics_service.calculate_all_teams(
                    season=current_season,
                    window_size=10,
                    stat_date=calculation_date
                )
                logging.info(f"Team metrics: {len(metrics)} teams")
                return len(metrics)
            success, result, error = run_task(task_info['name'], calc_metrics)
        
        elif task_key == 'flags':
            def calc_flags():
                flags = flags_service.generate_all_flags(
                    season=current_season,
                    window_size=10,
                    stat_date=calculation_date
                )
                logging.info(f"Team flags: {len(flags)} flags")
                return len(flags)
            success, result, error = run_task(task_info['name'], calc_flags)
        
        elif task_key == 'environment':
            def calc_env():
                envs = env_service.calculate_for_date(
                    target_date=calculation_date,
                    season=current_season,
                    window_size=10
                )
                logging.info(f"Game environments: {len(envs)} games")
                return len(envs)
            success, result, error = run_task(task_info['name'], calc_env)

        if task_run_id:
            finish_task(
                task_run_id,
                "success" if success else "failed",
                result=result,
                error=error,
                error_summary=None if success else str(error),
            )
        
        tasks_completed += 1 if success else 0
        tasks_failed += 0 if success else 1
        
        if task_info['delay_after'] > 0:
            time.sleep(task_info['delay_after'])
    
    return tasks_completed, tasks_failed


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Daily NBA calculation/analysis script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daily_calculate.py                           # Run all calculations
  python daily_calculate.py --tasks streaks heat      # Run specific tasks
  python daily_calculate.py --exclude flags           # Run all except specified
  python daily_calculate.py --list                    # List available tasks

Task Order (recommended):
  1. streaks     - Needs gamelogs
  2. heat        - Needs gamelogs  
  3. consistency - Needs gamelogs
  4. player_snapshots - Versioned, pre-slate player analytics
  5. schedule    - Needs game schedule
  6. team_snapshots - Versioned pregame team/game analytics
  7. metrics     - Latest-state compatibility projection
  8. flags       - Latest-state compatibility projection
  9. environment - Latest-state compatibility projection
        """
    )
    parser.add_argument('--tasks', nargs='+', choices=list(CALC_TASKS.keys()),
                       help='Specific tasks to run')
    parser.add_argument('--exclude', nargs='+', choices=list(CALC_TASKS.keys()),
                       help='Tasks to exclude from run')
    parser.add_argument('--list', action='store_true',
                       help='List available tasks and exit')
    parser.add_argument('--season', type=str, default=None,
                       help='Override season (e.g., "2024-25")')
    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Operational calculation date in YYYY-MM-DD format (historical dates are not yet supported)',
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # List tasks and exit
    if args.list:
        print("\nAvailable Calculation Tasks:")
        print("-" * 60)
        for key, info in CALC_TASKS.items():
            print(f"  {key:15} - {info['description']}")
        print("\nRecommended order:", ', '.join(CALC_TASKS.keys()))
        return 0

    try:
        calculation_date = (
            datetime.strptime(args.date, "%Y-%m-%d").date()
            if args.date
            else date.today()
        )
    except ValueError:
        logging.error("Invalid --date value %r; expected YYYY-MM-DD", args.date)
        return 2

    # Existing derived tables are latest-season replacements and are not safe for
    # historical as-of calculation. Reject historical labels until snapshot v2.
    if calculation_date != date.today():
        logging.error(
            "Historical calculation dates are disabled until versioned, leakage-safe snapshots exist"
        )
        return 2
    
    # Determine which tasks to run
    if args.tasks:
        tasks_to_run = args.tasks
    else:
        tasks_to_run = list(CALC_TASKS.keys())
    
    # Apply exclusions
    if args.exclude:
        tasks_to_run = [t for t in tasks_to_run if t not in args.exclude]
    
    try:
        current_season = (
            normalize_season(args.season)
            if args.season
            else resolve_active_ingestion_season(calculation_date)
        )
    except InvalidSeason as exc:
        logging.error(str(exc))
        return 2
    except Exception as exc:
        logging.error("Could not resolve the active ingestion season: %s", exc)
        return 1
    
    logging.info("=" * 70)
    logging.info("Starting Daily Calculations")
    logging.info(f"Season: {current_season}")
    logging.info(f"Date: {calculation_date}")
    logging.info(f"Tasks to run: {', '.join(tasks_to_run)}")
    logging.info("=" * 70)
    
    parent_run_id = os.getenv("YUNOBALL_INGESTION_RUN_ID")

    if parent_run_id:
        completed, failed = run_calc_tasks(
            tasks_to_run,
            current_season,
            calculation_date,
            run_id=parent_run_id,
        )
    else:
        try:
            with IngestionRunTracker(
                run_type="daily_calculate",
                source="derived",
                season=current_season,
                season_type="Regular Season",
                target_date=calculation_date,
                feature_cutoff=feature_cutoff_for_slate(calculation_date),
                calculation_version="daily-v2",
                details={"tasks": tasks_to_run},
            ) as tracker:
                completed, failed = run_calc_tasks(
                    tasks_to_run,
                    current_season,
                    calculation_date,
                    run_id=tracker.run_id,
                )
                tracker.finish(
                    "success" if failed == 0 else "failed",
                    validation_status="not_run",
                    details={
                        "tasks": tasks_to_run,
                        "tasks_completed": completed,
                        "tasks_failed": failed,
                    },
                )
        except Exception as exc:
            logging.error("Calculation run tracking failed: %s", exc)
            logging.error(traceback.format_exc())
            return 1
    
    logging.info("=" * 70)
    logging.info(f"Daily Calculations Complete: {completed} succeeded, {failed} failed")
    logging.info("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

