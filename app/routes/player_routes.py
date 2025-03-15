from flask import Blueprint, render_template, request, jsonify
from app.models.player import Player
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
        grouped_streaks = PlayerService.get_grouped_player_streaks()
        logger.debug(f"Found {len(grouped_streaks) if grouped_streaks else 0} streak types")
        
        # Define thresholds for common stats
        default_thresholds = {
            "PTS": 10,
            "REB": 5,
            "AST": 5,
            "STL": 2,
            "BLK": 2,
            "FG3M": 2
        }
        
        # Flatten and format the streaks for display
        streaks = []
        if grouped_streaks:
            for stat_type, stat_streaks in grouped_streaks.items():
                for streak in stat_streaks:
                    # Format the stat display (e.g., "20+ points", "10+ rebounds")
                    stat_display = stat_type
                    threshold = streak.get('streak_value', default_thresholds.get(stat_type, 10))
                    
                    # Format stat display based on stat type
                    if stat_type == "PTS":
                        stat_display = "Points"
                    elif stat_type == "REB":
                        stat_display = "Rebounds"
                    elif stat_type == "AST":
                        stat_display = "Assists"
                    elif stat_type == "STL":
                        stat_display = "Steals"
                    elif stat_type == "BLK":
                        stat_display = "Blocks"
                    elif stat_type == "FG3M":
                        stat_display = "3-Pointers"
                    
                    formatted_streak = {
                        'player_name': streak.get('player_name', 'Unknown'),
                        'team_abbreviation': streak.get('team', 'N/A'),  # Note: key is 'team' from database
                        'stat': stat_display,
                        'threshold': threshold,
                        'streak_games': streak.get('streak_games', 0)
                    }
                    streaks.append(formatted_streak)
        
        # Sort streaks by streak length (descending)
        streaks = sorted(streaks, key=lambda x: x['streak_games'], reverse=True)
        
        if not streaks:
            logger.warning("No streaks found to display")
            return render_template("player_streaks.html", streaks=[], message="No active streaks found")
            
        logger.info(f"Successfully formatted {len(streaks)} streaks for display")
        return render_template("player_streaks.html", streaks=streaks)
        
    except Exception as e:
        logger.error(f"Error displaying player streaks: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")  # Add traceback for better debugging
        return render_template("error.html", message="Error loading player streaks"), 500

# This function is kept here for backward compatibility with other modules
# that might be importing it directly from routes
def get_player_comparison_stats(player_id):
    """Helper function to get properly formatted player stats for comparison."""
    return PlayerService.get_comparison_stats(player_id)
