"""Service for calculating player heat index (hot & cold detection).

This service identifies players who are significantly above or below their
season baseline by comparing recent form (last N games) to their season averages.

Created: December 2024
Part of: Enhanced Analytics Engine (Phase 1.2)
"""

from typing import List, Dict, Optional, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
import statistics

from app.database import get_db_context
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.player_sqlalchemy import PlayerORM
from app.models.player_heat_index_sqlalchemy import PlayerHeatIndexORM
from app.utils.config_utils import logger


class HeatIndexService:
    """Service for calculating player heat index metrics."""
    
    # Stats to calculate heat for
    STATS = ['PTS', 'REB', 'AST', 'PRA']  # PRA = Points + Rebounds + Assists
    
    # Window sizes for recent form
    WINDOW_SIZES = [3, 5, 10]
    
    # Heat thresholds (standard deviations from season average)
    ON_FIRE_THRESHOLD = 1.0  # ≥ +1σ
    ICE_COLD_THRESHOLD = -1.0  # ≤ -1σ
    
    def get_stat_value(self, game_log: GameLogORM, stat: str) -> Optional[float]:
        """Extract stat value from game log.
        
        Args:
            game_log: Game log object
            stat: Statistic name (PTS, REB, AST, PRA)
            
        Returns:
            Stat value or None if not available
        """
        if stat == 'PTS':
            return float(game_log.points) if game_log.points is not None else None
        elif stat == 'REB':
            return float(game_log.rebounds) if game_log.rebounds is not None else None
        elif stat == 'AST':
            return float(game_log.assists) if game_log.assists is not None else None
        elif stat == 'PRA':
            pts = game_log.points if game_log.points is not None else 0
            reb = game_log.rebounds if game_log.rebounds is not None else 0
            ast = game_log.assists if game_log.assists is not None else 0
            return float(pts + reb + ast)
        return None
    
    def calculate_season_stats(
        self, 
        player_id: int, 
        season: str, 
        stat: str,
        db: Session
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate season average and standard deviation for a player.
        
        Args:
            player_id: Player identifier
            season: Season string (e.g., "2024-25")
            stat: Statistic name
            db: Database session
            
        Returns:
            Tuple of (season_avg, season_std) or (None, None) if insufficient data
        """
        # Get all game logs for player in season
        game_logs = GameLogORM.get_by_player_and_season(player_id, season, db=db)
        
        if not game_logs:
            return None, None
        
        # Extract stat values
        values = []
        for game_log in game_logs:
            value = self.get_stat_value(game_log, stat)
            if value is not None:
                values.append(value)
        
        if len(values) < 3:  # Need at least 3 games for meaningful stats
            return None, None
        
        # Calculate mean and standard deviation
        avg = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        
        return avg, std
    
    def calculate_recent_average(
        self,
        player_id: int,
        season: str,
        stat: str,
        window_size: int,
        db: Session
    ) -> Optional[float]:
        """Calculate average for last N games.
        
        Args:
            player_id: Player identifier
            season: Season string
            stat: Statistic name
            window_size: Number of recent games
            db: Database session
            
        Returns:
            Average value or None if insufficient games
        """
        # Get game logs (already ordered by game_id desc - most recent first)
        game_logs = GameLogORM.get_by_player_and_season(player_id, season, db=db)
        
        if not game_logs:
            return None
        
        # Get last N games
        last_n_games = game_logs[:window_size]
        
        # Extract stat values
        values = []
        for game_log in last_n_games:
            value = self.get_stat_value(game_log, stat)
            if value is not None:
                values.append(value)
        
        if not values:
            return None
        
        return statistics.mean(values)
    
    def calculate_heat_index(
        self,
        player_id: int,
        season: str,
        stat: str,
        window_size: int,
        db: Session
    ) -> Optional[Dict]:
        """Calculate heat index for a player (Z-score of recent form vs season).
        
        Args:
            player_id: Player identifier
            season: Season string
            stat: Statistic name
            window_size: Number of recent games
            db: Database session
            
        Returns:
            Dictionary with heat index data or None if insufficient data
        """
        # Get season stats
        season_avg, season_std = self.calculate_season_stats(player_id, season, stat, db)
        
        if season_avg is None or season_std is None or season_std == 0:
            return None
        
        # Get recent average
        recent_avg = self.calculate_recent_average(player_id, season, stat, window_size, db)
        
        if recent_avg is None:
            return None
        
        # Calculate Z-score: (recent_avg - season_avg) / season_std
        z_score = (recent_avg - season_avg) / season_std
        
        # Determine heat status
        if z_score >= self.ON_FIRE_THRESHOLD:
            status = "on_fire"
        elif z_score <= self.ICE_COLD_THRESHOLD:
            status = "ice_cold"
        else:
            status = "normal"
        
        # Get player name
        player = PlayerORM.get_by_id(player_id, db=db)
        player_name = player.name if player else f"Player {player_id}"
        
        return {
            'player_id': player_id,
            'player_name': player_name,
            'stat': stat,
            'season': season,
            'window_size': window_size,
            'season_avg': round(season_avg, 2),
            'season_std': round(season_std, 2),
            'recent_avg': round(recent_avg, 2),
            'z_score': round(z_score, 3),
            'status': status
        }
    
    def calculate_all_players(
        self,
        season: str,
        stats: Optional[List[str]] = None,
        window_sizes: Optional[List[int]] = None,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Calculate heat index for all players.
        
        Args:
            season: Season string
            stats: Optional list of stats (default: all)
            window_sizes: Optional list of window sizes (default: all)
            db: Optional database session
            
        Returns:
            List of heat index dictionaries
        """
        if stats is None:
            stats = self.STATS
        
        if window_sizes is None:
            window_sizes = self.WINDOW_SIZES
        
        session = db or self.db if hasattr(self, 'db') else None
        if not session:
            with get_db_context() as session:
                return self._calculate_all_players_internal(season, stats, window_sizes, session)
        else:
            return self._calculate_all_players_internal(season, stats, window_sizes, session)
    
    def _calculate_all_players_internal(
        self,
        season: str,
        stats: List[str],
        window_sizes: List[int],
        db: Session
    ) -> List[Dict]:
        """Internal method to calculate for all players."""
        logger.info(f"Starting heat index calculation for season {season}")
        
        # Clear existing heat index records for this season to ensure fresh calculation
        # This prevents stale data from previous calculations
        logger.info(f"Clearing existing heat index records for season {season}...")
        deleted_count = PlayerHeatIndexORM.clear_by_season(season, db=db)
        logger.info(f"Cleared {deleted_count} existing heat index records for season {season}")
        
        # Get active players for this season (players with data in this season)
        players = PlayerORM.get_active_for_season(season, db=db)
        logger.info(f"Found {len(players)} active players for season {season}")
        
        all_heat_indices = []
        players_processed = 0
        
        for player in players:
            player_id = player.player_id
            
            try:
                for stat in stats:
                    for window_size in window_sizes:
                        heat_index = self.calculate_heat_index(
                            player_id, season, stat, window_size, db
                        )
                        
                        if heat_index:
                            all_heat_indices.append(heat_index)
                
                players_processed += 1
                
                if players_processed % 100 == 0:
                    logger.info(f"Processed {players_processed}/{len(players)} players")
                
            except Exception as e:
                logger.error(f"Error calculating heat index for player {player_id}: {e}")
                continue
        
        # Persist results to database using bulk upsert
        if all_heat_indices:
            try:
                PlayerHeatIndexORM.bulk_create(all_heat_indices, db=db)
                db.commit()
                logger.info(f"Persisted {len(all_heat_indices)} heat index records to database")
            except Exception as e:
                logger.error(f"Error persisting heat index records: {e}")
                db.rollback()
                raise
        
        # Count by status
        on_fire_count = sum(1 for h in all_heat_indices if h['status'] == 'on_fire')
        ice_cold_count = sum(1 for h in all_heat_indices if h['status'] == 'ice_cold')
        
        logger.info(
            f"Heat index calculation complete: {len(all_heat_indices)} total calculations, "
            f"{on_fire_count} 'On Fire', {ice_cold_count} 'Ice Cold'"
        )
        
        return all_heat_indices
    
    def get_hot_players(
        self,
        season: str,
        stat: str = 'PTS',
        window_size: int = 5,
        limit: int = 20,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Get hottest players (On Fire) for a stat from database.
        
        Args:
            season: Season string
            stat: Statistic name
            window_size: Window size
            limit: Maximum number of players to return
            db: Optional database session
            
        Returns:
            List of heat index dictionaries, sorted by Z-score descending
        """
        session = db or self.db if hasattr(self, 'db') else None
        if not session:
            with get_db_context() as session:
                records = PlayerHeatIndexORM.get_hot_players(season, stat, window_size, limit, db=session)
        else:
            records = PlayerHeatIndexORM.get_hot_players(season, stat, window_size, limit, db=session)
        
        # Convert ORM records to dictionaries
        return [
            {
                'player_id': r.player_id,
                'player_name': r.player_name,
                'stat': r.stat,
                'season': r.season,
                'window_size': r.window_size,
                'season_avg': r.season_avg,
                'season_std': r.season_std,
                'recent_avg': r.recent_avg,
                'z_score': r.z_score,
                'status': r.status
            }
            for r in records
        ]
    
    def get_cold_players(
        self,
        season: str,
        stat: str = 'PTS',
        window_size: int = 5,
        limit: int = 20,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Get coldest players (Ice Cold) for a stat from database.
        
        Args:
            season: Season string
            stat: Statistic name
            window_size: Window size
            limit: Maximum number of players to return
            db: Optional database session
            
        Returns:
            List of heat index dictionaries, sorted by Z-score ascending
        """
        session = db or self.db if hasattr(self, 'db') else None
        if not session:
            with get_db_context() as session:
                records = PlayerHeatIndexORM.get_cold_players(season, stat, window_size, limit, db=session)
        else:
            records = PlayerHeatIndexORM.get_cold_players(season, stat, window_size, limit, db=session)
        
        # Convert ORM records to dictionaries
        return [
            {
                'player_id': r.player_id,
                'player_name': r.player_name,
                'stat': r.stat,
                'season': r.season,
                'window_size': r.window_size,
                'season_avg': r.season_avg,
                'season_std': r.season_std,
                'recent_avg': r.recent_avg,
                'z_score': r.z_score,
                'status': r.status
            }
            for r in records
        ]

