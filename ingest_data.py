"""
    This script is responsible for ingesting NBA data into the database.
    The script performs the following operations:
    1. Fetches and stores basic information for all active NBA players
    2. Retrieves and stores current team rosters
    3. Collects and stores career statistics for all active players
    4. Fetches and stores league dashboard player statistics
    The data is fetched using utility functions from app.utils and stored in the database.
    Required Functions:
        - fetch_and_store_players: Retrieves and stores basic player information
        - fetch_and_store_current_rosters: Gets and stores current team rosters
        - fetch_and_store_all_players_stats: Collects career stats for active players
        - fetch_and_store_leaguedashplayer_stats: Fetches league dashboard statistics
    Note:
        This script should be run periodically to keep the database updated with the latest NBA statistics.
    """

from app.utils import (
    fetch_and_store_players,
    fetch_and_store_all_players_stats,
    fetch_and_store_current_rosters,
    fetch_and_store_leaguedashplayer_stats,
)

# Run both functions to populate the database

# #Fetch all active players and store basic info in player DB
fetch_and_store_players()


# #Fetch Teams, and Current Roster, Store to DB
fetch_and_store_current_rosters()


# Fetch all career stats for active players and store in DB
fetch_and_store_all_players_stats()

fetch_and_store_leaguedashplayer_stats()
