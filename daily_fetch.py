"""
Daily Fetch Script - Handles all NBA API data fetching tasks.

Fetches data from external APIs and stores in database.
Run this first, then run daily_calculate.py for analysis.

Usage:
    python daily_fetch.py                    # Run all fetch tasks
    python daily_fetch.py --tasks players rosters gamelogs
    python daily_fetch.py --list             # List available tasks
    python daily_fetch.py --exclude injury odds  # Run all except specified

See docs/DAILY_SCRIPTS.md for full documentation.
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
from datetime import datetime

load_dotenv()

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

# Parse early CLI flags that affect imports
if "--proxy" in sys.argv:
    os.environ["FORCE_PROXY"] = "true"
    logging.info("Forcing proxy usage for API calls")
    sys.argv.remove("--proxy")

if "--local" in sys.argv:
    os.environ["FORCE_LOCAL"] = "true"
    logging.info("Forcing local (direct) connection for API calls")
    sys.argv.remove("--local")

# Import app modules
try:
    import app
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


def get_current_season():
    """Get current NBA season string."""
    now = datetime.now()
    if 10 <= now.month <= 12:
        return f"{now.year}-{str(now.year + 1)[-2:]}"
    return f"{now.year - 1}-{str(now.year)[-2:]}"


def run_task(task_name, task_function, *args, **kwargs):
    """Run a task with timing and error handling."""
    start_time = time.perf_counter()
    logging.info(f"Starting task: {task_name}")
    try:
        result = task_function(*args, **kwargs)
        duration = time.perf_counter() - start_time
        logging.info(f"✓ Completed: {task_name} in {duration:.1f}s")
        return True, result
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.error(f"✗ Failed: {task_name} after {duration:.1f}s - {str(e)}")
        logging.error(traceback.format_exc())
        return False, None


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
    'gamelogs': {
        'name': 'Fetch game logs',
        'description': 'Fetch player game logs for current season',
        'delay_after': 15
    },
    'schedule': {
        'name': 'Update game schedule',
        'description': 'Update game schedule with results',
        'delay_after': 10
    },
    'future': {
        'name': 'Update future games',
        'description': 'Fetch upcoming game schedule',
        'delay_after': 10
    },
    'teamstats': {
        'name': 'Update team stats',
        'description': 'Fetch team game stats for season',
        'delay_after': 10
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


def run_fetch_tasks(tasks_to_run: list, current_season: str):
    """Run specified fetch tasks."""
    team_fetcher = TeamFetcher()
    player_fetcher = PlayerFetcher()
    schedule_fetcher = ScheduleFetcher()
    gamelog_fetcher = SmartGameLogFetcher()
    injury_fetcher = InjuryFetcher()
    odds_fetcher = OddsFetcher()
    
    tasks_completed = 0
    tasks_failed = 0
    
    for task_key in tasks_to_run:
        task_info = FETCH_TASKS.get(task_key)
        if not task_info:
            logging.warning(f"Unknown task: {task_key}")
            continue
        
        success = False
        
        if task_key == 'players':
            success, _ = run_task(
                task_info['name'],
                player_fetcher.sync_active_players,
                current_season=current_season
            )
        
        elif task_key == 'rosters':
            success, _ = run_task(
                task_info['name'],
                team_fetcher.fetch_current_rosters
            )
        
        elif task_key == 'gamelogs':
            success, _ = run_task(
                task_info['name'],
                gamelog_fetcher.fetch_game_logs_tiered,
                tier="current"
            )
        
        elif task_key == 'schedule':
            success, _ = run_task(
                task_info['name'],
                schedule_fetcher.fetch_and_store_schedule,
                current_season
            )
        
        elif task_key == 'future':
            success, _ = run_task(
                task_info['name'],
                schedule_fetcher.fetch_and_store_future_games,
                current_season
            )
        
        elif task_key == 'teamstats':
            success, _ = run_task(
                task_info['name'],
                team_fetcher.fetch_team_game_stats_for_season,
                season=current_season
            )
        
        elif task_key == 'leagueteam':
            success, _ = run_task(
                task_info['name'],
                team_fetcher.fetch_league_dash_team_stats,
                season=current_season
            )
        
        elif task_key == 'leagueplayer':
            success, _ = run_task(
                task_info['name'],
                player_fetcher.fetch_league_dash_player_stats,
                season_from=2025,
                season_to=2026
            )
        
        elif task_key == 'injury':
            success, _ = run_task(
                task_info['name'],
                lambda: injury_fetcher.fetch_injury_data(season=current_season)
            )
        
        elif task_key == 'odds':
            success, _ = run_task(
                task_info['name'],
                lambda: odds_fetcher.fetch_todays_odds(season=current_season)
            )
        
        tasks_completed += 1 if success else 0
        tasks_failed += 0 if success else 1
        
        if task_info['delay_after'] > 0:
            time.sleep(task_info['delay_after'])
    
    return tasks_completed, tasks_failed


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
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # List tasks and exit
    if args.list:
        print("\nAvailable Fetch Tasks:")
        print("-" * 60)
        for key, info in FETCH_TASKS.items():
            print(f"  {key:15} - {info['description']}")
        print("\nDefault order:", ', '.join(FETCH_TASKS.keys()))
        return
    
    # Determine which tasks to run
    if args.tasks:
        tasks_to_run = args.tasks
    else:
        tasks_to_run = list(FETCH_TASKS.keys())
    
    # Apply exclusions
    if args.exclude:
        tasks_to_run = [t for t in tasks_to_run if t not in args.exclude]
    
    current_season = args.season or get_current_season()
    
    logging.info("=" * 70)
    logging.info("Starting Daily Fetch")
    logging.info(f"Season: {current_season}")
    logging.info(f"Tasks to run: {', '.join(tasks_to_run)}")
    logging.info("=" * 70)
    
    completed, failed = run_fetch_tasks(tasks_to_run, current_season)
    
    logging.info("=" * 70)
    logging.info(f"Daily Fetch Complete: {completed} succeeded, {failed} failed")
    logging.info("=" * 70)


if __name__ == "__main__":
    main()

