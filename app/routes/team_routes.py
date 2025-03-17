from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.models.team import Team
from app.models.gameschedule import GameSchedule
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.utils.cache_utils import get_cache, set_cache
from app.utils.get.get_utils import get_enhanced_teams_data
from app.services.team_service import get_complete_team_details, get_team_visuals_data
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
    # Get comprehensive team data using the service
    team_data = get_complete_team_details(team_id)
    
    if not team_data:
        return render_template("error.html", message="Team not found"), 404
    
    # # Ensure stats is always present even if empty
    # if "stats" not in team_data:
    #     team_data["stats"] = {
    #         "pts": None, "reb": None, "ast": None, "stl": None, "blk": None, 
    #         "tov": None, "fg_pct": None, "fg3_pct": None, "ft_pct": None,
    #         "off_rtg": None, "def_rtg": None, "net_rtg": None, "pace": None, "ts_pct": None
    #     }
    
    # # Calculate win percentage if not present but wins and losses are available
    # if "w_pct" not in team_data and "w" in team_data and "l" in team_data:
    #     total_games = team_data["w"] + team_data["l"]
    #     if total_games > 0:
    #         team_data["w_pct"] = team_data["w"] / total_games
    #     else:
    #         team_data["w_pct"] = None
    
    return render_template("team_detail.html", team=team_data)

#Todo Fix this route
@team_bp.route("/stats-visuals")
def team_stats_visuals():
    """Display team statistics visualizations."""
    data = get_team_visuals_data()
    print(data)
    
    return render_template("team_stats_visuals.html", **data)
