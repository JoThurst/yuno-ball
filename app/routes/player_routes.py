from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.player_service import PlayerService
from app.models.team_sqlalchemy import TeamORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.database import get_db_context
from app.utils.config_utils import logger
import traceback

player_bp = Blueprint("player", __name__, url_prefix="/players")

@player_bp.route("/", strict_slashes=False)
def player_list():
    """Display a list of all players."""
    players = PlayerService.get_all_players()
    return render_template("player_list.html", players=players)

# Player detail route - displays comprehensive player dashboard
@player_bp.route("/<int:player_id>")
def player_detail(player_id):
    """Display detailed information for a specific player."""
    # Get season from query params or use current season
    from app.utils.fetch.fetch_utils import get_current_season_str
    season = request.args.get("season") or get_current_season_str()
    current_season = get_current_season_str()
    
    # Get player details using the service
    player_data = PlayerService.get_player_details(player_id)
    
    if not player_data:
        return render_template("error.html", message="Player not found"), 404
    
    # Get team information if available
    team_info = None
    if player_data.get('roster') and player_data['roster'].get('team_id'):
        team_id = player_data['roster']['team_id']
        with get_db_context() as db:
            team_orm = TeamORM.get_by_id(team_id, db)
            team_info = team_orm.to_dict() if team_orm else None
    
    # Add season info to template context
    player_data['season'] = season
    player_data['current_season'] = current_season
    # Keep the legacy template safe for players without current-season logs.
    # Missing observations remain missing; the template presents an em dash.
    player_data.setdefault('game_logs', [])
    player_data.setdefault('league_stats', [])
    player_data.setdefault('averages', {})

    return render_template(
        "player_detail.html",
        player_data=player_data,
        player_id=player_id,
        team_info=team_info
    )

@player_bp.route("/streaks")
def player_streaks():
    """Retire the unscoped streak table; Daily owns contextual player signals."""
    return redirect(url_for("daily.fan_daily"), code=302)

# This function is kept here for backward compatibility with other modules
# that might be importing it directly from routes
def get_player_comparison_stats(player_id):
    """Helper function to get properly formatted player stats for comparison."""
    return PlayerService.get_comparison_stats(player_id)
