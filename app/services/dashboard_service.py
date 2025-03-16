from datetime import datetime
import traceback
from typing import Dict, List, Any, Tuple, Optional

from app.models.gameschedule import GameSchedule
from app.models.team import Team
from app.models.player import Player
from app.models.player_streaks import PlayerStreaks
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.utils.cache_utils import get_cache, set_cache
from app.utils.config_utils import logger
from app.utils.get.get_utils import fetch_todays_games
from app.utils.fetch.fetch_utils import fetch_team_rosters


def get_home_dashboard_data(season="2024-25"):
    """
    Get comprehensive data for the home dashboard.
    
    Args:
        season (str): The NBA season (e.g., "2024-25").
    
    Returns:
        dict: A dictionary containing all data needed for the home dashboard.
    """
    # Try to get from cache first
    cache_key = f"home_dashboard_{season}_{datetime.now().strftime('%Y-%m-%d')}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        print("[INFO] Cache HIT for home dashboard data")
        return cached_data
    
    print("[INFO] Cache MISS for home dashboard data - Fetching fresh data")
    
    # 1. Get today's games for the featured section -- Correct
    today_games_data = fetch_todays_games()
    all_games = today_games_data.get("games", [])
    featured_games = all_games[:3] if all_games else []  # Limit to 3 games for the featured widget
    
    # Add additional data to each game
    for game in all_games:
        # Get team objects
        home_team = Team.get_team_with_details(game["home_team_id"])
        away_team = Team.get_team_with_details(game["away_team_id"])
        
        # Handle home team data
        if home_team:
            # Calculate record dynamically from game results
            home_record = game.get("home_record", "0-0")  # Use record from game data if available
            game["home_team_abbreviation"] = home_team['abbreviation']
        else:
            game["home_record"] = "0-0"
            game["home_team_abbreviation"] = ""
        
        # Handle away team data
        if away_team:
            # Calculate record dynamically from game data
            away_record = game.get("away_record", "0-0")  # Use record from game data if available
            game["away_team_abbreviation"] = away_team['abbreviation']
        else:
            game["away_record"] = "0-0"
            game["away_team_abbreviation"] = ""
        
        # Check if game is live (placeholder for now)
        game["is_live"] = False
        game["home_score"] = game.get("home_score", 0)
        game["away_score"] = game.get("away_score", 0)
        game["game_clock"] = game.get("game_clock", "")
        
        # Add team stats for comparison
        game["home_team_stats"] = {
            "ppg": 0,
            "rpg": 0,
            "apg": 0,
            "fg_pct": 0
        }
        
        game["away_team_stats"] = {
            "ppg": 0,
            "rpg": 0,
            "apg": 0,
            "fg_pct": 0
        }
        
        # Try to get actual stats if available
        team_stats = LeagueDashTeamStats.get_team_stats(season, "Totals")
        if team_stats:
            for stat in team_stats:
                if stat.get("team_id") == game["home_team_id"]:
                    game["home_team_stats"] = {
                        "ppg": stat.get("base_totals_pts_rank", 0),
                        "rpg": stat.get("base_totals_reb_rank", 0),
                        "apg": stat.get("base_totals_ast_rank", 0),
                        "fg_pct": stat.get("base_totals_fgm_rank", 0)
                    }
                
                if stat.get("team_id") == game["away_team_id"]:
                    game["away_team_stats"] = {
                        "ppg": stat.get("base_totals_pts_rank", 0),
                        "rpg": stat.get("base_totals_reb_rank", 0),
                        "apg": stat.get("base_totals_ast_rank", 0),
                        "fg_pct": stat.get("base_totals_fgm_rank", 0)
                    }
    
    # Fix player streaks processing
    player_streaks_by_stat = PlayerStreaks.get_all_player_streaks(min_streak_games=3)
    print(f"Retrieved streaks for {len(player_streaks_by_stat.keys()) if player_streaks_by_stat else 0} stat categories")
    
    # Convert the stat-grouped dictionary into a flat list of streaks
    processed_streaks = []
    if player_streaks_by_stat:
        for stat_type, streaks in player_streaks_by_stat.items():
            for streak in streaks:
                # Format the stat display (e.g., "20+ points", "10+ rebounds")
                stat_display = f"{stat_type}"
                if stat_type.lower() in ['points', 'rebounds', 'assists', 'steals', 'blocks']:
                    threshold = streak.get("streak_value", 10)  # Default to 10 if not specified
                    stat_display = f"{threshold}+ {stat_type}"
                
                streak_dict = {
                    "player_name": streak.get("player_name", "Unknown"),
                    "team_abbreviation": streak.get("team", "N/A"),  # Note: the key is 'team' in the returned data
                    "team_id": None,  # We don't have this in the returned data
                    "streak_type": stat_type,  # Original stat type
                    "stat": stat_display,  # Formatted display version
                    "threshold": streak.get("streak_value", 10),  # Default to 10 if not specified
                    "streak_games": streak.get("streak_games", 0),
                    "streak_count": streak.get("streak_games", 0)  # Add this for compatibility
                }
                processed_streaks.append(streak_dict)
    
    # Sort by streak length and limit to top 5
    try:
        # Now sort the processed streaks
        featured_streaks = sorted(processed_streaks, 
                                key=lambda x: x.get("streak_games", 0), 
                                reverse=True)[:5]
        
    except (AttributeError, TypeError) as e:
        print(f"Error sorting player_streaks: {str(e)}")
        featured_streaks = []
        
    # Store both the featured and all streaks
    player_streaks = processed_streaks  # Store all processed streaks
    
    # 3. Get standings data -- Correct
    standings = today_games_data.get("standings", {"East": [], "West": []})
    
    # 4. Get team data for the performance chart -- Correct
    teams = Team.list_all_teams()
    team_names = []

    
    # Get team stats for visualization
    team_data = get_team_visuals_data()
    
    # 5. Get player data for the players section -- Correct
    # Get top scorers and assisters from LeagueDashPlayerStats
    player_stats = LeagueDashPlayerStats.get_all_stats({"season": season})
    
    top_scorers = []
    top_assisters = []
    
    # Create a mapping of team_id to abbreviation
    team_abbr_map = {team.get("team_id"): team.get("abbreviation", "") for team in teams}

    # Get all team rosters to map players to teams
    all_team_ids = [team.get("team_id") for team in teams]
    all_rosters = fetch_team_rosters(all_team_ids)
    
    # Create player_id to team_id mapping
    player_team_map = {str(player["player_id"]): player["team_id"] for player in all_rosters}
    
    if player_stats:
        # Sort by points and assists
        sorted_by_pts = sorted(player_stats, key=lambda x: float(x.get("pts", 0)) if x.get("pts") else 0, reverse=True)
        sorted_by_ast = sorted(player_stats, key=lambda x: float(x.get("ast", 0)) if x.get("ast") else 0, reverse=True)
        
        # Get top 5 scorers
        for player in sorted_by_pts[:5]:
            player_id = player.get("player_id")
            if player_id:
                player_name = Player.get_player_name(player_id) or "Unknown Player"
                team_id = player.get("team_id")
                team_abbr = team_abbr_map.get(team_id, "N/A") if team_id else "N/A"
                
                top_scorers.append({
                    "player_id": player_id,
                    "player_name": player_name,
                    "team_abbreviation": team_abbr,
                    "pts": round(float(player.get("pts", 0)) if player.get("pts") else 0, 1)
                })
        
        # Get top 5 assisters
        for player in sorted_by_ast[:5]:
            player_id = player.get("player_id")
            if player_id:
                player_name = Player.get_player_name(player_id) or "Unknown Player"
                team_id = player.get("team_id")
                team_abbr = team_abbr_map.get(team_id, "N/A") if team_id else "N/A"
                
                top_assisters.append({
                    "player_id": player_id,
                    "player_name": player_name,
                    "team_abbreviation": team_abbr,
                    "ast": round(float(player.get("ast", 0)) if player.get("ast") else 0, 1)
                })
    
    # 6. Get all players for the comparison tool -- Incorrect. 
    # Explanation: We dont have a player_team_map to use to get the team_id and team_abbr
    # We need to create a player_team_map to get the team_id and use the team_abbr_map to get the team_abbr
    all_players = []
    players_data = Player.get_all_players()
    
    if players_data:
        for player in players_data:
            # Only include players with current season data
            if season in player.available_seasons:
                team_id = player_team_map.get(str(player.player_id))
                team_abbr = team_abbr_map.get(team_id, "N/A") if team_id else "N/A"
            
                all_players.append({
                    "player_id": player.player_id,
                    "name": player.name,
                    "team_abbreviation": team_abbr
                })
    
    # Prepare the final data structure
    dashboard_data = {
        "featured_games": featured_games,
        "games": all_games,
        "standings": standings,
        "featured_streaks": featured_streaks,
        "player_streaks": player_streaks,
        "top_scorers": top_scorers,
        "top_assisters": top_assisters,
        "all_players": all_players,
        "team_names": team_data["team_names"],
        "team_ppg": team_data["team_ppg"],
        "team_rpg": team_data["team_rpg"],
        "team_apg": team_data["team_apg"],
        "team_fg_pct": team_data["team_fg_pct"],
        "teams": teams
    }
    
    # Cache the data
    set_cache(cache_key, dashboard_data, ex=3600)  # Cache for 1 hour
    
    return dashboard_data

