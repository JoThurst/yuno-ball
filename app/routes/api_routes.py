from flask import Blueprint, request, jsonify
import json

from app.services.player_service import PlayerService
from app.services.team_service import TeamService
from app.models.team_sqlalchemy import TeamORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.database import get_db_context
from app.middleware.security import secure_endpoint, api_key_required, rate_limit_by_ip

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
    
    # Get team details using service
    team_service = TeamService()
    with get_db_context() as db:
        team_data = team_service.get_complete_team_details(int(team_id), db)
        
        if not team_data:
            return jsonify({"error": "Team not found"}), 404
        
        # Get team stats - use Per48 stats for rankings (lower is better)
        team_rankings = LeagueDashTeamStatsORM.get_team_rankings(season=season, per_mode="Per48", db=db)
    
        # Initialize default stats
        stats = {
            "pts": 0,
            "reb": 0,
            "ast": 0,
            "fg_pct": 0
        }
        
        # Find the stats for this team
        for stat in team_rankings:
            if isinstance(stat, dict) and stat.get("team_id") == int(team_id):
                # Use ranking stats (lower is better)
                stats = {
                    "pts": stat.get("pts_rank", 0),
                    "reb": stat.get("reb_rank", 0),
                    "ast": stat.get("ast_rank", 0),
                    "fg_pct": stat.get("fgm_rank", 0)
                }
                break
        
        # Get last 10 games using ORM
        last_games_orm = GameScheduleORM.get_last_n_games(int(team_id), 10, db=db)
        last_games = [game.to_dict() if hasattr(game, 'to_dict') else game for game in last_games_orm]
        
        # Process games
        games = []
        for game in last_games:
            # Determine if team is home or away
            is_home = str(game.get("home_team_id")) == str(team_id)
            
            # Get opponent details using ORM
            opponent_id = game.get("away_team_id") if is_home else game.get("home_team_id")
            opponent_orm = TeamORM.get_by_id(opponent_id, db)
            opponent_abbreviation = opponent_orm.abbreviation if opponent_orm else ""
            
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
        
        # Prepare response
        response = {
            "name": team_data.get('name', ''),
            "abbreviation": team_data.get('abbreviation', ''),
            "record": team_data.get('record', ''),
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
    player_service = PlayerService()
    comparison_data = player_service.compare_players(int(player1_id), int(player2_id))
    print(f"Comparison Data: {comparison_data}")
    if not comparison_data:
        return jsonify({"error": "One or both players not found"}), 404
    
    return jsonify(comparison_data)


