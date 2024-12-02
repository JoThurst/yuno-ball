from app.utils import (
    fetch_and_store_players,
    fetch_and_store_all_players_stats,
    fetch_and_store_current_rosters,
    fetch_and_store_leaguedashplayer_stats,
    get_game_logs,
    get_game_logs_for_player,
    get_game_logs_for_all_players
)

# Run both functions to populate the database

# #Fetch all active players and store basic info in player DB
# fetch_and_store_players()


# #Fetch Teams, and Current Roster, Store to DB
#fetch_and_store_current_rosters()
#get_game_logs_for_player(player_id="1628389",season="2023-24")
get_game_logs_for_all_players()
#get_game_logs()
#Fetch all career stats for active players and store in DB
#fetch_and_store_all_players_stats()
