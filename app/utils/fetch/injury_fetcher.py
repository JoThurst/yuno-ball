"""
Fetcher for player injury/status data from NBA Live BoxScore endpoint.

Uses the same robust patterns as SmartGameLogFetcher:
- Extends BaseFetcher for retry/rate limiting
- Batch processing with adaptive throttling
- Consecutive failure tracking
- ThreadPoolExecutor for parallel fetching

Created: December 2, 2025
Part of: Phase 1.6 - Injury Tracking
"""

import logging
import time
import random
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Set

from requests.exceptions import Timeout, RequestException
from tqdm import tqdm

from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_status_sqlalchemy import PlayerGameStatusORM
from app.database import get_db_context
from app.utils.config_utils import MAX_WORKERS

from .base_fetcher import BaseFetcher, rate_limiter

# NBA API imports
try:
    from nba_api.live.nba.endpoints import boxscore
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False

logger = logging.getLogger(__name__)


class InjuryFetcher(BaseFetcher):
    """
    Fetches player injury/status data from NBA Live BoxScore endpoint.
    
    Uses batch processing with adaptive throttling to avoid rate limits.
    Designed to handle ~1,230 games per season efficiently.
    """
    
    # Batch processing settings
    DEFAULT_BATCH_SIZE = 25  # Games per batch (smaller than gamelogs since each has more data)
    INTER_BATCH_DELAY = 3.0  # Seconds between batches
    LONG_PAUSE_DELAY = 300  # 5 minutes if too many failures
    MAX_CONSECUTIVE_FAILURES = 3
    
    def __init__(self):
        """Initialize the fetcher."""
        super().__init__()
        if not NBA_API_AVAILABLE:
            logger.warning("nba_api.live not available - injury fetching disabled")
    
    def _fetch_single_game_status(self, game_id: str) -> Optional[List[Dict]]:
        """
        Fetch player status data for a single game from Live BoxScore.
        
        Args:
            game_id: NBA game ID (10-digit string)
            
        Returns:
            List of player status dictionaries, empty list if no data, or None on failure
        """
        if not NBA_API_AVAILABLE:
            return None
        
        try:
            rate_limiter.wait_if_needed()
            
            boxscore_data = boxscore.BoxScore(game_id=game_id)
            game_data = boxscore_data.game.get_dict()
            
            if not game_data:
                logger.debug(f"No game data returned for {game_id}")
                return []
            
            status_records = []
            
            # Process both teams
            for team_type in ['homeTeam', 'awayTeam']:
                team = game_data.get(team_type, {})
                team_id = team.get('teamId')
                
                if not team_id:
                    continue
                
                players = team.get('players', [])
                
                for player in players:
                    status = player.get('status')
                    not_playing_reason = player.get('notPlayingReason')
                    played = player.get('played') == '1'
                    
                    # Capture players who are inactive OR didn't play
                    if status != 'ACTIVE' or not played or not_playing_reason:
                        status_records.append({
                            'game_id': game_id,
                            'player_id': player.get('personId'),
                            'team_id': team_id,
                            'status': status,
                            'not_playing_reason': not_playing_reason,
                            'not_playing_description': player.get('notPlayingDescription'),
                            'played': played,
                            'player_name': player.get('name')
                        })
            
            logger.debug(f"Fetched {len(status_records)} status records for game {game_id}")
            return status_records
            
        except (Timeout, RequestException) as exc:
            # 403 errors are expected for upcoming games
            if '403' in str(exc):
                logger.debug(f"Game {game_id} not available yet (403)")
                return []
            logger.warning(f"Timeout/RequestError fetching boxscore for {game_id}: {exc}")
            return None
        except Exception as exc:
            # 403 in response is also expected
            if '403' in str(exc):
                logger.debug(f"Game {game_id} not available yet (403)")
                return []
            logger.error(f"Unexpected error fetching boxscore for {game_id}: {exc}")
            return None
    
    def _get_games_to_process(
        self,
        season: str,
        start_date: Optional[date],
        end_date: Optional[date],
        db
    ) -> List[Dict]:
        """
        Get list of games that need status data fetched.
        
        Filters to:
        - Completed games (have a result)
        - Games not already in player_game_status table
        """
        # Get games that already have status data
        existing_games = set(PlayerGameStatusORM.get_games_with_status_data(season, db=db))
        logger.info(f"Found {len(existing_games)} games with existing status data")
        
        # Build query for completed games in date range
        query = db.query(GameScheduleORM).filter(
            GameScheduleORM.season == season,
            GameScheduleORM.result.isnot(None)  # Only completed games
        )
        
        if start_date:
            query = query.filter(
                GameScheduleORM.game_date >= datetime.combine(start_date, datetime.min.time())
            )
        if end_date:
            query = query.filter(
                GameScheduleORM.game_date <= datetime.combine(end_date, datetime.max.time())
            )
        
        all_games = query.all()
        
        # Get unique game IDs (each game has 2 entries - home and away)
        game_ids_seen: Set[str] = set()
        games_to_process = []
        
        for game in all_games:
            if game.game_id not in game_ids_seen and game.game_id not in existing_games:
                game_ids_seen.add(game.game_id)
                game_date = game.game_date.date() if isinstance(game.game_date, datetime) else game.game_date
                games_to_process.append({
                    'game_id': game.game_id,
                    'game_date': game_date,
                    'season': season
                })
        
        return games_to_process
    
    def fetch_injury_data(
        self,
        season: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        lookback_days: int = 14,
        batch_size: int = DEFAULT_BATCH_SIZE
    ) -> Tuple[int, int]:
        """
        Fetch injury/status data for completed games in a date range.
        
        Uses batch processing with adaptive throttling similar to SmartGameLogFetcher.
        
        Args:
            season: Season string (e.g., "2024-25")
            start_date: Start date (default: lookback_days before end_date)
            end_date: End date (default: yesterday)
            lookback_days: Days to look back when start_date is omitted (daily default: 14).
                For full-season backfill, pass an explicit start_date (e.g. season open).
            batch_size: Number of games per batch
            
        Returns:
            Tuple of (games_processed, records_stored)
        """
        if not NBA_API_AVAILABLE:
            logger.error("nba_api.live not available - cannot fetch injury data")
            return 0, 0
        
        # Default date range: last N days (daily path uses 14; widen via start_date for backfill)
        if end_date is None:
            end_date = date.today() - timedelta(days=1)
        if start_date is None:
            start_date = end_date - timedelta(days=lookback_days)
        
        logger.info(f"Fetching injury data for {start_date} to {end_date}, season {season}")
        
        # Get games to process
        with get_db_context() as db:
            games_to_process = self._get_games_to_process(season, start_date, end_date, db)
        
        if not games_to_process:
            logger.info("No new games to process for injury data")
            return 0, 0
        
        # Shuffle for better load distribution
        random.shuffle(games_to_process)
        total_games = len(games_to_process)
        logger.info(f"Found {total_games} games to process for injury data")
        
        # Batch processing with adaptive throttling
        successful_fetches = 0
        failed_fetches: List[str] = []
        total_records = 0
        consecutive_failures = 0
        
        for idx in tqdm(range(0, total_games, batch_size), desc="Processing Injury Data Batches"):
            batch = games_to_process[idx:idx + batch_size]
            
            # Adaptive throttling
            if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                logger.warning(f"Hit {self.MAX_CONSECUTIVE_FAILURES}+ consecutive failing batches. Sleeping 5 minutes...")
                time.sleep(self.LONG_PAUSE_DELAY)
                consecutive_failures = 0
            elif consecutive_failures > 0:
                adaptive_delay = self.INTER_BATCH_DELAY + (consecutive_failures * 2)
                logger.info(f"Adaptive delay: {adaptive_delay}s (consecutive failures: {consecutive_failures})")
                time.sleep(adaptive_delay)
            else:
                time.sleep(self.INTER_BATCH_DELAY)
            
            batch_results: List[Dict] = []
            batch_failures = 0
            
            # Use ThreadPoolExecutor with controlled workers
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, 3)) as executor:
                futures = {
                    executor.submit(self._fetch_single_game_status, game_info['game_id']): game_info
                    for game_info in batch
                }
                
                for future in as_completed(futures):
                    game_info = futures[future]
                    game_id = game_info['game_id']
                    
                    try:
                        status_records = future.result(timeout=60)
                        
                        if status_records is not None:
                            # Add game_date and season to each record
                            for record in status_records:
                                record['game_date'] = game_info['game_date']
                                record['season'] = game_info['season']
                            
                            batch_results.extend(status_records)
                            successful_fetches += 1
                        else:
                            failed_fetches.append(game_id)
                            batch_failures += 1
                            
                    except TimeoutError:
                        logger.warning(f"Future timed out for game {game_id}")
                        failed_fetches.append(game_id)
                        batch_failures += 1
                    except Exception as exc:
                        logger.error(f"Error processing game {game_id}: {exc}")
                        failed_fetches.append(game_id)
                        batch_failures += 1
            
            # Store batch results
            if batch_results:
                try:
                    with get_db_context() as db:
                        count = PlayerGameStatusORM.bulk_create(batch_results, db=db)
                        db.commit()
                    total_records += count
                    logger.info(f"Stored {count} status records from batch")
                    consecutive_failures = 0
                except Exception as e:
                    logger.error(f"Error storing injury data batch: {e}")
                    consecutive_failures += 1
            else:
                if batch_failures == len(batch):
                    consecutive_failures += 1
                    logger.warning(f"All games in batch failed. Consecutive failures: {consecutive_failures}")
            
            logger.info(
                f"Batch progress: {min(idx + batch_size, total_games)}/{total_games} | "
                f"Successful: {successful_fetches} | Failed: {len(failed_fetches)} | "
                f"Records: {total_records}"
            )
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("Injury Data Fetching Summary")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Total games attempted: {total_games}")
        logger.info(f"Successful game fetches: {successful_fetches}")
        logger.info(f"Failed game fetches: {len(failed_fetches)}")
        logger.info(f"Total status records stored: {total_records}")
        if failed_fetches:
            logger.warning(f"Failed games (first 20): {failed_fetches[:20]}")
        logger.info("=" * 70 + "\n")
        
        return successful_fetches, total_records
    
    def fetch_for_date(
        self,
        target_date: date,
        season: str
    ) -> Tuple[int, int]:
        """
        Fetch injury data for all completed games on a specific date.
        
        Args:
            target_date: Date to fetch
            season: Season string
            
        Returns:
            Tuple of (games_processed, records_stored)
        """
        return self.fetch_injury_data(
            season=season,
            start_date=target_date,
            end_date=target_date,
            batch_size=10  # Smaller batch for single day
        )
    
    def backfill_season(
        self,
        season: str,
        batch_size: int = 50
    ) -> Tuple[int, int]:
        """
        Backfill injury data for an entire season.
        
        Uses larger batches and longer delays for bulk historical data.
        
        Args:
            season: Season string
            batch_size: Number of games per batch (larger for backfill)
            
        Returns:
            Tuple of (games_processed, records_stored)
        """
        logger.info(f"Starting full season backfill for {season}")
        
        # Get season start/end from schedule
        with get_db_context() as db:
            first_game = db.query(GameScheduleORM).filter(
                GameScheduleORM.season == season
            ).order_by(GameScheduleORM.game_date.asc()).first()
            
            last_game = db.query(GameScheduleORM).filter(
                GameScheduleORM.season == season,
                GameScheduleORM.result.isnot(None)
            ).order_by(GameScheduleORM.game_date.desc()).first()
        
        if not first_game or not last_game:
            logger.warning(f"No games found for season {season}")
            return 0, 0
        
        start_date = first_game.game_date.date() if isinstance(first_game.game_date, datetime) else first_game.game_date
        end_date = last_game.game_date.date() if isinstance(last_game.game_date, datetime) else last_game.game_date
        
        return self.fetch_injury_data(
            season=season,
            start_date=start_date,
            end_date=end_date,
            batch_size=batch_size
        )

