import logging
from app.utils.fetch.fetch_utils import (
    fetch_and_store_current_rosters,
    fetch_and_store_league_dash_team_stats,
    fetch_and_store_leaguedashplayer_stats_for_current_season,
    fetch_and_store_schedule,
    fetch_and_store_future_games
)
from app.utils.get.get_utils import (
    get_game_logs_for_current_season,
    populate_schedule,
)

# Set up logging
logging.basicConfig(
    filename="daily_ingest.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)

try:
    logging.info("Starting daily data ingestion...")

    # =====================
    # 🔵 Daily Ingestion Tasks
    # =====================

    logging.info("Updated game schedule.")
    # Fetch and update current rosters (Run Daily)
    fetch_and_store_current_rosters()
    logging.info("Updated current rosters.")

    # Fetch game logs for the current season (Run Daily)
    get_game_logs_for_current_season()
    logging.info("Fetched and stored game logs for the current season.")

    # Populate schedule for the current season (Run Daily)
    populate_schedule()
    fetch_and_store_future_games("2024-25")
    logging.info("Updated game schedule.")

    # Fetch and update League Dash Team Stats (Run Daily)
    fetch_and_store_league_dash_team_stats(season="2024-25")
    logging.info("Updated League Team Dashboard.")

    # Fetch and update League Dash Player Stats (Run Daily)
    fetch_and_store_leaguedashplayer_stats_for_current_season()
    logging.info("Updated League Player Dashboard.")

    logging.info("Daily ingestion completed successfully!")

except Exception as e:
    logging.error("Error during daily ingestion: %s", e)
