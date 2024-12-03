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


from app.models import Player, Statistics, LeagueDashPlayerStats, get_player_data

main = Blueprint("main", __name__)


@main.route("/")
def player_list():
    """Display a list of all players."""
    players = Player.get_all_players()
    # Retrieve all players from the database
    return render_template("player_list.html", players=players)


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
