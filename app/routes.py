"""
This module defines the main blueprint for the web application, which includes
routes for listing players, viewing player details, displaying a dashboard,
and serving player statistics data via an API endpoint.

Blueprint Name:
- main: The main blueprint for rendering player and dashboard views.

Endpoints:
- `/`: Displays a list of all players.
- `/player/<int:player_id>`: Displays detailed statistics for a specific
player.
- `/dashboard`: Renders the dashboard page for player statistics.
- `/api/dashboard`: Serves JSON data of player statistics for use in the
dashboard.
"""

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    jsonify,
    request
)


from app.models import Player, Statistics, LeagueDashPlayerStats, Team, get_player_data
from app.utils import get_todays_games_and_standings, get_enhanced_teams_data

main = Blueprint("main", __name__)


@main.route("/")
def player_list():
    """Display a list of all players."""
    players = Player.get_all_players()
    # Retrieve all players from the database
    return render_template("player_list.html", players=players)

@main.route('/games')
def games_dashboard():
    """
    Main dashboard to display today's games and other relevant info.
    """
    data = get_todays_games_and_standings()
    standings = data['standings']
    games = data['games']
    print(data)
    return render_template('games_dashboard.html', standings=standings, games = games)



@main.route('/player/<int:player_id>')
def player_detail(player_id):
    """
    Route to display player details.
    """
    player_data = get_player_data(player_id)
    print(player_data)
    return render_template('player_detail.html', player_data=player_data, player_id=player_id)


@main.route("/dashboard")
def dashboard():
    """Render the dashboard with player stats."""
    return render_template("dashboard.html")


@main.route("/api/dashboard")
def dashboard_data():
    """Serve player statistics data for the dashboard."""
    # Optional: Add query parameters for filtering if needed
    filters = request.args.to_dict()

    # Fetch data from the database
    data = LeagueDashPlayerStats.get_all_stats(filters)
    return jsonify(data)

@main.route("/teams")
def teams():
    """Display all teams with records, conference, and today's game status."""
    teams_data = get_enhanced_teams_data()
    return render_template("teams.html", teams=teams_data)

@main.route("/team/<int:team_id>")
def team_detail(team_id):
    """Display details for a specific team."""
    team_data = Team.get_team_with_details(team_id)
    if not team_data:
        return "Team Not Found", 404
    return render_template("team_detail.html", team=team_data)