import logging
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from nba_api.stats.endpoints import LeagueGameFinder
from app.models.team import Team
from app.models.gameschedule import GameSchedule
from app.utils.config_utils import MAX_WORKERS
from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

NBA_SCHEDULE_CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"

class ScheduleFetcher(BaseFetcher):
    """Fetcher for NBA game schedules."""

    def _fetch_single_team_schedule(self, team_id, season):
        """Helper method to fetch and store schedule for a single team."""
        try:
            logger.info(f"Fetching schedule for team {team_id} in {season}")

            # Create endpoint using base fetcher's method (which handles rate limiting)
            game_finder = self.create_endpoint(
                LeagueGameFinder,
                season_nullable=season,
                team_id_nullable=team_id
            )
            response_data = game_finder.get_dict()

            if not response_data.get("resultSets"):
                logger.warning(f"No schedule data found for team {team_id}")
                return []

            games = response_data["resultSets"][0]
            headers = games["headers"]
            rows = games["rowSet"]
            all_games = []

            for row in rows:
                game = dict(zip(headers, row))
                opponent_abbreviation = game["MATCHUP"].split()[-1]
                opponent_team_id = Team.get_team_id_by_abbreviation(opponent_abbreviation)

                if opponent_team_id is None:
                    logger.warning(f"Could not find team_id for {opponent_abbreviation}. Skipping game.")
                    continue

                # Parse game date
                game_date = datetime.strptime(game["GAME_DATE"], "%Y-%m-%d").date()
                today = datetime.today().date()
                is_future_game = game_date > today

                # Handle game data based on whether it's a past or future game
                if not is_future_game:
                    team_score = game.get("PTS")
                    plus_minus = game.get("PLUS_MINUS")
                    if team_score is not None and plus_minus is not None:
                        opponent_score = (
                            team_score - plus_minus if game.get("WL") == "W"
                            else team_score + plus_minus
                        )
                    else:
                        opponent_score = None

                    result = game.get("WL")
                    score = f"{team_score} - {opponent_score}" if team_score and opponent_score else None
                else:
                    result = None
                    score = None

                # Append formatted game data
                all_games.append({
                    "game_id": game["GAME_ID"],
                    "season": season,
                    "team_id": game["TEAM_ID"],
                    "opponent_team_id": opponent_team_id,
                    "game_date": game["GAME_DATE"],
                    "home_or_away": "H" if "vs." in game["MATCHUP"] else "A",
                    "result": result,
                    "score": score
                })

            return all_games

        except Exception as e:
            logger.error(f"Error fetching schedule for team {team_id}: {e}")
            return []

    def fetch_and_store_schedule(self, season):
        """
        Fetch and store the season game schedule for all teams using multi-threading.
        
        Args:
            season (str): Season string in "YYYY-YY" format (e.g., "2023-24")
        """
        logger.info(f"Fetching full schedule for season {season}")

        # Ensure the schedule table exists
        GameSchedule.create_table()

        # Get all teams
        teams = Team.list_all_teams()
        team_ids = [team["team_id"] for team in teams]

        all_games = []
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Map the fetch function to all team IDs with progress bar
            futures = list(tqdm(
                executor.map(
                    lambda tid: self._fetch_single_team_schedule(tid, season),
                    team_ids
                ),
                total=len(team_ids),
                desc="Fetching Team Schedules"
            ))

            # Combine all results
            for games in futures:
                all_games.extend(games)

        # Store all games in the database
        if all_games:
            GameSchedule.insert_game_schedule(all_games)
            logger.info(f"Successfully stored {len(all_games)} games for {season}")
        else:
            logger.warning(f"No games found for {season}")

    def fetch_and_store_future_games(self, season):
        """
        Fetch and store upcoming games for the current NBA season from the NBA CDN.
        
        Args:
            season (str): Season in "YYYY-YY" format (e.g., "2024-25")
        """
        logger.info(f"Fetching future games for season {season}")

        try:
            response = requests.get(NBA_SCHEDULE_CDN_URL)
            response.raise_for_status()
            data = response.json()

            games_list = data.get("leagueSchedule", {}).get("gameDates", [])
            today = datetime.today().date()
            all_games = []

            for game_date_info in games_list:
                try:
                    game_date = datetime.strptime(
                        game_date_info["gameDate"],
                        "%m/%d/%Y %H:%M:%S"
                    ).date()
                except ValueError as e:
                    logger.error(f"Error parsing date {game_date_info['gameDate']}: {e}")
                    continue

                if game_date <= today:
                    continue

                for game in game_date_info.get("games", []):
                    game_id = game["gameId"]
                    home_team_id = game["homeTeam"]["teamId"]
                    away_team_id = game["awayTeam"]["teamId"]

                    # Add home team's game
                    all_games.append({
                        "game_id": game_id,
                        "season": season,
                        "team_id": home_team_id,
                        "opponent_team_id": away_team_id,
                        "game_date": game_date.strftime("%Y-%m-%d"),
                        "home_or_away": "H",
                        "result": None,
                        "score": None
                    })

                    # Add away team's game
                    all_games.append({
                        "game_id": game_id,
                        "season": season,
                        "team_id": away_team_id,
                        "opponent_team_id": home_team_id,
                        "game_date": game_date.strftime("%Y-%m-%d"),
                        "home_or_away": "A",
                        "result": None,
                        "score": None
                    })

            if all_games:
                GameSchedule.insert_game_schedule(all_games)
                logger.info(f"Successfully stored {len(all_games)} future games")
            else:
                logger.warning("No new future games to insert")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching NBA schedule: {e}")
            raise 