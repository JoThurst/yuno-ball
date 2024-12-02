from app.utils import (
    fetch_and_store_players,
    fetch_and_store_all_players_stats,
    fetch_and_store_current_rosters,
    fetch_and_store_leaguedashplayer_stats,
)

# Run both functions to populate the database

# #Fetch all active players and store basic info in player DB
# fetch_and_store_players()


# #Fetch Teams, and Current Roster, Store to DB
# fetch_and_store_current_rosters()


# Fetch all career stats for active players and store in DB
# fetch_and_store_all_players_stats()

fetch_and_store_leaguedashplayer_stats()
