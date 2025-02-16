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

import re
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
)

from app.cache_utils import get_cache, set_cache
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.models.player import Player
from app.models.playergamelog import PlayerGameLog
from app.models.team import Team
from app.utils import (
    get_enhanced_teams_data,
    get_player_data,
    get_team_lineup_stats,
    get_todays_games_and_standings,
)

main = Blueprint(name="main", import_name=__name__)


@main.route(rule="/")
def player_list():
    """Display a list of all players."""
    cache_key = "players"
    data = get_cache(key=cache_key)

    if not data:
        print("❌ Cache MISS on Players - Fetching fresh data.")
        # Retrieve all players from the database
        players: list[Player] = Player.get_all_players()

        # Convert Player objects to dictionaries
        data = [player.__dict__ for player in players]

        set_cache(key=cache_key, data=data, ex=3600)
    else:
        print("✅ Cache HIT on Players")

    return render_template(template_name_or_list="player_list.html", players=data)


@main.context_processor
def inject_today_matchups():
    """
    Inject today's matchups into all templates for the navbar dropdown.
    Uses Redis caching to improve performance.
    """
    cache_key = "today_matchups"
    cached_matchups = get_cache(cache_key)

    if cached_matchups:
        return dict(today_matchups=cached_matchups)

    print("❌ Cache MISS - Fetching fresh matchups")

    games = get_todays_games_and_standings().get("games", [])
    all_teams = Team.get_all_teams()
    team_name_to_id = {team["name"]: team["team_id"] for team in all_teams}

    # Attach team IDs to game objects
    for game in games:
        game["home_team_id"] = team_name_to_id.get(game["home_team"])
        game["away_team_id"] = team_name_to_id.get(game["away_team"])

    # ✅ Cache matchups for 10 minutes
    set_cache(key=cache_key, data=games, ex=600)

    return dict(today_matchups=games)


@main.route(rule="/games")
def games_dashboard():
    """
    Main dashboard to display today's games and other relevant info.
    """
    data = get_todays_games_and_standings()
    standings = data["standings"]
    games = data["games"]
    print(data)
    return render_template(
        template_name_or_list="games_dashboard.html", standings=standings, games=games
    )


@main.route("/player/<int:player_id>")
def player_detail(player_id):
    """
    Route to display player details.
    """
    player_data = get_player_data(player_id=player_id)
    print(player_data)
    return render_template(
        template_name_or_list="player_detail.html",
        player_data=player_data,
        player_id=player_id,
    )


@main.route(rule="/dashboard")
def dashboard():
    """Render the dashboard with player stats fetched directly from the database."""
    player_stats = LeagueDashPlayerStats.get_all_stats()  # Fetch all stats
    teams = Team.get_all_teams()
    return render_template(
        template_name_or_list="dashboard.html", player_stats=player_stats, teams=teams
    )


@main.route(rule="/teams")
def teams():
    """
    Retrieves and displays NBA teams data, utilizing caching for improved performance.
    This function first attempts to fetch teams data from the cache. If not found,
    it retrieves fresh data from the NBA API and caches it for future use.
    Returns:
        flask.Response: Rendered HTML template with teams data.
    Cache Details:
        - Key: "teams_data"
        - Expiration: 3600 seconds (1 hour)
        - Storage: Enhanced teams data including additional statistics and information
    Template:
        teams.html: Template file used to display the teams data
    """
    cache_key = "teams_data"
    data = get_cache(key=cache_key)

    if not data:
        print("❌ Cache MISS - Fetching fresh data.")
        data = get_enhanced_teams_data()
        set_cache(key=cache_key, data=data, ex=3600)
    else:
        print("✅ Cache HIT")

    return render_template(template_name_or_list="teams.html", teams=data)


@main.route("/team/<int:team_id>")
def team_detail(team_id):
    """Display details for a specific team."""
    team_data = Team.get_team_with_details(team_id=team_id)
    if not team_data:
        return "Team Not Found", 404
    return render_template(template_name_or_list="team_detail.html", team=team_data)


