import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    filename="ingest.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)

# Initialize database connection
from db_config import init_db

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Initialize the database connection pool
init_db(DATABASE_URL)
logging.info("Database connection pool initialized")

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
from app.utils.fetch.fetch_utils import (
    fetch_and_store_players,
    fetch_and_store_all_players_stats,
    fetch_and_store_current_rosters,
    fetch_and_store_leaguedashplayer_stats,
    fetch_and_store_team_game_stats_for_season,
    fetch_and_store_league_dash_team_stats,
)
from app.utils.get.get_utils import (
    get_game_logs_for_all_players,
    populate_schedule,
)

try:
    logging.info("Starting one-time/weekly data ingestion...")
    logging.info(f"Proxy configuration: FORCE_PROXY={os.getenv('FORCE_PROXY', 'Not set')}, FORCE_LOCAL={os.getenv('FORCE_LOCAL', 'Not set')}")

    # =========================
    # 🟢 Weekly Ingestion Tasks
    # =========================
    
    # TODO Upate with task fetcher classes like daily_ingest.py

    # Fetch all active players and store in the database (Run Weekly)
    # fetch_and_store_players()
    # logging.info("Fetched and stored all players.")

    #populate schedule from 2015 to 2025
    for year in range(2015, 2025):
        season_str = f"{year}-{str(year+1)[-2:]}"
        logging.info(f"Fetching schedule/results for {season_str}...")
        populate_schedule(season_str)
        logging.info(f"Stored schedule/results for {season_str}.")

    # Fetch all career stats for players (Run Weekly)
    # fetch_and_store_all_players_stats()
    # logging.info("Fetched and stored all players' career stats.")

    # Fetch game logs for multiple seasons (Run when needed)
    # get_game_logs_for_all_players(2015, 2024)
    # logging.info("Fetched and stored game logs for all players in selected seasons.")

    # Populate schedule and results for past seasons (Run when needed)
    # for year in range(2015, 2025):
    #     season_str = f"{year}-{str(year+1)[-2:]}"
    #     logging.info(f"Fetching schedule/results for {season_str}...")
    #     populate_schedule(season_str)
    #     logging.info(f"Stored schedule/results for {season_str}.")

    # Fetch League Dash Player Stats for historical seasons (Run when needed)
    # fetch_and_store_leaguedashplayer_stats(2015, 2024)
    # logging.info("Stored League Dash Player Stats for past seasons.")

    # Run database cleanup after all ingestion tasks
    logging.info("Running database cleanup...")
    from scripts.database_cleanup import DatabaseCleaner
    cleaner = DatabaseCleaner()
    cleaner.cleanup_all()
    logging.info("✓ Database cleanup completed successfully")

    logging.info("One-time/weekly ingestion completed successfully!")

except Exception as e:
    logging.error("Error during ingestion: %s", e)