def get_today_matchups():
    """
    Get today's matchups for the navbar dropdown.
    
    Returns:
        list: A list of today's games.
    """
    # Try to get from cache first
    cache_key = f"today_matchups_{datetime.now().strftime('%Y-%m-%d')}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        print("[CACHE] Hit for today's matchups")
        return cached_data
    
    print("[CACHE] Miss for today's matchups - Fetching fresh data")
    
    # Get today's games
    today_games_data = fetch_todays_games()
    games = today_games_data.get("games", [])
    
    # Cache the data
    set_cache(cache_key, games, ex=3600)  # Cache for 1 hour
    
    return games

def process_games_data(today_games: List[Tuple], team_stats: List[Any]) -> List[Dict[str, Any]]:
    """
    Process games data to create a list of game objects.
    
    Args:
        today_games: List of game tuples from GameSchedule
        team_stats: List of team stats from LeagueDashTeamStats
        
    Returns:
        List of processed game objects
    """
    games = []
    
    for game_tuple in today_games:
        # game_tuple is (game_id, team_id, opponent_team_id, game_date, home_or_away, result, score)
        logger.debug(f"Processing game: {game_tuple}")
        game_id, team_id, opponent_team_id, game_date, home_or_away, result, score = game_tuple
        
        # Determine which team is home and which is away
        if home_or_away == 'H':
            home_team_id = team_id
            away_team_id = opponent_team_id
        else:
            home_team_id = opponent_team_id
            away_team_id = team_id
        
        # Get team details
        home_team = Team.get_team_with_details(home_team_id)
        away_team = Team.get_team_with_details(away_team_id)
        
        # Set default values
        home_record = ""
        away_record = ""
        home_team_abbreviation = ""
        away_team_abbreviation = ""
        home_team_name = ""
        away_team_name = ""
        home_team_score = 0
        away_team_score = 0
        
        # Get team records and abbreviations if teams exist
        if home_team:
            if isinstance(home_team, dict):
                home_record = home_team.get("record", "")
                home_team_abbreviation = home_team.get("abbreviation", "")
                home_team_name = home_team.get("name", "")
            else:
                home_record = getattr(home_team, "record", "")
                home_team_abbreviation = getattr(home_team, "abbreviation", "")
                home_team_name = getattr(home_team, "name", "")
        
        if away_team:
            if isinstance(away_team, dict):
                away_record = away_team.get("record", "")
                away_team_abbreviation = away_team.get("abbreviation", "")
                away_team_name = away_team.get("name", "")
            else:
                away_record = getattr(away_team, "record", "")
                away_team_abbreviation = getattr(away_team, "abbreviation", "")
                away_team_name = getattr(away_team, "name", "")
        
        # Parse score if available
        if score:
            score_parts = score.split(" - ")
            if len(score_parts) == 2:
                try:
                    if home_or_away == 'H':
                        home_team_score = int(score_parts[0])
                        away_team_score = int(score_parts[1])
                    else:
                        away_team_score = int(score_parts[0])
                        home_team_score = int(score_parts[1])
                except (ValueError, TypeError):
                    pass
        
        # Determine game status
        game_status = "Scheduled"
        if result:
            game_status = "Final"
        elif datetime.now().date() == game_date.date():
            game_status = "Today"
        
        # Format game time
        game_time = game_date.strftime("%I:%M %p") if hasattr(game_date, 'strftime') else ""
        
        # Add team stats
        home_team_stats = {"ppg": 0, "rpg": 0, "apg": 0, "fg_pct": 0}
        away_team_stats = {"ppg": 0, "rpg": 0, "apg": 0, "fg_pct": 0}
        
        # Find team stats in the team_stats data
        for stat in team_stats:
            if stat:
                # Handle both list/tuple and dictionary formats
                if isinstance(stat, (list, tuple)) and len(stat) > 0:
                    stat_team_id = stat[0]
                elif isinstance(stat, dict):
                    stat_team_id = stat.get('team_id')
                else:
                    continue
                
                if stat_team_id == home_team_id:
                    if isinstance(stat, (list, tuple)):
                        home_team_stats = {
                            "ppg": stat[26] if len(stat) > 26 else 0,
                            "rpg": stat[18] if len(stat) > 18 else 0,
                            "apg": stat[19] if len(stat) > 19 else 0,
                            "fg_pct": stat[9] * 100 if len(stat) > 9 and stat[9] else 0
                        }
                    else:
                        home_team_stats = {
                            "ppg": stat.get('base_totals_pts_rank', 0),
                            "rpg": stat.get('base_totals_reb_rank', 0),
                            "apg": stat.get('base_totals_ast_rank', 0),
                            "fg_pct": stat.get('base_totals_fgm_rank', 0)
                        }
                
                if stat_team_id == away_team_id:
                    if isinstance(stat, (list, tuple)):
                        away_team_stats = {
                            "ppg": stat[26] if len(stat) > 26 else 0,
                            "rpg": stat[18] if len(stat) > 18 else 0,
                            "apg": stat[19] if len(stat) > 19 else 0,
                            "fg_pct": stat[9] * 100 if len(stat) > 9 and stat[9] else 0
                        }
                    else:
                        away_team_stats = {
                            "ppg": stat.get('base_totals_pts_rank', 0),
                            "rpg": stat.get('base_totals_reb_rank', 0),
                            "apg": stat.get('base_totals_ast_rank', 0),
                            "fg_pct": stat.get('base_totals_fgm_rank', 0)
                        }
        
        # Create game object
        game_obj = {
            "game_id": game_id,
            "home_team_id": home_team_id,
            "home_team_name": home_team_name,
            "home_team_score": home_team_score,
            "away_team_id": away_team_id,
            "away_team_name": away_team_name,
            "away_team_score": away_team_score,
            "game_status": game_status,
            "game_date": game_date.strftime("%Y-%m-%d") if hasattr(game_date, 'strftime') else "",
            "game_time": game_time,
            "home_record": home_record,
            "away_record": away_record,
            "home_team_abbreviation": home_team_abbreviation,
            "away_team_abbreviation": away_team_abbreviation,
            "home_team_stats": home_team_stats,
            "away_team_stats": away_team_stats,
            "is_live": game_status == "Live"
        }
        
        games.append(game_obj)
    
    return games

