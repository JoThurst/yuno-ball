from flask import Blueprint, render_template, request, jsonify
from app.models.player import Player
from app.services.player_service import PlayerService
from app.utils.config_utils import logger

player_bp = Blueprint("player", __name__, url_prefix="/players")

@player_bp.route("/")
def player_list():
    """Display a list of all players."""
    players = PlayerService.get_all_players()
    return render_template("player_list.html", players=players)

#Todo Fix this route
@player_bp.route("/<int:player_id>")
def player_detail(player_id):
    """Display detailed information for a specific player."""
    # Get player details using the service
    player_data = PlayerService.get_player_details(player_id)
    
    if not player_data:
        return render_template("error.html", message="Player not found"), 404
    
    return render_template(
        "player_detail.html",
        player_data=player_data,
        player_id=player_id
    )

@player_bp.route("/streaks")
def player_streaks():
    """Display players on hot streaks."""
    try:
        logger.info("Fetching player streaks for display")
        grouped_streaks = PlayerService.get_grouped_player_streaks()
        logger.debug(f"Found {len(grouped_streaks)} streak types")
        
        # Flatten the grouped streaks
        streaks = []
        for streak_type, type_streaks in grouped_streaks.items():
            for streak in type_streaks:
                streaks.append({
                    'player_name': streak['player_name'],
                    'team_abbreviation': streak.get('team_abbreviation', ''),
                    'team_id': streak.get('team_id', ''),
                    'stat': streak['streak_type'],
                    'threshold': streak['streak_value'],
                    'streak_games': streak['streak_count']
                })
        
        if not streaks:
            logger.warning("No streaks found to display")
            return render_template("player_streaks.html", streaks=[], message="No active streaks found")
            
        return render_template("player_streaks.html", streaks=streaks)
    except Exception as e:
        logger.error(f"Error displaying player streaks: {str(e)}")
        return render_template("error.html", message="Error loading player streaks"), 500

# This function is kept here for backward compatibility with other modules
# that might be importing it directly from routes
def get_player_comparison_stats(player_id):
    """Helper function to get properly formatted player stats for comparison."""
    return PlayerService.get_comparison_stats(player_id)
