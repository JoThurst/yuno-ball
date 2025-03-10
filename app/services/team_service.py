from app.models.team import Team
from app.utils.cache_utils import get_cache, set_cache
from nba_api.stats.endpoints import leaguedashlineups
import logging

def get_team_lineup_stats(team_id, season="2024-25"):
    """
    Fetch the most recent and most used starting lineups for a given team.
    
    Args:
        team_id (int): The ID of the team.
        season (str): The NBA season (e.g., "2024-25").
    
    Returns:
        dict: Contains both the most recent lineup, most used lineup, and resolved player IDs.
    """
    # Check cache first
    cache_key = f"team_lineup_stats_{team_id}_{season}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        return cached_data
    
    try:
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
        team_roster = Team.get_team_with_details(team_id)["roster"] if Team.get_team_with_details(team_id) else []

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

        result = {
            "most_used_lineup": {
                "team_id": int(most_used_lineup["TEAM_ID"]) if "TEAM_ID" in most_used_lineup else None,
                "team_abbreviation": most_used_lineup["TEAM_ABBREVIATION"] if "TEAM_ABBREVIATION" in most_used_lineup else None,
                "lineup": most_used_lineup["GROUP_NAME"] if "GROUP_NAME" in most_used_lineup else None,
                "gp": int(most_used_lineup["GP"]) if "GP" in most_used_lineup else None,
                "w_pct": float(most_used_lineup["W_PCT"]) if "W_PCT" in most_used_lineup else None,
                "pts_rank": int(most_used_lineup["PTS_RANK"]) if "PTS_RANK" in most_used_lineup else None, 
                "plus_minus_rank": int(most_used_lineup["PLUS_MINUS_RANK"]) if "PLUS_MINUS_RANK" in most_used_lineup else None,  
                "reb_rank": int(most_used_lineup["REB_RANK"]) if "REB_RANK" in most_used_lineup else None,
                "ast_rank": int(most_used_lineup["AST_RANK"]) if "AST_RANK" in most_used_lineup else None,
                "player_ids": match_players_to_ids(most_used_players),  # Attach player IDs
            },
            "most_recent_lineup": {
                "team_id": int(most_recent_lineup["TEAM_ID"]) if "TEAM_ID" in most_recent_lineup else None,
                "team_abbreviation": most_recent_lineup["TEAM_ABBREVIATION"] if "TEAM_ABBREVIATION" in most_recent_lineup else None,
                "lineup": most_recent_lineup["GROUP_NAME"] if "GROUP_NAME" in most_recent_lineup else None,
                "gp": int(most_recent_lineup["GP"]) if "GP" in most_recent_lineup else None,
                "w_pct": float(most_recent_lineup["W_PCT"]) if "W_PCT" in most_recent_lineup else None,
                "pts_rank": int(most_recent_lineup["PTS_RANK"]) if "PTS_RANK" in most_recent_lineup else None,
                "reb_rank": int(most_recent_lineup["REB_RANK"]) if "REB_RANK" in most_recent_lineup else None,
                "ast_rank": int(most_recent_lineup["AST_RANK"]) if "AST_RANK" in most_recent_lineup else None,
                "plus_minus_rank": int(most_recent_lineup["PLUS_MINUS_RANK"]) if "PLUS_MINUS_RANK" in most_recent_lineup else None, 
                "player_ids": match_players_to_ids(most_recent_players),  # Attach player IDs
            },
        }
        
        # Cache the result for 6 hours
        set_cache(cache_key, result, ex=21600)
        
        return result
    except Exception as e:
        print(f"Error fetching team lineup stats: {e}")
        return None

def get_team_stats(team_id, season="2024-25"):
    """
    Fetch team statistics for the given season.
    
    Args:
        team_id (int): The ID of the team.
        season (str): The NBA season (e.g., "2024-25").
        
    Returns:
        dict: Team statistics.
    """
    # Check cache first
    cache_key = f"team_stats_{team_id}_{season}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        return cached_data
    
    # Get stats from Team model (which now handles API calls if needed)
    stats = Team.get_team_statistics(team_id, season)
    
    # Define default stats with None values
    default_stats = {
        "pts": None, "reb": None, "ast": None, "stl": None, "blk": None, 
        "tov": None, "fg_pct": None, "fg3_pct": None, "ft_pct": None,
        "off_rtg": None, "def_rtg": None, "net_rtg": None, "pace": None, "ts_pct": None
    }
    
    if stats:
        # Update default stats with actual values
        for key in default_stats:
            if key in stats:
                default_stats[key] = stats[key]
    
    # Cache the result for 6 hours
    set_cache(cache_key, default_stats, ex=21600)
    
    return default_stats

