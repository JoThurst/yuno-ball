from flask import Blueprint, render_template, request, jsonify
from app.models.player import Player
from app.models.player_streaks import PlayerStreaks
from app.services.player_service import PlayerService
from app.utils.config_utils import logger
import traceback

player_bp = Blueprint("player", __name__, url_prefix="/players")

@player_bp.route("/")
def player_list():
    """Display a list of all players."""
    players = PlayerService.get_all_players()
    return render_template("player_list.html", players=players)

# Player detail route - displays comprehensive player dashboard
@player_bp.route("/<int:player_id>")
def player_detail(player_id):
    """Display detailed information for a specific player."""
    # Get player details using the service
    player_data = PlayerService.get_player_details(player_id)
    
    if not player_data:
        return render_template("error.html", message="Player not found"), 404
    
    # Get team information if available
    team_info = None
    if player_data.get('roster') and player_data['roster'].get('team_id'):
        from app.models.team import Team
        team_id = player_data['roster']['team_id']
        team_info = Team.get_team(team_id)
    
    return render_template(
        "player_detail.html",
        player_data=player_data,
        player_id=player_id,
        team_info=team_info
    )

@player_bp.route("/streaks")
def player_streaks():
    """Display players on hot streaks."""
    try:
        logger.info("Fetching player streaks for display")
        
        # Get all streaks with a minimum of 7 games
        grouped_streaks = PlayerStreaks.get_all_player_streaks(min_streak_games=7)
        
        if not grouped_streaks:
            logger.warning("No streaks found to display")
            return render_template("player_streaks.html", streaks=[], message="No active streaks found")
        
        # Flatten the grouped streaks for display
        streaks = []
        for stat_streaks in grouped_streaks.values():
            streaks.extend(stat_streaks)
        
        # Sort streaks by streak length (descending)
        streaks = sorted(streaks, key=lambda x: x['streak_games'], reverse=True)
        
        logger.info(f"Successfully retrieved {len(streaks)} streaks for display")
        return render_template("player_streaks.html", streaks=streaks)
        
    except Exception as e:
        logger.error(f"Error displaying player streaks: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return render_template("error.html", message="Error loading player streaks"), 500

# This function is kept here for backward compatibility with other modules
# that might be importing it directly from routes
def get_player_comparison_stats(player_id):
    """Helper function to get properly formatted player stats for comparison."""
    return PlayerService.get_comparison_stats(player_id)
