"""SQLAlchemy ORM models for Team and Roster.

This module provides the TeamORM and RosterORM classes which represent basketball
teams and their roster assignments in the database using SQLAlchemy ORM.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2)
"""

from typing import Optional, List, Dict
from sqlalchemy import CheckConstraint, Column, Integer, String, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Session, relationship
from sqlalchemy.dialects.postgresql import VARCHAR

from app.database import Base, get_db_context
from app.utils.config_utils import logger
from app.utils.season_utils import normalize_season


class TeamORM(Base):
    """SQLAlchemy ORM model for NBA teams.
    
    This model represents a professional basketball team.
    It maps to the 'teams' table in the public schema.
    
    Attributes:
        team_id: Unique identifier for the team (NBA API ID)
        name: Full team name (e.g., "Los Angeles Lakers")
        abbreviation: Short team code (e.g., "LAL")
        
    Relationships:
        roster_entries: Players on this team's roster
    """
    
    __tablename__ = 'teams'
    
    # Primary Key
    team_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Team Information
    name = Column(String(255), nullable=True)
    abbreviation = Column(VARCHAR(10), nullable=True)
    
    # Relationships
    roster_entries = relationship("RosterORM", back_populates="team", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        """String representation of the team."""
        return f"<TeamORM(team_id={self.team_id}, name='{self.name}', abbreviation='{self.abbreviation}')>"
    
    def to_dict(self, include_roster: bool = False) -> dict:
        """Convert team object to dictionary.
        
        Args:
            include_roster: Whether to include roster data
            
        Returns:
            dict: Dictionary representation of the team
        """
        result = {
            'team_id': self.team_id,
            'name': self.name,
            'abbreviation': self.abbreviation
        }
        
        if include_roster:
            result['roster'] = [entry.to_dict() for entry in self.roster_entries]
        
        return result
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_id(cls, team_id: int, db: Optional[Session] = None) -> Optional['TeamORM']:
        """Get a team by its ID.
        
        Args:
            team_id: The team's unique identifier
            db: Optional database session
            
        Returns:
            TeamORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.team_id == team_id).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.team_id == team_id).first()
    
    @classmethod
    def get_by_abbreviation(cls, abbreviation: str, db: Optional[Session] = None) -> Optional['TeamORM']:
        """Get a team by its abbreviation.
        
        Args:
            abbreviation: Team abbreviation (e.g., "LAL")
            db: Optional database session
            
        Returns:
            TeamORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(cls.abbreviation == abbreviation).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.abbreviation == abbreviation).first()
    
    @classmethod
    def get_all(cls, db: Optional[Session] = None) -> List['TeamORM']:
        """Get all teams from the database, ordered by name.
        
        Args:
            db: Optional database session
            
        Returns:
            List of TeamORM objects
        """
        if db:
            return db.query(cls).order_by(cls.name).all()
        
        with get_db_context() as db:
            return db.query(cls).order_by(cls.name).all()
    
    @classmethod
    def get_by_ids(cls, team_ids: List[int], db: Optional[Session] = None) -> List['TeamORM']:
        """Get multiple teams by their IDs.
        
        Args:
            team_ids: List of team IDs
            db: Optional database session
            
        Returns:
            List of TeamORM objects
        """
        if db:
            return db.query(cls).filter(cls.team_id.in_(team_ids)).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.team_id.in_(team_ids)).all()
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               name: str,
               abbreviation: str,
               team_id: Optional[int] = None,
               db: Optional[Session] = None) -> 'TeamORM':
        """Create a new team.
        
        Args:
            name: Team's full name
            abbreviation: Team's short code
            team_id: Optional specific team ID (for NBA API compatibility)
            db: Optional database session
            
        Returns:
            TeamORM: The created team object
        """
        def _create(session: Session) -> 'TeamORM':
            team = cls(
                name=name,
                abbreviation=abbreviation
            )
            if team_id is not None:
                team.team_id = team_id
            
            session.add(team)
            session.flush()
            logger.info(f"Created new team: {name} ({abbreviation})")
            return team
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            team = _create(session)
            session.commit()
            return team
    
    def update(self,
               name: Optional[str] = None,
               abbreviation: Optional[str] = None,
               db: Optional[Session] = None) -> 'TeamORM':
        """Update team information.
        
        Args:
            name: New team name
            abbreviation: New abbreviation
            db: Optional database session
            
        Returns:
            Self (updated TeamORM object)
        """
        def _update(session: Session) -> 'TeamORM':
            if name is not None:
                self.name = name
            if abbreviation is not None:
                self.abbreviation = abbreviation
            
            session.flush()
            logger.info(f"Updated team: {self.name} (ID: {self.team_id})")
            return self
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            if self not in session:
                self = session.merge(self)
            team = _update(session)
            session.commit()
            return team
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this team from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted team: {self.name} (ID: {self.team_id})")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()
    
    # ==================== Roster Management ====================
    
    def get_roster(self, season: Optional[str] = None, db: Optional[Session] = None) -> List['RosterORM']:
        """Get the team's roster.
        
        Args:
            season: Optional season filter (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of RosterORM objects
        """
        if db:
            query = db.query(RosterORM).filter(RosterORM.team_id == self.team_id)
            if season:
                query = query.filter(RosterORM.season == season)
            return query.all()
        
        with get_db_context() as session:
            query = session.query(RosterORM).filter(RosterORM.team_id == self.team_id)
            if season:
                query = query.filter(RosterORM.season == season)
            return query.all()
    
    def add_to_roster(self,
                      player_id: int,
                      player_name: str,
                      season: str,
                      player_number: Optional[int] = None,
                      position: Optional[str] = None,
                      how_acquired: Optional[str] = None,
                      db: Optional[Session] = None) -> 'RosterORM':
        """Add a player to this team's roster.
        
        Args:
            player_id: The player's ID
            player_name: The player's name
            season: The season (e.g., "2024-25")
            player_number: Jersey number
            position: Player position
            how_acquired: How the player was acquired
            db: Optional database session
            
        Returns:
            RosterORM: The roster entry
        """
        return RosterORM.create(
            team_id=self.team_id,
            player_id=player_id,
            player_name=player_name,
            season=season,
            player_number=player_number,
            position=position,
            how_acquired=how_acquired,
            db=db
        )
    
    def clear_roster(self, season: Optional[str] = None, db: Optional[Session] = None) -> None:
        """Clear one explicitly named team-season roster.
        
        Args:
            season: Optional season filter (clears only that season)
            db: Optional database session
        """
        if season is None:
            raise ValueError("season is required; clearing all roster history is prohibited")
        season = normalize_season(season)

        def _clear(session: Session) -> None:
            query = session.query(RosterORM).filter(RosterORM.team_id == self.team_id)
            query = query.filter(RosterORM.season == season)
            count = query.delete()
            session.flush()
            logger.info(f"Cleared {count} players from {self.name} roster" + 
                       (f" for season {season}" if season else ""))
        
        if db:
            _clear(db)
        else:
            with get_db_context() as session:
                _clear(session)
                session.commit()


