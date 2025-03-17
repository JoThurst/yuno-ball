from flask import Blueprint, request, jsonify
from app.models.team import Team
from app.models.player import Player
from app.models.gameschedule import GameSchedule
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.services.player_service import PlayerService
from app.middleware.security import secure_endpoint, api_key_required, rate_limit_by_ip
import json

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route('/team-stats', methods=['GET'])
@secure_endpoint()
@rate_limit_by_ip()
def get_team_stats_api():
    """API endpoint to get team statistics."""
    team_id = request.args.get('team_id')
    season = request.args.get('season', '2024-25')
    
    if not team_id:
        return jsonify({"error": "Team ID is required"}), 400
    
    # Get team details
    team = Team.get_team_with_details(team_id)
    
    if not team:
        return jsonify({"error": "Team not found"}), 404
    
    # Get team stats - use Per48 stats for rankings (lower is better)
    team_stats = LeagueDashTeamStats.get_team_stats(season, "Per48") or []
    
    # Initialize default stats
    stats = {
        "pts": 0,
        "reb": 0,
        "ast": 0,
        "fg_pct": 0
    }
    
    # Find the stats for this team
    for stat in team_stats:
        # Handle both list/tuple and dictionary formats
        if isinstance(stat, (list, tuple)) and len(stat) > 0 and stat[0] == int(team_id):
            # If it's a list/tuple, we need to map indices to the right stats
            # This is a fallback, but we prefer dictionary format
            stats = {
                "pts": stat[26] if len(stat) > 26 else 0,
                "reb": stat[18] if len(stat) > 18 else 0,
                "ast": stat[19] if len(stat) > 19 else 0,
                "fg_pct": stat[9] * 100 if len(stat) > 9 and stat[9] else 0
            }
            break
        elif isinstance(stat, dict) and stat.get("team_id") == int(team_id):
            # Use ranking stats if available (lower is better)
            stats = {
                "pts": stat.get("base_per48_pts_rank", 0),
                "reb": stat.get("base_per48_reb_rank", 0),
                "ast": stat.get("base_per48_ast_rank", 0),
                "fg_pct": stat.get("base_per48_fgm_rank", 0)
            }
            break
    
    # Get last 10 games
    last_games = GameSchedule.get_last_n_games_by_team(team_id, 10) or []
    
    # Process games
    games = []
    for game in last_games:
        # Determine if team is home or away
        is_home = str(game.get("home_team_id")) == str(team_id)
        
        # Get opponent details
        opponent_id = game.get("away_team_id") if is_home else game.get("home_team_id")
        opponent = Team.get_team(opponent_id)
        
        # Get opponent abbreviation
        opponent_abbreviation = ""
        if opponent:
            if hasattr(opponent, 'abbreviation'):
                opponent_abbreviation = opponent.abbreviation
            elif isinstance(opponent, dict):
                opponent_abbreviation = opponent.get('abbreviation', '')
        
        # Format game date
        game_date = game.get("game_date", "")
        if hasattr(game_date, 'strftime'):
            game_date = game_date.strftime("%Y-%m-%d")
        
        # Get score and result directly from the game data
        score = game.get("score", "0-0")
        result = game.get("result", "TBD")
        
        # Add game to list
        games.append({
            "date": game_date,
            "opponent": opponent_abbreviation,
            "result": result,
            "score": score
        })
    
    # Prepare response - handle both object and dictionary formats for team
    response = {
        "name": team.name if hasattr(team, 'name') else team.get('name', ''),
        "abbreviation": team.abbreviation if hasattr(team, 'abbreviation') else team.get('abbreviation', ''),
        "record": team.record if hasattr(team, 'record') else team.get('record', ''),
        "stats": stats,
        "games": games
    }
    
    # Print response for debugging
    print(f"Team Stats API Response: {json.dumps(response, default=str)}")
    
    return jsonify(response)

@api_bp.route('/player-comparison', methods=['GET'])
@secure_endpoint()
@rate_limit_by_ip()
def get_player_comparison():
    """API endpoint to compare two players."""
    player1_id = request.args.get('player1_id')
    player2_id = request.args.get('player2_id')
    
    if not player1_id or not player2_id:
        return jsonify({"error": "Both player IDs are required"}), 400
    
    # Use the service to compare players
    comparison_data = PlayerService.compare_players(player1_id, player2_id)
    print(f"Comparison Data: {comparison_data}")
    if not comparison_data:
        return jsonify({"error": "One or both players not found"}), 404
    
    return jsonify(comparison_data)

@api_bp.route('/fetch-player-streaks')
@secure_endpoint()
@api_key_required()
@rate_limit_by_ip()
def fetch_and_store_player_streaks():
    """API endpoint to fetch and store player streaks."""
    from app.utils.fetch.fetch_player_utils import fetch_player_streaks
    
    try:
        result = fetch_player_streaks()
        return jsonify({"success": True, "message": "Player streaks fetched and stored", "count": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
