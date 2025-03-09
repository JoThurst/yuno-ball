from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.models.team import Team
from app.models.gameschedule import GameSchedule
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.utils.cache_utils import get_cache, set_cache
from app.utils.get.get_utils import get_enhanced_teams_data
team_bp = Blueprint("team", __name__, url_prefix="/team")

#Todo Fix this route
@team_bp.route("/list")
def teams():
    """Display a list of all teams."""
    # Try to get from cache first
    cache_key = "teams"
    teams = get_cache(cache_key)
    
    if not teams:
        print("❌ Cache MISS on Teams - Fetching fresh data.")
        teams = get_enhanced_teams_data()
        set_cache(cache_key, teams, ex=3600)  # Cache for 1 hour
    else:
        print("✅ Cache HIT on Teams")
    
    # If it's a POST request, redirect to GET
    if request.method == 'POST':
        return redirect(url_for('team.teams'))
    
    return render_template("teams.html", teams=teams)

@team_bp.route("/<int:team_id>")
def team_detail(team_id):
    """Display detailed information for a specific team."""
    # Get team data
    team_data = Team.get_team_with_details(team_id)
    
    if not team_data:
        return render_template("error.html", message="Team not found"), 404
    
    return render_template( "team_detail.html" , team=team_data )

#Todo Fix this route
@team_bp.route("/stats-visuals")
def team_stats_visuals():
    """Display team statistics visualizations."""
    teams = Team.get_all_teams() or []
    return render_template("team_stats_visuals.html", teams=teams)