def get_matchup_data(team1_id, team2_id):
    # Fetch team details
    team1 = Team.get_team_with_details(team_id=team1_id)
    team2 = Team.get_team_with_details(team_id=team2_id)

    # ✅ Fetch Lineup Stats
    team1_lineup_stats = get_team_lineup_stats(team_id=team1_id)
    team2_lineup_stats = get_team_lineup_stats(team_id=team2_id)

    def normalize_logs(raw_logs):
        headers: list[str] = [
            "home_team_name",
            "opponent_abbreviation",
            "game_date",
            "result",
            "formatted_score",
            "home_or_away",
            "points",
            "assists",
            "rebounds",
            "steals",
            "blocks",
            "turnovers",
            "minutes_played",
            "season",
        ]
        logs = [dict(zip(headers, row)) for row in raw_logs]

        for log in logs:
            if isinstance(log["game_date"], datetime):
                log["game_date"] = log["game_date"].strftime(format="%a %m/%d")

            log["minutes_played"] = (
                f"{float(x=log['minutes_played']):.1f}"
                if log["minutes_played"]
                else "0.0"
            )

            # Format the score
            if "formatted_score" in log:
                match: re.Match[str] | None = re.search(
                    pattern=r"(\D+)\s(\d+\.?\d*)\s-\s(\d+\.?\d*)\s(\D+)",
                    string=log["formatted_score"],
                )
                if match:
                    team1_abv, score1, score2, team2_abv = match.groups()
                    log["formatted_score"] = (
                        f"{team1_abv} {int(float(x=score1))} - {int(float(x=score2))} {team2_abv}"
                    )

        return logs

    def fetch_logs(players, opponent_id=None):
        logs = {}
        for player in players:
            player_id = player["player_id"]
            if opponent_id:
                raw_logs = PlayerGameLog.get_game_logs_vs_opponent(
                    player_id=player_id, opponent_team_id=opponent_id
                )
            else:
                raw_logs = PlayerGameLog.get_last_n_games_by_player(
                    player_id=player_id, n=10
                )
            logs[player_id] = normalize_logs(raw_logs=raw_logs)
        return logs

    # Fetch logs
    team1_recent_logs = fetch_logs(players=team1["roster"])
    team2_recent_logs = fetch_logs(players=team2["roster"])
    team1_vs_team2_logs = fetch_logs(players=team1["roster"], opponent_id=team2_id)
    team2_vs_team1_logs = fetch_logs(players=team2["roster"], opponent_id=team1_id)

    return {
        "team1": team1,
        "team2": team2,
        "team1_lineup_stats": team1_lineup_stats,
        "team2_lineup_stats": team2_lineup_stats,
        "team1_recent_logs": team1_recent_logs,
        "team2_recent_logs": team2_recent_logs,
        "team1_vs_team2_logs": team1_vs_team2_logs,
        "team2_vs_team1_logs": team2_vs_team1_logs,
    }


@main.route(rule="/matchup")
def matchup():
    team1_id: int | None = request.args.get(key="team1_id", type=int)
    team2_id: int | None = request.args.get(key="team2_id", type=int)

    if not team1_id or not team2_id:
        return "Both team IDs are required", 400

    cache_key: str = f"matchup:{team1_id}:{team2_id}"
    data = get_cache(key=cache_key)

    if not data:
        data = get_matchup_data(team1_id=team1_id, team2_id=team2_id)
        print(f"Storing matchup data in cache with key: {cache_key}")

        data["team1_recent_logs"] = {
            str(k): v for k, v in data.get("team1_recent_logs", {}).items()
        }
        data["team2_recent_logs"] = {
            str(k): v for k, v in data.get("team2_recent_logs", {}).items()
        }
        data["team1_vs_team2_logs"] = {
            str(k): v for k, v in data.get("team1_vs_team2_logs", {}).items()
        }
        data["team2_vs_team1_logs"] = {
            str(k): v for k, v in data.get("team2_vs_team1_logs", {}).items()
        }

        set_cache(key=f"matchup:{team1_id}:{team2_id}", data=data, ex=86400)
        print(f"✅ Cached Matchup: {team1_id} vs {team2_id}")
    else:
        print("✅ Cache HIT")
        # print(f"Retrieved matchup data from cache: {data}")

    return render_template("matchup.html", **data)
