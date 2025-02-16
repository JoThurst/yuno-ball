"""
Cache warming utility for NBA data application.
This module provides functionality to pre-fetch and cache commonly accessed NBA data,
improving application performance by reducing direct API calls. It utilizes Flask's
application context to handle request-scoped operations.
The module implements a cache warming strategy that includes:
- Today's NBA games and matchups
- Detailed head-to-head matchup statistics
- Enhanced team data and statistics
Functions:
    warm_cache(): Main function to execute the cache warming process
Dependencies:
    - Flask
    - app.routes (get_matchup_data, get_enhanced_teams_data)
    - app.utils (get_todays_games_and_standings)
    - app.cache_utils (set_cache)
Note:
    This module is designed to be run as a standalone script or imported as a module.
    When run as a script, it automatically executes the cache warming process.
"""

from flask import Flask
from app import create_app
from app.routes import get_matchup_data, get_enhanced_teams_data
from app.utils import get_todays_games_and_standings
from app.cache_utils import set_cache

app: Flask = create_app()


def warm_cache() -> None:
    """
    Warms the cache by pre-fetching and storing commonly accessed NBA data.
    This function performs the following cache warming operations:
    1. Caches today's games and matchups
    2. For each game, caches detailed matchup data between the teams
    3. Caches enhanced team data for all teams
    The function converts dictionary keys to strings for proper cache storage and sets appropriate
    expiration times for different types of data:
    - Today's matchups: 6000 seconds
    - Matchup data: 86400 seconds (24 hours)
    - Teams data: 86400 seconds (24 hours)
    Returns:
        None
    Prints status messages during the cache warming process to indicate progress and completion.
    """
    with app.app_context():
        print("🔥 Warming Cache...")

        # Cache today's games and matchups
        games = get_todays_games_and_standings().get("games", [])
        set_cache(key="today_matchups", data=games, ex=6000)
        print(f"✅ Cached {len(games)} Matchups for Today!")
        for game in games:
            team1_id = game.get("home_team_id")
            team2_id = game.get("away_team_id")
            if team1_id and team2_id:
                matchup_data = get_matchup_data(team1_id, team2_id)

                matchup_data["team1_recent_logs"] = {
                    str(object=k): v
                    for k, v in matchup_data.get("team1_recent_logs", {}).items()
                }
                matchup_data["team2_recent_logs"] = {
                    str(object=k): v
                    for k, v in matchup_data.get("team2_recent_logs", {}).items()
                }
                matchup_data["team1_vs_team2_logs"] = {
                    str(object=k): v
                    for k, v in matchup_data.get("team1_vs_team2_logs", {}).items()
                }
                matchup_data["team2_vs_team1_logs"] = {
                    str(object=k): v
                    for k, v in matchup_data.get("team2_vs_team1_logs", {}).items()
                }

                set_cache(
                    key=f"matchup:{team1_id}:{team2_id}", data=matchup_data, ex=86400
                )
                print(f"✅ Cached Matchup: {game['home_team']} vs {game['away_team']}")

        # Cache team data
        teams_data = get_enhanced_teams_data()
        set_cache(key="teams_data", data=teams_data, ex=86400)
        print("✅ Cached Teams Data")

        print("🚀 Cache warming complete!")


if __name__ == "__main__":
    warm_cache()
