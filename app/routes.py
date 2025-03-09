"""
This module defines the main blueprint for the web application, which includes
routes for listing players, viewing player details, displaying a dashboard,
and serving player statistics data via an API endpoint.

Blueprint Name:
- main: The main blueprint for rendering player and dashboard views.

Endpoints:
- `/`: Displays a list of all players.
- `/player/<int:player_id>`: Displays detailed statistics for a specific
player.
- `/dashboard`: Renders the dashboard page for player statistics.
- `/api/dashboard`: Serves JSON data of player statistics for use in the
dashboard.
"""

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    jsonify,
    request,
    current_app as app,
    flash
)
import json
import pandas as pd
import numpy as np
from datetime import datetime
import re

from app.utils.cache_utils import get_cache, set_cache

from app.models.player import Player
from app.models.player_streaks import PlayerStreaks
from app.models.statistics import Statistics
from app.models.team import Team
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.models.playergamelog import PlayerGameLog
from app.models.gameschedule import GameSchedule

from app.utils.get.get_utils import get_enhanced_teams_data, get_team_lineup_stats, get_player_data
from app.utils.fetch.fetch_utils import fetch_todays_games, fetch_team_rosters
from app.utils.fetch.fetch_player_utils import fetch_player_streaks

main = Blueprint("main", __name__)


@main.route("/")
def welcome():
    """Display the welcome page."""
    return render_template("welcome.html")

@main.route("/players")
def player_list():
    """Display a list of all players."""
    cache_key = "players"
    data = get_cache(cache_key)

    if not data:
        print("❌ Cache MISS on Players - Fetching fresh data.")
        # Retrieve all players from the database
        players = Player.get_all_players()
        
        # Convert Player objects to dictionaries
        data = [player.__dict__ for player in players]
        
        set_cache(cache_key, data, ex=3600)
    else:
        print("✅ Cache HIT on Players")
    
    return render_template("player_list.html", players=data)

@main.context_processor
def inject_today_matchups():
    """
    Inject today's matchups into all templates for the navbar dropdown.
    Uses Redis caching to improve performance.
    """
    cache_key = "today_matchups"
    cached_matchups = get_cache(cache_key)

    if cached_matchups:
        return dict(today_matchups=cached_matchups)

    print("❌ Cache MISS - Fetching fresh matchups")

    games = fetch_todays_games().get('games', [])
    teams = Team.get_all_teams()
    team_name_to_id = {team['name']: team['team_id'] for team in teams}

    # Attach team IDs to game objects
    for game in games:
        game['home_team_id'] = team_name_to_id.get(game['home_team'])
        game['away_team_id'] = team_name_to_id.get(game['away_team'])

    # ✅ Cache matchups for 10 minutes
    set_cache(cache_key, games, ex=600)

    return dict(today_matchups=games)

@main.route('/games')
def games_dashboard():
    """
    Main dashboard to display today's games and other relevant info.
    """
    data = fetch_todays_games()
    standings = data["standings"]
    games = data["games"]
    print(data)
    return render_template("games_dashboard.html", standings=standings, games=games)


@main.route("/player/<int:player_id>")
def player_detail(player_id):
    """
    Route to display player details.
    """
    player_data = get_player_data(player_id)
    print(player_data)
    return render_template(
        "player_detail.html", player_data=player_data, player_id=player_id
    )

@main.route("/dashboard")
def dashboard():
    """Render the dashboard with player stats fetched directly from the database."""
    player_stats = LeagueDashPlayerStats.get_all_stats()  # Fetch all stats
    teams = Team.get_all_teams()
    return render_template("dashboard.html", player_stats=player_stats, teams=teams)

@main.route("/teams")
def teams():
    cache_key = "teams_data"
    data = get_cache(cache_key)
    
    if not data:
        print("❌ Cache MISS - Fetching fresh data.")
        data = get_enhanced_teams_data()
        set_cache(cache_key, data, ex=3600)
    else:
        print("✅ Cache HIT")

    return render_template("teams.html", teams=data)

@main.route("/team/<int:team_id>")
def team_detail(team_id):
    """Display details for a specific team."""
    team_data = Team.get_team_with_details(team_id)
    if not team_data:
        return "Team Not Found", 404
    return render_template("team_detail.html", team=team_data)



