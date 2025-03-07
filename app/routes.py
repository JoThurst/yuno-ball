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
    current_app as app
)
import json
import numpy as np
from datetime import datetime
import re

from app.utils.cache_utils import get_cache, set_cache

from app.models.player import Player
from app.models.statistics import Statistics
from app.models.team import Team
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.models.playergamelog import PlayerGameLog
from app.models.gameschedule import GameSchedule

from app.utils.get.get_utils import get_enhanced_teams_data, get_team_lineup_stats, get_player_data
from app.utils.fetch.fetch_utils import fetch_todays_games

main = Blueprint("main", __name__)


@main.route("/")
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
def get_team_stats():
    """
    API Endpoint to return team stats data for Chart.js
    Accepts:
    - season (e.g., "2023-24")
    - per_mode (e.g., "Totals", "Per48", "Per100Possessions")
    """
    season = request.args.get("season", "2023-24")
    per_mode = request.args.get("per_mode", "Totals")  # Default to Totals

    stats = LeagueDashTeamStats.get_team_stats(season, per_mode)
    return jsonify(stats)



def get_team_visuals_data():
    """
    Fetch and organize relevant data for the /team-stats-visuals page.
    Includes standings, today's games, last 10 games for each team, and upcoming matchups.
    """
    print("🔄 Fetching team stats visuals data...")

    cache_key = "team_visuals_data"
    cached_data = get_cache(cache_key)

    if cached_data:
        print(f"✅ Cache HIT for team visuals data")
        return cached_data

    # 🔹 Fetch standings and today's games
    data = fetch_todays_games()
    standings = data.get("standings", [])
    today_games = data.get("games", [])

    # 🔹 Get last 10 games for teams playing today
    matchups = []
    for game in today_games:
        home_team_id = game["home_team_id"]
        away_team_id = game["away_team_id"]

        home_team_games = GameSchedule.get_last_n_games_by_team(home_team_id, 10)
        away_team_games = GameSchedule.get_last_n_games_by_team(away_team_id, 10)

        # ✅ Standardize game headers (1-10) instead of game dates
        home_team_games_standardized = {str(i+1): game["team_score"] for i, game in enumerate(home_team_games)}
        away_team_games_standardized = {str(i+1): game["team_score"] for i, game in enumerate(away_team_games)}

        matchups.append({
            "game_id": game["game_id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "game_time": game["game_time"],
            "home_last_10_games": home_team_games_standardized,
            "away_last_10_games": away_team_games_standardized
        })

    # ✅ Cache for 10 minutes
    set_cache(cache_key, {"standings": standings, "today_games": today_games, "matchups": matchups}, ex=600)

    print(f"✅ Stored team visuals data in cache")
    return {"standings": standings, "today_games": today_games, "matchups": matchups}

