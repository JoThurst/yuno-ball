import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from nba_api.stats.endpoints import PlayerGameLogs, playergamelogs
from nba_api.stats.static import players
from app.models.player import Player
from app.models.playergamelog import PlayerGameLog
from app.models.player_streaks import PlayerStreaks
from app.utils.config_utils import MAX_WORKERS
from .base_fetcher import BaseFetcher, rate_limiter

logger = logging.getLogger(__name__)

class PlayerFetcher(BaseFetcher):
    """Fetcher for player-related data from NBA API."""

    def _fetch_single_player_logs(self, player, season):
        """Helper method to fetch and store game logs for a single player."""
        try:
            player_id = player["id"]
            
            # Fetch game logs using the API
            game_logs_endpoint = self.create_endpoint(
                PlayerGameLogs,
                player_id_nullable=player_id,
                season_nullable=season
            )
            response_data = game_logs_endpoint.get_dict()

            # Process the response
            result_sets = response_data.get("resultSets", [])
            if not result_sets:
                logger.warning(f"No resultSets in response for player {player_id}")
                return

            # Extract rows and headers
            rows = result_sets[0].get("rowSet", [])
            headers = result_sets[0].get("headers", [])
            if not rows:
                logger.info(f"No game logs found for player {player_id} in season {season}")
                return

            # Convert rows into dictionaries and add season
            logs = []
            for row in rows:
                log_dict = dict(zip(headers, row))
                log_dict["SEASON"] = season  # Add season to each log
                logs.append(log_dict)

            logger.info(f"Found {len(logs)} logs for {player['full_name']} in {season}")

            # Store the logs in the database
            if logs:
                PlayerGameLog.insert_game_logs(logs)
                logger.info(f"Successfully stored {len(logs)} logs for {player['full_name']}")

        except Exception as e:
            logger.error(f"Error processing player {player.get('full_name', 'Unknown')}: {str(e)}")

    def fetch_current_season_game_logs(self):
        """Fetch and store game logs for all active players in the current season."""
        # Determine current season
        current_year = datetime.now().year
        current_month = datetime.now().month
        current_season = (
            f"{current_year}-{str(current_year + 1)[-2:]}"
            if current_month > 9
            else f"{current_year-1}-{str(current_year)[-2:]}"
        )

        logger.info(f"Fetching game logs for current season: {current_season}")

        # Ensure the game logs table exists
        PlayerGameLog.create_table()

        # Get active players
        active_players = players.get_active_players()
        logger.info(f"Found {len(active_players)} active players")

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            list(tqdm(
                executor.map(
                    lambda player: self._fetch_single_player_logs(player, current_season),
                    active_players
                ),
                total=len(active_players),
                desc="Fetching Player Logs"
            ))

        logger.info(f"Completed fetching game logs for {current_season}")

    def fetch_player_game_logs_range(self, season_from, season_to):
        """
        Fetch and store game logs for all players within a specified season range.

        Args:
            season_from (str): Start season in format "YYYY-YY" (e.g., "2018-19")
            season_to (str): End season in format "YYYY-YY" (e.g., "2023-24")
        """
        logger.info(f"Fetching game logs from {season_from} to {season_to}")

        # Ensure the game logs table exists
        PlayerGameLog.create_table()

        # Get all players from the database
        players_list = Player.get_all_players()
        logger.info(f"Found {len(players_list)} players in database")

        # Generate list of seasons
        start_year = int(season_from[:4])
        end_year = int(season_to[:4])
        seasons = [f"{year}-{str(year + 1)[-2:]}" for year in range(start_year, end_year + 1)]

        # Process each player
        for player in players_list:
            logger.info(f"Processing {player.name} (ID: {player.player_id})")
            
            # Process each season for the player
            for season in seasons:
                self._fetch_single_player_logs(
                    {"id": player.player_id, "full_name": player.name},
                    season
                )

        logger.info(f"Completed fetching game logs from {season_from} to {season_to}")

    def fetch_player_streaks(self, season='2024-25'):
        """
        Fetch and store player streaks for the last 10 games.

        Tracks streaks for:
        - Points: 10, 15, 20, 25
        - Rebounds: 4, 6, 8, 10
        - Assists: 2, 4, 6, 8, 10
        - 3-Pointers Made: 1, 2, 3, 4

        Args:
            season (str): Season string in "YYYY-YY" format (e.g., "2023-24")

        Returns:
            int: Number of streaks stored
        """
        logger.info(f"Fetching player streaks for season {season}")

        # Ensure table exists and clear old streaks
        PlayerStreaks.create_table()
        PlayerStreaks.clear_streaks()

        # Define thresholds for streaks
        streak_thresholds = {
            "PTS": [10, 15, 20, 25],
            "REB": [4, 6, 8, 10],
            "AST": [2, 4, 6, 8, 10],
            "FG3M": [1, 2, 3, 4],
        }

        active_players = players.get_active_players()
        player_ids = [p['id'] for p in active_players]

        streak_data = []

        def fetch_player_logs(player_id):
            """Helper function to fetch and process game logs for a single player."""
            try:
                # Ensure rate limiting
                rate_limiter.wait_if_needed()

                # Create endpoint using BaseFetcher's create_endpoint
                endpoint = self.create_endpoint(
                    playergamelogs.PlayerGameLogs,
                    player_id_nullable=player_id,
                    season_nullable=season,
                    last_n_games_nullable=10
                )

                logs = endpoint.get_data_frames()[0]

                if logs.empty:
                    logger.warning(f"No data returned for player {player_id}")
                    return []

                player_name = Player.get_player_name(player_id)
                player_streaks = []

                # Track streaks
                for stat, thresholds in streak_thresholds.items():
                    for threshold in thresholds:
                        streak = (logs[stat] >= threshold).sum()

                        if streak >= 7:
                            logger.info(f"Found streak for {player_name}: {stat} >= {threshold} in {streak}/10 games")
                            player_streaks.append({
                                "player_id": player_id,
                                "player_name": player_name,
                                "stat": stat,
                                "threshold": threshold,
                                "streak_games": streak,
                                "season": season
                            })

                return player_streaks

            except Exception as e:
                logger.error(f"Error fetching logs for player {player_id}: {str(e)}")
                return []

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(fetch_player_logs, player_id)
                for player_id in player_ids
            ]

            # Show progress bar
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Fetching player streaks"
            ):
                try:
                    result = future.result()
                    if result:
                        streak_data.extend(result)
                except Exception as e:
                    logger.error(f"Error processing player streak: {str(e)}")

        # Store streaks in the database
        if streak_data:
            PlayerStreaks.store_streaks(streak_data)
            logger.info(f"Stored {len(streak_data)} player streaks in the database")
            
            # Clean up any duplicate streaks
            PlayerStreaks.clean_duplicate_streaks()
            logger.info("Cleaned up duplicate streaks from database")
            
            return len(streak_data)
        else:
            logger.info("No qualifying streaks found")
            return 0 