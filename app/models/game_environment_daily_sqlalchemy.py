"""SQLAlchemy ORM model for GameEnvironmentDaily.

This module provides the GameEnvironmentDailyORM class which represents
game matchup environment by combining metrics from both teams.

Created: December 2024
Part of: Enhanced Analytics Engine (Phase 1.4 - Team Trend Analysis)
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import Column, Integer, BigInteger, String, Text, Float, Date, DateTime, Boolean, Index, UniqueConstraint, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class GameEnvironmentDailyORM(Base):
    """SQLAlchemy ORM model for game environment analysis.
    
    This model combines metrics from both teams to characterize the matchup
    environment and predict game characteristics.
    
    Attributes:
        id: Auto-incrementing primary key
        game_id: NBA game identifier
        game_date: Date of the game
        season: Season year (e.g., "2024-25")
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        
        Team Recent Form (from team_daily_metrics lastN):
        - home_off_rtg_lastn, home_def_rtg_lastn, home_pace_lastn
        - away_off_rtg_lastn, away_def_rtg_lastn, away_pace_lastn
        
        Environment Indices:
        - pace_projection: Blended pace estimate
        - scoring_env_index: Expected scoring level
        - three_env_index: 3-point shooting environment
        - reb_env_index: Rebounding battle intensity
        - ft_env_index: Free throw environment
        - chaos_index: Overall game chaos (pace, TOV, etc.)
        
        Boolean Flags:
        - pace_up_for_home, pace_up_for_away
        - three_point_fest, paint_battle, glass_war, whistle_heavy
        
        tags: Array of textual tags
        details_json: Raw metrics as JSON
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (game_id, game_date) - One record per game
    """
    
    __tablename__ = 'game_environment_daily'
    __table_args__ = (
        UniqueConstraint('game_id', 'game_date',
                        name='game_environment_daily_unique'),
        Index('idx_game_environment_game_id', 'game_id'),
        Index('idx_game_environment_game_date', 'game_date'),
        Index('idx_game_environment_season', 'season'),
        Index('idx_game_environment_home_team', 'home_team_id'),
        Index('idx_game_environment_away_team', 'away_team_id'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Game Identifiers
    game_id = Column(BigInteger, nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(Text, nullable=False)
    home_team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    away_team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    
    # Home Team Recent Form (Last N)
    home_off_rtg_lastn = Column(Float, nullable=True)
    home_def_rtg_lastn = Column(Float, nullable=True)
    home_pace_lastn = Column(Float, nullable=True)
    
    # Away Team Recent Form (Last N)
    away_off_rtg_lastn = Column(Float, nullable=True)
    away_def_rtg_lastn = Column(Float, nullable=True)
    away_pace_lastn = Column(Float, nullable=True)
    
    # Environment Indices
    pace_projection = Column(Float, nullable=True)  # Blended pace estimate
    scoring_env_index = Column(Float, nullable=True)  # High = more scoring
    three_env_index = Column(Float, nullable=True)  # 3PT shooting environment
    reb_env_index = Column(Float, nullable=True)  # Rebounding battle
    ft_env_index = Column(Float, nullable=True)  # Free throw environment
    chaos_index = Column(Float, nullable=True)  # Overall chaos level
    
    # Boolean Flags for UI
    pace_up_for_home = Column(Boolean, nullable=True, default=False, server_default=text("false"))
    pace_up_for_away = Column(Boolean, nullable=True, default=False, server_default=text("false"))
    three_point_fest = Column(Boolean, nullable=True, default=False, server_default=text("false"))
    paint_battle = Column(Boolean, nullable=True, default=False, server_default=text("false"))
    glass_war = Column(Boolean, nullable=True, default=False, server_default=text("false"))
    whistle_heavy = Column(Boolean, nullable=True, default=False, server_default=text("false"))
    
    # Additional Data
    tags = Column(ARRAY(Text), nullable=True)  # Textual tags list
    details_json = Column(JSONB, nullable=True)  # Raw metrics
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, server_default=func.now()
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary with all fields
        """
        return {
            'id': self.id,
            'game_id': self.game_id,
            'game_date': self.game_date.isoformat() if self.game_date else None,
            'season': self.season,
            'home_team_id': self.home_team_id,
            'away_team_id': self.away_team_id,
            'home_off_rtg_lastn': self.home_off_rtg_lastn,
            'home_def_rtg_lastn': self.home_def_rtg_lastn,
            'home_pace_lastn': self.home_pace_lastn,
            'away_off_rtg_lastn': self.away_off_rtg_lastn,
            'away_def_rtg_lastn': self.away_def_rtg_lastn,
            'away_pace_lastn': self.away_pace_lastn,
            'pace_projection': self.pace_projection,
            'scoring_env_index': self.scoring_env_index,
            'three_env_index': self.three_env_index,
            'reb_env_index': self.reb_env_index,
            'ft_env_index': self.ft_env_index,
            'chaos_index': self.chaos_index,
            'pace_up_for_home': self.pace_up_for_home,
            'pace_up_for_away': self.pace_up_for_away,
            'three_point_fest': self.three_point_fest,
            'paint_battle': self.paint_battle,
            'glass_war': self.glass_war,
            'whistle_heavy': self.whistle_heavy,
            'tags': self.tags,
            'details_json': self.details_json,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create(
        cls,
        game_id: int,
        game_date: date,
        season: str,
        home_team_id: int,
        away_team_id: int,
        environment_data: Dict[str, Any],
        db: Optional[Session] = None
    ) -> 'GameEnvironmentDailyORM':
        """Create or update a game environment record (upsert).
        
        Args:
            game_id: Game identifier
            game_date: Date of game
            season: Season string
            home_team_id: Home team identifier
            away_team_id: Away team identifier
            environment_data: Dictionary of environment metrics
            db: Optional database session
            
        Returns:
            GameEnvironmentDailyORM: The created or updated record
        """
        def _create(session: Session) -> 'GameEnvironmentDailyORM':
            # Check if record exists
            existing = session.query(cls).filter(
                cls.game_id == game_id,
                cls.game_date == game_date
            ).first()
            
            if existing:
                # Update existing record (preserve created_at)
                existing.season = season
                existing.home_team_id = home_team_id
                existing.away_team_id = away_team_id
                for key, value in environment_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                logger.debug(f"Updated game environment: {game_id}")
            else:
                # Create new record
                existing = cls(
                    game_id=game_id,
                    game_date=game_date,
                    season=season,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    **environment_data
                )
                session.add(existing)
                logger.debug(f"Created game environment: {game_id}")
            
            session.flush()
            return existing
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            record = _create(session)
            session.commit()
            return record
    
    @classmethod
    def bulk_create(
        cls,
        records: List[dict],
        db: Optional[Session] = None
    ) -> int:
        """Bulk create/update game environments using PostgreSQL INSERT ... ON CONFLICT.
        
        Args:
            records: List of dictionaries with game environment data
            db: Optional database session
            
        Returns:
            int: Number of records created/updated
        """
        if not records:
            return 0
        
        def _bulk_create(session: Session) -> int:
            from sqlalchemy.dialects.postgresql import insert
            
            # Prepare data for bulk insert
            values = []
            for record in records:
                value = {
                    'game_id': record['game_id'],
                    'game_date': record['game_date'],
                    'season': record['season'],
                    'home_team_id': record['home_team_id'],
                    'away_team_id': record['away_team_id'],
                    'created_at': datetime.utcnow()
                }
                # Add all other fields
                for key, val in record.items():
                    if key not in value:
                        value[key] = val
                values.append(value)
            
            # Use PostgreSQL INSERT ... ON CONFLICT for true bulk upsert
            stmt = insert(cls).values(values)
            
            # Build set dictionary for on_conflict_do_update (exclude game_id, game_date, created_at)
            update_dict = {col: stmt.excluded[col] for col in values[0].keys() 
                          if col not in ['game_id', 'game_date', 'created_at']}
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['game_id', 'game_date'],
                set_=update_dict
            )
            
            result = session.execute(stmt)
            session.flush()
            return len(values)
        
        if db:
            return _bulk_create(db)
        
        with get_db_context() as session:
            count = _bulk_create(session)
            session.commit()
            return count
    
    @classmethod
    def get_by_game(
        cls,
        game_id: int,
        db: Optional[Session] = None
    ) -> Optional['GameEnvironmentDailyORM']:
        """Get game environment by game ID.
        
        Args:
            game_id: Game identifier
            db: Optional database session
            
        Returns:
            GameEnvironmentDailyORM record or None
        """
        def _query(session: Session):
            return session.query(cls).filter(cls.game_id == game_id).first()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_by_date(
        cls,
        game_date: date,
        db: Optional[Session] = None
    ) -> List['GameEnvironmentDailyORM']:
        """Get all game environments for a specific date.
        
        Args:
            game_date: Date to query
            db: Optional database session
            
        Returns:
            List of GameEnvironmentDailyORM records
        """
        def _query(session: Session):
            return session.query(cls).filter(cls.game_date == game_date).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def clear_by_season(cls, season: str, db: Optional[Session] = None) -> int:
        """Clear all game environments for a specific season.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            int: Number of records deleted
        """
        def _clear(session: Session) -> int:
            deleted_count = session.query(cls).filter(cls.season == season).delete()
            session.flush()
            logger.info(f"Cleared {deleted_count} game environments for season {season}")
            return deleted_count
        
        if db:
            return _clear(db)
        
        with get_db_context() as session:
            count = _clear(session)
            session.commit()
            return count