def get_matchup_data(team1_id, team2_id):
    # Fetch team details
    team1 = Team.get_team_with_details(team1_id)
    team2 = Team.get_team_with_details(team2_id)

    # ✅ Fetch Lineup Stats
    team1_lineup_stats = get_team_lineup_stats(team1_id)
    team2_lineup_stats = get_team_lineup_stats(team2_id)

    def normalize_logs(raw_logs):
        headers = [
            "home_team_name", "opponent_abbreviation", "game_date", "result",
            "formatted_score", "home_or_away", "points", "assists", "rebounds",
            "steals", "blocks", "turnovers", "minutes_played", "season"
        ]
        logs = [dict(zip(headers, row)) for row in raw_logs]

        for log in logs:
            if isinstance(log["game_date"], datetime):
                log["game_date"] = log["game_date"].strftime("%a %m/%d")

            log["minutes_played"] = f"{float(log['minutes_played']):.1f}" if log["minutes_played"] else "0.0"

            # Format the score
            if "formatted_score" in log:
                match = re.search(r"(\D+)\s(\d+\.?\d*)\s-\s(\d+\.?\d*)\s(\D+)", log["formatted_score"])
                if match:
                    team1_abv, score1, score2, team2_abv = match.groups()
                    log["formatted_score"] = f"{team1_abv} {int(float(score1))} - {int(float(score2))} {team2_abv}"

        return logs

    def fetch_logs(players, opponent_id=None):
        logs = {}
        for player in players:
            player_id = player['player_id']
            if opponent_id:
                raw_logs = PlayerGameLog.get_game_logs_vs_opponent(player_id, opponent_id)
            else:
                raw_logs = PlayerGameLog.get_last_n_games_by_player(player_id, 10)
            logs[player_id] = normalize_logs(raw_logs)
        return logs

    # Fetch logs
    team1_recent_logs = fetch_logs(team1['roster'])
    team2_recent_logs = fetch_logs(team2['roster'])
    team1_vs_team2_logs = fetch_logs(team1['roster'], team2_id)
    team2_vs_team1_logs = fetch_logs(team2['roster'], team1_id)

    return {
        "team1": team1,
        "team2": team2,
        "team1_lineup_stats": team1_lineup_stats,
        "team2_lineup_stats": team2_lineup_stats,
        "team1_recent_logs": team1_recent_logs,
        "team2_recent_logs": team2_recent_logs,
        "team1_vs_team2_logs": team1_vs_team2_logs,
        "team2_vs_team1_logs": team2_vs_team1_logs
    }

@main.route("/matchup")
def matchup():
    team1_id = request.args.get('team1_id', type=int)
    team2_id = request.args.get('team2_id', type=int)
    
    if not team1_id or not team2_id:
        return "Both team IDs are required", 400
    
    cache_key = f"matchup:{team1_id}:{team2_id}"
    data = get_cache(cache_key)
    
    

    if not data : 
        data = get_matchup_data(team1_id, team2_id)
        print(f"Storing matchup data in cache with key: {cache_key}")

        data["team1_recent_logs"] = {
            str(k): v for k, v in data.get("team1_recent_logs", {}).items()
        }
        data["team2_recent_logs"] = {
            str(k): v for k, v in data.get("team2_recent_logs", {}).items()
        }
        data["team1_vs_team2_logs"] = {
            str(k): v for k, v in data.get("team1_vs_team2_logs", {}).items()
        }
        data["team2_vs_team1_logs"] = {
            str(k): v for k, v in data.get("team2_vs_team1_logs", {}).items()
        }
        
        set_cache(f"matchup:{team1_id}:{team2_id}", data, ex=86400)
        print(f"✅ Cached Matchup: {team1_id} vs {team2_id}")
    else:
        print("✅ Cache HIT")
        #print(f"Retrieved matchup data from cache: {data}")
        




    
    return render_template("matchup.html", **data)


@main.route('/team-stats-visuals')
def team_stats_visuals():
    """Render the team stats visualization page."""
    data = get_team_visuals_data()
    return render_template('team_stats_visuals.html', **data)

