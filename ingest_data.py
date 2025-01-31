import logging
from app.utils import (
    fetch_and_store_players,
    fetch_and_store_all_players_stats,
    fetch_and_store_current_rosters,
    fetch_and_store_leaguedashplayer_stats,
    fetch_and_store_leaguedashplayer_stats_for_current_season,
    get_game_logs_for_all_players,
    get_game_logs_for_current_season,
    populate_schedule,
)

# Set up logging
logging.basicConfig(filename='daily_ingest.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s:%(message)s')

try:
    # Uncomment the necessary functions based on your requirements
    logging.info("Starting daily data ingestion...")

    # Fetch all active players and store basic info in player DB
    # Run Weekly
    #fetch_and_store_players()
    #logging.info("Fetched and stored players.")

    # Fetch teams, current rosters, and store to DB 
    # Updates Team Rosters if exists
    # Run Daily
    #fetch_and_store_current_rosters()
    logging.info("Fetched and stored current rosters.")

    # Get Game Logs In X Seasons
    # Used to populate database
    # Run once or when specific season data is needed
    # get_game_logs_for_all_players(2015, 2024)
    # logging.info("Fetched and stored game logs for all players in selected season(s)")
    
    # Get Game Logs Current Season 
    # Run Daily 
    #get_game_logs_for_current_season()
    logging.info("Fetched and stored game logs for all players in Current Season")

    # Fetch all career stats for all players and store in statistics table
    # Run Daily
    #fetch_and_store_all_players_stats()
    logging.info("Fetched and stored all players' stats.")

    # Fetch the game schedule for the current season
    # Run Daily 
    populate_schedule()
    logging.info("Populated the game schedule.")

    # Populate League Dash Player Stats for Last XXXX-XXXX Seasons
    # Used for Populating Database
    # Run once or when specific season data is needed
    #fetch_and_store_leaguedashplayer_stats(2015,2024)

    # Fetch and Update League Dash Player Stats for Current Season
    # Run Daily to Update stats / rankings in League Dash Player Stats Table
    fetch_and_store_leaguedashplayer_stats_for_current_season()
    logging.info("Updating League Player Dashboard")

    logging.info("Data ingestion completed successfully!")

except Exception as e:
    logging.error(f"Error during data ingestion: {e}")