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
    teams = Team.list_all_teams() or []
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
        teams = Team.list_all_teams() or []
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
        print(f"Starting matchup data retrieval for teams {team1_id} vs {team2_id}")
        # Convert string IDs to integers if needed
        if isinstance(team1_id, str):
            team1_id = int(team1_id)
        if isinstance(team2_id, str):
            team2_id = int(team2_id)
            
        # Fetch team details
        print(f"Fetching team details for {team1_id} and {team2_id}")
        team1 = Team.get_team_with_details(team1_id)
        team2 = Team.get_team_with_details(team2_id)
        
        if not team1 or not team2:
            print(f"❌ Could not find team data for {team1_id} or {team2_id}")
            return None
        
        print(f"Successfully retrieved team details. Team1 roster size: {len(team1['roster'])}, Team2 roster size: {len(team2['roster'])}")
        
        # Get lineup stats (from old implementation)
        try:
            print(f"Fetching lineup stats for teams {team1_id} and {team2_id}")
            from app.services.team_service import get_team_lineup_stats
            team1_lineup_stats = get_team_lineup_stats(team1['team_id'])
            team2_lineup_stats = get_team_lineup_stats(team2['team_id'])
            print(f"Successfully retrieved lineup stats")
        except Exception as e:
            print(f"Error fetching team lineup stats: {str(e)}")
            team1_lineup_stats = []
            team2_lineup_stats = []
        
        # Get player logs for both teams
        print(f"Fetching recent logs for team {team1_id}")
        team1_recent_logs = fetch_logs(team1['roster'])
        print(f"Fetching recent logs for team {team2_id}")
        team2_recent_logs = fetch_logs(team2['roster'])
        print(f"Fetching team1 vs team2 logs")
        team1_vs_team2_logs = fetch_logs(team1['roster'], team2_id)
        print(f"Fetching team2 vs team1 logs")
        team2_vs_team1_logs = fetch_logs(team2['roster'], team1_id)
        print(f"Successfully retrieved all game logs")
        
        return {
            "team1": team1,
            "team2": team2,
            "team1_lineup_stats": team1_lineup_stats,
            "team2_lineup_stats": team2_lineup_stats,
            "team1_recent_logs": team1_recent_logs,
            "team2_recent_logs": team2_recent_logs,
            "team1_vs_team2_logs": team1_vs_team2_logs,
            "team2_vs_team1_logs": team2_vs_team1_logs,
            "teams": Team.list_all_teams()  # Add this for the team selection dropdown
        }
    except Exception as e:
        print(f"❌ Error in get_matchup_data: {str(e)}")
        traceback.print_exc()
        return None

