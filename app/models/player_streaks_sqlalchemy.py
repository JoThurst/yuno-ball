"""SQLAlchemy ORM model for PlayerStreaks.

This module provides the PlayerStreaksORM class which represents player
streak data in the database using SQLAlchemy ORM. It maintains backward
compatibility with the existing psycopg2-based PlayerStreaks class.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 continued)
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class PlayerStreaksORM(Base):
    """SQLAlchemy ORM model for player streaks.
    
    This model tracks player performance streaks (consecutive games above a threshold).
    It maps to the 'player_streaks' table in the public schema.
    
    Attributes:
        id: Auto-incrementing primary key
        player_id: Reference to player (NBA API ID)
        player_name: Name of the player
        stat: Type of statistic (PTS, REB, AST, STL, BLK, FG3M)
        threshold: Minimum value for the streak
        streak_games: Number of consecutive games above threshold
        season: Season year (e.g., "2024-25")
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (player_id, stat, season, threshold) - Prevents duplicate streaks
    """
    
    __tablename__ = 'player_streaks'
    __table_args__ = (
        UniqueConstraint('player_id', 'stat', 'season', 'threshold',
                        name='player_streaks_player_id_stat_season_threshold_key'),
        Index('idx_player_streaks_player_id', 'player_id'),
        Index('idx_player_streaks_season', 'season'),
        Index('idx_player_streaks_stat', 'stat'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Streak Information
    player_id = Column(Integer, nullable=False)
    player_name = Column(Text, nullable=False)
    stat = Column(Text, nullable=False)
    threshold = Column(Integer, nullable=False)
    streak_games = Column(Integer, nullable=False)
    season = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Display names mapping
    STAT_DISPLAY_NAMES = {
        "PTS": "Points",
        "REB": "Rebounds",
        "AST": "Assists",
        "STL": "Steals",
        "BLK": "Blocks",
        "FG3M": "3-Pointers"
    }
    
    def __repr__(self) -> str:
        """String representation of the streak."""
        return (f"<PlayerStreaksORM(id={self.id}, player='{self.player_name}', "
                f"stat={self.stat}, threshold={self.threshold}, streak={self.streak_games})>")
    
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
            'streak_games': self.streak_games,
            'season': self.season,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_id(cls, streak_id: int, db: Optional[Session] = None) -> Optional['PlayerStreaksORM']:
        """Get a streak by its ID.
        
        Args:
            streak_id: The streak's unique identifier
            db: Optional database session
            
        Returns:
            PlayerStreaksORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.id == streak_id).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.id == streak_id).first()
    
    @classmethod
    def get_by_season(cls, season: str = "2025-26", db: Optional[Session] = None) -> List['PlayerStreaksORM']:
        """Get all streaks for a given season.
        
        Args:
            season: Season year (e.g., "2025-26")
            db: Optional database session
            
        Returns:
            List of PlayerStreaksORM objects ordered by streak length
        """
        if db:
            return db.query(cls).filter(cls.season == season).order_by(cls.streak_games.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.season == season).order_by(cls.streak_games.desc()).all()
    
    @classmethod
    def get_by_player(cls, player_id: int, season: Optional[str] = None,
                     db: Optional[Session] = None) -> List['PlayerStreaksORM']:
        """Get all streaks for a player.
        
        Args:
            player_id: The player's unique identifier
            season: Optional season filter
            db: Optional database session
            
        Returns:
            List of PlayerStreaksORM objects
        """
        def _query(session: Session):
            query = session.query(cls).filter(cls.player_id == player_id)
            if season:
                query = query.filter(cls.season == season)
            return query.order_by(cls.streak_games.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_hot_streaks(cls, min_streak: int = 10, season: str = "2025-26",
                       limit: Optional[int] = None, db: Optional[Session] = None) -> List[dict]:
        """Get current hot streaks for players.
        
        Args:
            min_streak: Minimum streak games to consider
            season: Season to filter by
            limit: Optional maximum number of results
            db: Optional database session
            
        Returns:
            List of streak dictionaries with team information
        """
        from app.models.team_sqlalchemy import TeamORM, RosterORM
        
        def _query(session: Session):
            query = (
                session.query(
                    cls.player_id,
                    cls.player_name,
                    cls.stat,
                    cls.streak_games,
                    cls.season,
                    TeamORM.abbreviation.label('team')
                )
                .outerjoin(RosterORM, cls.player_id == RosterORM.player_id)
                .outerjoin(TeamORM, RosterORM.team_id == TeamORM.team_id)
                .filter(cls.streak_games >= min_streak)
                .filter(cls.season == season)
                .order_by(cls.streak_games.desc())
            )
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
            
            return [
                {
                    'player_id': row.player_id,
                    'player_name': row.player_name,
                    'stat': row.stat,
                    'streak_games': row.streak_games,
                    'season': row.season,
                    'team': row.team if row.team else 'N/A'
                }
                for row in results
            ]
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_all_streaks_by_stat(cls, min_streak: int = 7, season: str = "2025-26",
                                db: Optional[Session] = None) -> dict:
        """Get all player streaks grouped by stat type.
        
        Args:
            min_streak: Minimum number of games for a streak
            season: Season to filter by
            db: Optional database session
            
        Returns:
            Dictionary of streaks grouped by stat type
        """
        from app.models.team_sqlalchemy import TeamORM, RosterORM
        
        def _query(session: Session):
            results = (
                session.query(
                    cls.player_id,
                    cls.player_name,
                    cls.stat,
                    cls.threshold,
                    cls.streak_games,
                    cls.season,
                    TeamORM.abbreviation.label('team_abbreviation')
                )
                .outerjoin(RosterORM, cls.player_id == RosterORM.player_id)
                .outerjoin(TeamORM, RosterORM.team_id == TeamORM.team_id)
                .filter(cls.streak_games >= min_streak)
                .filter(cls.season == season)
                .order_by(cls.stat, cls.streak_games.desc())
                .all()
            )
            
            streaks_by_stat = {}
            for row in results:
                streak = {
                    'player_id': row.player_id,
                    'player_name': row.player_name,
                    'stat': row.stat,
                    'stat_display': cls.STAT_DISPLAY_NAMES.get(row.stat, row.stat),
                    'threshold': row.threshold,
                    'streak_games': row.streak_games,
                    'season': row.season,
                    'team_abbreviation': row.team_abbreviation if row.team_abbreviation else 'N/A'
                }
                
                if row.stat not in streaks_by_stat:
                    streaks_by_stat[row.stat] = []
                streaks_by_stat[row.stat].append(streak)
            
            return streaks_by_stat
        
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
               streak_games: int,
               season: str,
               db: Optional[Session] = None) -> 'PlayerStreaksORM':
        """Create a new streak or update if exists (upsert).
        
        Args:
            player_id: Player's unique identifier
            player_name: Player's name
            stat: Statistic type (PTS, REB, AST, etc.)
            threshold: Minimum value for streak
            streak_games: Number of consecutive games
            season: Season year
            db: Optional database session
            
        Returns:
            PlayerStreaksORM: The created or updated streak object
        """
        def _create(session: Session) -> 'PlayerStreaksORM':
            # Check if streak exists (unique constraint)
            streak = session.query(cls).filter(
                cls.player_id == player_id,
                cls.stat == stat,
                cls.season == season,
                cls.threshold == threshold
            ).first()
            
            if streak:
                # Update existing streak
                streak.streak_games = streak_games
                streak.created_at = datetime.utcnow()
                logger.info(f"Updated streak: {player_name} {stat} {threshold}+ ({streak_games} games)")
            else:
                # Create new streak
                streak = cls(
                    player_id=player_id,
                    player_name=player_name,
                    stat=stat,
                    threshold=threshold,
                    streak_games=streak_games,
                    season=season
                )
                session.add(streak)
                logger.info(f"Created new streak: {player_name} {stat} {threshold}+ ({streak_games} games)")
            
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
        """Bulk create or update streaks.
        
        Args:
            streaks: List of streak dictionaries with keys:
                    player_id, player_name, stat, threshold, streak_games, season
            db: Optional database session
            
        Returns:
            int: Number of streaks created/updated
        """
        def _bulk_create(session: Session) -> int:
            count = 0
            for streak_data in streaks:
                cls.create(
                    player_id=int(streak_data['player_id']),
                    player_name=streak_data['player_name'],
                    stat=streak_data['stat'],
                    threshold=int(streak_data['threshold']),
                    streak_games=int(streak_data['streak_games']),
                    season=streak_data['season'],
                    db=session
                )
                count += 1
            return count
        
        if db:
            return _bulk_create(db)
        
        with get_db_context() as session:
            count = _bulk_create(session)
            session.commit()
            logger.info(f"Bulk created/updated {count} player streaks")
            return count
    
    def update(self, streak_games: Optional[int] = None,
              db: Optional[Session] = None) -> 'PlayerStreaksORM':
        """Update streak information.
        
        Args:
            streak_games: New streak length
            db: Optional database session
            
        Returns:
            Self (updated PlayerStreaksORM object)
        """
        def _update(session: Session) -> 'PlayerStreaksORM':
            if streak_games is not None:
                self.streak_games = streak_games
                self.created_at = datetime.utcnow()
            
            session.flush()
            logger.info(f"Updated streak: {self.player_name} (ID: {self.id})")
            return self
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            if self not in session:
                self = session.merge(self)
            streak = _update(session)
            session.commit()
            return streak
    
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
            logger.info(f"Deleted streak: {self.player_name} (ID: {self.id})")
        
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
            logger.info("Cleared all player streaks from the database")
        
        if db:
            _clear(db)
        else:
            with get_db_context() as session:
                _clear(session)
                session.commit()


# Backward compatibility
def get_player_streaks_model():
    """Get the appropriate player streaks model (SQLAlchemy version).
    
    Returns:
        PlayerStreaksORM class
    """
    return PlayerStreaksORM

