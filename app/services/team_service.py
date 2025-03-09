from app.models.team import Team
from app.utils.cache_utils import get_cache, set_cache
from nba_api.stats.endpoints import leaguedashlineups

def get_team_lineup_stats(team_id, season="2024-25"):
    """
    Fetch the most recent and most used starting lineups for a given team.
    
    - Most Recent Lineup: Based on the most recent game played.
    - Most Used Lineup: The lineup with the most games played (`GP`).
    - Resolves player IDs for both lineups using the Roster class.

    Args:
        team_id (int): The ID of the team.
        season (str): The NBA season (e.g., "2024-25").
    
    Returns:
        dict: Contains both the most recent lineup, most used lineup, and resolved player IDs.
    """
    response = leaguedashlineups.LeagueDashLineups(
        team_id_nullable=team_id,
        season=season,
        season_type_all_star="Regular Season",
        group_quantity=5,  # Get full starting lineups
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Base",
        rank="N",
    ).get_data_frames()[0]

    if response.empty:
        return None

    # Sort by most games played (`GP`)
    sorted_by_gp = response.sort_values(by="GP", ascending=False)
    # Sort by most recent game (`MIN` as a proxy for latest game data)
    sorted_by_recent = response.sort_values(by="MIN", ascending=False)

    # Select most used & most recent lineups
    most_used_lineup = sorted_by_gp.iloc[0]
    most_recent_lineup = sorted_by_recent.iloc[0]

    # Extract player names from "GROUP_NAME"
    most_used_players = most_used_lineup["GROUP_NAME"].split(" - ")
    most_recent_players = most_recent_lineup["GROUP_NAME"].split(" - ")
    
    # Fetch the team's full roster
    team_roster = Team.get_team_with_details(team_id)["roster"]

    # Function to match player names to IDs using the Roster class
    def match_players_to_ids(player_names):
        matched_player_ids = []
        for player in team_roster:
            full_name = player["player_name"]  # Get full player name
            first_initial = full_name.split(" ")[0][0]  # First initial
            last_name = " ".join(full_name.split(" ")[1:])  # Full last name (Handles Jr., III cases)

            # Match exact name using full name comparison
            if any(f"{first_initial}. {last_name}" in name for name in player_names):
                matched_player_ids.append(player["player_id"])

        return matched_player_ids

    return {
        "most_used_lineup": {
            "team_id": most_used_lineup["TEAM_ID"],
            "team_abbreviation": most_used_lineup["TEAM_ABBREVIATION"],
            "lineup": most_used_lineup["GROUP_NAME"],
            "gp": most_used_lineup["GP"],
            "w_pct": most_used_lineup["W_PCT"],
            "pts_rank": most_used_lineup["PTS_RANK"], 
            "plus_minus_rank": most_used_lineup["PLUS_MINUS_RANK"],  
            "reb_rank": most_used_lineup["REB_RANK"],
            "ast_rank": most_used_lineup["AST_RANK"],
            "player_ids": match_players_to_ids(most_used_players),  # Attach player IDs
        },
        "most_recent_lineup": {
            "team_id": most_recent_lineup["TEAM_ID"],
            "team_abbreviation": most_recent_lineup["TEAM_ABBREVIATION"],
            "lineup": most_recent_lineup["GROUP_NAME"],
            "gp": most_recent_lineup["GP"],
            "w_pct": most_recent_lineup["W_PCT"],
            "pts_rank": most_recent_lineup["PTS_RANK"],
            "reb_rank": most_recent_lineup["REB_RANK"],
            "ast_rank": most_recent_lineup["AST_RANK"],
            "plus_minus_rank": most_recent_lineup["PLUS_MINUS_RANK"], 
            "player_ids": match_players_to_ids(most_recent_players),  # Attach player IDs
        },
    }

def get_enhanced_teams_data():
    """
    Get enhanced team data including records, standings, and game information.
    
    Returns:
        list: A list of team dictionaries with enhanced data.
    """
    # Implementation would go here
    pass