def normalize_logs(raw_logs):
    """Normalize player game logs."""
    if not raw_logs:
        return []
    
    # Convert minutes_played from "MM:SS" format to decimal minutes
    def convert_minutes(min_str):
        if not min_str or min_str == "00:00":
            return "0.0"
        try:
            if ':' in str(min_str):
                minutes, seconds = map(int, str(min_str).split(':'))
                return f"{minutes + seconds/60:.1f}"
            return f"{float(min_str):.1f}"
        except (ValueError, TypeError):
            return "0.0"
    
    def format_game_date(date_str):
        if isinstance(date_str, datetime):
            return date_str.strftime("%a %m/%d")
        try:
            date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")
            return date_obj.strftime("%a %m/%d")
        except (ValueError, TypeError):
            return str(date_str)
    
    normalized_logs = []
    for log in raw_logs:
        if isinstance(log, dict):
            # Format the score
            team_score = log.get('team_score', 0)
            opponent_score = log.get('opponent_score', 0)
            team_abbrev = log.get('team_abbreviation', 'TEAM')
            opp_abbrev = log.get('opponent_abbreviation', 'OPP')
            
            # Determine win/loss
            result = 'W' if team_score > opponent_score else 'L'
            formatted_score = f"{team_abbrev} {team_score} - {opponent_score} {opp_abbrev}"
            
            # Create normalized log with all fields
            normalized_log = {
                'game_date': format_game_date(log.get('game_date')),
                'points': log.get('points', 0),
                'assists': log.get('assists', 0),
                'rebounds': log.get('rebounds', 0),
                'steals': log.get('steals', 0),
                'blocks': log.get('blocks', 0),
                'turnovers': log.get('turnovers', 0),
                'minutes_played': convert_minutes(log.get('minutes_played', '00:00')),
                'season': log.get('season', '2024-25'),
                'home_or_away': log.get('home_or_away', 'H'),
                'opponent_abbreviation': opp_abbrev,
                'team_abbreviation': team_abbrev,
                'result': result,
                'formatted_score': formatted_score,
                'team_score': team_score,
                'opponent_score': opponent_score
            }
        else:
            # Fallback for tuple input (should be rare)
            normalized_log = {
                'game_date': format_game_date(datetime.now()),
                'points': 0,
                'assists': 0,
                'rebounds': 0,
                'steals': 0,
                'blocks': 0,
                'turnovers': 0,
                'minutes_played': '0.0',
                'season': '2024-25',
                'home_or_away': 'H',
                'opponent_abbreviation': 'OPP',
                'team_abbreviation': 'TEAM',
                'result': 'W',
                'formatted_score': 'TEAM 100 - 90 OPP',
                'team_score': 100,
                'opponent_score': 90
            }
            
            # Try to extract values if possible
            try:
                if len(log) > 3:
                    normalized_log['points'] = int(log[3] or 0)
                if len(log) > 4:
                    normalized_log['assists'] = int(log[4] or 0)
                if len(log) > 5:
                    normalized_log['rebounds'] = int(log[5] or 0)
                if len(log) > 6:
                    normalized_log['steals'] = int(log[6] or 0)
                if len(log) > 7:
                    normalized_log['blocks'] = int(log[7] or 0)
                if len(log) > 8:
                    normalized_log['turnovers'] = int(log[8] or 0)
                if len(log) > 9:
                    normalized_log['minutes_played'] = convert_minutes(log[9])
            except (ValueError, TypeError, IndexError):
                pass  # Keep default values if conversion fails
        
        normalized_logs.append(normalized_log)
    
    return normalized_logs

def fetch_logs(players, opponent_id=None, max_players=None):
    """Fetch game logs for players against a specific opponent."""
    print(f"Starting fetch_logs for {len(players)} players, opponent_id: {opponent_id}")
    player_logs = {}
    
    # Deduplicate players by player_id
    unique_players = {}
    for player in players:
        player_id = player.get("player_id")
        if player_id and player_id not in unique_players:
            unique_players[player_id] = player
    
    # Convert back to list
    deduplicated_players = list(unique_players.values())
    print(f"Deduplicated roster from {len(players)} to {len(deduplicated_players)} players")
    
    for i, player in enumerate(deduplicated_players):
        player_id = player.get("player_id")
        player_name = player.get("player_name")
        
        print(f"Processing player {i+1}/{len(deduplicated_players)}: {player_name} (ID: {player_id})")
        
        if not player_id or not player_name:
            print(f"Skipping player with missing ID or name")
            continue
        
        try:
            if opponent_id:
                print(f"Fetching logs for player {player_id} vs opponent {opponent_id}")
                logs = PlayerGameLog.get_game_logs_vs_opponent(player_id, opponent_id)
                print(f"Retrieved {len(logs)} logs for player {player_id} vs opponent {opponent_id}")
            else:
                print(f"Fetching last 10 logs for player {player_id}")
                logs = PlayerGameLog.get_last_n_games_by_player(player_id, 10)
                print(f"Retrieved {len(logs)} logs for player {player_id}")
            
            # Normalize logs
            print(f"Normalizing logs for player {player_id}")
            normalized_logs = normalize_logs(logs)
            
            if normalized_logs:
                player_logs[player_id] = normalized_logs
                print(f"Added {len(normalized_logs)} logs for player {player_id}")
            else:
                print(f"No logs found for player {player_id}")
                
        except Exception as e:
            print(f"Error processing logs for player {player_id}: {str(e)}")
            traceback.print_exc()
    
    print(f"Completed fetch_logs, retrieved logs for {len(player_logs)} players")
    return player_logs
