from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.models.gameschedule import GameSchedule
from app.models.team import Team
from app.models.player import Player
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.models.playergamelog import PlayerGameLog
from app.utils.fetch.fetch_utils import fetch_todays_games
from app.utils.cache_utils import get_cache, set_cache
from datetime import datetime, timedelta
import re
import traceback


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

#Todo Fix this route
@dashboard_bp.route("/")
def dashboard():
    """Main dashboard with various statistics and visualizations."""
    player_stats = LeagueDashPlayerStats.get_all_stats()
    teams = Team.get_all_teams() or []
    return render_template("dashboard.html", player_stats=player_stats, teams=teams)

@dashboard_bp.route('/games')
def games_dashboard():
    """Dashboard showing today's games and standings."""
    # Use fetch_todays_games to get both standings and games data
    data = fetch_todays_games()
    standings = data.get("standings", {"East": [], "West": []})
    games = data.get("games", [])
    
    print(f"Retrieved {len(games)} games and standings for East ({len(standings.get('East', []))}) and West ({len(standings.get('West', []))})")
    
    return render_template("games_dashboard.html", standings=standings, games=games)

#Todo Fix this route
#maybe, need to fix matchups populating 
@dashboard_bp.route("/matchup", methods=['GET', 'POST'])
def matchup():
    """Display matchup analysis between two teams."""
    # If it's a POST request, redirect to GET with the same parameters
    if request.method == 'POST':
        team1_id = request.form.get("team1_id")
        team2_id = request.form.get("team2_id")
        return redirect(url_for('dashboard.matchup', team1_id=team1_id, team2_id=team2_id))
    
    team1_id = request.args.get("team1_id")
    team2_id = request.args.get("team2_id")
    
    if not team1_id or not team2_id:
        teams = Team.get_all_teams() or []
        return render_template("matchup.html", teams=teams)
    
    # Check cache first
    cache_key = f"matchup:{team1_id}:{team2_id}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        print(f"✅ Cache HIT for matchup: {team1_id} vs {team2_id}")
        return render_template("matchup.html", **cached_data)
    
    # Get matchup data
    matchup_data = get_matchup_data(team1_id, team2_id)
    
    if not matchup_data:
        return render_template("error.html", message="Could not retrieve matchup data for the selected teams"), 404
    
    # Cache the data
    print(f"[CACHE] Cached Matchup: {team1_id} vs {team2_id}")
    
    # Convert player IDs to strings for JSON serialization
    matchup_data["team1_recent_logs"] = {
        str(k): v for k, v in matchup_data.get("team1_recent_logs", {}).items()
    }
    matchup_data["team2_recent_logs"] = {
        str(k): v for k, v in matchup_data.get("team2_recent_logs", {}).items()
    }
    matchup_data["team1_vs_team2_logs"] = {
        str(k): v for k, v in matchup_data.get("team1_vs_team2_logs", {}).items()
    }
    matchup_data["team2_vs_team1_logs"] = {
        str(k): v for k, v in matchup_data.get("team2_vs_team1_logs", {}).items()
    }
    
    set_cache(cache_key, matchup_data, ex=86400)  # Cache for 24 hours
    print(f"✅ Cached Matchup: {team1_id} vs {team2_id}")
    
    return render_template("matchup.html", **matchup_data)

def get_matchup_data(team1_id, team2_id):
    """Get matchup data for two teams."""
    try:
        # Convert string IDs to integers if needed
        if isinstance(team1_id, str):
            team1_id = int(team1_id)
        if isinstance(team2_id, str):
            team2_id = int(team2_id)
            
        # Fetch team details
        team1 = Team.get_team_with_details(team1_id)
        team2 = Team.get_team_with_details(team2_id)
        
        if not team1 or not team2:
            print(f"❌ Could not find team data for {team1_id} or {team2_id}")
            return None
        
        # Get team rosters
        team1_roster = Team.get_roster_by_team_id(team1_id) or []
        team2_roster = Team.get_roster_by_team_id(team2_id) or []
        
        # Get team stats
        #team1_stats = LeagueDashTeamStats.get_team_stats_by_id(team1_id) or []
        #team2_stats = LeagueDashTeamStats.get_team_stats_by_id(team2_id) or []
        
        # Get lineup stats (from old implementation)
        from app.services.team_service import get_team_lineup_stats
        team1_lineup_stats = get_team_lineup_stats(team1_id)
        team2_lineup_stats = get_team_lineup_stats(team2_id)
        
        # Get player logs for both teams
        team1_recent_logs = fetch_logs(team1["roster"])
        team2_recent_logs = fetch_logs(team2["roster"])
        team1_vs_team2_logs = fetch_logs(team1["roster"], team2_id)
        team2_vs_team1_logs = fetch_logs(team2["roster"], team1_id)
        
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
    except Exception as e:
        print(f"❌ Error in get_matchup_data: {str(e)}")
        traceback.print_exc()
        return None

def normalize_logs(raw_logs):
    """Normalize player game logs."""
    if not raw_logs:
        return []
    
    # Define headers based on query output
    game_logs_headers = [
        "home_team_name", "opponent_abbreviation", "game_date", "result",
        "formatted_score", "home_or_away", "points", "assists", "rebounds",
        "steals", "blocks", "turnovers", "minutes_played", "season"
    ]
    
    # Convert tuples into dictionaries
    game_logs = [dict(zip(game_logs_headers, row)) for row in raw_logs]
    
    # Format game_date, minutes_played, and formatted_score
    for log in game_logs:
        if isinstance(log["game_date"], datetime):
            log["game_date"] = log["game_date"].strftime("%a %m/%d")
        
        # Format minutes to 1 decimal place
        log["minutes_played"] = f"{float(log['minutes_played']):.1f}" if log["minutes_played"] else "0.0"
        
        # Format the score (from old implementation)
        if "formatted_score" in log:
            match = re.search(r"(\D+)\s(\d+\.?\d*)\s-\s(\d+\.?\d*)\s(\D+)", str(log["formatted_score"]))
            if match:
                team1_abv, score1, score2, team2_abv = match.groups()
                log["formatted_score"] = f"{team1_abv} {int(float(score1))} - {int(float(score2))} {team2_abv}"
    
    return game_logs

def fetch_logs(players, opponent_id=None):
    """Fetch game logs for players against a specific opponent."""
    player_logs = {}
    
    for player in players:
        player_id = player["player_id"]
        player_name = player["player_name"]
        
        if not player_id or not player_name:
            continue
        
        # Get game logs against opponent
        if opponent_id:
            logs = PlayerGameLog.get_game_logs_vs_opponent(player_id, opponent_id)
        else:
            logs = PlayerGameLog.get_last_n_games_by_player(player_id, 10)
        
        # Normalize logs
        normalized_logs = normalize_logs(logs)
        
        if normalized_logs:
            player_logs[player_id] = normalized_logs
    
    return player_logs