@main.route('/api/team-stats', methods=['GET'])
def get_team_stats_api():
    """API endpoint to get detailed team statistics."""
    team_id = request.args.get('team_id')
    season = request.args.get('season', '2023-24')
    
    if not team_id:
        return jsonify({"error": "Team ID is required"}), 400
    
    # Get team details
    team = Team.get_team_with_details(team_id)
    if not team:
        return jsonify({"error": "Team not found"}), 404
    
    # Get team stats
    team_stats = LeagueDashTeamStats.get_team_stats(season, "Per48")
    stats = {
        "pts": 0,
        "reb": 0,
        "ast": 0,
        "fg_pct": 0
    }
    
    # Find the stats for this team
    for stat in team_stats:
        if stat.get("team_id") == int(team_id):
            # Use ranking stats if actual values aren't available
            stats = {
                "pts": stat.get("base_per48_pts_rank", 0),
                "reb": stat.get("base_per48_reb_rank", 0),
                "ast": stat.get("base_per48_ast_rank", 0),
                "fg_pct": stat.get("base_per48_fgm_rank", 0)
            }
            break
    
    # Get last 10 games
    last_games = GameSchedule.get_last_n_games_by_team(team_id, 10)
    games = []
    
    for game in last_games:
        opponent_id = game.get("opponent_team_id")
        
        # Get opponent team - handle both dictionary and object returns
        opponent = Team.get_team(opponent_id)
        
        # Check if opponent is a dictionary or an object
        if opponent:
            if hasattr(opponent, 'abbreviation'):
                # It's an object
                opponent_name = opponent.abbreviation if hasattr(opponent, 'abbreviation') else "Unknown"
            else:
                # It's a dictionary
                opponent_name = opponent.get("abbreviation", "Unknown")
        else:
            opponent_name = "Unknown"
        
        # Get the result and score
        result = game.get("result", "")
        team_score = game.get("team_score", 0)
        opponent_score = game.get("opponent_score", 0)
        
        games.append({
            "date": game.get("game_date", ""),
            "opponent": opponent_name,
            "result": result,
            "score": f"{team_score}-{opponent_score}" if team_score is not None and opponent_score is not None else "N/A"
        })
    
    # Check if team is a dictionary or an object
    if hasattr(team, 'name'):
        # It's an object
        response = {
            "name": team.name if hasattr(team, 'name') else "",
            "abbreviation": team.abbreviation if hasattr(team, 'abbreviation') else "",
            "record": team.record if hasattr(team, 'record') else "0-0",
            "stats": stats,
            "games": games
        }
    else:
        # It's a dictionary
        response = {
            "name": team.get("name", ""),
            "abbreviation": team.get("abbreviation", ""),
            "record": team.get("record", "0-0"),
            "stats": stats,
            "games": games
        }
    
    print(f"Team stats response: {response}")
    return jsonify(response)

def get_player_comparison_stats(player_id):
    """
    Helper function to get properly formatted player stats for comparison.
    Returns a dictionary with standardized stats.
    """
    # Create default stats dictionary with zeros
    default_stats = {
        "pts": 0,
        "reb": 0,
        "ast": 0,
        "stl": 0,
        "blk": 0,
        "fg_pct": 0
    }
    
    # Try to get player stats from LeagueDashPlayerStats
    player_stats = LeagueDashPlayerStats.get_all_stats({"player_id": player_id})
    
    if player_stats and len(player_stats) > 0:
        # Get the most recent season's stats (first entry)
        stats = player_stats[0]
        
        # Extract the stats we need
        try:
            # Convert per-game stats from total stats
            games_played = float(stats.get("gp", 1)) if stats.get("gp") and float(stats.get("gp")) > 0 else 1
            
            # Calculate per-game averages
            default_stats["pts"] = float(stats.get("pts", 0)) / games_played if stats.get("pts") else 0
            default_stats["reb"] = float(stats.get("reb", 0)) / games_played if stats.get("reb") else 0
            default_stats["ast"] = float(stats.get("ast", 0)) / games_played if stats.get("ast") else 0
            default_stats["stl"] = float(stats.get("stl", 0)) / games_played if stats.get("stl") else 0
            default_stats["blk"] = float(stats.get("blk", 0)) / games_played if stats.get("blk") else 0
            default_stats["fg_pct"] = float(stats.get("fg_pct", 0)) if stats.get("fg_pct") else 0
            
            # Apply reasonable caps for better visualization
            # These caps match the normalization scales in the frontend
            if default_stats["pts"] > 40: default_stats["pts"] = 40
            if default_stats["reb"] > 15: default_stats["reb"] = 15
            if default_stats["ast"] > 15: default_stats["ast"] = 15
            if default_stats["stl"] > 5: default_stats["stl"] = 5
            if default_stats["blk"] > 5: default_stats["blk"] = 5
            
            # Round to 1 decimal place for better display
            default_stats["pts"] = round(default_stats["pts"], 1)
            default_stats["reb"] = round(default_stats["reb"], 1)
            default_stats["ast"] = round(default_stats["ast"], 1)
            default_stats["stl"] = round(default_stats["stl"], 1)
            default_stats["blk"] = round(default_stats["blk"], 1)
            default_stats["fg_pct"] = round(default_stats["fg_pct"], 3)
            
            print(f"Calculated stats for player {player_id}: {default_stats}")
        except (ValueError, TypeError) as e:
            print(f"Error converting stats for player {player_id}: {e}")
    
    return default_stats

