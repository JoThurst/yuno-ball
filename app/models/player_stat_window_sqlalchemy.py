"""SQLAlchemy ORM model for PlayerStatWindows.

This module provides the PlayerStatWindowORM class which represents recent form
metrics (X of last N games) in the database using SQLAlchemy ORM.

Created: December 2024
Part of: Enhanced Streak Metrics System (Phase 1.1)
"""

from typing import Optional, List
from datetime import datetime, date
from sqlalchemy import Column, Integer, BigInteger, String, Text, Date, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class PlayerStatWindowORM(Base):
    """SQLAlchemy ORM model for player stat windows (recent form).
    
    This model tracks "X of last N" metrics (recent form, not necessarily consecutive).
    Examples: "8 of last 10 games with 20+ points", "4 of last 5 with 15+ rebounds"
    
    Attributes:
        id: Auto-incrementing primary key
        player_id: Reference to player (NBA API ID)
        player_name: Name of the player
        stat: Type of statistic (PTS, REB, AST, STL, BLK, FG3M)
        threshold: Minimum value for the window
        season: Season year (e.g., "2024-25")
        window_size: Size of the window (5, 10, etc.)
        games_played: Number of games in the window (allows for missed games)
        games_hit: Number of games that met the threshold
        last_game_id: Most recent game ID in the window
        last_game_date: Date of most recent game in the window
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (player_id, stat, threshold, season, window_size) - Prevents duplicate windows
    """
    
    __tablename__ = 'player_stat_windows'
    __table_args__ = (
        UniqueConstraint('player_id', 'stat', 'threshold', 'season', 'window_size',
                        name='player_stat_windows_unique'),
        Index('idx_stat_windows_player_id', 'player_id'),
        Index('idx_stat_windows_season', 'season'),
        Index('idx_stat_windows_stat', 'stat'),
        Index('idx_stat_windows_window_size', 'window_size'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Player Information
    player_id = Column(Integer, nullable=False)
    player_name = Column(Text, nullable=False)
    
    # Window Information
    stat = Column(Text, nullable=False)
    threshold = Column(Integer, nullable=False)
    season = Column(Text, nullable=False)
    window_size = Column(Integer, nullable=False)  # 5, 10, etc.
    
    # Window Statistics
    games_played = Column(Integer, nullable=False)  # Usually == window_size, but allows missed games
    games_hit = Column(Integer, nullable=False)  # How many games >= threshold
    
    # Last Game Reference
    last_game_id = Column(BigInteger, nullable=False)
    last_game_date = Column(Date, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Display names mapping
    STAT_DISPLAY_NAMES = {
        "PTS": "Points",
        "REB": "Rebounds",
        "AST": "Assists",
        "STL": "Steals",
        "BLK": "Blocks",
        "FG3M": "3-Pointers",
        "PRA": "Points+Rebounds+Assists"
    }
    
    def __repr__(self) -> str:
        """String representation of the window."""
        return (f"<PlayerStatWindowORM(id={self.id}, player='{self.player_name}', "
                f"stat={self.stat}, threshold={self.threshold}, "
                f"{self.games_hit}/{self.games_played} in last {self.window_size})>")
    
    def to_dict(self) -> dict:
        """Convert window object to dictionary.
        
        Returns:
            dict: Dictionary representation of the window
        """
        hit_rate = (self.games_hit / self.games_played * 100) if self.games_played > 0 else 0
        
        return {
            'id': self.id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'stat': self.stat,
            'stat_display': self.STAT_DISPLAY_NAMES.get(self.stat, self.stat),
            'threshold': self.threshold,
            'season': self.season,
            'window_size': self.window_size,
            'games_played': self.games_played,
            'games_hit': self.games_hit,
            'hit_rate': round(hit_rate, 1),
            'last_game_id': self.last_game_id,
            'last_game_date': self.last_game_date.isoformat() if self.last_game_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_id(cls, window_id: int, db: Optional[Session] = None) -> Optional['PlayerStatWindowORM']:
        """Get a window by its ID.
        
        Args:
            window_id: The window's unique identifier
            db: Optional database session
            
        Returns:
            PlayerStatWindowORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.id == window_id).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.id == window_id).first()
    
    @classmethod
    def get_by_player(cls,
                     player_id: int,
                     season: Optional[str] = None,
                     stat: Optional[str] = None,
                     window_size: Optional[int] = None,
                     db: Optional[Session] = None) -> List['PlayerStatWindowORM']:
        """Get all windows for a player.
        
        Args:
            player_id: The player's unique identifier
            season: Optional season filter
            stat: Optional stat filter
            window_size: Optional window size filter (5, 10, etc.)
            db: Optional database session
            
        Returns:
            List of PlayerStatWindowORM objects
        """
        def _query(session: Session):
            query = session.query(cls).filter(cls.player_id == player_id)
            if season:
                query = query.filter(cls.season == season)
            if stat:
                query = query.filter(cls.stat == stat)
            if window_size:
                query = query.filter(cls.window_size == window_size)
            return query.order_by(cls.window_size.desc(), cls.games_hit.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_high_hit_rate(cls,
                          season: str,
                          window_size: int,
                          min_hit_rate: float = 0.7,
                          stat: Optional[str] = None,
                          db: Optional[Session] = None) -> List['PlayerStatWindowORM']:
        """Get windows with high hit rates (e.g., 8 of 10 = 80%).
        
        Args:
            season: Season year (e.g., "2024-25")
            window_size: Window size to filter by (5, 10, etc.)
            min_hit_rate: Minimum hit rate (0.0 to 1.0)
            stat: Optional stat filter
            db: Optional database session
            
        Returns:
            List of PlayerStatWindowORM objects ordered by hit rate
        """
        def _query(session: Session):
            query = session.query(cls).filter(
                cls.season == season,
                cls.window_size == window_size
            )
            
            # Calculate hit rate in SQL
            # games_hit / games_played >= min_hit_rate
            # Equivalent to: games_hit >= min_hit_rate * games_played
            if stat:
                query = query.filter(cls.stat == stat)
            
            results = query.all()
            
            # Filter by hit rate (post-process since we need division)
            filtered = []
            for window in results:
                if window.games_played > 0:
                    hit_rate = window.games_hit / window.games_played
                    if hit_rate >= min_hit_rate:
                        filtered.append(window)
            
            # Sort by hit rate descending
            filtered.sort(key=lambda w: w.games_hit / w.games_played if w.games_played > 0 else 0, reverse=True)
            return filtered
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               player_id: int,
               player_name: str,
               stat: str,
               threshold: int,
               season: str,
               window_size: int,
               games_played: int,
               games_hit: int,
               last_game_id: int,
               last_game_date: date,
               db: Optional[Session] = None) -> 'PlayerStatWindowORM':
        """Create a new window or update if exists (upsert).
        
        Args:
            player_id: Player's unique identifier
            player_name: Player's name
            stat: Statistic type (PTS, REB, AST, etc.)
            threshold: Minimum value for window
            season: Season year
            window_size: Size of the window (5, 10, etc.)
            games_played: Number of games in window
            games_hit: Number of games that met threshold
            last_game_id: Most recent game ID
            last_game_date: Date of most recent game
            db: Optional database session
            
        Returns:
            PlayerStatWindowORM: The created or updated window object
        """
        def _create(session: Session) -> 'PlayerStatWindowORM':
            # Check if window exists (unique constraint)
            window = session.query(cls).filter(
                cls.player_id == player_id,
                cls.stat == stat,
                cls.threshold == threshold,
                cls.season == season,
                cls.window_size == window_size
            ).first()
            
            if window:
                # Update existing window
                window.games_played = games_played
                window.games_hit = games_hit
                window.last_game_id = last_game_id
                window.last_game_date = last_game_date
                window.created_at = datetime.utcnow()
                logger.debug(f"Updated stat window: {player_name} {stat} {threshold}+ ({games_hit}/{games_played} in last {window_size})")
            else:
                # Create new window
                window = cls(
                    player_id=player_id,
                    player_name=player_name,
                    stat=stat,
                    threshold=threshold,
                    season=season,
                    window_size=window_size,
                    games_played=games_played,
                    games_hit=games_hit,
                    last_game_id=last_game_id,
                    last_game_date=last_game_date
                )
                session.add(window)
                logger.debug(f"Created new stat window: {player_name} {stat} {threshold}+ ({games_hit}/{games_played} in last {window_size})")
            
            session.flush()
            return window
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            window = _create(session)
            session.commit()
            return window
    
    @classmethod
    def bulk_create(cls, windows: List[dict], db: Optional[Session] = None) -> int:
        """Bulk create or update windows using efficient bulk operations.
        
        Args:
            windows: List of window dictionaries with required keys
            db: Optional database session
            
        Returns:
            int: Number of windows created/updated
        """
        if not windows:
            return 0
        
        def _bulk_create(session: Session) -> int:
            from sqlalchemy.dialects.postgresql import insert
            from datetime import datetime
            
            # Prepare data for bulk insert
            values = []
            for window_data in windows:
                values.append({
                    'player_id': int(window_data['player_id']),
                    'player_name': window_data['player_name'],
                    'stat': window_data['stat'],
                    'threshold': int(window_data['threshold']),
                    'season': window_data['season'],
                    'window_size': int(window_data['window_size']),
                    'games_played': int(window_data['games_played']),
                    'games_hit': int(window_data['games_hit']),
                    'last_game_id': int(window_data['last_game_id']),
                    'last_game_date': window_data['last_game_date'],
                    'created_at': datetime.utcnow()
                })
            
            # Use PostgreSQL INSERT ... ON CONFLICT for upsert
            # Note: created_at is NOT updated on conflict to preserve original creation timestamp
            stmt = insert(cls.__table__).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint='player_stat_windows_unique',
                set_={
                    'player_name': stmt.excluded.player_name,  # Update name in case it changed
                    'games_played': stmt.excluded.games_played,
                    'games_hit': stmt.excluded.games_hit,
                    'last_game_id': stmt.excluded.last_game_id,
                    'last_game_date': stmt.excluded.last_game_date
                    # created_at is NOT updated - preserve original creation timestamp
                }
            )
            
            session.execute(stmt)
            return len(values)
        
        if db:
            return _bulk_create(db)
        
        with get_db_context() as session:
            count = _bulk_create(session)
            session.commit()
            logger.info(f"Bulk created/updated {count} stat windows")
            return count
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this window from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.debug(f"Deleted stat window: {self.player_name} (ID: {self.id})")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()
    
    @classmethod
    def clear_all(cls, db: Optional[Session] = None) -> None:
        """Clear all windows from the database.
        
        Args:
            db: Optional database session
        """
        def _clear(session: Session) -> None:
            session.query(cls).delete()
            session.flush()
            logger.info("Cleared all stat windows from the database")
        
        if db:
            _clear(db)
        else:
            with get_db_context() as session:
                _clear(session)
                session.commit()
    
    @classmethod
    def clear_by_season(cls, season: str, db: Optional[Session] = None) -> int:
        """Clear all stat windows for a specific season.
        
        This is useful before recalculating windows to ensure no stale data remains.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            int: Number of records deleted
        """
        def _clear(session: Session) -> int:
            deleted_count = session.query(cls).filter(cls.season == season).delete()
            session.flush()
            logger.info(f"Cleared {deleted_count} stat windows for season {season}")
            return deleted_count
        
        if db:
            return _clear(db)
        
        with get_db_context() as session:
            count = _clear(session)
            session.commit()
            return count

