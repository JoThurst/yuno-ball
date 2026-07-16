"""SQLAlchemy ORM model for GameSchedule.

This module provides the GameScheduleORM class which represents NBA game
schedules and results in the database using SQLAlchemy ORM. It maintains
backward compatibility with the existing psycopg2-based GameSchedule class.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 continued)
"""

from typing import Optional, List
from datetime import datetime, date
from sqlalchemy import BigInteger, Column, Integer, String, DateTime, ForeignKey, Index, PrimaryKeyConstraint, CheckConstraint, func, text
from sqlalchemy.orm import Session, relationship

from app.database import Base, get_db_context
from app.utils.config_utils import logger
from app.utils.season_utils import season_type_from_game_id


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
        CheckConstraint(
            "season_type IN ('Pre Season', 'Regular Season', 'All-Star', "
            "'Playoffs', 'Play-In', 'NBA Cup', 'Unknown')",
            name='ck_game_schedule_season_type',
        ),
        CheckConstraint(
            "game_date_precision IN ('exact', 'date_only')",
            name='ck_game_schedule_date_precision',
        ),
        CheckConstraint(
            "(team_score IS NULL) = (opponent_score IS NULL)",
            name='ck_game_schedule_score_pair',
        ),
        CheckConstraint(
            "team_score IS NULL OR (team_score >= 0 AND opponent_score >= 0)",
            name='ck_game_schedule_scores_nonnegative',
        ),
        CheckConstraint(
            "team_score IS NULL OR "
            "(result = 'W' AND team_score > opponent_score) OR "
            "(result = 'L' AND team_score < opponent_score)",
            name='ck_game_schedule_result_scores',
        ),
        CheckConstraint(
            "source_row_number IS NULL OR source_row_number >= 2",
            name='ck_game_schedule_source_row',
        ),
        CheckConstraint(
            "source_row_sha256 IS NULL OR source_row_sha256 ~ '^[0-9a-f]{64}$'",
            name='ck_game_schedule_source_row_sha256',
        ),
        CheckConstraint(
            "source_name <> 'kaggle-uploaded-pack' OR "
            "(source_import_id IS NOT NULL AND source_run_id IS NOT NULL AND "
            "source_row_number IS NOT NULL AND source_row_sha256 IS NOT NULL AND "
            "source_parser_version IS NOT NULL AND team_score IS NOT NULL AND "
            "opponent_score IS NOT NULL)",
            name='ck_game_schedule_external_lineage',
        ),
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
    season_type = Column(String(32), nullable=False)
    game_date = Column(DateTime, nullable=False)
    game_date_precision = Column(String(16), nullable=False)
    home_or_away = Column(String(1), nullable=False)
    result = Column(String(1), nullable=True)
    score = Column(String, nullable=True)
    team_score = Column(Integer, nullable=True)
    opponent_score = Column(Integer, nullable=True)

    # Durable source lineage. External rows require the full row-level chain.
    source_name = Column(String(64), nullable=False)
    source_import_id = Column(
        String(36),
        ForeignKey('external_dataset_imports.import_id'),
        nullable=True,
    )
    source_run_id = Column(
        String(36),
        ForeignKey('ingestion_runs.run_id'),
        nullable=True,
    )
    source_row_number = Column(BigInteger, nullable=True)
    source_row_sha256 = Column(String(64), nullable=True)
    source_parser_version = Column(String(64), nullable=True)
    
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
            'season_type': self.season_type,
            'team_id': self.team_id,
            'opponent_team_id': self.opponent_team_id,
            'game_date': self.game_date.isoformat() if self.game_date else None,
            'game_date_precision': self.game_date_precision,
            'home_or_away': self.home_or_away,
            'result': self.result,
            'score': self.score,
            'team_score': self.team_score,
            'opponent_score': self.opponent_score,
            'source_name': self.source_name,
            'source_import_id': self.source_import_id,
            'source_run_id': self.source_run_id,
            'source_row_number': self.source_row_number,
            'source_row_sha256': self.source_row_sha256,
            'source_parser_version': self.source_parser_version,
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
            # Games are stored in UTC (from gameDateTimeUTC), but NBA API uses EST/EDT dates
            # Convert UTC timestamp to EST/EDT, then extract date for comparison
            # This matches how fetch_todays_games() works (uses EST/EDT date from API)
            # PostgreSQL syntax: (timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York'
            # Then extract DATE from that
            results = (
                session.query(
                    cls,
                    TeamORM.name.label('team_name'),
                    TeamORM.abbreviation.label('team_abbreviation')
                )
                .join(TeamORM, cls.team_id == TeamORM.team_id)
                .filter(
                    text(f"DATE((game_schedule.game_date AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York') = '{game_date}'")
                )
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
               season_type: Optional[str] = None,
               game_date_precision: Optional[str] = None,
               team_score: Optional[int] = None,
               opponent_score: Optional[int] = None,
               source_name: Optional[str] = None,
               source_import_id: Optional[str] = None,
               source_run_id: Optional[str] = None,
               source_row_number: Optional[int] = None,
               source_row_sha256: Optional[str] = None,
               source_parser_version: Optional[str] = None,
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
            resolved_season_type = season_type or season_type_from_game_id(game_id)
            resolved_date_precision = game_date_precision or (
                'date_only'
                if game_date.time() == datetime.min.time()
                else 'exact'
            )
            # Check if schedule exists
            schedule = session.query(cls).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
            
            if schedule:
                # Update existing schedule
                schedule.season = season
                schedule.season_type = resolved_season_type
                schedule.opponent_team_id = opponent_team_id
                schedule.game_date = game_date
                schedule.game_date_precision = resolved_date_precision
                schedule.home_or_away = home_or_away
                schedule.result = result
                schedule.score = score
                if team_score is not None or opponent_score is not None:
                    schedule.team_score = team_score
                    schedule.opponent_score = opponent_score
                if source_name is not None:
                    schedule.source_name = source_name
                    schedule.source_import_id = source_import_id
                    schedule.source_run_id = source_run_id
                    schedule.source_row_number = source_row_number
                    schedule.source_row_sha256 = source_row_sha256
                    schedule.source_parser_version = source_parser_version
                logger.info(f"Updated game schedule: Game {game_id}, Team {team_id}")
            else:
                # Create new schedule
                schedule = cls(
                    game_id=game_id,
                    season=season,
                    season_type=resolved_season_type,
                    team_id=team_id,
                    opponent_team_id=opponent_team_id,
                    game_date=game_date,
                    game_date_precision=resolved_date_precision,
                    home_or_away=home_or_away,
                    result=result,
                    score=score,
                    team_score=team_score,
                    opponent_score=opponent_score,
                    source_name=source_name or 'nba-cdn-schedule',
                    source_import_id=source_import_id,
                    source_run_id=source_run_id,
                    source_row_number=source_row_number,
                    source_row_sha256=source_row_sha256,
                    source_parser_version=source_parser_version,
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
                        season_type=schedule_data.get('season_type'),
                        game_date_precision=schedule_data.get('game_date_precision'),
                        team_score=schedule_data.get('team_score'),
                        opponent_score=schedule_data.get('opponent_score'),
                        source_name=schedule_data.get('source_name'),
                        source_import_id=schedule_data.get('source_import_id'),
                        source_run_id=schedule_data.get('source_run_id'),
                        source_row_number=schedule_data.get('source_row_number'),
                        source_row_sha256=schedule_data.get('source_row_sha256'),
                        source_parser_version=schedule_data.get('source_parser_version'),
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

