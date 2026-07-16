"""SQLAlchemy ORM model for Statistics.

This module provides the StatisticsORM class which represents player season statistics
in the database using SQLAlchemy ORM.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 continued)
"""

from typing import Optional, List
from sqlalchemy import Column, Integer, String, ForeignKey, Index
from sqlalchemy.orm import Session, relationship

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class StatisticsORM(Base):
    """SQLAlchemy ORM model for player season statistics.
    
    This model represents aggregated statistics for a player in a given season.
    It maps to the 'statistics' table in the public schema.
    
    Attributes:
        stat_id: Unique identifier for the statistics entry (auto-generated)
        player_id: Reference to the player
        season_year: Season identifier (e.g., "2024-25")
        points: Total points scored
        rebounds: Total rebounds
        assists: Total assists
        steals: Total steals
        blocks: Total blocks
        
    Relationships:
        player: The player these statistics belong to
    """
    
    __tablename__ = 'statistics'
    __table_args__ = (
        Index('idx_statistics_player_id', 'player_id'),
        Index('idx_statistics_season', 'season_year'),
        Index('idx_statistics_player_season', 'player_id', 'season_year'),
        Index('idx_statistics_player_season_year', 'player_id', 'season_year'),
        Index('idx_statistics_season_year', 'season_year'),
        Index('idx_statistics_points', 'points'),
        Index('idx_statistics_rebounds', 'rebounds'),
        Index('idx_statistics_assists', 'assists'),
        Index('stats_player_season_idx', 'player_id', 'season_year'),
        Index('stats_season_idx', 'season_year'),
    )
    
    # Primary Key
    stat_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    
    # Statistics
    season_year = Column(String(10), nullable=True)
    points = Column(Integer, nullable=True)
    rebounds = Column(Integer, nullable=True)
    assists = Column(Integer, nullable=True)
    steals = Column(Integer, nullable=True)
    blocks = Column(Integer, nullable=True)
    
    # Relationships (when PlayerORM has relationship defined)
    # player = relationship("PlayerORM", back_populates="statistics")
    
    def __repr__(self) -> str:
        """String representation of the statistics."""
        return f"<StatisticsORM(stat_id={self.stat_id}, player_id={self.player_id}, season='{self.season_year}', pts={self.points})>"
    
    def to_dict(self) -> dict:
        """Convert statistics object to dictionary.
        
        Returns:
            dict: Dictionary representation of the statistics
        """
        return {
            'stat_id': self.stat_id,
            'player_id': self.player_id,
            'season_year': self.season_year,
            'points': self.points,
            'rebounds': self.rebounds,
            'assists': self.assists,
            'steals': self.steals,
            'blocks': self.blocks
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_id(cls, stat_id: int, db: Optional[Session] = None) -> Optional['StatisticsORM']:
        """Get statistics by ID.
        
        Args:
            stat_id: The statistics entry ID
            db: Optional database session
            
        Returns:
            StatisticsORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.stat_id == stat_id).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.stat_id == stat_id).first()
    
    @classmethod
    def get_by_player(cls, player_id: int, db: Optional[Session] = None) -> List['StatisticsORM']:
        """Get all statistics for a player, ordered by season.
        
        Args:
            player_id: The player's unique identifier
            db: Optional database session
            
        Returns:
            List of StatisticsORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.season_year.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.season_year.desc()).all()
    
    @classmethod
    def get_by_player_and_season(cls, player_id: int, season_year: str, db: Optional[Session] = None) -> Optional['StatisticsORM']:
        """Get statistics for a player in a specific season.
        
        Args:
            player_id: The player's unique identifier
            season_year: Season identifier (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            StatisticsORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season_year == season_year
            ).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season_year == season_year
            ).first()
    
    @classmethod
    def get_by_season(cls, season_year: str, db: Optional[Session] = None) -> List['StatisticsORM']:
        """Get all statistics for a specific season.
        
        Args:
            season_year: Season identifier (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of StatisticsORM objects
        """
        if db:
            return db.query(cls).filter(cls.season_year == season_year).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.season_year == season_year).all()
    
    @classmethod
    def exists_for_player(cls, player_id: int, db: Optional[Session] = None) -> bool:
        """Check if statistics exist for a player.
        
        Args:
            player_id: The player's unique identifier
            db: Optional database session
            
        Returns:
            True if statistics exist, False otherwise
        """
        if db:
            return db.query(cls).filter(cls.player_id == player_id).count() > 0
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.player_id == player_id).count() > 0
    
    @classmethod
    def get_player_ids_for_season(cls, season_year: str, db: Optional[Session] = None) -> List[int]:
        """Get all player IDs who have statistics for a specific season.
        
        Args:
            season_year: Season identifier (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of player IDs
        """
        if db:
            results = db.query(cls.player_id).filter(
                cls.season_year == season_year
            ).distinct().order_by(cls.player_id).all()
            return [r[0] for r in results]
        
        with get_db_context() as db:
            results = db.query(cls.player_id).filter(
                cls.season_year == season_year
            ).distinct().order_by(cls.player_id).all()
            return [r[0] for r in results]
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               player_id: int,
               season_year: str,
               points: Optional[int] = None,
               rebounds: Optional[int] = None,
               assists: Optional[int] = None,
               steals: Optional[int] = None,
               blocks: Optional[int] = None,
               db: Optional[Session] = None) -> 'StatisticsORM':
        """Create new statistics or update if exists (upsert).
        
        Args:
            player_id: Player's unique identifier
            season_year: Season identifier
            points: Total points scored
            rebounds: Total rebounds
            assists: Total assists
            steals: Total steals
            blocks: Total blocks
            db: Optional database session
            
        Returns:
            StatisticsORM: The created or updated statistics object
        """
        def _create(session: Session) -> 'StatisticsORM':
            # Check if statistics exists
            stats = session.query(cls).filter(
                cls.player_id == player_id,
                cls.season_year == season_year
            ).first()
            
            if stats:
                # Update existing statistics
                if points is not None:
                    stats.points = points
                if rebounds is not None:
                    stats.rebounds = rebounds
                if assists is not None:
                    stats.assists = assists
                if steals is not None:
                    stats.steals = steals
                if blocks is not None:
                    stats.blocks = blocks
                logger.info(f"Updated statistics for player {player_id}, season {season_year}")
            else:
                # Create new statistics
                stats = cls(
                    player_id=player_id,
                    season_year=season_year,
                    points=points,
                    rebounds=rebounds,
                    assists=assists,
                    steals=steals,
                    blocks=blocks
                )
                session.add(stats)
                logger.info(f"Created statistics for player {player_id}, season {season_year}")
            
            session.flush()
            return stats
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            stats = _create(session)
            session.commit()
            return stats
    
    def update(self,
               points: Optional[int] = None,
               rebounds: Optional[int] = None,
               assists: Optional[int] = None,
               steals: Optional[int] = None,
               blocks: Optional[int] = None,
               db: Optional[Session] = None) -> 'StatisticsORM':
        """Update statistics.
        
        Args:
            points: New points value
            rebounds: New rebounds value
            assists: New assists value
            steals: New steals value
            blocks: New blocks value
            db: Optional database session
            
        Returns:
            Self (updated StatisticsORM object)
        """
        def _update(session: Session) -> 'StatisticsORM':
            if points is not None:
                self.points = points
            if rebounds is not None:
                self.rebounds = rebounds
            if assists is not None:
                self.assists = assists
            if steals is not None:
                self.steals = steals
            if blocks is not None:
                self.blocks = blocks
            
            session.flush()
            logger.info(f"Updated statistics: player {self.player_id}, season {self.season_year}")
            return self
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            if self not in session:
                self = session.merge(self)
            stats = _update(session)
            session.commit()
            return stats
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this statistics entry from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted statistics: player {self.player_id}, season {self.season_year}")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility function
def get_statistics_model():
    """Get the appropriate statistics model (SQLAlchemy version).
    
    Returns:
        StatisticsORM class
    """
    return StatisticsORM