@main.route("/player-streaks", methods=["GET"])
def player_streaks():
    """Returns player streaks with team filtering."""
    season = request.args.get("season", "2024-25")

    # 1️⃣ Get today's games
    today_games = fetch_todays_games()
    if not today_games["games"]:
        return render_template("player_streaks.html", streaks=[], teams=[])

    # 2️⃣ Get all rosters for today's teams
    matchups = []
    team_ids = set()
    for game in today_games["games"]:
        team_ids.add(game["home_team_id"])
        team_ids.add(game["away_team_id"])
        matchups.append({
            "game_id": game["game_id"],
            "home_team_id": game["home_team_id"],
            "away_team_id": game["away_team_id"],
            "home_team_name": game["home_team"],
            "away_team_name": game["away_team"],
        })
    
    all_rosters = fetch_team_rosters(list(team_ids))
    player_ids = [p["player_id"] for p in all_rosters]
    
    # Create a player_id to team_id mapping
    player_team_map = {str(p["player_id"]): p["team_id"] for p in all_rosters}
    
    # 3️⃣ Fetch streaks for these players
    streaks = PlayerStreaks.get_streaks_by_player_ids(player_ids, season)

    # Add team_id to each streak
    for streak in streaks:
        player_id = str(streak["player_id"])
        if player_id in player_team_map:
            streak["team_id"] = player_team_map[player_id]
    
    # 4️⃣ Pass team data for filtering
    teams = Team.get_teams_by_ids(list(team_ids))
    
    # Add team abbreviation to each streak
    team_abbr_map = {str(team["team_id"]): team["abbreviation"] for team in teams}
    for streak in streaks:
        if "team_id" in streak and str(streak["team_id"]) in team_abbr_map:
            streak["team_abbreviation"] = team_abbr_map[str(streak["team_id"])]
        else:
            streak["team_abbreviation"] = "N/A"
    
    return render_template("player_streaks.html", streaks=streaks, teams=teams, matchups=matchups)


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

@main.route("/home")
def home_dashboard():
    """
    Renders the main home page dashboard with analytics widgets.
    This is the central hub for all app functionality.
    """
    season = request.args.get("season", "2024-25")
    
    # 1. Get today's games for the featured section
    today_games_data = fetch_todays_games()
    all_games = today_games_data.get("games", [])
    featured_games = all_games[:3] if all_games else []  # Limit to 3 games for the featured widget
    
    # Add additional data to each game
    for game in all_games:
        # Add team records
        home_team = Team.get_team_with_details(game["home_team_id"])
        away_team = Team.get_team_with_details(game["away_team_id"])
        
        if home_team:
            game["home_record"] = home_team.get("record", "0-0")
            game["home_team_abbreviation"] = home_team.get("abbreviation", "")
        else:
            game["home_team_abbreviation"] = ""
        
        if away_team:
            game["away_record"] = away_team.get("record", "0-0")
            game["away_team_abbreviation"] = away_team.get("abbreviation", "")
        else:
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
    
    # 2. Get player streaks for the hot streaks widget
    player_streaks = PlayerStreaks.get_streaks(season)
    print(f"Retrieved {len(player_streaks) if player_streaks else 0} player streaks")
    
    # Check if player_streaks is a list of tuples (raw database results)
    if player_streaks and isinstance(player_streaks, list) and player_streaks and isinstance(player_streaks[0], tuple):
        # Convert tuples to dictionaries
        # Assuming the order is: id, player_id, player_name, stat, threshold, streak_games, season, created_at, team_id
        streak_dicts = []
        for streak in player_streaks:
            streak_dict = {
                "id": streak[0],
                "player_id": streak[1],
                "player_name": streak[2],
                "stat": streak[3],
                "threshold": streak[4],
                "streak_games": streak[5],
                "season": streak[6],
                "created_at": streak[7],
                "team_id": streak[8] if len(streak) > 8 else None
            }
            streak_dicts.append(streak_dict)
        player_streaks = streak_dicts
    
    # Make sure player_streaks is a list
    if player_streaks is None:
        player_streaks = []
    
    # Sort by streak length and limit to top 5
    try:
        featured_streaks = sorted(player_streaks, key=lambda x: x.get("streak_games", 0) if isinstance(x, dict) else 0, reverse=True)[:5] if player_streaks else []
    except (AttributeError, TypeError) as e:
        print(f"Error sorting player_streaks: {e}")
        print(f"Type of player_streaks: {type(player_streaks)}")
        if player_streaks:
            print(f"Type of first item: {type(player_streaks[0])}")
        featured_streaks = []
    
    print(f"Featured streaks: {featured_streaks}")
    
    # 3. Get standings data
    standings = today_games_data.get("standings", {"East": [], "West": []})
    
    # 4. Get team data for the performance chart
    teams = Team.get_all_teams()
    team_names = []
    team_ppg = []
    team_rpg = []
    team_apg = []
    team_fg_pct = []
    
    # Get team stats for visualization
    team_stats = LeagueDashTeamStats.get_team_stats(season, "Per48")
    
    # Create a mapping of team_id to stats
    team_stats_map = {}
    if team_stats:
        for stat in team_stats:
            team_stats_map[stat.get("team_id")] = stat
    
    # Populate team data arrays
    for team in teams:
        team_id = team.get("team_id")
        team_names.append(team.get("abbreviation", ""))
        
        # Get stats if available
        if team_id in team_stats_map:
            stats = team_stats_map[team_id]
            team_ppg.append(stats.get("pts", 0))
            team_rpg.append(stats.get("reb", 0))
            team_apg.append(stats.get("ast", 0))
            team_fg_pct.append(stats.get("fg_pct", 0))
        else:
            team_ppg.append(0)
            team_rpg.append(0)
            team_apg.append(0)
            team_fg_pct.append(0)
    
    # 5. Get player data for the players section
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
                team_id = player_team_map.get(str(player_id))
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
                team_id = player_team_map.get(str(player_id))
                team_abbr = team_abbr_map.get(team_id, "N/A") if team_id else "N/A"
                
                top_assisters.append({
                    "player_id": player_id,
                    "player_name": player_name,
                    "team_abbreviation": team_abbr,
                    "ast": round(float(player.get("ast", 0)) if player.get("ast") else 0, 1)
                })
    
    # 6. Get all players for the comparison tool
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
    
    # 7. Get calendar data for the games section
    calendar_days = []
    # This would be populated with upcoming games in a full implementation
    
    # Get team performance data for chart
    team_data = get_team_visuals_data()
    
    return render_template(
        "home_page.html",
        featured_games=featured_games,
        games=all_games,
        standings=standings,
        featured_streaks=featured_streaks,
        player_streaks=player_streaks,
        top_scorers=top_scorers,
        top_assisters=top_assisters,
        all_players=all_players,
        team_names=team_data["team_names"],
        team_ppg=team_data["team_ppg"],
        team_rpg=team_data["team_rpg"],
        team_apg=team_data["team_apg"],
        team_fg_pct=team_data["team_fg_pct"],
        teams=teams  # Add the teams data to the template
    )

