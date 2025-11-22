from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from app.services.team_service import TeamService
from app.utils.get.get_utils import get_enhanced_teams_data
from app.database import get_db_context
team_bp = Blueprint("team", __name__, url_prefix="/team")

#Todo Fix this route
@team_bp.route("/list")
def teams():
    """Display a list of all teams."""
    # Get teams data (service handles caching)
    teams = get_enhanced_teams_data()  # This function still uses old models, will migrate later
    
    # If it's a POST request, redirect to GET
    if request.method == 'POST':
        return redirect(url_for('team.teams'))
    
    return render_template("teams.html", teams=teams)

@team_bp.route("/<int:team_id>")
def team_detail(team_id):
    """Display detailed information for a specific team."""
    # Get season from query params or use current season
    from app.utils.fetch.fetch_utils import get_current_season_str
    season = request.args.get("season") or get_current_season_str()
    current_season = get_current_season_str()
    
    # Get comprehensive team data using the service
    team_service = TeamService()
    with get_db_context() as db:
        team_data = team_service.get_complete_team_details(team_id, season=season, db=db)
    
    if not team_data:
        return render_template("error.html", message="Team not found"), 404
    
    # Add season info to template context
    team_data['season'] = season
    team_data['current_season'] = current_season
    
    return render_template("team_detail.html", team=team_data)

#Todo Fix this route
@team_bp.route("/stats-visuals")
def team_stats_visuals():
    """Display team statistics visualizations."""
    team_service = TeamService()
    data = team_service.get_team_visuals_data()
    print(data)
    
    return render_template("team_stats_visuals.html", **data)
