import logging
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

# Set up logging
logging.basicConfig(
    filename="ingest.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)

try:
    logging.info("Starting one-time/weekly data ingestion...")

    # =========================
    # 🟢 Weekly Ingestion Tasks
    # =========================
    
    # Fetch all active players and store in the database (Run Weekly)
    fetch_and_store_players()
    # logging.info("Fetched and stored all players.")

    # Fetch all career stats for players (Run Weekly)
    fetch_and_store_all_players_stats()
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

    logging.info("One-time/weekly ingestion completed successfully!")

except Exception as e:
    logging.error("Error during ingestion: %s", e)
