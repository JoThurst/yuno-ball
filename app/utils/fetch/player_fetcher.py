import logging
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from nba_api.stats.endpoints import PlayerGameLogs, playergamelogs, commonplayerinfo, playercareerstats, leaguedashplayerstats
from nba_api.stats.static import players
from app.models.player_sqlalchemy import PlayerORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.models.statistics_sqlalchemy import StatisticsORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.database import get_db_context
from app.utils.config_utils import MAX_WORKERS
from app.utils.id_utils import normalize_nba_game_id
from app.utils.season_utils import get_current_season, normalize_season
from requests.exceptions import Timeout
from .base_fetcher import BaseFetcher, rate_limiter

logger = logging.getLogger(__name__)

class PlayerFetcher(BaseFetcher):
    """Fetcher for player-related data from NBA API."""

    def _fetch_single_player_logs(self, player, season):
        """Helper method to fetch and store game logs for a single player."""
        try:
            player_id = player["id"]
            season = normalize_season(season)
            
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

            # Store the logs in the database using ORM
            if logs:
                # Convert API format to ORM format
                game_logs_orm = []
                for log in logs:
                    game_logs_orm.append({
                        'player_id': log.get("PLAYER_ID"),
                        'game_id': normalize_nba_game_id(log.get("GAME_ID")),
                        'team_id': log.get("TEAM_ID"),
                        'season': log.get("SEASON"),
                        'points': log.get("PTS"),
                        'assists': log.get("AST"),
                        'rebounds': log.get("REB"),
                        'steals': log.get("STL"),
                        'blocks': log.get("BLK"),
                        'turnovers': log.get("TOV"),
                        'minutes_played': log.get("MIN")
                    })
                
                with get_db_context() as db:
                    GameLogORM.bulk_upsert(game_logs_orm, db=db)
                    db.commit()
                logger.info(f"Successfully stored {len(logs)} logs for {player['full_name']}")

        except Exception as e:
            logger.error(f"Error processing player {player.get('full_name', 'Unknown')}: {str(e)}")

    def fetch_current_season_game_logs(self, season=None):
        """Fetch and store game logs for all active players in the current season."""
        # Determine current season
        current_season = normalize_season(season or get_current_season())

        logger.info(f"Fetching game logs for current season: {current_season}")

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

        # Get all players from the database using ORM
        with get_db_context() as db:
            players_orm = PlayerORM.get_all(db)
            logger.info(f"Found {len(players_orm)} players in database")
        
        # Convert ORM objects to format expected by _fetch_single_player_logs
        players_list = [
            {"id": player.player_id, "full_name": player.name}
            for player in players_orm
        ]

        # Generate list of seasons
        start_year = int(season_from[:4])
        end_year = int(season_to[:4])
        seasons = [f"{year}-{str(year + 1)[-2:]}" for year in range(start_year, end_year + 1)]

        # Process each player
        for player in players_list:
            logger.info(f"Processing {player['full_name']} (ID: {player['id']})")
            
            # Process each season for the player
            for season in seasons:
                self._fetch_single_player_logs(player, season)

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

        # Clear old streaks using ORM
        with get_db_context() as db:
            # Delete all existing streaks
            db.query(PlayerStreaksORM).delete()
            db.commit()

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

                # Get player name using ORM
                with get_db_context() as db:
                    player = PlayerORM.get_by_id(player_id, db)
                    player_name = player.name if player else f"Player {player_id}"
                
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

        # Store streaks in the database using ORM
        if streak_data:
            with get_db_context() as db:
                PlayerStreaksORM.bulk_create(streak_data, db=db)
                db.commit()
            logger.info(f"Stored {len(streak_data)} player streaks in the database")
            
            return len(streak_data)
        else:
            logger.info("No qualifying streaks found")
            return 0

    def _fetch_single_player(self, player, min_year=2015, max_year=2026):
        """
        Helper method to fetch and store a single player.
        
        Args:
            player: Player dict with 'id' key
            min_year (int): Minimum season year to include (default: 2015)
            max_year (int): Maximum season year to include (default: 2026)
        """
        player_id = player["id"]
        valid_seasons = [f"{year}-{(year + 1) % 100:02d}" for year in range(min_year, max_year + 1)]

        # Check if player exists using ORM
        with get_db_context() as db:
            if PlayerORM.exists(player_id, db):
                logger.debug(f"Skipping player {player_id} - Already in database.")
                return

        retries = 3
        cplayerinfo_data = None
        for attempt in range(retries):
            try:
                rate_limiter.wait_if_needed()
                endpoint = self.create_endpoint(
                    commonplayerinfo.CommonPlayerInfo,
                    player_id=player_id
                )
                cplayerinfo_data = endpoint.get_data_frames()[0].iloc[0]
                break  # API call successful, exit retry loop

            except Timeout:
                logger.warning(f"Timeout for player {player_id}, retrying ({attempt+1}/{retries})...")
                if attempt < retries - 1:
                    time.sleep(5)
            except Exception as e:
                logger.error(f"Error processing player {player_id}: {e}")
                return  # Don't retry if it's not a timeout

        # Check if we successfully fetched the data
        if cplayerinfo_data is None:
            logger.error(f"Failed to fetch player data for {player_id} after {retries} retries")
            return

        try:
            # Safe int conversion with fallbacks for missing/invalid data
            def safe_int(value, default=None):
                """Safely convert value to int, handling empty strings and whitespace."""
                if value is None:
                    return default
                if isinstance(value, str):
                    value = value.strip()
                    if not value or value == '':
                        return default
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            
            from_year = safe_int(cplayerinfo_data.get("FROM_YEAR"))
            to_year = safe_int(cplayerinfo_data.get("TO_YEAR"))
            
            # Skip players with invalid year data
            if from_year is None or to_year is None:
                logger.warning(f"Player {player_id} has invalid FROM_YEAR or TO_YEAR data. Skipping.")
                return
            
            name = cplayerinfo_data.get("DISPLAY_FIRST_LAST", "Unknown")
            position = cplayerinfo_data.get("POSITION", "Unknown")
            weight = safe_int(cplayerinfo_data.get("WEIGHT"))
            born_date = cplayerinfo_data.get("BIRTHDATE", None)
            exp = safe_int(cplayerinfo_data.get("SEASON_EXP"))
            school = cplayerinfo_data.get("SCHOOL", None)

            age = None
            if born_date:
                born_date_obj = datetime.strptime(born_date.split("T")[0], "%Y-%m-%d")
                age = datetime.now().year - born_date_obj.year

            # Check if player has any seasons in our target range
            available_seasons = [season for season in valid_seasons if from_year <= int(season[:4]) <= to_year]

            if available_seasons:
                # Convert born_date string to date object if needed
                born_date_obj = None
                if born_date:
                    try:
                        born_date_obj = datetime.strptime(born_date.split("T")[0], "%Y-%m-%d").date()
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid birth date format for player {player_id}: {born_date}")
                
                # Add player using ORM
                with get_db_context() as db:
                    PlayerORM.create(
                        player_id=int(player_id),
                        name=name,
                        position=position,
                        weight=weight,
                        born_date=born_date_obj,
                        age=age,
                        exp=exp,
                        school=school,
                        available_seasons=available_seasons,  # ORM expects list, not comma-separated string
                        db=db
                    )
                    db.commit()
                logger.debug(f"Player {name} (ID: {player_id}) added with seasons: {available_seasons}.")
            else:
                # Player has no seasons in our target range - skip storing
                logger.debug(f"Player {name} (ID: {player_id}) has seasons {from_year}-{to_year}, outside range {min_year}-{max_year}. Skipping.")

        except Exception as e:
            logger.error(f"Error processing player {player_id} after successful API call: {e}")

    def rebuild_available_seasons_for_all_players(self, min_year=2015, max_year=2026):
        """
        Rebuild available_seasons for all players from CommonPlayerInfo API.
        
        This function fetches CommonPlayerInfo for each player and rebuilds their
        available_seasons based on FROM_YEAR and TO_YEAR from the API.
        
        Use this to fix corrupted available_seasons data.
        
        Args:
            min_year (int): Minimum season year to include (default: 2015)
            max_year (int): Maximum season year to include (default: 2026)
            
        Returns:
            dict: Summary with 'updated', 'failed', 'skipped' counts
        """
        logger.info(f"Rebuilding available_seasons for all players (years {min_year}-{max_year})")
        
        # Get all players from database
        with get_db_context() as db:
            all_players = PlayerORM.get_all(db=db)
            logger.info(f"Found {len(all_players)} players in database to rebuild")
        
        valid_seasons = [f"{year}-{(year + 1) % 100:02d}" for year in range(min_year, max_year + 1)]
        
        players_updated = 0
        players_failed = 0
        players_skipped = 0
        
        import re
        season_pattern = re.compile(r'^\d{4}-\d{2}$')
        
        def safe_int(value, default=None):
            """Safely convert value to int, handling empty strings and whitespace."""
            if value is None:
                return default
            if isinstance(value, str):
                value = value.strip()
                if not value or value == '':
                    return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        for idx, player in enumerate(all_players):
            player_id = player.player_id
            player_name = player.name
            
            if (idx + 1) % 100 == 0:
                logger.info(f"Processing {idx + 1}/{len(all_players)} players...")
            
            # Check if player already has valid seasons data
            # Skip API call if player already has valid seasons to avoid unnecessary requests
            existing_seasons = player.available_seasons
            if existing_seasons and isinstance(existing_seasons, (list, tuple)):
                # Check if all seasons are valid (format: YYYY-YY)
                valid_existing_seasons = [s for s in existing_seasons if s and season_pattern.match(str(s).strip())]
                
                # If player has valid seasons, skip API call
                if valid_existing_seasons:
                    players_skipped += 1
                    if (idx + 1) % 100 == 0:
                        logger.info(f"Skipping {player_name} (ID: {player_id}): Already has valid seasons")
                    continue
            
            # Player needs to be updated - fetch from API
            retries = 3
            cplayerinfo_data = None
            
            for attempt in range(retries):
                try:
                    rate_limiter.wait_if_needed()
                    endpoint = self.create_endpoint(
                        commonplayerinfo.CommonPlayerInfo,
                        player_id=player_id
                    )
                    # Use get_data_frames() like the existing _fetch_single_player method
                    data_frames = endpoint.get_data_frames()
                    if data_frames and len(data_frames) > 0 and len(data_frames[0]) > 0:
                        cplayerinfo_data = data_frames[0].iloc[0]
                        break  # API call successful, exit retry loop
                    else:
                        logger.warning(f"No data returned for player {player_id}")
                        cplayerinfo_data = None
                        break
                    
                except Timeout:
                    logger.warning(f"Timeout for player {player_id}, retrying ({attempt+1}/{retries})...")
                    if attempt < retries - 1:
                        time.sleep(5)
                except Exception as e:
                    logger.error(f"Error fetching CommonPlayerInfo for player {player_id}: {e}")
                    if attempt == retries - 1:
                        break
                    time.sleep(2)
            
            if cplayerinfo_data is None:
                logger.warning(f"Failed to fetch CommonPlayerInfo for player {player_name} (ID: {player_id}) after {retries} retries")
                players_failed += 1
                continue
            
            try:
                from_year = safe_int(cplayerinfo_data.get("FROM_YEAR"))
                to_year = safe_int(cplayerinfo_data.get("TO_YEAR"))
                
                if from_year is None or to_year is None:
                    logger.warning(f"Player {player_name} (ID: {player_id}) has invalid FROM_YEAR or TO_YEAR. Skipping.")
                    players_skipped += 1
                    continue
                
                # Calculate available seasons based on FROM_YEAR and TO_YEAR
                available_seasons = [
                    season for season in valid_seasons 
                    if from_year <= int(season[:4]) <= to_year
                ]
                
                if not available_seasons:
                    logger.debug(f"Player {player_name} (ID: {player_id}) has no seasons in range {min_year}-{max_year}")
                    players_skipped += 1
                    continue
                
                # Update player with rebuilt seasons
                with get_db_context() as db:
                    # Use PlayerORM.create() which handles upsert
                    PlayerORM.create(
                        player_id=player_id,
                        name=player.name,  # Keep existing name
                        position=player.position,
                        weight=player.weight,
                        born_date=player.born_date,
                        age=player.age,
                        exp=player.exp,
                        school=player.school,
                        available_seasons=available_seasons,  # Rebuilt list
                        db=db
                    )
                    db.commit()
                
                players_updated += 1
                logger.debug(f"Rebuilt seasons for {player_name} (ID: {player_id}): {available_seasons}")
                
            except Exception as e:
                logger.error(f"Error rebuilding seasons for player {player_name} (ID: {player_id}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                players_failed += 1
                continue
        
        logger.info(
            f"Rebuild complete: {players_updated} updated, {players_failed} failed, "
            f"{players_skipped} skipped"
        )
        
        return {
            'updated': players_updated,
            'failed': players_failed,
            'skipped': players_skipped,
            'total': len(all_players)
        }
    
    def sync_active_players(self, current_season: str = None):
        """
        Sync active players from NBA static API and ensure current_season is in available_seasons.
        
        Uses ORM methods only - no raw SQL. For existing players, appends current_season
        to available_seasons if not present. For new players, creates them with current_season.
        
        This ensures all active players have the current season in their available_seasons,
        which is needed for filtering active players in calculations.
        
        Args:
            current_season: Season string (e.g., "2025-26"). If None, auto-detects.
            
        Returns:
            dict: Summary with 'created', 'updated', 'skipped', 'total_active' counts
        """
        from datetime import datetime
        
        # Auto-detect current season if not provided
        if current_season is None:
            now = datetime.now()
            if now.month > 9:  # October onwards
                current_season = f"{now.year}-{str(now.year + 1)[-2:]}"
            else:
                current_season = f"{now.year - 1}-{str(now.year)[-2:]}"
        
        logger.info(f"Syncing active players for season {current_season}")
        
        # Get active players from static API (no HTTP request needed)
        active_players = players.get_active_players()
        logger.info(f"Found {len(active_players)} active players from NBA API")
        
        players_updated = 0
        players_created = 0
        players_skipped = 0
        
        with get_db_context() as db:
            for player_data in active_players:
                player_id = player_data['id']
                player_name = player_data['full_name']
                
                try:
                    # Check if player exists
                    existing_player = PlayerORM.get_by_id(player_id, db=db)
                    
                    if existing_player:
                        # Player exists - check if season is already present
                        current_seasons = existing_player.available_seasons or []
                        
                        # Ensure it's a list (handles both list and array types)
                        if not isinstance(current_seasons, list):
                            current_seasons = list(current_seasons) if current_seasons else []
                        
                        # Append current season if not already present
                        if current_season not in current_seasons:
                            current_seasons.append(current_season)
                            current_seasons.sort()  # Sort chronologically
                            
                            # Use ORM to update - SQLAlchemy handles array conversion
                            PlayerORM.create(
                                player_id=player_id,
                                name=existing_player.name,
                                position=existing_player.position,
                                weight=existing_player.weight,
                                born_date=existing_player.born_date,
                                age=existing_player.age,
                                exp=existing_player.exp,
                                school=existing_player.school,
                                available_seasons=current_seasons,
                                db=db
                            )
                            db.flush()
                            players_updated += 1
                            logger.debug(f"Updated {player_name} (ID: {player_id}): Added season {current_season}")
                        else:
                            players_skipped += 1
                    else:
                        # Player doesn't exist - create with current season
                        # Note: We only have basic info from static API (id, name)
                        # For full details, we'd need CommonPlayerInfo, but user wants to just add season
                        PlayerORM.create(
                            player_id=player_id,
                            name=player_name,
                            position=None,  # Will be filled later if needed
                            weight=None,
                            born_date=None,
                            age=None,
                            exp=None,
                            school=None,
                            available_seasons=[current_season],
                            db=db
                        )
                        players_created += 1
                        logger.info(f"Created new player: {player_name} (ID: {player_id}) with season {current_season}")
                
                except Exception as e:
                    logger.error(f"Error processing player {player_name} (ID: {player_id}): {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            # Commit all changes
            try:
                db.commit()
                logger.info(f"Committed all player updates to database")
            except Exception as e:
                logger.error(f"Error committing player updates: {e}")
                db.rollback()
                raise
        
        logger.info(
            f"Active players sync complete: {players_created} created, "
            f"{players_updated} updated, {players_skipped} skipped (season already present)"
        )
        
        return {
            'created': players_created,
            'updated': players_updated,
            'skipped': players_skipped,
            'total_active': len(active_players)
        }
    
    def fetch_all_players(self, min_year=2015, max_year=2026):
        """
        Fetch NBA players and store them in the players table using parallel processing.
        
        Args:
            min_year (int): Minimum season year to include (default: 2015)
            max_year (int): Maximum season year to include (default: 2026)
        """
        all_players = players.get_players()
        logger.info(f"Fetched {len(all_players)} players from NBA API.")
        
        # Pre-filter players: Skip players likely outside our range based on player ID
        # Older players typically have lower IDs, but this is not perfect
        # We'll let the API call determine the actual years, but we can optimize
        # by checking if player already exists first
        filtered_players = []
        skipped_count = 0
        
        logger.info("Checking for existing players in database...")
        try:
            # Batch check for existing players to optimize database queries
            # Get all existing player IDs in one query using ORM
            with get_db_context() as db:
                existing_players = PlayerORM.get_all(db)
                existing_player_ids = {p.player_id for p in existing_players}
            logger.info(f"Found {len(existing_player_ids)} existing players in database.")
        except Exception as e:
            logger.error(f"Error fetching existing players: {e}")
            logger.warning("Continuing without pre-filtering (will check individually during fetch)")
            existing_player_ids = set()
        
        logger.info(f"Filtering {len(all_players)} players...")
        for idx, player in enumerate(all_players):
            if idx % 1000 == 0 and idx > 0:
                logger.info(f"Processed {idx}/{len(all_players)} players...")
            player_id = player["id"]
            # Skip if player already exists
            if player_id in existing_player_ids:
                skipped_count += 1
                continue
            filtered_players.append(player)
        
        logger.info(f"Filtered to {len(filtered_players)} new players (skipped {skipped_count} existing).")
        
        # If no new players to fetch, return early
        if not filtered_players:
            logger.info("No new players to fetch. All players already in database.")
            return

        # Use ThreadPoolExecutor for parallel processing
        # Pass min_year and max_year to each player fetch
        def fetch_with_years(player):
            try:
                return self._fetch_single_player(player, min_year=min_year, max_year=max_year)
            except Exception as e:
                logger.error(f"Error in fetch_with_years for player {player.get('id', 'Unknown')}: {e}")
                return None
        
        logger.info(f"Starting to fetch {len(filtered_players)} players with {MAX_WORKERS} workers...")
        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                results = list(tqdm(
                    executor.map(fetch_with_years, filtered_players),
                    total=len(filtered_players),
                    desc="Fetching Players"
                ))
            logger.info(f"Completed fetching {len(filtered_players)} players.")
        except Exception as e:
            logger.error(f"Error during parallel player fetching: {e}")
            raise

    def _fetch_single_player_stats(self, player):
        """Helper method to fetch and store career stats for a single player."""
        player_id = player.player_id
        retries = 3

        for attempt in range(retries):
            try:
                rate_limiter.wait_if_needed()
                endpoint = self.create_endpoint(
                    playercareerstats.PlayerCareerStats,
                    player_id=player_id
                )
                stats_df = endpoint.get_data_frames()[0]

                # Insert stats into the database using ORM
                with get_db_context() as db:
                    for _, row in stats_df.iterrows():
                        StatisticsORM.create(
                            player_id=player_id,
                            season_year=row["SEASON_ID"],
                            points=row["PTS"],
                            rebounds=row["REB"],
                            assists=row["AST"],
                            steals=row["STL"],
                            blocks=row["BLK"],
                            db=db
                        )
                    db.commit()

                logger.debug(f"Stats for player {player_id} ({player.name}) stored successfully.")
                break  # Exit retry loop if request succeeds

            except Timeout:
                logger.warning(f"Timeout for player {player_id}, retrying ({attempt+1}/{retries})...")
                if attempt < retries - 1:
                    time.sleep(5)
            except Exception as e:
                logger.error(f"Error fetching stats for player {player_id}: {e}")
                return  # Don't retry if it's not a timeout

    def fetch_all_players_stats(self):
        """Fetch and store career stats for all players in parallel using multi-threading."""
        with get_db_context() as db:
            players_orm = PlayerORM.get_all(db)
            logger.info(f"Found {len(players_orm)} players in the database.")
        
        # Convert ORM objects to format expected by _fetch_single_player_stats
        players_list = players_orm

        # Use ThreadPoolExecutor to process players in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            list(tqdm(
                executor.map(self._fetch_single_player_stats, players_list),
                total=len(players_list),
                desc="Fetching Player Stats"
            ))

        logger.info("Successfully stored all player stats.")

    def fetch_league_dash_player_stats(self, season_from, season_to):
        """Fetch and store player statistics for multiple seasons."""
        logger.info(f"Fetching league-wide player stats from {season_from} to {season_to}.")

        # Generate list of seasons
        start_year = int(season_from)
        end_year = int(season_to)
        seasons = [f"{year}-{str(year + 1)[-2:]}" for year in range(start_year, end_year + 1)]

        for season in seasons:
            logger.info(f"Fetching league dash player stats for {season}...")
            try:
                endpoint = self.create_endpoint(
                    leaguedashplayerstats.LeagueDashPlayerStats,
                    season=season
                )
                api_response = endpoint.get_normalized_dict()

                if "LeagueDashPlayerStats" not in api_response:
                    logger.error(f"Unexpected API response structure for {season}")
                    continue

                stats = api_response["LeagueDashPlayerStats"]

                if not isinstance(stats, list):
                    logger.error(f"Expected list but got {type(stats)} for {season}")
                    continue

                logger.info(f"Fetched {len(stats)} player stats for {season}.")

                for player_stat in stats:
                    if not isinstance(player_stat, dict):
                        logger.error(f"Unexpected data format in {season}: {player_stat}")
                        continue

                    # Convert all keys to lowercase
                    player_stat_lower = {k.lower(): v for k, v in player_stat.items()}

                    # Manually add 'season'
                    player_stat_lower["season"] = season

                    # Check if player exists in database and store stats using ORM
                    player_id = player_stat_lower.get('player_id')
                    if player_id:
                        with get_db_context() as db:
                            if PlayerORM.exists(player_id, db):
                                LeagueDashPlayerStatsORM.create_from_dict(player_stat_lower, db=db)
                                db.commit()

                logger.info(f"Stored league dash player stats for {season}.")

            except Exception as e:
                logger.error(f"Error fetching stats for season {season}: {e}")

        logger.info(f"Completed fetching league dash player stats from {season_from} to {season_to}.")
