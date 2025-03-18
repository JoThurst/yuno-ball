import logging
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from nba_api.stats.endpoints import commonteamroster, teamgamelog, TeamGameLog, leaguedashteamstats
from app.models.team import Team
from app.models.player import Player
from app.models.team_game_stats import TeamGameStats
from app.models.gameschedule import GameSchedule
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.utils.config_utils import MAX_WORKERS
from .base_fetcher import BaseFetcher, rate_limiter
import time

logger = logging.getLogger(__name__)

class TeamFetcher(BaseFetcher):
    """Fetcher for team-related data from NBA API."""

    def _fetch_single_team_roster(self, team_dict):
        """Helper method to fetch and store roster for a single team."""
        try:
            team_id = team_dict["team_id"]
            team_name = team_dict["name"]
            
            # Fetch roster data
            roster_endpoint = self.create_endpoint(
                commonteamroster.CommonTeamRoster,
                team_id=team_id
            )
            roster_data = roster_endpoint.get_normalized_dict()
            
            if "CommonTeamRoster" not in roster_data:
                logger.error(f"Invalid roster data for team {team_name}")
                return

            # Clear existing roster
            Team.clear_roster(team_id)

            # Process and store each player
            for player in roster_data["CommonTeamRoster"]:
                player_id = player["PLAYER_ID"]
                if not Player.player_exists(player_id):
                    logger.warning(f"Player {player['PLAYER']} not in database")
                    continue

                # Handle empty player number
                player_number = player["NUM"]
                if not player_number or player_number.strip() == "":
                    player_number = 0  # Default to 0 for players without a number
                else:
                    try:
                        player_number = int(player_number)
                    except ValueError:
                        logger.warning(f"Invalid player number for {player['PLAYER']}, defaulting to 0")
                        player_number = 0

                # Add to roster using Team model's method
                team = Team.get_team(team_id)
                Team.add_to_roster(
                    self=team,
                    player_id=player_id,
                    player_name=player["PLAYER"],
                    player_number=player_number,
                    position=player["POSITION"],
                    how_acquired=player["HOW_ACQUIRED"],
                    season=player["SEASON"]
                )

            logger.info(f"Updated roster for {team_name}")

        except Exception as e:
            logger.error(f"Error processing team {team_dict.get('name', 'Unknown')}: {str(e)}")

    def fetch_current_rosters(self):
        """Fetch and store current team rosters using parallel processing."""
        teams_list = Team.list_all_teams()
        logger.info(f"Fetching rosters for {len(teams_list)} teams")

        # Use ThreadPoolExecutor to parallelize roster fetching
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            list(tqdm(
                executor.map(self._fetch_single_team_roster, teams_list),
                total=len(teams_list),
                desc="Fetching Rosters"
            ))

        logger.info("[SUCCESS] Successfully updated all NBA team rosters.")

    def _fetch_single_game_stats(self, game_id, team_id, season):
        """Helper method to fetch and store stats for a single game."""
        try:
            logger.info(f"Fetching stats for team {team_id} in game {game_id}")

            # Get opponent team ID from game_schedule
            opponent_team_id = GameSchedule.get_opponent_team_id(game_id, team_id)
            if opponent_team_id is None:
                logger.warning(f"Opponent team ID not found for game {game_id}, team {team_id}. Skipping.")
                return

            # Fetch stats using the API
            game_log = self.create_endpoint(
                TeamGameLog,
                season=season,
                team_id=team_id
            )
            response = game_log.get_dict()

            if "resultSets" not in response or not response["resultSets"]:
                logger.warning(f"No game log data found for team {team_id} in game {game_id}")
                return

            headers = response["resultSets"][0]["headers"]
            rows = response["resultSets"][0]["rowSet"]

            # Find the specific game entry
            game_stats = None
            for row in rows:
                row_data = dict(zip(headers, row))
                if row_data["Game_ID"] == game_id:
                    game_stats = row_data
                    break

            if not game_stats:
                logger.warning(f"No matching game log found for team {team_id}, game {game_id}")
                return

            # Extract game date and derive season ID
            game_date_str = game_stats["GAME_DATE"]  # Format: 'APR 01, 2016'
            game_date = datetime.strptime(game_date_str, "%b %d, %Y")
            season_start_year = game_date.year if game_date.month >= 10 else game_date.year - 1
            season_id = f"{season_start_year}-{str(season_start_year + 1)[-2:]}"

            # Insert or update stats in the database
            TeamGameStats.add_team_game_stat({
                "game_id": game_id,
                "team_id": team_id,
                "opponent_team_id": opponent_team_id,
                "season": season_id,
                "game_date": game_date,
                "fg": game_stats.get("FGM", 0),
                "fga": game_stats.get("FGA", 0),
                "fg_pct": game_stats.get("FG_PCT", 0),
                "fg3": game_stats.get("FG3M", 0),
                "fg3a": game_stats.get("FG3A", 0),
                "fg3_pct": game_stats.get("FG3_PCT", 0),
                "ft": game_stats.get("FTM", 0),
                "fta": game_stats.get("FTA", 0),
                "ft_pct": game_stats.get("FT_PCT", 0),
                "reb": game_stats.get("REB", 0),
                "ast": game_stats.get("AST", 0),
                "stl": game_stats.get("STL", 0),
                "blk": game_stats.get("BLK", 0),
                "tov": game_stats.get("TOV", 0),
                "pts": game_stats.get("PTS", 0),
                "plus_minus": 0,  # API doesn't return Plus-Minus
            })

            logger.info(f"Successfully stored stats for team {team_id} in game {game_id}")

        except Exception as e:
            logger.error(f"Error processing game {game_id} for team {team_id}: {str(e)}")

    def _fetch_team_season_stats(self, team, season):
        """Helper method to fetch and store all game stats for a team in a season."""
        team_id = team.team_id
        logger.info(f"Fetching game logs for team {team_id} in {season}")

        try:
            # Fetch team's game log for the season
            game_log = self.create_endpoint(
                TeamGameLog,
                season=season,
                team_id=team_id
            )
            response = game_log.get_dict()

            if "resultSets" not in response or not response["resultSets"]:
                logger.warning(f"No game log data found for team {team_id} in season {season}")
                return

            headers = response["resultSets"][0]["headers"]
            rows = response["resultSets"][0]["rowSet"]

            # Process each game
            for row in rows:
                game_data = dict(zip(headers, row))
                game_id = game_data["Game_ID"]
                self._fetch_single_game_stats(game_id, team_id, season)

            logger.info(f"Successfully processed all games for team {team_id} in season {season}")

        except Exception as e:
            logger.error(f"Error processing team {team_id} for season {season}: {str(e)}")

    def fetch_team_game_stats_for_season(self, season):
        """
        Fetch and store game statistics for all teams in a given season using multi-threading.
        
        Args:
            season (str): Season string in "YYYY-YY" format (e.g., "2023-24")
        """
        logger.info(f"Fetching team game stats for season {season}")

        # Get all teams
        teams = Team.get_all_teams()
        logger.info(f"Found {len(teams)} teams to process")

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            list(tqdm(
                executor.map(
                    lambda team: self._fetch_team_season_stats(team, season),
                    teams
                ),
                total=len(teams),
                desc="Fetching Team Stats"
            ))

        logger.info(f"Completed fetching team game stats for season {season}")

    def fetch_team_game_stats(self, team_id, game_id, season):
        """
        Fetch and store game statistics for a specific team and game.
        
        Args:
            team_id (int): The team's ID
            game_id (str): The game's ID
            season (str): Season string in "YYYY-YY" format (e.g., "2023-24")
        """
        logger.info(f"Fetching game stats for team {team_id}, game {game_id}")
        self._fetch_single_game_stats(game_id, team_id, season)

    def fetch_league_dash_team_stats(self, season="2024-25"):
        """
        Fetch and store league-wide team statistics for all measure types and modes.
        Handles both Regular Season and Playoffs data separately.

        Args:
            season (str): Season string in "YYYY-YY" format (e.g., "2023-24")
        """
        logger.info(f"Fetching LeagueDashTeamStats for {season}")

        # Ensure table exists
        LeagueDashTeamStats.create_table()

        # Define all the different types of stats to fetch
        measure_types = ["Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Defense"]
        per_modes = ["Totals", "Per48", "Per100Possessions"]
        season_types = ["Regular Season", "Playoffs"]

        # Track successful and failed fetches
        successful_fetches = set()
        failed_fetches = set()

        # Separate storage for regular season and playoff stats
        regular_season_stats = {}
        playoffs_stats = {}

        def fetch_stats(measure_type, per_mode, season_type):
            """Helper function to fetch stats for a specific combination."""
            clean_measure_type = measure_type.replace(" ", "")  # Remove spaces
            fetch_key = f"{clean_measure_type}_{per_mode}_{season_type}"

            try:
                logger.info(f"Attempting to fetch: {fetch_key}")
                
                # Ensure rate limiting before making the request
                rate_limiter.wait_if_needed()
                
                # Create endpoint and get data - BaseFetcher handles retries and timeouts
                endpoint = self.create_endpoint(
                    leaguedashteamstats.LeagueDashTeamStats,
                    league_id_nullable="00",
                    season=season,
                    season_type_all_star=season_type,
                    measure_type_detailed_defense=measure_type,
                    per_mode_detailed=per_mode,
                    rank="Y"
                )
                
                response = endpoint.get_dict()

                # Validate response
                if "resultSets" not in response:
                    logger.error(f"API response missing 'resultSets' for {fetch_key}")
                    failed_fetches.add(fetch_key)
                    return

                data_set = response["resultSets"][0]
                headers = data_set["headers"]
                rows = data_set["rowSet"]

                if not rows:
                    logger.warning(f"No data found for {fetch_key}")
                    return

                # Process each team's stats
                for row in rows:
                    team_id = row[headers.index("TEAM_ID")]
                    team_name = row[headers.index("TEAM_NAME")]

                    # Choose correct storage based on season type
                    storage = regular_season_stats if season_type == "Regular Season" else playoffs_stats

                    # Initialize team entry if not present
                    if team_id not in storage:
                        storage[team_id] = {
                            "team_id": team_id,
                            "team_name": team_name,
                            "season": season,
                            "season_type": season_type
                        }

                    # Add prefixed stats
                    for i, stat in enumerate(headers):
                        if stat not in ["TEAM_ID", "TEAM_NAME"]:
                            col_name = f"{clean_measure_type}_{per_mode}_{stat}".lower()
                            storage[team_id][col_name] = row[i]

                successful_fetches.add(fetch_key)
                logger.info(f"Successfully fetched {len(rows)} records for {fetch_key}")

            except Exception as e:
                failed_fetches.add(fetch_key)
                logger.error(f"Error fetching {fetch_key}: {str(e)}")

        # Create all combinations of parameters
        combinations = [
            (measure_type, per_mode, season_type)
            for measure_type in measure_types
            for per_mode in per_modes
            for season_type in season_types
        ]

        # Use ThreadPoolExecutor with original MAX_WORKERS setting
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(fetch_stats, measure_type, per_mode, season_type)
                for measure_type, per_mode, season_type in combinations
            ]
            
            # Show progress bar
            list(tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Fetching League Stats"
            ))

        # Log summary of fetches
        total_combinations = len(measure_types) * len(per_modes) * len(season_types)
        logger.info(f"\nFetch Summary:")
        logger.info(f"Total combinations attempted: {total_combinations}")
        logger.info(f"Successful fetches: {len(successful_fetches)}")
        logger.info(f"Failed fetches: {len(failed_fetches)}")
        
        if failed_fetches:
            logger.warning("Failed fetches:")
            for failed in failed_fetches:
                logger.warning(f"  - {failed}")

        # Insert Regular Season Data
        regular_season_stored = 0
        for team_id, team_data in regular_season_stats.items():
            try:
                LeagueDashTeamStats.add_team_season_stat(team_data)
                regular_season_stored += 1
            except Exception as e:
                logger.error(f"Error storing Regular Season data for Team ID {team_id}: {str(e)}")

        # Insert Playoff Data
        playoff_stored = 0
        for team_id, team_data in playoffs_stats.items():
            try:
                LeagueDashTeamStats.add_team_season_stat(team_data)
                playoff_stored += 1
            except Exception as e:
                logger.error(f"Error storing Playoff data for Team ID {team_id}: {str(e)}")

        # Log storage summary
        logger.info(f"\nStorage Summary:")
        logger.info(f"Regular Season teams stored: {regular_season_stored}")
        logger.info(f"Playoff teams stored: {playoff_stored}")
        logger.info(f"Completed fetching and storing league stats for {season}")

        return {
            'successful_fetches': list(successful_fetches),
            'failed_fetches': list(failed_fetches),
            'regular_season_teams_stored': regular_season_stored,
            'playoff_teams_stored': playoff_stored
        } 