class RosterORM(Base):
    """SQLAlchemy ORM model for team roster entries.
    
    This model represents a player's assignment to a team for a specific season.
    It's an association table with additional data (player number, position, etc.).
    Maps to the 'roster' table in the public schema.
    
    Attributes:
        team_id: Reference to the team
        player_id: Reference to the player
        player_name: Player's name (denormalized for convenience)
        player_number: Jersey number
        position: Player's position on this team
        how_acquired: How the team acquired the player
        season: Season for this roster entry (e.g., "2024-25")
        
    Relationships:
        team: The team this roster entry belongs to
        player: The player in this roster entry
    """
    
    __tablename__ = 'roster'
    __table_args__ = (
        PrimaryKeyConstraint('team_id', 'player_id', 'season'),
        CheckConstraint(
            "season ~ '^[0-9]{4}-[0-9]{2}$'",
            name='ck_roster_season_canonical',
        ),
    )
    
    # Composite Primary Key
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    season = Column(VARCHAR(10), nullable=False)
    
    # Roster Information
    player_name = Column(String(255), nullable=True)
    player_number = Column(Integer, nullable=True)
    position = Column(VARCHAR(50), nullable=True)
    how_acquired = Column(String(255), nullable=True)
    
    # Relationships
    team = relationship("TeamORM", back_populates="roster_entries")
    # player = relationship("PlayerORM", back_populates="roster_entries")  # Uncomment when PlayerORM has relationship
    
    def __repr__(self) -> str:
        """String representation of the roster entry."""
        return f"<RosterORM(team_id={self.team_id}, player={self.player_name}, season='{self.season}')>"
    
    def to_dict(self) -> dict:
        """Convert roster entry to dictionary.
        
        Returns:
            dict: Dictionary representation of the roster entry
        """
        return {
            'team_id': self.team_id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'player_number': self.player_number,
            'position': self.position,
            'how_acquired': self.how_acquired,
            'season': self.season
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_player(cls, player_id: int, db: Optional[Session] = None) -> List['RosterORM']:
        """Get all roster entries for a player.
        
        Args:
            player_id: The player's ID
            db: Optional database session
            
        Returns:
            List of RosterORM objects
        """
        if db:
            return db.query(cls).filter(cls.player_id == player_id).order_by(cls.season.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.player_id == player_id).order_by(cls.season.desc()).all()
    
    @classmethod
    def get_by_team_and_season(cls, team_id: int, season: str, db: Optional[Session] = None) -> List['RosterORM']:
        """Get roster for a specific team and season.
        
        Args:
            team_id: The team's ID
            season: The season (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of RosterORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season
            ).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season
            ).all()
    
    @classmethod
    def get_current_team(cls, player_id: int, db: Optional[Session] = None) -> Optional['RosterORM']:
        """Get player's most recent team.
        
        Args:
            player_id: The player's ID
            db: Optional database session
            
        Returns:
            RosterORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.season.desc()).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id
            ).order_by(cls.season.desc()).first()
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               team_id: int,
               player_id: int,
               season: str,
               player_name: str,
               player_number: Optional[int] = None,
               position: Optional[str] = None,
               how_acquired: Optional[str] = None,
               db: Optional[Session] = None) -> 'RosterORM':
        """Create a new roster entry or update if exists (upsert).
        
        Args:
            team_id: Team ID
            player_id: Player ID
            season: Season (e.g., "2024-25")
            player_name: Player's name
            player_number: Jersey number
            position: Player's position
            how_acquired: How player was acquired
            db: Optional database session
            
        Returns:
            RosterORM: The created or updated roster entry
        """
        season = normalize_season(season)

        def _create(session: Session) -> 'RosterORM':
            # Check if roster entry exists
            roster_entry = session.query(cls).filter(
                cls.team_id == team_id,
                cls.player_id == player_id,
                cls.season == season
            ).first()
            
            if roster_entry:
                # Update existing entry
                roster_entry.player_name = player_name
                roster_entry.player_number = player_number
                roster_entry.position = position
                roster_entry.how_acquired = how_acquired
                logger.info(f"Updated roster entry: {player_name} on team {team_id} for {season}")
            else:
                # Create new entry
                roster_entry = cls(
                    team_id=team_id,
                    player_id=player_id,
                    season=season,
                    player_name=player_name,
                    player_number=player_number,
                    position=position,
                    how_acquired=how_acquired
                )
                session.add(roster_entry)
                logger.info(f"Created roster entry: {player_name} on team {team_id} for {season}")
            
            session.flush()
            return roster_entry
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            entry = _create(session)
            session.commit()
            return entry
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this roster entry from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted roster entry: {self.player_name} from team {self.team_id} ({self.season})")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility functions
def get_team_model():
    """Get the appropriate team model (SQLAlchemy version).
    
    Returns:
        TeamORM class
    """
    return TeamORM


def get_roster_model():
    """Get the appropriate roster model (SQLAlchemy version).
    
    Returns:
        RosterORM class
    """
    return RosterORM