def get_featured_games(games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get featured games for the dashboard.
    
    Args:
        games: List of processed game objects
        
    Returns:
        List of featured game objects (max 3)
    """
    featured_games = []
    
    # Add to featured games if it's not a final game
    for game in games:
        if len(featured_games) < 3 and game["game_status"] != "Final":
            featured_games.append(game)
    
    # If we don't have enough featured games, add some from the regular games
    if len(featured_games) < 3:
        remaining_games = [g for g in games if g not in featured_games]
        featured_games.extend(remaining_games[:3 - len(featured_games)])
    
    return featured_games

def get_standings_data(teams: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process teams data to create standings.
    
    Args:
        teams: List of team objects
        
    Returns:
        Dict with East and West conference standings
    """
    try:
        standings_data = {
            "East": [],
            "West": []
        }
        
        for team in teams:
            team_data = {
                "TEAM": team.get('name', ''),
                "W": team.get('wins', 0),
                "L": team.get('losses', 0),
                "W_PCT": team.get('win_pct', 0.0)
            }
            if team.get('conference') == 'East':
                standings_data["East"].append(team_data)
            else:
                standings_data["West"].append(team_data)
        
        # Sort standings by win percentage
        standings_data["East"] = sorted(standings_data["East"], key=lambda x: x["W_PCT"], reverse=True)
        standings_data["West"] = sorted(standings_data["West"], key=lambda x: x["W_PCT"], reverse=True)
        logger.debug("Standings data processed successfully")
        
        return standings_data
    except Exception as e:
        logger.error(f"Error processing standings data: {str(e)}")
        return {"East": [], "West": []}

def get_hot_players_data() -> List[Dict[str, Any]]:
    """
    Get players on streaks data.
    
    Returns:
        List of players on streaks
    """
    try:
        hot_players_data = PlayerStreaks.get_hot_player_streaks(limit=5, threshold=10) or []
        logger.debug(f"Retrieved {len(hot_players_data)} players on hot streaks")
        
        hot_players = []
        for player in hot_players_data:
            player_obj = {
                "player_id": player.get("player_id") if isinstance(player, dict) else getattr(player, "player_id", None),
                "player_name": player.get("player_name") if isinstance(player, dict) else getattr(player, "player_name", ""),
                "team_abbreviation": player.get("team_abbreviation") if isinstance(player, dict) else getattr(player, "team_abbreviation", ""),
                "streak_type": player.get("streak_type") if isinstance(player, dict) else getattr(player, "streak_type", ""),
                "streak_value": player.get("streak_value") if isinstance(player, dict) else getattr(player, "streak_value", 0),
                "streak_count": player.get("streak_count") if isinstance(player, dict) else getattr(player, "streak_count", 0)
            }
            hot_players.append(player_obj)
        
        return hot_players
    except Exception as e:
        logger.warning(f"Error fetching player streaks: {str(e)}")
        return []

def get_team_visuals_data():
    """
    Get team performance data for visualization.
    """
    season = "2024-25"  # Default to current season
    
    # Get team rankings from LeagueDashTeamStats
    team_rankings = LeagueDashTeamStats.get_team_stats(season, "Totals")
    print(f"Retrieved {len(team_rankings) if team_rankings else 0} team rankings")
    
    team_names = []
    team_ppg_ranks = []
    team_rpg_ranks = []
    team_apg_ranks = []
    team_fg_pct_ranks = []
    
    if team_rankings:
        # Sort by points rank for initial display
        sorted_teams = sorted(team_rankings, key=lambda x: x.get("base_totals_pts_rank", 30))
        
        for team in sorted_teams[:15]:  # Show top 15 teams for better visualization
            team_name = team.get("team_name", "")
            if team_name:
                team_names.append(team_name)
                team_ppg_ranks.append(team.get("base_totals_pts_rank", 30))
                team_rpg_ranks.append(team.get("base_totals_reb_rank", 30))
                team_apg_ranks.append(team.get("base_totals_ast_rank", 30))
                team_fg_pct_ranks.append(team.get("base_totals_fgm_rank", 30))
    
    result = {
        "team_names": team_names,
        "team_ppg": team_ppg_ranks,
        "team_rpg": team_rpg_ranks,
        "team_apg": team_apg_ranks,
        "team_fg_pct": team_fg_pct_ranks
    }
    
    print(f"Team names: {team_names}")
    print(f"Points ranks: {team_ppg_ranks}")
    print(f"Rebounds ranks: {team_rpg_ranks}")
    print(f"Assists ranks: {team_apg_ranks}")
    print(f"FG% ranks: {team_fg_pct_ranks}")
    
    return result
