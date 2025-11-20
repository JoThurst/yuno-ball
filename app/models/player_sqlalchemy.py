"""SQLAlchemy ORM model for Player.

This module provides the PlayerORM class which represents a basketball player
in the database using SQLAlchemy ORM. It maintains backward compatibility with
the existing psycopg2-based Player class.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2)
"""

from typing import Optional, List
from datetime import date
from sqlalchemy import Column, Integer, String, Date, ARRAY, Text, Index
from sqlalchemy.orm import Session, relationship
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class PlayerORM(Base):
    """SQLAlchemy ORM model for NBA players.
    
    This model represents a basketball player with their biographical information
    and available seasons. It maps to the 'players' table in the public schema.
    
    Attributes:
        player_id: Unique identifier for the player (NBA API ID)
        name: Full name of the player
        position: Playing position (PG, SG, SF, PF, C, G, F, etc.)
        weight: Player weight in pounds
        born_date: Birth date of the player
        age: Current age of the player
        exp: Years of NBA experience
        school: Last school/college attended
        available_seasons: Array of seasons the player has data for
        
    Relationships:
        roster_entries: Roster assignments (team memberships) for this player
        statistics: Career statistics for this player
        gamelogs: Game-by-game performance logs
    """
    
    __tablename__ = 'players'
    __table_args__ = (
        Index('idx_players_name', 'name'),
        Index('idx_players_position', 'position'),
        Index('idx_players_seasons', 'available_seasons', postgresql_using='gin'),
        Index('player_id_idx', 'player_id'),
        Index('player_name_idx', 'name'),
    )
    
    # Primary Key
    player_id = Column(Integer, primary_key=True, autoincrement=False)
    
    # Player Information
    name = Column(String(255), nullable=False)
    position = Column(String(50), nullable=True)
    weight = Column(Integer, nullable=True)
    born_date = Column(Date, nullable=True)
    age = Column(Integer, nullable=True)
    exp = Column(Integer, nullable=True)  # Years of experience
    school = Column(String(255), nullable=True)
    available_seasons = Column(PG_ARRAY(Text), nullable=True)
    
    # Relationships (will be defined when other models are converted)
    # roster_entries = relationship("RosterORM", back_populates="player")
    # statistics = relationship("StatisticsORM", back_populates="player")
    # gamelogs = relationship("GameLogORM", back_populates="player")
    
    def __repr__(self) -> str:
        """String representation of the player."""
        return f"<PlayerORM(player_id={self.player_id}, name='{self.name}', position='{self.position}')>"
    
    def to_dict(self) -> dict:
        """Convert player object to dictionary.
        
        Returns:
            dict: Dictionary representation of the player
        """
        # Handle born_date - might be date object or string from database
        born_date_str = None
        if self.born_date:
            if hasattr(self.born_date, 'isoformat'):
                born_date_str = self.born_date.isoformat()
            else:
                born_date_str = str(self.born_date)
        
        return {
            'player_id': self.player_id,
            'name': self.name,
            'position': self.position,
            'weight': self.weight,
            'born_date': born_date_str,
            'age': self.age,
            'exp': self.exp,
            'school': self.school,
            'available_seasons': self.available_seasons
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_id(cls, player_id: int, db: Optional[Session] = None) -> Optional['PlayerORM']:
        """Get a player by their ID.
        
        Args:
            player_id: The player's unique identifier
            db: Optional database session (creates one if not provided)
            
        Returns:
            PlayerORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.player_id == player_id).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.player_id == player_id).first()
    
    @classmethod
    def get_by_name(cls, name: str, db: Optional[Session] = None) -> Optional['PlayerORM']:
        """Get a player by their name (case-insensitive).
        
        Args:
            name: Player's name to search for
            db: Optional database session
            
        Returns:
            PlayerORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.name.ilike(f"%{name}%")).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.name.ilike(f"%{name}%")).first()
    
    @classmethod
    def get_all(cls, db: Optional[Session] = None) -> List['PlayerORM']:
        """Get all players from the database, ordered by name.
        
        Args:
            db: Optional database session
            
        Returns:
            List of PlayerORM objects
        """
        if db:
            return db.query(cls).order_by(cls.name).all()
        
        with get_db_context() as db:
            return db.query(cls).order_by(cls.name).all()
    
    @classmethod
    def get_by_position(cls, position: str, db: Optional[Session] = None) -> List['PlayerORM']:
        """Get all players at a specific position.
        
        Args:
            position: Player position (PG, SG, SF, PF, C)
            db: Optional database session
            
        Returns:
            List of PlayerORM objects at that position
        """
        if db:
            return db.query(cls).filter(cls.position == position).order_by(cls.name).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.position == position).order_by(cls.name).all()
    
    @classmethod
    def exists(cls, player_id: int, db: Optional[Session] = None) -> bool:
        """Check if a player exists in the database.
        
        Args:
            player_id: The player's unique identifier
            db: Optional database session
            
        Returns:
            True if player exists, False otherwise
        """
        if db:
            return db.query(cls).filter(cls.player_id == player_id).count() > 0
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.player_id == player_id).count() > 0
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               player_id: int,
               name: str,
               position: Optional[str] = None,
               weight: Optional[int] = None,
               born_date: Optional[date] = None,
               age: Optional[int] = None,
               exp: Optional[int] = None,
               school: Optional[str] = None,
               available_seasons: Optional[List[str]] = None,
               db: Optional[Session] = None) -> 'PlayerORM':
        """Create a new player or update if exists (upsert).
        
        Args:
            player_id: Unique player identifier
            name: Player's full name
            position: Player's position
            weight: Player's weight in pounds
            born_date: Player's birth date
            age: Player's current age
            exp: Years of experience
            school: Last school attended
            available_seasons: List of seasons with data
            db: Optional database session
            
        Returns:
            PlayerORM: The created or updated player object
        """
        def _create(session: Session) -> 'PlayerORM':
            # Check if player exists
            player = session.query(cls).filter(cls.player_id == player_id).first()
            
            if player:
                # Update existing player
                player.name = name
                player.position = position
                player.weight = weight
                player.born_date = born_date
                player.age = age
                player.exp = exp
                player.school = school
                player.available_seasons = available_seasons
                logger.info(f"Updated player: {name} (ID: {player_id})")
            else:
                # Create new player
                player = cls(
                    player_id=player_id,
                    name=name,
                    position=position,
                    weight=weight,
                    born_date=born_date,
                    age=age,
                    exp=exp,
                    school=school,
                    available_seasons=available_seasons
                )
                session.add(player)
                logger.info(f"Created new player: {name} (ID: {player_id})")
            
            session.flush()
            return player
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            player = _create(session)
            session.commit()
            return player
    
    def update(self,
               name: Optional[str] = None,
               position: Optional[str] = None,
               weight: Optional[int] = None,
               born_date: Optional[date] = None,
               age: Optional[int] = None,
               exp: Optional[int] = None,
               school: Optional[str] = None,
               available_seasons: Optional[List[str]] = None,
               db: Optional[Session] = None) -> 'PlayerORM':
        """Update player information.
        
        Args:
            name: New name (if changing)
            position: New position
            weight: New weight
            born_date: New birth date
            age: New age
            exp: New experience years
            school: New school
            available_seasons: New seasons list
            db: Optional database session
            
        Returns:
            Self (updated PlayerORM object)
        """
        def _update(session: Session) -> 'PlayerORM':
            if name is not None:
                self.name = name
            if position is not None:
                self.position = position
            if weight is not None:
                self.weight = weight
            if born_date is not None:
                self.born_date = born_date
            if age is not None:
                self.age = age
            if exp is not None:
                self.exp = exp
            if school is not None:
                self.school = school
            if available_seasons is not None:
                self.available_seasons = available_seasons
            
            session.flush()
            logger.info(f"Updated player: {self.name} (ID: {self.player_id})")
            return self
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            # Merge this object into the session if it's detached
            if self not in session:
                self = session.merge(self)
            player = _update(session)
            session.commit()
            return player
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this player from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted player: {self.name} (ID: {self.player_id})")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility functions
def get_player_model():
    """Get the appropriate player model (SQLAlchemy version).
    
    Returns:
        PlayerORM class
    """
    return PlayerORM

