from app import create_app
import os
from app.routes import get_matchup_data, get_enhanced_teams_data
from app.utils.get.get_utils import fetch_todays_games
from app.utils.cache_utils import set_cache

app = create_app()

def warm_cache():
    with app.app_context():
        print("🔥 Warming Cache...")

        # Cache today's games and matchups
        games = fetch_todays_games().get("games", [])
        set_cache("today_matchups", games, ex=6000)
        print(f"✅ Cached {len(games)} Matchups for Today!")
        for game in games:
            team1_id = game.get("home_team_id")
            team2_id = game.get("away_team_id")
            if team1_id and team2_id:
                matchup_data = get_matchup_data(team1_id, team2_id)

                matchup_data["team1_recent_logs"] = {
                    str(k): v for k, v in matchup_data.get("team1_recent_logs", {}).items()
                }
                matchup_data["team2_recent_logs"] = {
                    str(k): v for k, v in matchup_data.get("team2_recent_logs", {}).items()
                }
                matchup_data["team1_vs_team2_logs"] = {
                    str(k): v for k, v in matchup_data.get("team1_vs_team2_logs", {}).items()
                }
                matchup_data["team2_vs_team1_logs"] = {
                    str(k): v for k, v in matchup_data.get("team2_vs_team1_logs", {}).items()
                }

                set_cache(f"matchup:{team1_id}:{team2_id}", matchup_data, ex=86400)
                print(f"✅ Cached Matchup: {game['home_team']} vs {game['away_team']}")

        # Cache team data
        teams_data = get_enhanced_teams_data()
        set_cache("teams_data", teams_data, ex=86400)
        print("✅ Cached Teams Data")

        print("🚀 Cache warming complete!")

if __name__ == "__main__":
    warm_cache()
