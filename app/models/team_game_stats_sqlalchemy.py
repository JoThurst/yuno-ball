"""SQLAlchemy ORM model for TeamGameStats.

This module provides the TeamGameStatsORM class which represents team
game statistics in the database using SQLAlchemy ORM. It maintains backward
compatibility with the existing psycopg2-based TeamGameStats class.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 continued)
"""

from typing import Optional, List
from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date, Index, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Session, relationship
from sqlalchemy.dialects.postgresql import insert

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class TeamGameStatsORM(Base):
    """SQLAlchemy ORM model for team game statistics.
    
    This model represents a team's performance in a specific game.
    It maps to the 'team_game_stats' table in the public schema.
    
    Attributes:
        game_id: Game identifier
        team_id: Team identifier (FK to teams)
        opponent_team_id: Opponent team identifier (FK to teams)
        season: Season year (e.g., "2023-24")
        game_date: Date of the game
        fg: Field Goals Made
        fga: Field Goals Attempted
        fg_pct: Field Goal Percentage
        fg3: Three-Point Field Goals Made
        fg3a: Three-Point Attempts
        fg3_pct: Three-Point Percentage
        ft: Free Throws Made
        fta: Free Throws Attempted
        ft_pct: Free Throw Percentage
        reb: Total Rebounds
        ast: Assists
        stl: Steals
        blk: Blocks
        tov: Turnovers
        pts: Points Scored
        plus_minus: Plus-Minus Rating
        
    Relationships:
        team: The team this stat belongs to
        opponent: The opposing team
    """
    
    __tablename__ = 'team_game_stats'
    __table_args__ = (
        PrimaryKeyConstraint('game_id', 'team_id'),
        Index('idx_team_game_stats_team_id', 'team_id'),
        Index('idx_team_game_stats_season', 'season'),
        Index('idx_team_game_stats_game_date', 'game_date'),
    )
    
    # Primary Key (composite)
    game_id = Column(String(20), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    
    # Foreign Keys
    opponent_team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    
    # Game Information
    season = Column(String(10), nullable=False)
    game_date = Column(Date, nullable=False)
    
    # Field Goals
    fg = Column(Integer, nullable=True)
    fga = Column(Integer, nullable=True)
    fg_pct = Column(Float, nullable=True)
    
    # Three-Point Field Goals
    fg3 = Column(Integer, nullable=True)
    fg3a = Column(Integer, nullable=True)
    fg3_pct = Column(Float, nullable=True)
    
    # Free Throws
    ft = Column(Integer, nullable=True)
    fta = Column(Integer, nullable=True)
    ft_pct = Column(Float, nullable=True)
    
    # Other Stats
    reb = Column(Integer, nullable=True)
    ast = Column(Integer, nullable=True)
    stl = Column(Integer, nullable=True)
    blk = Column(Integer, nullable=True)
    tov = Column(Integer, nullable=True)
    pts = Column(Integer, nullable=True)
    plus_minus = Column(Float, nullable=True)
    
    # Relationships (will be defined when team model is available)
    # team = relationship("TeamORM", foreign_keys=[team_id], back_populates="game_stats")
    # opponent = relationship("TeamORM", foreign_keys=[opponent_team_id])
    
    def __repr__(self) -> str:
        """String representation of the team game stat."""
        return (f"<TeamGameStatsORM(game_id='{self.game_id}', team_id={self.team_id}, "
                f"pts={self.pts}, date={self.game_date})>")
    
    def to_dict(self) -> dict:
        """Convert team game stat object to dictionary.
        
        Returns:
            dict: Dictionary representation of the team game stat
        """
        return {
            'game_id': self.game_id,
            'team_id': self.team_id,
            'opponent_team_id': self.opponent_team_id,
            'season': self.season,
            'game_date': self.game_date.isoformat() if self.game_date else None,
            'fg': self.fg,
            'fga': self.fga,
            'fg_pct': self.fg_pct,
            'fg3': self.fg3,
            'fg3a': self.fg3a,
            'fg3_pct': self.fg3_pct,
            'ft': self.ft,
            'fta': self.fta,
            'ft_pct': self.ft_pct,
            'reb': self.reb,
            'ast': self.ast,
            'stl': self.stl,
            'blk': self.blk,
            'tov': self.tov,
            'pts': self.pts,
            'plus_minus': self.plus_minus
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_game_and_team(cls, game_id: str, team_id: int,
                            db: Optional[Session] = None) -> Optional['TeamGameStatsORM']:
        """Get team game statistics for a specific game.
        
        Args:
            game_id: The game identifier
            team_id: The team identifier
            db: Optional database session
            
        Returns:
            TeamGameStatsORM object if found, None otherwise
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
                   db: Optional[Session] = None) -> List['TeamGameStatsORM']:
        """Get all game statistics for a team.
        
        Args:
            team_id: The team identifier
            season: Optional season filter
            db: Optional database session
            
        Returns:
            List of TeamGameStatsORM objects
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
    def get_by_season(cls, season: str, db: Optional[Session] = None) -> List['TeamGameStatsORM']:
        """Get all team game stats for a season.
        
        Args:
            season: Season year (e.g., "2023-24")
            db: Optional database session
            
        Returns:
            List of TeamGameStatsORM objects
        """
        if db:
            return db.query(cls).filter(cls.season == season).order_by(cls.game_date.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.season == season).order_by(cls.game_date.desc()).all()
    
    @classmethod
    def get_by_date(cls, game_date: date, db: Optional[Session] = None) -> List['TeamGameStatsORM']:
        """Get all team game stats for a specific date.
        
        Args:
            game_date: Date to filter by
            db: Optional database session
            
        Returns:
            List of TeamGameStatsORM objects
        """
        if db:
            return db.query(cls).filter(cls.game_date == game_date).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.game_date == game_date).all()
    
    @classmethod
    def get_vs_opponent(cls, team_id: int, opponent_team_id: int,
                       db: Optional[Session] = None) -> List['TeamGameStatsORM']:
        """Get all games between two teams.
        
        Args:
            team_id: The team identifier
            opponent_team_id: The opponent team identifier
            db: Optional database session
            
        Returns:
            List of TeamGameStatsORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.opponent_team_id == opponent_team_id
            ).order_by(cls.game_date.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.opponent_team_id == opponent_team_id
            ).order_by(cls.game_date.desc()).all()
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create(cls,
               game_id: str,
               team_id: int,
               opponent_team_id: int,
               season: str,
               game_date: date,
               fg: Optional[int] = None,
               fga: Optional[int] = None,
               fg_pct: Optional[float] = None,
               fg3: Optional[int] = None,
               fg3a: Optional[int] = None,
               fg3_pct: Optional[float] = None,
               ft: Optional[int] = None,
               fta: Optional[int] = None,
               ft_pct: Optional[float] = None,
               reb: Optional[int] = None,
               ast: Optional[int] = None,
               stl: Optional[int] = None,
               blk: Optional[int] = None,
               tov: Optional[int] = None,
               pts: Optional[int] = None,
               plus_minus: Optional[float] = None,
               db: Optional[Session] = None) -> 'TeamGameStatsORM':
        """Create a new team game stat or update if exists (upsert).
        
        Args:
            game_id: Game identifier
            team_id: Team identifier
            opponent_team_id: Opponent team identifier
            season: Season year
            game_date: Date of the game
            fg, fga, fg_pct: Field goal stats
            fg3, fg3a, fg3_pct: Three-point stats
            ft, fta, ft_pct: Free throw stats
            reb, ast, stl, blk, tov: Other stats
            pts: Points scored
            plus_minus: Plus-minus rating
            db: Optional database session
            
        Returns:
            TeamGameStatsORM: The created or updated team game stat object
        """
        def _create(session: Session) -> 'TeamGameStatsORM':
            # Check if stat exists
            stat = session.query(cls).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
            
            if stat:
                # Update existing stat
                stat.opponent_team_id = opponent_team_id
                stat.season = season
                stat.game_date = game_date
                stat.fg = fg
                stat.fga = fga
                stat.fg_pct = fg_pct
                stat.fg3 = fg3
                stat.fg3a = fg3a
                stat.fg3_pct = fg3_pct
                stat.ft = ft
                stat.fta = fta
                stat.ft_pct = ft_pct
                stat.reb = reb
                stat.ast = ast
                stat.stl = stl
                stat.blk = blk
                stat.tov = tov
                stat.pts = pts
                stat.plus_minus = plus_minus
                logger.info(f"Updated team game stat: Game {game_id}, Team {team_id}")
            else:
                # Create new stat
                stat = cls(
                    game_id=game_id,
                    team_id=team_id,
                    opponent_team_id=opponent_team_id,
                    season=season,
                    game_date=game_date,
                    fg=fg, fga=fga, fg_pct=fg_pct,
                    fg3=fg3, fg3a=fg3a, fg3_pct=fg3_pct,
                    ft=ft, fta=fta, ft_pct=ft_pct,
                    reb=reb, ast=ast, stl=stl, blk=blk, tov=tov,
                    pts=pts, plus_minus=plus_minus
                )
                session.add(stat)
                logger.info(f"Created new team game stat: Game {game_id}, Team {team_id}")
            
            session.flush()
            return stat
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            stat = _create(session)
            session.commit()
            return stat
    
    @classmethod
    def create_from_dict(cls, game_stats: dict, db: Optional[Session] = None) -> 'TeamGameStatsORM':
        """Create team game stat from dictionary.
        
        Args:
            game_stats: Dictionary containing game statistics
            db: Optional database session
            
        Returns:
            TeamGameStatsORM: The created or updated team game stat object
        """
        return cls.create(
            game_id=game_stats['game_id'],
            team_id=game_stats['team_id'],
            opponent_team_id=game_stats['opponent_team_id'],
            season=game_stats['season'],
            game_date=game_stats['game_date'],
            fg=game_stats.get('fg'),
            fga=game_stats.get('fga'),
            fg_pct=game_stats.get('fg_pct'),
            fg3=game_stats.get('fg3'),
            fg3a=game_stats.get('fg3a'),
            fg3_pct=game_stats.get('fg3_pct'),
            ft=game_stats.get('ft'),
            fta=game_stats.get('fta'),
            ft_pct=game_stats.get('ft_pct'),
            reb=game_stats.get('reb'),
            ast=game_stats.get('ast'),
            stl=game_stats.get('stl'),
            blk=game_stats.get('blk'),
            tov=game_stats.get('tov'),
            pts=game_stats.get('pts'),
            plus_minus=game_stats.get('plus_minus'),
            db=db
        )
    
    @classmethod
    def bulk_upsert(cls, stats: List[dict], db: Optional[Session] = None) -> int:
        """Bulk upsert team game stats using INSERT ... ON CONFLICT.
        
        Args:
            stats: List of dictionaries containing team game stats
            db: Optional database session
        
        Returns:
            int: Number of records processed
        """
        if not stats:
            return 0
        
        def _bulk(session: Session) -> int:
            values = []
            for row in stats:
                values.append({
                    'game_id': row['game_id'],
                    'team_id': int(row['team_id']),
                    'opponent_team_id': int(row['opponent_team_id']),
                    'season': row['season'],
                    'game_date': row['game_date'],
                    'fg': row.get('fg'),
                    'fga': row.get('fga'),
                    'fg_pct': row.get('fg_pct'),
                    'fg3': row.get('fg3'),
                    'fg3a': row.get('fg3a'),
                    'fg3_pct': row.get('fg3_pct'),
                    'ft': row.get('ft'),
                    'fta': row.get('fta'),
                    'ft_pct': row.get('ft_pct'),
                    'reb': row.get('reb'),
                    'ast': row.get('ast'),
                    'stl': row.get('stl'),
                    'blk': row.get('blk'),
                    'tov': row.get('tov'),
                    'pts': row.get('pts'),
                    'plus_minus': row.get('plus_minus')
                })
            
            stmt = insert(cls.__table__).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['game_id', 'team_id'],
                set_={
                    'opponent_team_id': stmt.excluded.opponent_team_id,
                    'season': stmt.excluded.season,
                    'game_date': stmt.excluded.game_date,
                    'fg': stmt.excluded.fg,
                    'fga': stmt.excluded.fga,
                    'fg_pct': stmt.excluded.fg_pct,
                    'fg3': stmt.excluded.fg3,
                    'fg3a': stmt.excluded.fg3a,
                    'fg3_pct': stmt.excluded.fg3_pct,
                    'ft': stmt.excluded.ft,
                    'fta': stmt.excluded.fta,
                    'ft_pct': stmt.excluded.ft_pct,
                    'reb': stmt.excluded.reb,
                    'ast': stmt.excluded.ast,
                    'stl': stmt.excluded.stl,
                    'blk': stmt.excluded.blk,
                    'tov': stmt.excluded.tov,
                    'pts': stmt.excluded.pts,
                    'plus_minus': stmt.excluded.plus_minus
                }
            )
            session.execute(stmt)
            return len(values)
        
        if db:
            return _bulk(db)
        
        with get_db_context() as session:
            count = _bulk(session)
            session.commit()
            logger.info(f"Bulk upserted {count} team game stats")
            return count
    
    def update(self, **kwargs) -> 'TeamGameStatsORM':
        """Update team game stat fields.
        
        Args:
            **kwargs: Fields to update
            
        Returns:
            Self (updated TeamGameStatsORM object)
        """
        def _update(session: Session) -> 'TeamGameStatsORM':
            for key, value in kwargs.items():
                if hasattr(self, key) and value is not None:
                    setattr(self, key, value)
            
            session.flush()
            logger.info(f"Updated team game stat: Game {self.game_id}, Team {self.team_id}")
            return self
        
        db = kwargs.pop('db', None)
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            if self not in session:
                self = session.merge(self)
            stat = _update(session)
            session.commit()
            return stat
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this team game stat from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted team game stat: Game {self.game_id}, Team {self.team_id}")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility
def get_team_game_stats_model():
    """Get the appropriate team game stats model (SQLAlchemy version).
    
    Returns:
        TeamGameStatsORM class
    """
    return TeamGameStatsORM