def get_team_game_results(team_id, limit=10):
    """
    Get recent game results for a team.
    
    Args:
        team_id (int): The ID of the team.
        limit (int): Maximum number of games to return.
        
    Returns:
        list: Recent game results.
    """
    # Check cache first
    cache_key = f"team_game_results_{team_id}_{limit}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        return cached_data
    
    # Get recent games from Team model
    recent_games = Team.get_team_recent_games(team_id, limit)
    
    if recent_games:
        # Get team names for the games
        team_ids = set()
        team_ids.add(team_id)
        for game in recent_games:
            team_ids.add(game["opponent_team_id"])
        
        teams = Team.get_teams_by_ids(list(team_ids))
        team_dict = {team["team_id"]: team for team in teams}
        
        # Enhance game data with team names
        for game in recent_games:
            # Get team names
            game["team_name"] = team_dict.get(team_id, {}).get("name", "Unknown")
            game["opponent_name"] = team_dict.get(game["opponent_team_id"], {}).get("name", "Unknown")
            
            # Determine if the team is home or away
            game["is_home"] = game["home_or_away"] == "H"
            
            # Convert game_date string to datetime if needed
            if isinstance(game["game_date"], str):
                from datetime import datetime
                try:
                    game["game_date"] = datetime.strptime(game["game_date"], "%Y-%m-%d")
                except ValueError:
                    pass
    
        # Cache the result for 1 hour
        set_cache(cache_key, recent_games, ex=3600)
    
    return recent_games

def get_team_upcoming_schedule(team_id, limit=5):
    """
    Get upcoming games for a team.
    
    Args:
        team_id (int): The ID of the team.
        limit (int): Maximum number of games to return.
        
    Returns:
        list: Upcoming games.
    """
    # Check cache first
    cache_key = f"team_upcoming_games_{team_id}_{limit}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        return cached_data
    
    # Get upcoming games from Team model
    upcoming_games = Team.get_team_upcoming_games(team_id, limit)
    
    if upcoming_games:
        # Get team names for the games
        team_ids = set()
        team_ids.add(team_id)
        for game in upcoming_games:
            team_ids.add(game["opponent_team_id"])
        
        teams = Team.get_teams_by_ids(list(team_ids))
        team_dict = {team["team_id"]: team for team in teams}
        
        # Enhance game data with team names
        for game in upcoming_games:
            # Get team names
            game["team_name"] = team_dict.get(team_id, {}).get("name", "Unknown")
            game["opponent_name"] = team_dict.get(game["opponent_team_id"], {}).get("name", "Unknown")
            
            # Determine if the team is home or away
            game["is_home"] = game["home_or_away"] == "H"
            
            # Convert game_date string to datetime if needed
            if isinstance(game["game_date"], str):
                from datetime import datetime
                try:
                    game["game_date"] = datetime.strptime(game["game_date"], "%Y-%m-%d")
                except ValueError:
                    pass
    
        # Cache the result for 1 hour
        set_cache(cache_key, upcoming_games, ex=3600)
    
    return upcoming_games

def get_complete_team_details(team_id):
    """
    Get comprehensive team details for the team detail page.
    
    Args:
        team_id (int): The ID of the team.
        
    Returns:
        dict: Complete team details.
    """
    try:
        # Get base team data
        team_data = Team.get_team_with_details(team_id)
        
        if not team_data:
            logging.error(f"Team with ID {team_id} not found")
            return None
        
        # Get current season
        from datetime import datetime
        current_year = datetime.now().year
        current_month = datetime.now().month
        if current_month >= 10:  # NBA season starts in October
            season = f"{current_year}-{str(current_year + 1)[-2:]}"
        else:
            season = f"{current_year-1}-{str(current_year)[-2:]}"
        
        # Get team standings rank
        try:
            standings_rank = Team.get_team_standings_rank(team_id, season)
            if standings_rank:
                team_data.update(standings_rank)
        except Exception as e:
            logging.error(f"Error getting team standings rank: {e}")
        
        # Get team statistics
        try:
            team_stats = get_team_stats(team_id, season)
            if team_stats:
                team_data["stats"] = team_stats
        except Exception as e:
            logging.error(f"Error getting team stats: {e}")
            # Ensure stats is always present even if empty
            team_data["stats"] = {
                "pts": None, "reb": None, "ast": None, "stl": None, "blk": None, 
                "tov": None, "fg_pct": None, "fg3_pct": None, "ft_pct": None,
                "off_rtg": None, "def_rtg": None, "net_rtg": None, "pace": None, "ts_pct": None
            }
        
        # Get team lineups
        try:
            lineups = get_team_lineup_stats(team_id, season)
            if lineups:
                team_data["lineups"] = lineups
        except Exception as e:
            logging.error(f"Error getting team lineups: {e}")
        
        # Get recent game results
        try:
            recent_games = get_team_game_results(team_id, 5)
            if recent_games:
                team_data["recent_games"] = recent_games
        except Exception as e:
            logging.error(f"Error getting recent games: {e}")
        
        # Get upcoming schedule
        try:
            upcoming_games = get_team_upcoming_schedule(team_id, 5)
            if upcoming_games:
                team_data["upcoming_games"] = upcoming_games
        except Exception as e:
            logging.error(f"Error getting upcoming games: {e}")
        
        return team_data
    except Exception as e:
        logging.error(f"Error in get_complete_team_details: {e}")
        return None

def get_enhanced_teams_data():
    """
    Get enhanced team data including records, standings, and game information.
    
    Returns:
        list: A list of team dictionaries with enhanced data.
    """
    # Implementation would go here
    pass
