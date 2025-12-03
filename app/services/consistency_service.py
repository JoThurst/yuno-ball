"""Service for calculating player consistency/volatility metrics.

This service computes Coefficient of Variation (CV) for each player's stats
to identify "steady" vs "boom/bust" players.

CV = stddev / mean
- Lower CV = more consistent/predictable
- Higher CV = more volatile/unpredictable

Created: December 2, 2025
Part of: Phase 1.6 - Consistency/Volatility Metrics
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime
from sqlalchemy.orm import Session
import statistics

from app.database import get_db_context
from app.models.player_sqlalchemy import PlayerORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.player_consistency_sqlalchemy import PlayerConsistencyORM
from app.utils.config_utils import logger


class ConsistencyService:
    """Service for calculating player consistency/volatility metrics."""
    
    # Stats to calculate consistency for
    # Maps display name -> GameLogORM attribute name
    STATS_TO_ANALYZE = {
        'pts': 'points',
        'reb': 'rebounds',
        'ast': 'assists',
        'pra': 'pra',  # Combined - calculated specially
        'stl': 'steals',
        'blk': 'blocks',
        'tov': 'turnovers',
    }
    
    # Minimum games required for meaningful CV calculation
    MIN_GAMES_REQUIRED = 5
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service."""
        self.db = db
    
    def calculate_stats_from_gamelogs(
        self,
        gamelogs: List[GameLogORM],
        stat_name: str
    ) -> Optional[Dict[str, float]]:
        """Calculate consistency metrics for a stat from game logs.
        
        Args:
            gamelogs: List of game log records
            stat_name: Display name of the stat (e.g., 'pts')
            
        Returns:
            Dictionary with mean, stddev, cv, min, max, median or None if insufficient data
        """
        # Get the actual attribute name from the mapping
        attr_name = self.STATS_TO_ANALYZE.get(stat_name, stat_name)
        
        # Extract stat values
        values = []
        for log in gamelogs:
            if stat_name == 'pra':
                # Combined Points + Rebounds + Assists
                pts = log.points or 0
                reb = log.rebounds or 0
                ast = log.assists or 0
                values.append(pts + reb + ast)
            else:
                # Individual stat - use the mapped attribute name
                val = getattr(log, attr_name, None)
                if val is not None:
                    values.append(float(val))
        
        # Need minimum games
        if len(values) < self.MIN_GAMES_REQUIRED:
            return None
        
        # Calculate statistics
        mean = statistics.mean(values)
        
        # Handle edge case where all values are the same (stddev = 0)
        if len(set(values)) == 1:
            stddev = 0.0
            cv = 0.0
        else:
            stddev = statistics.stdev(values)
            # Avoid division by zero
            cv = stddev / mean if mean > 0 else 0.0
        
        return {
            'games_played': len(values),
            'mean': round(mean, 2),
            'stddev': round(stddev, 2),
            'cv': round(cv, 4),
            'min_val': round(min(values), 2),
            'max_val': round(max(values), 2),
            'median': round(statistics.median(values), 2)
        }
    
    def calculate_player_consistency(
        self,
        player_id: int,
        player_name: str,
        season: str,
        window_size: int,
        gamelogs: List[GameLogORM]
    ) -> List[Dict]:
        """Calculate consistency metrics for all stats for a player.
        
        Args:
            player_id: Player ID
            player_name: Player name
            season: Season string
            window_size: Number of games (0 = all games)
            gamelogs: Game logs to analyze
            
        Returns:
            List of consistency metric dictionaries
        """
        # Apply window size
        if window_size > 0 and len(gamelogs) > window_size:
            gamelogs = gamelogs[:window_size]
        
        results = []
        
        for stat_name in self.STATS_TO_ANALYZE.keys():
            metrics = self.calculate_stats_from_gamelogs(gamelogs, stat_name)
            
            if metrics:
                tier = PlayerConsistencyORM.classify_tier(metrics['cv'])
                
                results.append({
                    'player_id': player_id,
                    'player_name': player_name,
                    'season': season,
                    'stat_name': stat_name,
                    'window_size': window_size,
                    'games_played': metrics['games_played'],
                    'mean': metrics['mean'],
                    'stddev': metrics['stddev'],
                    'cv': metrics['cv'],
                    'min_val': metrics['min_val'],
                    'max_val': metrics['max_val'],
                    'median': metrics['median'],
                    'consistency_tier': tier
                })
        
        return results
    
    def calculate_all_players(
        self,
        season: str,
        window_sizes: List[int] = [0, 10],
        db: Optional[Session] = None
    ) -> int:
        """Calculate consistency metrics for all players in a season.
        
        Args:
            season: Season string (e.g., "2024-25")
            window_sizes: List of window sizes (0 = full season, 10 = last 10 games)
            db: Optional database session
            
        Returns:
            int: Total number of records created
        """
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._calculate_all_players_internal(season, window_sizes, session)
        else:
            return self._calculate_all_players_internal(season, window_sizes, session)
    
    def _calculate_all_players_internal(
        self,
        season: str,
        window_sizes: List[int],
        db: Session
    ) -> int:
        """Internal method to calculate for all players."""
        logger.info(f"Starting consistency calculation for season {season}")
        
        # Clear existing records
        logger.info(f"Clearing existing consistency records for season {season}...")
        deleted_count = PlayerConsistencyORM.clear_by_season(season, db=db)
        logger.info(f"Cleared {deleted_count} existing records")
        
        # Get active players for the season
        players = PlayerORM.get_active_for_season(season, db=db)
        logger.info(f"Found {len(players)} active players for season {season}")
        
        all_records = []
        players_processed = 0
        players_skipped = 0
        
        for player in players:
            try:
                # Get game logs for the player
                gamelogs = GameLogORM.get_by_player_and_season(
                    player.player_id, season, db=db
                )
                
                if len(gamelogs) < self.MIN_GAMES_REQUIRED:
                    players_skipped += 1
                    continue
                
                # Calculate for each window size
                for window_size in window_sizes:
                    records = self.calculate_player_consistency(
                        player_id=player.player_id,
                        player_name=player.name,
                        season=season,
                        window_size=window_size,
                        gamelogs=gamelogs
                    )
                    all_records.extend(records)
                
                players_processed += 1
                
                if players_processed % 50 == 0:
                    logger.info(f"Processed {players_processed} players...")
                
            except Exception as e:
                logger.error(f"Error calculating consistency for player {player.player_id}: {e}")
                players_skipped += 1
                continue
        
        # Bulk insert all records
        if all_records:
            try:
                count = PlayerConsistencyORM.bulk_create(all_records, db=db)
                db.commit()
                logger.info(f"Persisted {count} consistency records")
            except Exception as e:
                logger.error(f"Error persisting consistency records: {e}")
                db.rollback()
                raise
        
        logger.info(
            f"Consistency calculation complete: {players_processed} players processed, "
            f"{players_skipped} skipped, {len(all_records)} records created"
        )
        
        return len(all_records)
    
    def get_player_profile(
        self,
        player_id: int,
        season: str,
        window_size: int = 0,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get a complete consistency profile for a player.
        
        Args:
            player_id: Player ID
            season: Season string
            window_size: Window size (0 = full season)
            db: Optional database session
            
        Returns:
            Dictionary with player's consistency profile
        """
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._get_player_profile_internal(player_id, season, window_size, session)
        else:
            return self._get_player_profile_internal(player_id, season, window_size, session)
    
    def _get_player_profile_internal(
        self,
        player_id: int,
        season: str,
        window_size: int,
        db: Session
    ) -> Dict[str, Any]:
        """Internal method for player profile."""
        records = PlayerConsistencyORM.get_by_player(
            player_id=player_id,
            season=season,
            window_size=window_size,
            db=db
        )
        
        if not records:
            return {}
        
        # Build profile
        profile = {
            'player_id': player_id,
            'player_name': records[0].player_name if records else None,
            'season': season,
            'window_size': window_size,
            'stats': {}
        }
        
        steady_count = 0
        volatile_count = 0
        
        for record in records:
            profile['stats'][record.stat_name] = {
                'mean': record.mean,
                'stddev': record.stddev,
                'cv': record.cv,
                'tier': record.consistency_tier,
                'games': record.games_played
            }
            
            if record.consistency_tier == 'steady':
                steady_count += 1
            elif record.consistency_tier == 'volatile':
                volatile_count += 1
        
        # Overall classification
        if steady_count > volatile_count + 2:
            profile['overall_classification'] = 'steady'
        elif volatile_count > steady_count + 2:
            profile['overall_classification'] = 'volatile'
        else:
            profile['overall_classification'] = 'mixed'
        
        profile['steady_stats'] = steady_count
        profile['volatile_stats'] = volatile_count
        
        return profile