# API endpoints for dashboard functionality
@main.route('/api/player-comparison', methods=['GET'])
def get_player_comparison():
    """API endpoint to get player comparison data."""
    player1_id = request.args.get('player1_id')
    player2_id = request.args.get('player2_id')
    
    if not player1_id or not player2_id:
        return jsonify({"error": "Both player IDs are required"}), 400
    
    # Get player details
    player1 = Player.get_player(player1_id)
    player2 = Player.get_player(player2_id)
    
    if not player1 or not player2:
        return jsonify({"error": "One or both players not found"}), 404
    
    # Get player stats using the helper function
    p1_stats = get_player_comparison_stats(player1_id)
    p2_stats = get_player_comparison_stats(player2_id)
    
    print(f"Player 1 ({player1.name}) stats: {p1_stats}")
    print(f"Player 2 ({player2.name}) stats: {p2_stats}")
    
    # Format response
    response = {
        "player1": {
            "name": player1.name,
            "stats": p1_stats
        },
        "player2": {
            "name": player2.name,
            "stats": p2_stats
        }
    }
    
    return jsonify(response)

@main.route('/fetch-player-streaks')
def fetch_and_store_player_streaks():
    """Fetch and store player streaks, then redirect back to the home page."""
    from app.utils.fetch.fetch_player_utils import fetch_player_streaks
    
    try:
        # Use the existing fetch_player_streaks function
        season = request.args.get("season", "2024-25")
        streaks = fetch_player_streaks(season)
        
        # Store the streaks in the database
        if streaks:
            # Clear existing streaks first
            PlayerStreaks.clear_streaks()
            
            # Store new streaks
            PlayerStreaks.store_streaks(streaks)
            
            flash(f"Successfully fetched and stored {len(streaks)} player streaks.", "success")
        else:
            flash("No player streaks found.", "warning")
    except Exception as e:
        flash(f"Error fetching player streaks: {str(e)}", "error")
        print(f"Error in fetch_and_store_player_streaks: {e}")
    
    # Redirect back to the home page
    return redirect(url_for('main.home_dashboard'))

