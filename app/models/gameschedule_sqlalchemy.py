"""SQLAlchemy ORM model for GameSchedule.

This module provides the GameScheduleORM class which represents NBA game
schedules and results in the database using SQLAlchemy ORM. It maintains
backward compatibility with the existing psycopg2-based GameSchedule class.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 continued)
"""

from typing import Optional, List
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, PrimaryKeyConstraint, CheckConstraint
from sqlalchemy.orm import Session, relationship

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class GameScheduleORM(Base):
    """SQLAlchemy ORM model for game schedules.
    
    This model represents NBA game schedules and results.
    It maps to the 'game_schedule' table in the public schema.
    
    Attributes:
        game_id: Game identifier
        season: Season year (e.g., "2023-24")
        team_id: Team identifier (FK to teams)
        opponent_team_id: Opponent team identifier (FK to teams)
        game_date: Timestamp of the game
        home_or_away: Home ('H') or Away ('A') indicator
        result: Game result ('W', 'L', or None for unplayed)
        score: Final score string (e.g., "110-105")
        
    Relationships:
        team: The team for this schedule entry
        opponent: The opposing team
    """
    
    __tablename__ = 'game_schedule'
    __table_args__ = (
        PrimaryKeyConstraint('game_id', 'team_id'),
        CheckConstraint("home_or_away IN ('H', 'A')", name='game_schedule_home_or_away_check'),
        CheckConstraint("result IN ('W', 'L') OR result IS NULL", name='game_schedule_result_check'),
        Index('idx_game_schedule_game_id', 'game_id'),
        Index('idx_game_schedule_team_id', 'team_id'),
        Index('idx_game_schedule_game_date', 'game_date'),
        Index('idx_game_schedule_season', 'season'),
    )
    
    # Primary Key (composite)
    game_id = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    
    # Foreign Keys
    opponent_team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    
    # Game Information
    season = Column(String, nullable=False)
    game_date = Column(DateTime, nullable=False)
    home_or_away = Column(String(1), nullable=False)
    result = Column(String(1), nullable=True)
    score = Column(String, nullable=True)
    
    # Relationships (will be defined when team model is available)
    # team = relationship("TeamORM", foreign_keys=[team_id], back_populates="schedule")
    # opponent = relationship("TeamORM", foreign_keys=[opponent_team_id])
    
    def __repr__(self) -> str:
        """String representation of the game schedule."""
        return (f"<GameScheduleORM(game_id='{self.game_id}', team_id={self.team_id}, "
                f"date={self.game_date}, result={self.result})>")
    
    def to_dict(self) -> dict:
        """Convert game schedule object to dictionary.
        
        Returns:
            dict: Dictionary representation of the game schedule
        """
        return {
            'game_id': self.game_id,
            'season': self.season,
            'team_id': self.team_id,
            'opponent_team_id': self.opponent_team_id,
            'game_date': self.game_date.isoformat() if self.game_date else None,
            'home_or_away': self.home_or_away,
            'result': self.result,
            'score': self.score
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_game_and_team(cls, game_id: str, team_id: int,
                            db: Optional[Session] = None) -> Optional['GameScheduleORM']:
        """Get game schedule for a specific game and team.
        
        Args:
            game_id: The game identifier
            team_id: The team identifier
            db: Optional database session
            
        Returns:
            GameScheduleORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
    
    @classmethod
    def get_by_team(cls, team_id: int, season: Optional[str] = None,
                   db: Optional[Session] = None) -> List['GameScheduleORM']:
        """Get all games for a team.
        
        Args:
            team_id: The team identifier
            season: Optional season filter
            db: Optional database session
            
        Returns:
            List of GameScheduleORM objects
        """
        def _query(session: Session):
            query = session.query(cls).filter(cls.team_id == team_id)
            if season:
                query = query.filter(cls.season == season)
            return query.order_by(cls.game_date.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_by_date(cls, game_date: date, db: Optional[Session] = None) -> List[dict]:
        """Get all games for a specific date with team information.
        
        Args:
            game_date: Date to filter by
            db: Optional database session
            
        Returns:
            List of game dictionaries with team details
        """
        from app.models.team_sqlalchemy import TeamORM
        
        def _query(session: Session):
            results = (
                session.query(
                    cls,
                    TeamORM.name.label('team_name'),
                    TeamORM.abbreviation.label('team_abbreviation')
                )
                .join(TeamORM, cls.team_id == TeamORM.team_id)
                .filter(cls.game_date >= game_date)
                .filter(cls.game_date < datetime.combine(game_date, datetime.max.time()))
                .order_by(cls.game_date)
                .all()
            )
            
            # Get opponent information
            games = []
            for schedule, team_name, team_abbr in results:
                opponent = session.query(TeamORM).filter(
                    TeamORM.team_id == schedule.opponent_team_id
                ).first()
                
                game_dict = schedule.to_dict()
                game_dict['team_name'] = team_name
                game_dict['team_abbreviation'] = team_abbr
                if opponent:
                    game_dict['opponent_name'] = opponent.name
                    game_dict['opponent_abbreviation'] = opponent.abbreviation
                
                games.append(game_dict)
            
            return games
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_opponent_team_id(cls, game_id: str, team_id: int,
                            db: Optional[Session] = None) -> Optional[int]:
        """Get the opponent team ID for a game.
        
        Args:
            game_id: The game identifier
            team_id: The team identifier
            db: Optional database session
            
        Returns:
            Opponent team ID if found, None otherwise
        """
        if db:
            schedule = db.query(cls.opponent_team_id).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
            return schedule[0] if schedule else None
        
        with get_db_context() as db:
            schedule = db.query(cls.opponent_team_id).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
            return schedule[0] if schedule else None
    
    @classmethod
    def get_last_n_games(cls, team_id: int, n: int = 10,
                        db: Optional[Session] = None) -> List[dict]:
        """Get the last N completed games for a team.
        
        Args:
            team_id: The team identifier
            n: Number of games to return
            db: Optional database session
            
        Returns:
            List of game dictionaries with full details
        """
        from app.models.team_sqlalchemy import TeamORM
        
        def _query(session: Session):
            # Get games where this team played
            today = date.today()
            games = (
                session.query(cls)
                .filter(cls.team_id == team_id)
                .filter(cls.game_date < datetime.combine(today, datetime.min.time()))
                .filter(cls.result.isnot(None))
                .order_by(cls.game_date.desc())
                .limit(n)
                .all()
            )
            
            results = []
            for game in games:
                # Get team info
                team = session.query(TeamORM).filter(TeamORM.team_id == game.team_id).first()
                opponent = session.query(TeamORM).filter(TeamORM.team_id == game.opponent_team_id).first()
                
                game_dict = game.to_dict()
                if team:
                    game_dict['team_name'] = team.name
                    game_dict['team_abbreviation'] = team.abbreviation
                if opponent:
                    game_dict['opponent_name'] = opponent.name
                    game_dict['opponent_abbreviation'] = opponent.abbreviation
                
                # Determine home/away teams
                if game.home_or_away == 'H':
                    game_dict['home_team_id'] = game.team_id
                    game_dict['home_team_name'] = team.name if team else None
                    game_dict['home_team_abbr'] = team.abbreviation if team else None
                    game_dict['away_team_id'] = game.opponent_team_id
                    game_dict['away_team_name'] = opponent.name if opponent else None
                    game_dict['away_team_abbr'] = opponent.abbreviation if opponent else None
                else:
                    game_dict['home_team_id'] = game.opponent_team_id
                    game_dict['home_team_name'] = opponent.name if opponent else None
                    game_dict['home_team_abbr'] = opponent.abbreviation if opponent else None
                    game_dict['away_team_id'] = game.team_id
                    game_dict['away_team_name'] = team.name if team else None
                    game_dict['away_team_abbr'] = team.abbreviation if team else None
                
                results.append(game_dict)
            
            return results
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_upcoming_n_games(cls, team_id: int, n: int = 5,
                            db: Optional[Session] = None) -> List[dict]:
        """Get the next N upcoming games for a team.
        
        Args:
            team_id: The team identifier
            n: Number of games to return
            db: Optional database session
            
        Returns:
            List of game dictionaries with full details
        """
        from app.models.team_sqlalchemy import TeamORM
        
        def _query(session: Session):
            today = date.today()
            games = (
                session.query(cls)
                .filter(cls.team_id == team_id)
                .filter(cls.game_date >= datetime.combine(today, datetime.min.time()))
                .order_by(cls.game_date.asc())
                .limit(n)
                .all()
            )
            
            results = []
            for game in games:
                # Get team info
                team = session.query(TeamORM).filter(TeamORM.team_id == game.team_id).first()
                opponent = session.query(TeamORM).filter(TeamORM.team_id == game.opponent_team_id).first()
                
                game_dict = game.to_dict()
                if team:
                    game_dict['team_name'] = team.name
                    game_dict['team_abbreviation'] = team.abbreviation
                if opponent:
                    game_dict['opponent_name'] = opponent.name
                    game_dict['opponent_abbreviation'] = opponent.abbreviation
                
                # Determine home/away teams
                if game.home_or_away == 'H':
                    game_dict['home_team_id'] = game.team_id
                    game_dict['home_team_name'] = team.name if team else None
                    game_dict['home_team_abbr'] = team.abbreviation if team else None
                    game_dict['away_team_id'] = game.opponent_team_id
                    game_dict['away_team_name'] = opponent.name if opponent else None
                    game_dict['away_team_abbr'] = opponent.abbreviation if opponent else None
                else:
                    game_dict['home_team_id'] = game.opponent_team_id
                    game_dict['home_team_name'] = opponent.name if opponent else None
                    game_dict['home_team_abbr'] = opponent.abbreviation if opponent else None
                    game_dict['away_team_id'] = game.team_id
                    game_dict['away_team_name'] = team.name if team else None
                    game_dict['away_team_abbr'] = team.abbreviation if team else None
                
                results.append(game_dict)
            
            return results
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               game_id: str,
               season: str,
               team_id: int,
               opponent_team_id: int,
               game_date: datetime,
               home_or_away: str,
               result: Optional[str] = None,
               score: Optional[str] = None,
               db: Optional[Session] = None) -> 'GameScheduleORM':
        """Create a new game schedule or update if exists (upsert).
        
        Args:
            game_id: Game identifier
            season: Season year
            team_id: Team identifier
            opponent_team_id: Opponent team identifier
            game_date: Game date and time
            home_or_away: 'H' for home, 'A' for away
            result: 'W' for win, 'L' for loss, None for unplayed
            score: Final score string
            db: Optional database session
            
        Returns:
            GameScheduleORM: The created or updated game schedule object
        """
        def _create(session: Session) -> 'GameScheduleORM':
            # Check if schedule exists
            schedule = session.query(cls).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
            
            if schedule:
                # Update existing schedule
                schedule.season = season
                schedule.opponent_team_id = opponent_team_id
                schedule.game_date = game_date
                schedule.home_or_away = home_or_away
                schedule.result = result
                schedule.score = score
                logger.info(f"Updated game schedule: Game {game_id}, Team {team_id}")
            else:
                # Create new schedule
                schedule = cls(
                    game_id=game_id,
                    season=season,
                    team_id=team_id,
                    opponent_team_id=opponent_team_id,
                    game_date=game_date,
                    home_or_away=home_or_away,
                    result=result,
                    score=score
                )
                session.add(schedule)
                logger.info(f"Created new game schedule: Game {game_id}, Team {team_id}")
            
            session.flush()
            return schedule
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            schedule = _create(session)
            session.commit()
            return schedule
    
    @classmethod
    def bulk_create(cls, schedules: List[dict], db: Optional[Session] = None) -> int:
        """Bulk create or update game schedules.
        
        Args:
            schedules: List of schedule dictionaries
            db: Optional database session
            
        Returns:
            int: Number of schedules created/updated
        """
        def _bulk_create(session: Session) -> int:
            from sqlalchemy.exc import IntegrityError
            count = 0
            skipped = 0
            
            # Process each schedule individually to handle errors gracefully
            for schedule_data in schedules:
                try:
                    cls.create(
                        game_id=schedule_data['game_id'],
                        season=schedule_data['season'],
                        team_id=schedule_data['team_id'],
                        opponent_team_id=schedule_data['opponent_team_id'],
                        game_date=schedule_data['game_date'],
                        home_or_away=schedule_data['home_or_away'],
                        result=schedule_data.get('result'),
                        score=schedule_data.get('score'),
                        db=session
                    )
                    count += 1
                except IntegrityError as e:
                    # Handle foreign key violations or duplicate key errors gracefully
                    session.rollback()  # Rollback this specific item's transaction
                    if 'foreign key' in str(e).lower():
                        skipped += 1
                        logger.debug(f"Skipping schedule with invalid team_id or opponent_team_id: "
                                   f"game_id={schedule_data.get('game_id')}, "
                                   f"team_id={schedule_data.get('team_id')}, "
                                   f"opponent_team_id={schedule_data.get('opponent_team_id')}")
                    else:
                        skipped += 1
                        logger.warning(f"Skipping schedule due to integrity error "
                                     f"(game_id={schedule_data.get('game_id')}): {e}")
                except Exception as e:
                    # Log other errors but continue with remaining schedules
                    session.rollback()  # Rollback this specific item's transaction
                    skipped += 1
                    logger.error(f"Error creating schedule (game_id={schedule_data.get('game_id')}): {e}")
            
            # Final flush for any remaining pending changes
            try:
                session.flush()
                if skipped > 0:
                    logger.info(f"Bulk created/updated {count} game schedules, skipped {skipped} due to errors")
                else:
                    logger.info(f"Bulk created/updated {count} game schedules")
            except Exception as e:
                logger.error(f"Error flushing game schedules: {e}")
                session.rollback()
                raise
            
            return count
        
        if db:
            return _bulk_create(db)
        
        with get_db_context() as session:
            count = _bulk_create(session)
            session.commit()
            return count
    
    def update(self,
              result: Optional[str] = None,
              score: Optional[str] = None,
              db: Optional[Session] = None) -> 'GameScheduleORM':
        """Update game schedule (typically result and score after game completion).
        
        Args:
            result: 'W' or 'L'
            score: Final score
            db: Optional database session
            
        Returns:
            Self (updated GameScheduleORM object)
        """
        def _update(session: Session) -> 'GameScheduleORM':
            if result is not None:
                self.result = result
            if score is not None:
                self.score = score
            
            session.flush()
            logger.info(f"Updated game schedule: Game {self.game_id}, Team {self.team_id}")
            return self
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            if self not in session:
                self = session.merge(self)
            schedule = _update(session)
            session.commit()
            return schedule
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this game schedule from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted game schedule: Game {self.game_id}, Team {self.team_id}")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility
def get_game_schedule_model():
    """Get the appropriate game schedule model (SQLAlchemy version).
    
    Returns:
        GameScheduleORM class
    """
    return GameScheduleORM

