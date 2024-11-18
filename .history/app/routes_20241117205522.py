
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    jsonify,
    request,
)

from app.models import Player, Statistics, LeagueDashPlayerStats

main = Blueprint('main', __name__)


@main.route('/')
def player_list():
    """Display a list of all players."""
    players = Player.get_all_players()  # Retrieve all players from the
    # database
    return render_template('player_list.html', players=players)


@main.route('/player/<int:player_id>')
def player_detail(player_id):
    """Display details for a specific player, including their statistics."""
    player = Player.get_player(player_id)
    if not player:
        return redirect(url_for('main.player_list'))

    stats = Statistics.get_stats_by_player(player_id)  # Retrieve player stats
    return render_template('player_detail.html', player=player, stats=stats)

@main.route('/dashboard')
def dashboard():
    """Render the dashboard with player stats."""
    return render_template('dashboard.html')

@main.route('/api/dashboard')
def dashboard_data():
    """Serve player statistics data for the dashboard."""
    # Optional: Add query parameters for filtering if needed
    filters = request.args.to_dict()

    # Fetch data from the database
    data = LeagueDashPlayerStats.get_all_stats(filters)
    return jsonify(data)