"""SQLAlchemy ORM model for PlayerConsecutiveStreaks.

This module provides the ConsecutiveStreakORM class which represents consecutive
streak data (true streaks - games in a row) in the database using SQLAlchemy ORM.

Created: December 2024
Part of: Enhanced Streak Metrics System (Phase 1.1)
"""

from typing import Optional, List
from datetime import datetime, date
from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, Date, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class ConsecutiveStreakORM(Base):
    """SQLAlchemy ORM model for consecutive player streaks.
    
    This model tracks consecutive streaks (true streaks - games in a row).
    It distinguishes between current active streaks and season-best streaks.
    
    Attributes:
        id: Auto-incrementing primary key
        player_id: Reference to player (NBA API ID)
        player_name: Name of the player
        stat: Type of statistic (PTS, REB, AST, STL, BLK, FG3M)
        threshold: Minimum value for the streak
        season: Season year (e.g., "2024-25")
        streak_games: Length of the streak
        start_game_id: First game ID in the streak
        end_game_id: Last game ID in the streak
        start_date: Date of first game in streak
        end_date: Date of last game in streak
        is_active: True if streak is still alive going into next game
        streak_kind: 'current' (active streak) or 'season_max' (best streak this season)
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (player_id, stat, threshold, season, streak_kind) - Prevents duplicate streaks
    """
    
    __tablename__ = 'player_consecutive_streaks'
    __table_args__ = (
        UniqueConstraint('player_id', 'stat', 'threshold', 'season', 'streak_kind',
                        name='player_consecutive_streaks_unique'),
        Index('idx_consecutive_streaks_player_id', 'player_id'),
        Index('idx_consecutive_streaks_season', 'season'),
        Index('idx_consecutive_streaks_stat', 'stat'),
        Index('idx_consecutive_streaks_active', 'is_active'),
        Index('idx_consecutive_streaks_kind', 'streak_kind'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Player Information
    player_id = Column(Integer, nullable=False)
    player_name = Column(Text, nullable=False)
    
    # Streak Information
    stat = Column(Text, nullable=False)
    threshold = Column(Integer, nullable=False)
    season = Column(Text, nullable=False)
    streak_games = Column(Integer, nullable=False)
    
    # Streak Range
    start_game_id = Column(BigInteger, nullable=False)
    end_game_id = Column(BigInteger, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # Streak Status
    is_active = Column(Boolean, nullable=False, default=True)
    streak_kind = Column(Text, nullable=False)  # 'current' or 'season_max'
    
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
        """String representation of the streak."""
        return (f"<ConsecutiveStreakORM(id={self.id}, player='{self.player_name}', "
                f"stat={self.stat}, threshold={self.threshold}, streak={self.streak_games}, "
                f"kind={self.streak_kind}, active={self.is_active})>")
    
    def to_dict(self) -> dict:
        """Convert streak object to dictionary.
        
        Returns:
            dict: Dictionary representation of the streak
        """
        return {
            'id': self.id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'stat': self.stat,
            'stat_display': self.STAT_DISPLAY_NAMES.get(self.stat, self.stat),
            'threshold': self.threshold,
            'season': self.season,
            'streak_games': self.streak_games,
            'start_game_id': self.start_game_id,
            'end_game_id': self.end_game_id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active,
            'streak_kind': self.streak_kind,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_id(cls, streak_id: int, db: Optional[Session] = None) -> Optional['ConsecutiveStreakORM']:
        """Get a streak by its ID.
        
        Args:
            streak_id: The streak's unique identifier
            db: Optional database session
            
        Returns:
            ConsecutiveStreakORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.id == streak_id).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.id == streak_id).first()
    
    @classmethod
    def get_active_streaks(cls, 
                          season: str,
                          min_streak: int = 3,
                          stat: Optional[str] = None,
                          db: Optional[Session] = None) -> List['ConsecutiveStreakORM']:
        """Get all active consecutive streaks for a season.
        
        Args:
            season: Season year (e.g., "2024-25")
            min_streak: Minimum streak length to include
            stat: Optional stat filter (PTS, REB, etc.)
            db: Optional database session
            
        Returns:
            List of ConsecutiveStreakORM objects ordered by streak length
        """
        def _query(session: Session):
            query = session.query(cls).filter(
                cls.season == season,
                cls.streak_kind == 'current',
                cls.is_active == True,
                cls.streak_games >= min_streak
            )
            if stat:
                query = query.filter(cls.stat == stat)
            return query.order_by(cls.streak_games.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_by_player(cls, 
                     player_id: int, 
                     season: Optional[str] = None,
                     stat: Optional[str] = None,
                     streak_kind: Optional[str] = None,
                     db: Optional[Session] = None) -> List['ConsecutiveStreakORM']:
        """Get all streaks for a player.
        
        Args:
            player_id: The player's unique identifier
            season: Optional season filter
            stat: Optional stat filter
            streak_kind: Optional kind filter ('current' or 'season_max')
            db: Optional database session
            
        Returns:
            List of ConsecutiveStreakORM objects
        """
        def _query(session: Session):
            query = session.query(cls).filter(cls.player_id == player_id)
            if season:
                query = query.filter(cls.season == season)
            if stat:
                query = query.filter(cls.stat == stat)
            if streak_kind:
                query = query.filter(cls.streak_kind == streak_kind)
            return query.order_by(cls.streak_games.desc()).all()
        
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
               streak_games: int,
               start_game_id: int,
               end_game_id: int,
               start_date: date,
               end_date: date,
               is_active: bool,
               streak_kind: str,
               db: Optional[Session] = None) -> 'ConsecutiveStreakORM':
        """Create a new streak or update if exists (upsert).
        
        Args:
            player_id: Player's unique identifier
            player_name: Player's name
            stat: Statistic type (PTS, REB, AST, etc.)
            threshold: Minimum value for streak
            season: Season year
            streak_games: Number of consecutive games
            start_game_id: First game ID in streak
            end_game_id: Last game ID in streak
            start_date: Date of first game
            end_date: Date of last game
            is_active: Whether streak is still active
            streak_kind: 'current' or 'season_max'
            db: Optional database session
            
        Returns:
            ConsecutiveStreakORM: The created or updated streak object
        """
        def _create(session: Session) -> 'ConsecutiveStreakORM':
            # Check if streak exists (unique constraint)
            streak = session.query(cls).filter(
                cls.player_id == player_id,
                cls.stat == stat,
                cls.threshold == threshold,
                cls.season == season,
                cls.streak_kind == streak_kind
            ).first()
            
            if streak:
                # Update existing streak
                streak.streak_games = streak_games
                streak.start_game_id = start_game_id
                streak.end_game_id = end_game_id
                streak.start_date = start_date
                streak.end_date = end_date
                streak.is_active = is_active
                streak.created_at = datetime.utcnow()
                logger.debug(f"Updated consecutive streak: {player_name} {stat} {threshold}+ ({streak_games} games, {streak_kind})")
            else:
                # Create new streak
                streak = cls(
                    player_id=player_id,
                    player_name=player_name,
                    stat=stat,
                    threshold=threshold,
                    season=season,
                    streak_games=streak_games,
                    start_game_id=start_game_id,
                    end_game_id=end_game_id,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=is_active,
                    streak_kind=streak_kind
                )
                session.add(streak)
                logger.debug(f"Created new consecutive streak: {player_name} {stat} {threshold}+ ({streak_games} games, {streak_kind})")
            
            session.flush()
            return streak
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            streak = _create(session)
            session.commit()
            return streak
    
    @classmethod
    def bulk_create(cls, streaks: List[dict], db: Optional[Session] = None) -> int:
        """Bulk create or update streaks using efficient bulk operations.
        
        Args:
            streaks: List of streak dictionaries with required keys
            db: Optional database session
            
        Returns:
            int: Number of streaks created/updated
        """
        if not streaks:
            return 0
        
        def _bulk_create(session: Session) -> int:
            from sqlalchemy.dialects.postgresql import insert
            from datetime import datetime
            
            # Prepare data for bulk insert
            values = []
            for streak_data in streaks:
                values.append({
                    'player_id': int(streak_data['player_id']),
                    'player_name': streak_data['player_name'],
                    'stat': streak_data['stat'],
                    'threshold': int(streak_data['threshold']),
                    'season': streak_data['season'],
                    'streak_games': int(streak_data['streak_games']),
                    'start_game_id': int(streak_data['start_game_id']),
                    'end_game_id': int(streak_data['end_game_id']),
                    'start_date': streak_data['start_date'],
                    'end_date': streak_data['end_date'],
                    'is_active': bool(streak_data['is_active']),
                    'streak_kind': streak_data['streak_kind'],
                    'created_at': datetime.utcnow()
                })
            
            # Use PostgreSQL INSERT ... ON CONFLICT for upsert
            # Note: created_at is NOT updated on conflict to preserve original creation timestamp
            stmt = insert(cls.__table__).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint='player_consecutive_streaks_unique',
                set_={
                    'player_name': stmt.excluded.player_name,  # Update name in case it changed
                    'streak_games': stmt.excluded.streak_games,
                    'start_game_id': stmt.excluded.start_game_id,
                    'end_game_id': stmt.excluded.end_game_id,
                    'start_date': stmt.excluded.start_date,
                    'end_date': stmt.excluded.end_date,
                    'is_active': stmt.excluded.is_active
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
            logger.info(f"Bulk created/updated {count} consecutive streaks")
            return count
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this streak from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.debug(f"Deleted consecutive streak: {self.player_name} (ID: {self.id})")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()
    
    @classmethod
    def clear_all(cls, db: Optional[Session] = None) -> None:
        """Clear all streaks from the database.
        
        Args:
            db: Optional database session
        """
        def _clear(session: Session) -> None:
            session.query(cls).delete()
            session.flush()
            logger.info("Cleared all consecutive streaks from the database")
        
        if db:
            _clear(db)
        else:
            with get_db_context() as session:
                _clear(session)
                session.commit()
    
    @classmethod
    def clear_by_season(cls, season: str, db: Optional[Session] = None) -> int:
        """Clear all streaks for a specific season.
        
        This is useful before recalculating streaks to ensure no stale data remains.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            int: Number of records deleted
        """
        def _clear(session: Session) -> int:
            deleted_count = session.query(cls).filter(cls.season == season).delete()
            session.flush()
            logger.info(f"Cleared {deleted_count} consecutive streaks for season {season}")
            return deleted_count
        
        if db:
            return _clear(db)
        
        with get_db_context() as session:
            count = _clear(session)
            session.commit()
            return count

