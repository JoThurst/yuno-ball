import logging
import traceback
import time
import sys
import os
import socket
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    filename="daily_ingest.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Initialize database connection
from db_config import init_db

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Initialize the database connection pool
init_db(DATABASE_URL)
logging.info("Database connection pool initialized")

# Check if running on AWS (EC2)
def is_running_on_aws():
    try:
        # Try to access the EC2 metadata service
        socket.getaddrinfo('instance-data.ec2.internal', 80)
        return True
    except socket.gaierror:
        return False

# Adjust MAX_WORKERS based on environment
if is_running_on_aws():
    os.environ["MAX_WORKERS"] = "1"  # Use single worker on AWS
    logging.info("🔄 Running on AWS - Using single worker for ingestion")

# Check for proxy configuration in command line arguments
if "--proxy" in sys.argv:
    os.environ["FORCE_PROXY"] = "true"
    logging.info("🔄 Forcing proxy usage for API calls")
    sys.argv.remove("--proxy")

if "--local" in sys.argv:
    os.environ["FORCE_LOCAL"] = "true"
    logging.info("🔄 Forcing local (direct) connection for API calls")
    sys.argv.remove("--local")

# Now import app modules after environment variables are set
from app.utils.fetch.team_fetcher import TeamFetcher
from app.utils.fetch.player_fetcher import PlayerFetcher
from app.utils.fetch.schedule_fetcher import ScheduleFetcher
from app.utils.fetch.smart_gamelog_fetcher import SmartGameLogFetcher

from app.utils.get.get_utils import (
    get_game_logs_for_current_season,
    populate_schedule,
)

# Mock cache functions that do nothing
def get_cache(key):
    """Mock get_cache that always returns None (cache miss)."""
    logging.debug(f"Mock cache miss for key: {key}")
    return None

def set_cache(key, data, ex=3600):
    """Mock set_cache that does nothing."""
    logging.debug(f"Mock cache set for key: {key}")
    pass

def invalidate_cache(key):
    """Mock invalidate_cache that does nothing."""
    logging.debug(f"Mock cache invalidation for key: {key}")
    pass

def run_task(task_name, task_function, *args, **kwargs):
    """Run a task with timing and error handling."""
    start_time = time.perf_counter()
    logging.info(f"Starting task: {task_name}")
    try:
        result = task_function(*args, **kwargs)
        duration = time.perf_counter() - start_time
        logging.info(f"Completed task: {task_name} in {duration:.1f}s")
        return True, result
    except Exception as e:
        duration = time.perf_counter() - start_time
        logging.error(f"Error in task {task_name} after {duration:.1f}s: {str(e)}")
        logging.error(traceback.format_exc())
        return False, None

def get_current_season():
    # get current season from date, october-december is x-(y+1), january-september is (x-1)-y is current season
    now = datetime.now()
    if 10 <= now.month <= 12:
        return f"{now.year}-{str(now.year + 1)[-2:]}"
    else:
        return f"{now.year - 1}-{str(now.year)[-2:]}"

def main():
    """Main function to run all daily ingestion tasks."""
    logging.info("Starting daily data ingestion...")
    logging.info(f"Proxy configuration: FORCE_PROXY={os.getenv('FORCE_PROXY', 'Not set')}, FORCE_LOCAL={os.getenv('FORCE_LOCAL', 'Not set')}")
    
    tasks_completed = 0
    tasks_failed = 0
    
    from scripts.database_cleanup import DatabaseCleaner

    current_season = get_current_season()
    logging.info(f"Current season: {current_season}")
    # Initialize fetchers
    team_fetcher = TeamFetcher()
    player_fetcher = PlayerFetcher()
    schedule_fetcher = ScheduleFetcher()
    gamelog_fetcher = SmartGameLogFetcher()
    
    # Fetch and update current rosters
    # success, _ = run_task("Update current rosters", team_fetcher.fetch_current_rosters)
    # tasks_completed += 1 if success else 0
    # tasks_failed += 0 if success else 1
    
    # # Fetch game logs for the current season using the smart fetcher
    # success, _ = run_task(
    #     "Fetch game logs (current season)",
    #     gamelog_fetcher.fetch_game_logs_tiered,
    #     tier="current"
    # )
    # tasks_completed += 1 if success else 0
    # tasks_failed += 0 if success else 1

    # # Update game schedule with game results
    # success, _ = run_task(
    #     "Update game schedule",
    #     schedule_fetcher.fetch_and_store_schedule,
    #     current_season
    # )
    # tasks_completed += 1 if success else 0
    # tasks_failed += 0 if success else 1
    
    # # Get future games (upcoming only)
    # success, _ = run_task(
    #     "Update future games",
    #     schedule_fetcher.fetch_and_store_future_games,
    #     current_season
    # )
    # tasks_completed += 1 if success else 0
    # tasks_failed += 0 if success else 1
    
    # Update team stats
    success, _ = run_task(
        "Update team stats",
        team_fetcher.fetch_team_game_stats_for_season,
        season=current_season
    )
    tasks_completed += 1 if success else 0
    tasks_failed += 0 if success else 1

    # Update league dash team stats
    success, _ = run_task(
        "Update league dash team stats",
        team_fetcher.fetch_league_dash_team_stats,
        season=current_season
    )
    tasks_completed += 1 if success else 0
    tasks_failed += 0 if success else 1

    # Fetch player streaks
    success, _ = run_task(
        "Fetch player streaks",
        player_fetcher.fetch_player_streaks,
        season=current_season
    )
    tasks_completed += 1 if success else 0
    tasks_failed += 0 if success else 1
    
    # Run database cleanup as final task
    success, _ = run_task("Database Cleanup", lambda: DatabaseCleaner().cleanup_all())
    if success:
        tasks_completed += 1
        logging.info("✓ Database cleanup completed successfully")
    else:
        tasks_failed += 1
        logging.error("❌ Database cleanup failed")


    
    logging.info(f"Daily ingestion completed. Tasks completed: {tasks_completed}, Tasks failed: {tasks_failed}")

if __name__ == "__main__":
    main()