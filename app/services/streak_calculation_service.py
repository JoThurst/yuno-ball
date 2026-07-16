"""Service for calculating enhanced streak metrics.

This service calculates:
1. Consecutive streaks (true streaks - games in a row)
2. Recent form (X of last N games)
3. Season hit rates

Created: December 2024
Part of: Enhanced Streak Metrics System (Phase 1.1)
"""

from typing import List, Dict, Optional, Tuple, Set
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db_context
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.consecutive_streak_sqlalchemy import ConsecutiveStreakORM
from app.models.player_stat_window_sqlalchemy import PlayerStatWindowORM
from app.models.player_sqlalchemy import PlayerORM
from app.utils.config_utils import logger


class StreakCalculationService:
    """Service for calculating enhanced streak metrics from game logs."""
    
    # Stat field mappings (game log field -> stat name)
    # Note: GameLogORM only has: points, assists, rebounds, steals, blocks, turnovers
    # FG3M (three-pointers) is not available in game logs, only in league dash stats
    STAT_FIELDS = {
        'PTS': 'points',
        'REB': 'rebounds',
        'AST': 'assists',
        'STL': 'steals',
        'BLK': 'blocks',
        'PRA': None  # Calculated: points + rebounds + assists
    }
    
    # Default thresholds for each stat
    DEFAULT_THRESHOLDS = {
        'PTS': [10, 15, 20, 25, 30],
        'REB': [4, 6, 8, 10, 12],
        'AST': [2, 4, 6, 8, 10],
        'STL': [1, 2, 3, 4],
        'BLK': [1, 2, 3, 4],
        'PRA': [20, 25, 30, 35, 40]
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service.
        
        Args:
            db: Optional database session
        """
        self.db = db
    
    def get_stat_value(self, game_log: GameLogORM, stat: str) -> Optional[int]:
        """Get the stat value from a game log.
        
        Args:
            game_log: Game log ORM object
            stat: Stat name (PTS, REB, AST, etc.)
            
        Returns:
            Stat value or None if stat not found
        """
        if stat == 'PRA':
            # Calculate PRA (Points + Rebounds + Assists)
            pts = game_log.points or 0
            reb = game_log.rebounds or 0
            ast = game_log.assists or 0
            return pts + reb + ast
        
        field_name = self.STAT_FIELDS.get(stat)
        if not field_name:
            return None
        
        # Map field name to game log attribute
        value = getattr(game_log, field_name, None)
        return int(value) if value is not None else 0
    
    def get_game_date(self, game_id: str, team_id: int, db: Session) -> Optional[date]:
        """Get the game date from game schedule.
        
        Args:
            game_id: Game identifier
            team_id: Team identifier
            db: Database session
            
        Returns:
            Game date or None if not found
        """
        schedule = GameScheduleORM.get_by_game_and_team(game_id, team_id, db=db)
        if schedule and schedule.game_date:
            # Convert datetime to date
            if isinstance(schedule.game_date, datetime):
                return schedule.game_date.date()
            elif isinstance(schedule.game_date, date):
                return schedule.game_date
        return None
    
    def _bulk_fetch_game_dates(
        self, 
        game_team_pairs: List[Tuple[str, int]], 
        db: Session,
        batch_size: int = 1000
    ) -> Dict[Tuple[str, int], date]:
        """Bulk fetch game dates for multiple (game_id, team_id) pairs.
        
        Args:
            game_team_pairs: List of (game_id, team_id) tuples
            db: Database session
            batch_size: Number of pairs to query at once (to avoid huge OR clauses)
            
        Returns:
            Dictionary mapping (game_id, team_id) -> date
        """
        if not game_team_pairs:
            return {}
        
        date_lookup = {}
        
        # Process in batches to avoid huge OR clauses
        for i in range(0, len(game_team_pairs), batch_size):
            batch = game_team_pairs[i:i + batch_size]
            
            # Build OR conditions for this batch
            conditions = []
            for game_id, team_id in batch:
                conditions.append(
                    and_(GameScheduleORM.game_id == game_id, GameScheduleORM.team_id == team_id)
                )
            
            # Query this batch
            schedules = db.query(GameScheduleORM).filter(or_(*conditions)).all()
            
            # Add to lookup dictionary
            for schedule in schedules:
                key = (schedule.game_id, schedule.team_id)
                if schedule.game_date:
                    if isinstance(schedule.game_date, datetime):
                        date_lookup[key] = schedule.game_date.date()
                    elif isinstance(schedule.game_date, date):
                        date_lookup[key] = schedule.game_date
        
        return date_lookup
    
    def _bulk_fetch_game_logs(
        self, 
        season: str, 
        db: Session
    ) -> Dict[int, List[GameLogORM]]:
        """Bulk fetch all game logs for a season, grouped by player.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Database session
            
        Returns:
            Dictionary mapping player_id -> list of game logs (most recent first)
        """
        # Fetch all game logs for season in one query
        all_logs = db.query(GameLogORM).filter(
            GameLogORM.season == season
        ).order_by(GameLogORM.player_id, GameLogORM.game_id.desc()).all()
        
        # Group by player_id
        logs_by_player = {}
        for log in all_logs:
            if log.player_id not in logs_by_player:
                logs_by_player[log.player_id] = []
            logs_by_player[log.player_id].append(log)
        
        return logs_by_player
    
    def calculate_consecutive_streaks(
        self,
        player_id: int,
        season: str,
        stats: Optional[List[str]] = None,
        thresholds: Optional[Dict[str, List[int]]] = None,
        db: Optional[Session] = None,
        game_logs: Optional[List[GameLogORM]] = None,
        game_date_lookup: Optional[Dict[Tuple[str, int], date]] = None
    ) -> List[Dict]:
        """Calculate consecutive streaks for a player.
        
        Args:
            player_id: Player identifier
            season: Season string (e.g., "2024-25")
            stats: Optional list of stats to calculate (default: all)
            thresholds: Optional dict of stat -> list of thresholds
            db: Optional database session
            game_logs: Optional pre-fetched game logs (for bulk processing)
            game_date_lookup: Optional pre-fetched game dates (for bulk processing)
            
        Returns:
            List of streak dictionaries ready for database insertion
        """
        if stats is None:
            stats = list(self.STAT_FIELDS.keys())
        
        if thresholds is None:
            thresholds = self.DEFAULT_THRESHOLDS
        
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._calculate_consecutive_streaks_internal(
                    player_id, season, stats, thresholds, session, game_logs, game_date_lookup
                )
        else:
            return self._calculate_consecutive_streaks_internal(
                player_id, season, stats, thresholds, session, game_logs, game_date_lookup
            )
    
    def _precompute_stat_values(
        self, 
        game_logs: List[GameLogORM], 
        stats: List[str]
    ) -> Dict[str, List[Optional[int]]]:
        """Pre-compute all stat values for all games once.
        
        Args:
            game_logs: List of game logs
            stats: List of stats to compute
            
        Returns:
            Dictionary mapping stat -> list of values (one per game)
        """
        stat_values = {stat: [] for stat in stats}
        
        for game_log in game_logs:
            for stat in stats:
                stat_values[stat].append(self.get_stat_value(game_log, stat))
        
        return stat_values
    
    def _calculate_consecutive_streaks_internal(
        self,
        player_id: int,
        season: str,
        stats: List[str],
        thresholds: Dict[str, List[int]],
        db: Session,
        game_logs: Optional[List[GameLogORM]] = None,
        game_date_lookup: Optional[Dict[Tuple[str, int], date]] = None
    ) -> List[Dict]:
        """Internal method to calculate consecutive streaks.
        
        Args:
            player_id: Player identifier
            season: Season string
            stats: List of stats to calculate
            thresholds: Dict of stat -> list of thresholds
            db: Database session
            game_logs: Optional pre-fetched game logs (for bulk processing)
            game_date_lookup: Optional pre-fetched game dates (for bulk processing)
        """
        # Get player name
        player = PlayerORM.get_by_id(player_id, db=db)
        player_name = player.name if player else f"Player {player_id}"
        
        # Get game logs if not provided
        if game_logs is None:
            # Get all game logs for player in season, ordered by game_id desc (most recent first)
            game_logs = GameLogORM.get_by_player_and_season(player_id, season, db=db)
            
            if not game_logs:
                logger.debug(f"No game logs found for player {player_id} in season {season}")
                return []
            
            # Reverse to get chronological order (oldest first)
            game_logs = list(reversed(game_logs))
        else:
            # Ensure chronological order (oldest first)
            if game_logs and game_logs[0].game_id > game_logs[-1].game_id:
                # Most recent first, need to reverse
                game_logs = list(reversed(game_logs))
        
        # OPTIMIZATION: Pre-compute all stat values once
        stat_values = self._precompute_stat_values(game_logs, stats)
        
        streaks = []
        
        for stat in stats:
            if stat not in thresholds:
                continue
            
            # Get pre-computed values for this stat
            values = stat_values[stat]
            
            for threshold in thresholds[stat]:
                # Calculate current streak
                current_streak = self._calculate_single_consecutive_streak(
                    game_logs, stat, threshold, player_id, player_name, season, db, 
                    game_date_lookup, values
                )
                
                if current_streak:
                    streaks.append(current_streak)
                
                # Calculate season max streak
                season_max_streak = self._calculate_season_max_streak(
                    game_logs, stat, threshold, player_id, player_name, season, db, 
                    game_date_lookup, values
                )
                
                if season_max_streak:
                    streaks.append(season_max_streak)
        
        return streaks
    
    def _calculate_single_consecutive_streak(
        self,
        game_logs: List[GameLogORM],
        stat: str,
        threshold: int,
        player_id: int,
        player_name: str,
        season: str,
        db: Session,
        game_date_lookup: Optional[Dict[Tuple[str, int], date]] = None,
        precomputed_values: Optional[List[Optional[int]]] = None
    ) -> Optional[Dict]:
        """Calculate the current active consecutive streak.
        
        Args:
            game_logs: List of game logs in chronological order (oldest first)
            stat: Statistic to calculate streak for
            threshold: Minimum value for streak
            player_id: Player identifier
            player_name: Player name
            season: Season string
            db: Database session
            game_date_lookup: Optional pre-fetched game dates dictionary
            precomputed_values: Optional pre-computed stat values (one per game)
        """
        streak_length = 0
        streak_start_idx = None
        streak_end_idx = None  # Most recent game in streak
        
        # Use pre-computed values if provided, otherwise compute on the fly
        if precomputed_values is None:
            precomputed_values = [self.get_stat_value(game_log, stat) for game_log in game_logs]
        
        # Iterate from most recent game backwards
        for i in range(len(game_logs) - 1, -1, -1):
            stat_value = precomputed_values[i]
            
            if stat_value is None:
                continue
            
            if stat_value >= threshold:
                if streak_length == 0:
                    # Start of new streak - this is the most recent game
                    streak_start_idx = i
                    streak_end_idx = i  # Most recent game in streak
                else:
                    # Continue streak - update start to earlier game
                    streak_start_idx = i
                streak_length += 1
            else:
                # Streak broken
                break
        
        if streak_length == 0:
            return None
        
        # Get game dates for start and end
        start_game = game_logs[streak_start_idx]
        end_game = game_logs[streak_end_idx]
        
        start_game_id = int(start_game.game_id) if start_game.game_id.isdigit() else 0
        end_game_id = int(end_game.game_id) if end_game.game_id.isdigit() else 0
        
        # Use lookup if provided, otherwise fall back to individual query
        if game_date_lookup:
            start_date = game_date_lookup.get((start_game.game_id, start_game.team_id))
            end_date = game_date_lookup.get((end_game.game_id, end_game.team_id))
        else:
            start_date = self.get_game_date(start_game.game_id, start_game.team_id, db)
            end_date = self.get_game_date(end_game.game_id, end_game.team_id, db)
        
        # If we couldn't get dates, use today as fallback
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = date.today()
        
        # Check if streak is active (most recent game is in streak)
        # streak_end_idx should be the index of the most recent game (len-1) if active
        is_active = (streak_end_idx == len(game_logs) - 1)
        
        return {
            'player_id': player_id,
            'player_name': player_name,
            'stat': stat,
            'threshold': threshold,
            'season': season,
            'streak_games': streak_length,
            'start_game_id': start_game_id,
            'end_game_id': end_game_id,
            'start_date': start_date,
            'end_date': end_date,
            'is_active': is_active,
            'streak_kind': 'current'
        }
    
    def _calculate_season_max_streak(
        self,
        game_logs: List[GameLogORM],
        stat: str,
        threshold: int,
        player_id: int,
        player_name: str,
        season: str,
        db: Session,
        game_date_lookup: Optional[Dict[Tuple[str, int], date]] = None,
        precomputed_values: Optional[List[Optional[int]]] = None
    ) -> Optional[Dict]:
        """Calculate the season-best consecutive streak.
        
        Args:
            game_logs: List of game logs in chronological order (oldest first)
            stat: Statistic to calculate streak for
            threshold: Minimum value for streak
            player_id: Player identifier
            player_name: Player name
            season: Season string
            db: Database session
            game_date_lookup: Optional pre-fetched game dates dictionary
            precomputed_values: Optional pre-computed stat values (one per game)
        """
        max_streak_length = 0
        max_streak_start_idx = None
        max_streak_end_idx = None
        
        current_streak_length = 0
        current_streak_start_idx = None
        
        # Use pre-computed values if provided, otherwise compute on the fly
        if precomputed_values is None:
            precomputed_values = [self.get_stat_value(game_log, stat) for game_log in game_logs]
        
        # Iterate through all games chronologically
        for i, stat_value in enumerate(precomputed_values):
            if stat_value is None:
                continue
            
            if stat_value >= threshold:
                if current_streak_length == 0:
                    # Start of new streak
                    current_streak_start_idx = i
                current_streak_length += 1
            else:
                # Streak broken - check if it's the longest
                if current_streak_length > max_streak_length:
                    max_streak_length = current_streak_length
                    max_streak_start_idx = current_streak_start_idx
                    max_streak_end_idx = i - 1
                current_streak_length = 0
                current_streak_start_idx = None
        
        # Check final streak
        if current_streak_length > max_streak_length:
            max_streak_length = current_streak_length
            max_streak_start_idx = current_streak_start_idx
            max_streak_end_idx = len(game_logs) - 1
        
        if max_streak_length == 0:
            return None
        
        # Get game dates for start and end
        start_game = game_logs[max_streak_start_idx]
        end_game = game_logs[max_streak_end_idx]
        
        start_game_id = int(start_game.game_id) if start_game.game_id.isdigit() else 0
        end_game_id = int(end_game.game_id) if end_game.game_id.isdigit() else 0
        
        # Use lookup if provided, otherwise fall back to individual query
        if game_date_lookup:
            start_date = game_date_lookup.get((start_game.game_id, start_game.team_id))
            end_date = game_date_lookup.get((end_game.game_id, end_game.team_id))
        else:
            start_date = self.get_game_date(start_game.game_id, start_game.team_id, db)
            end_date = self.get_game_date(end_game.game_id, end_game.team_id, db)
        
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = date.today()
        
        return {
            'player_id': player_id,
            'player_name': player_name,
            'stat': stat,
            'threshold': threshold,
            'season': season,
            'streak_games': max_streak_length,
            'start_game_id': start_game_id,
            'end_game_id': end_game_id,
            'start_date': start_date,
            'end_date': end_date,
            'is_active': False,  # Season max is never "active"
            'streak_kind': 'season_max'
        }
    
    def calculate_stat_windows(
        self,
        player_id: int,
        season: str,
        window_sizes: List[int] = [5, 10],
        stats: Optional[List[str]] = None,
        thresholds: Optional[Dict[str, List[int]]] = None,
        db: Optional[Session] = None,
        game_logs: Optional[List[GameLogORM]] = None,
        game_date_lookup: Optional[Dict[Tuple[str, int], date]] = None
    ) -> List[Dict]:
        """Calculate recent form windows (X of last N games).
        
        Args:
            player_id: Player identifier
            season: Season string (e.g., "2024-25")
            window_sizes: List of window sizes (e.g., [5, 10])
            stats: Optional list of stats to calculate (default: all)
            thresholds: Optional dict of stat -> list of thresholds
            db: Optional database session
            game_logs: Optional pre-fetched game logs (for bulk processing)
            game_date_lookup: Optional pre-fetched game dates (for bulk processing)
            
        Returns:
            List of window dictionaries ready for database insertion
        """
        if stats is None:
            stats = list(self.STAT_FIELDS.keys())
        
        if thresholds is None:
            thresholds = self.DEFAULT_THRESHOLDS
        
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._calculate_stat_windows_internal(
                    player_id, season, window_sizes, stats, thresholds, session, game_logs, game_date_lookup
                )
        else:
            return self._calculate_stat_windows_internal(
                player_id, season, window_sizes, stats, thresholds, session, game_logs, game_date_lookup
            )
    
    def _calculate_stat_windows_internal(
        self,
        player_id: int,
        season: str,
        window_sizes: List[int],
        stats: List[str],
        thresholds: Dict[str, List[int]],
        db: Session,
        game_logs: Optional[List[GameLogORM]] = None,
        game_date_lookup: Optional[Dict[Tuple[str, int], date]] = None
    ) -> List[Dict]:
        """Internal method to calculate stat windows.
        
        Args:
            player_id: Player identifier
            season: Season string
            window_sizes: List of window sizes
            stats: List of stats to calculate
            thresholds: Dict of stat -> list of thresholds
            db: Database session
            game_logs: Optional pre-fetched game logs (for bulk processing)
            game_date_lookup: Optional pre-fetched game dates (for bulk processing)
        """
        # Get player name
        player = PlayerORM.get_by_id(player_id, db=db)
        player_name = player.name if player else f"Player {player_id}"
        
        # Get game logs if not provided
        if game_logs is None:
            # Get all game logs for player in season, ordered by game_id desc (most recent first)
            game_logs = GameLogORM.get_by_player_and_season(player_id, season, db=db)
            
            if not game_logs:
                logger.debug(f"No game logs found for player {player_id} in season {season}")
                return []
        
        # OPTIMIZATION: Pre-compute all stat values once
        stat_values = self._precompute_stat_values(game_logs, stats)
        
        windows = []
        
        for stat in stats:
            if stat not in thresholds:
                continue
            
            # Get pre-computed values for this stat
            values = stat_values[stat]
            
            for threshold in thresholds[stat]:
                for window_size in window_sizes:
                    # Get last N games (already in most recent first order)
                    last_n_games = game_logs[:window_size]
                    
                    if not last_n_games:
                        continue
                    
                    # Count games that met threshold using pre-computed values
                    games_hit = 0
                    for i in range(min(window_size, len(values))):
                        stat_value = values[i]
                        if stat_value is not None and stat_value >= threshold:
                            games_hit += 1
                    
                    # Get most recent game info
                    last_game = last_n_games[0]
                    last_game_id = int(last_game.game_id) if last_game.game_id.isdigit() else 0
                    
                    # Use lookup if provided, otherwise fall back to individual query
                    if game_date_lookup:
                        last_game_date = game_date_lookup.get((last_game.game_id, last_game.team_id))
                    else:
                        last_game_date = self.get_game_date(last_game.game_id, last_game.team_id, db)
                    
                    if not last_game_date:
                        last_game_date = date.today()
                    
                    windows.append({
                        'player_id': player_id,
                        'player_name': player_name,
                        'stat': stat,
                        'threshold': threshold,
                        'season': season,
                        'window_size': window_size,
                        'games_played': len(last_n_games),
                        'games_hit': games_hit,
                        'last_game_id': last_game_id,
                        'last_game_date': last_game_date
                    })
        
        return windows
    
    def calculate_all_players(
        self,
        season: str,
        stats: Optional[List[str]] = None,
        thresholds: Optional[Dict[str, List[int]]] = None,
        window_sizes: List[int] = [5, 10],
        db: Optional[Session] = None
    ) -> Tuple[int, int]:
        """Calculate streaks and windows for all players in a season.
        
        Args:
            season: Season string (e.g., "2024-25")
            stats: Optional list of stats to calculate
            thresholds: Optional dict of stat -> list of thresholds
            window_sizes: List of window sizes for recent form
            db: Optional database session
            
        Returns:
            Tuple of (streaks_created, windows_created)
        """
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._calculate_all_players_internal(
                    season, stats, thresholds, window_sizes, session
                )
        else:
            return self._calculate_all_players_internal(
                season, stats, thresholds, window_sizes, session
            )
    
    def _calculate_all_players_internal(
        self,
        season: str,
        stats: Optional[List[str]],
        thresholds: Optional[Dict[str, List[int]]],
        window_sizes: List[int],
        db: Session
    ) -> Tuple[int, int]:
        """Internal method to calculate for all players (OPTIMIZED VERSION).
        
        Performance optimizations:
        1. Bulk fetch all game logs for season in one query
        2. Bulk fetch all game dates in one query
        3. Process players in batches with batch commits
        """
        # Set defaults if not provided
        if stats is None:
            stats = list(self.STAT_FIELDS.keys())
        
        if thresholds is None:
            thresholds = self.DEFAULT_THRESHOLDS
        
        logger.info(f"Starting optimized streak calculation for season {season}")
        
        # Clear existing streaks and windows for this season to ensure fresh calculation
        # This prevents stale data from previous calculations
        logger.info(f"Clearing existing streaks and windows for season {season}...")
        deleted_streaks = ConsecutiveStreakORM.clear_by_season(season, db=db)
        deleted_windows = PlayerStatWindowORM.clear_by_season(season, db=db)
        logger.info(f"Cleared {deleted_streaks} existing streaks and {deleted_windows} existing windows for season {season}")
        
        # Get active players for this season (players with data in this season)
        players = PlayerORM.get_active_for_season(season, db=db)
        logger.info(f"Found {len(players)} active players for season {season}")
        
        # OPTIMIZATION 1: Bulk fetch all game logs for season in one query
        logger.info("Bulk fetching game logs for season...")
        logs_by_player = self._bulk_fetch_game_logs(season, db)
        logger.info(f"Fetched game logs for {len(logs_by_player)} players")
        
        # OPTIMIZATION 2: Collect all unique (game_id, team_id) pairs for bulk date lookup
        game_team_pairs = set()
        for player_logs in logs_by_player.values():
            for log in player_logs:
                game_team_pairs.add((log.game_id, log.team_id))
        
        logger.info(f"Bulk fetching game dates for {len(game_team_pairs)} unique games...")
        game_date_lookup = self._bulk_fetch_game_dates(list(game_team_pairs), db)
        logger.info(f"Fetched {len(game_date_lookup)} game dates")
        
        # OPTIMIZATION 3: Process players in batches
        batch_size = 100
        total_streaks = 0
        total_windows = 0
        
        all_streaks = []
        all_windows = []
        
        players_with_logs = [p for p in players if p.player_id in logs_by_player]
        logger.info(f"Processing {len(players_with_logs)} players with game logs")
        
        for i, player in enumerate(players_with_logs):
            player_id = player.player_id
            
            try:
                # Get pre-fetched game logs for this player
                player_logs = logs_by_player[player_id]
                
                # Reverse to chronological order for streak calculation
                chronological_logs = list(reversed(player_logs))
                
                # Calculate consecutive streaks (using pre-fetched data)
                streaks = self._calculate_consecutive_streaks_internal(
                    player_id, season, stats, thresholds, db,
                    game_logs=chronological_logs,
                    game_date_lookup=game_date_lookup
                )
                
                if streaks:
                    all_streaks.extend(streaks)
                    total_streaks += len(streaks)
                
                # Calculate stat windows (using pre-fetched data)
                windows = self._calculate_stat_windows_internal(
                    player_id, season, window_sizes, stats, thresholds, db,
                    game_logs=player_logs,  # Already in most recent first order
                    game_date_lookup=game_date_lookup
                )
                
                if windows:
                    all_windows.extend(windows)
                    total_windows += len(windows)
                
                # Commit in batches
                if (i + 1) % batch_size == 0:
                    if all_streaks:
                        ConsecutiveStreakORM.bulk_create(all_streaks, db=db)
                        all_streaks = []
                    if all_windows:
                        PlayerStatWindowORM.bulk_create(all_windows, db=db)
                        all_windows = []
                    db.commit()
                    logger.info(f"Processed {i + 1}/{len(players_with_logs)} players (batch commit)")
                
            except Exception as e:
                logger.error(f"Error calculating streaks for player {player_id}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        # Commit remaining items
        if all_streaks:
            ConsecutiveStreakORM.bulk_create(all_streaks, db=db)
        if all_windows:
            PlayerStatWindowORM.bulk_create(all_windows, db=db)
        db.commit()
        
        logger.info(f"Calculated {total_streaks} consecutive streaks and {total_windows} stat windows for season {season}")
        
        return total_streaks, total_windows

