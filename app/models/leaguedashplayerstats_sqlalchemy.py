"""SQLAlchemy ORM model for LeagueDashPlayerStats.

This module provides the LeagueDashPlayerStatsORM class which represents
league-wide player statistics for a given season using SQLAlchemy ORM.
It maintains backward compatibility with the existing psycopg2-based LeagueDashPlayerStats class.

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 - final model!)
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class LeagueDashPlayerStatsORM(Base):
    """SQLAlchemy ORM model for league-wide player statistics.
    
    This model represents comprehensive player statistics for a season from the NBA API's
    LeagueDashPlayerStats endpoint. It includes traditional box score stats, percentages,
    and fantasy points.
    
    Primary Key: (player_id, season)
    
    Attributes:
        player_id: Player identifier (FK to players)
        player_name: Player's name
        season: Season year (e.g., "2024-25")
        team_id: Team identifier
        team_abbreviation: Team abbreviation (e.g., "LAL")
        age: Player's age
        gp: Games played
        w: Wins
        l: Losses
        w_pct: Win percentage
        min: Minutes played
        fgm, fga, fg_pct: Field goal stats
        fg3m, fg3a, fg3_pct: Three-point stats
        ftm, fta, ft_pct: Free throw stats
        oreb, dreb, reb: Rebound stats
        ast: Assists
        tov: Turnovers
        stl: Steals
        blk: Blocks
        blka: Blocks against
        pf: Personal fouls
        pfd: Personal fouls drawn
        pts: Points
        plus_minus: Plus-minus
        nba_fantasy_pts: NBA fantasy points
        wnba_fantasy_pts: WNBA fantasy points
        dd2: Double-doubles
        td3: Triple-doubles
    """
    
    __tablename__ = 'leaguedashplayerstats'
    __table_args__ = (
        PrimaryKeyConstraint('player_id', 'season'),
        Index('idx_leaguedashplayerstats_player_id', 'player_id'),
        Index('idx_leaguedashplayerstats_season', 'season'),
        Index('idx_leaguedashplayerstats_team_id', 'team_id'),
    )
    
    # Primary Key
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    season = Column(String(10), nullable=False)
    
    # Player & Team Info
    player_name = Column(String(255))
    team_id = Column(Integer)
    team_abbreviation = Column(String(10))
    age = Column(Integer)
    
    # Game Stats
    gp = Column(Integer)
    w = Column(Integer)
    l = Column(Integer)
    w_pct = Column(Float)
    min = Column(Float)
    
    # Field Goals
    fgm = Column(Float)
    fga = Column(Float)
    fg_pct = Column(Float)
    
    # Three-Pointers
    fg3m = Column(Float)
    fg3a = Column(Float)
    fg3_pct = Column(Float)
    
    # Free Throws
    ftm = Column(Float)
    fta = Column(Float)
    ft_pct = Column(Float)
    
    # Rebounds
    oreb = Column(Float)
    dreb = Column(Float)
    reb = Column(Float)
    
    # Other Stats
    ast = Column(Float)
    tov = Column(Float)
    stl = Column(Float)
    blk = Column(Float)
    blka = Column(Float)
    pf = Column(Float)
    pfd = Column(Float)
    pts = Column(Float)
    plus_minus = Column(Float)
    
    # Fantasy & Achievements
    nba_fantasy_pts = Column(Float)
    wnba_fantasy_pts = Column(Float)
    dd2 = Column(Integer)  # Double-doubles
    td3 = Column(Integer)  # Triple-doubles
    
    # Ranking Columns (for all stats)
    gp_rank = Column(Integer)
    w_rank = Column(Integer)
    l_rank = Column(Integer)
    w_pct_rank = Column(Integer)
    min_rank = Column(Integer)
    fgm_rank = Column(Integer)
    fga_rank = Column(Integer)
    fg_pct_rank = Column(Integer)
    fg3m_rank = Column(Integer)
    fg3a_rank = Column(Integer)
    fg3_pct_rank = Column(Integer)
    ftm_rank = Column(Integer)
    fta_rank = Column(Integer)
    ft_pct_rank = Column(Integer)
    oreb_rank = Column(Integer)
    dreb_rank = Column(Integer)
    reb_rank = Column(Integer)
    ast_rank = Column(Integer)
    tov_rank = Column(Integer)
    stl_rank = Column(Integer)
    blk_rank = Column(Integer)
    blka_rank = Column(Integer)
    pf_rank = Column(Integer)
    pfd_rank = Column(Integer)
    pts_rank = Column(Integer)
    plus_minus_rank = Column(Integer)
    nba_fantasy_pts_rank = Column(Integer)
    wnba_fantasy_pts_rank = Column(Integer)
    dd2_rank = Column(Integer)
    td3_rank = Column(Integer)
    
    def __repr__(self) -> str:
        """String representation of the player stats."""
        return (f"<LeagueDashPlayerStatsORM(player_id={self.player_id}, name='{self.player_name}', "
                f"season='{self.season}', pts={self.pts})>")
    
    def to_dict(self) -> dict:
        """Convert player stats to dictionary.
        
        Returns:
            dict: Dictionary representation of the player stats
        """
        return {
            'player_id': self.player_id,
            'player_name': self.player_name,
            'season': self.season,
            'team_id': self.team_id,
            'team_abbreviation': self.team_abbreviation,
            'age': self.age,
            'gp': self.gp,
            'w': self.w,
            'l': self.l,
            'w_pct': self.w_pct,
            'min': self.min,
            'fgm': self.fgm,
            'fga': self.fga,
            'fg_pct': self.fg_pct,
            'fg3m': self.fg3m,
            'fg3a': self.fg3a,
            'fg3_pct': self.fg3_pct,
            'ftm': self.ftm,
            'fta': self.fta,
            'ft_pct': self.ft_pct,
            'oreb': self.oreb,
            'dreb': self.dreb,
            'reb': self.reb,
            'ast': self.ast,
            'tov': self.tov,
            'stl': self.stl,
            'blk': self.blk,
            'blka': self.blka,
            'pf': self.pf,
            'pfd': self.pfd,
            'pts': self.pts,
            'plus_minus': self.plus_minus,
            'nba_fantasy_pts': self.nba_fantasy_pts,
            'wnba_fantasy_pts': self.wnba_fantasy_pts,
            'dd2': self.dd2,
            'td3': self.td3,
            # Ranking columns
            'gp_rank': self.gp_rank,
            'w_rank': self.w_rank,
            'l_rank': self.l_rank,
            'w_pct_rank': self.w_pct_rank,
            'min_rank': self.min_rank,
            'fgm_rank': self.fgm_rank,
            'fga_rank': self.fga_rank,
            'fg_pct_rank': self.fg_pct_rank,
            'fg3m_rank': self.fg3m_rank,
            'fg3a_rank': self.fg3a_rank,
            'fg3_pct_rank': self.fg3_pct_rank,
            'ftm_rank': self.ftm_rank,
            'fta_rank': self.fta_rank,
            'ft_pct_rank': self.ft_pct_rank,
            'oreb_rank': self.oreb_rank,
            'dreb_rank': self.dreb_rank,
            'reb_rank': self.reb_rank,
            'ast_rank': self.ast_rank,
            'tov_rank': self.tov_rank,
            'stl_rank': self.stl_rank,
            'blk_rank': self.blk_rank,
            'blka_rank': self.blka_rank,
            'pf_rank': self.pf_rank,
            'pfd_rank': self.pfd_rank,
            'pts_rank': self.pts_rank,
            'plus_minus_rank': self.plus_minus_rank,
            'nba_fantasy_pts_rank': self.nba_fantasy_pts_rank,
            'wnba_fantasy_pts_rank': self.wnba_fantasy_pts_rank,
            'dd2_rank': self.dd2_rank,
            'td3_rank': self.td3_rank
        }
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_player(cls, player_id: int, season: str, 
                     db: Optional[Session] = None) -> Optional['LeagueDashPlayerStatsORM']:
        """Get player stats for a specific player and season.
        
        Args:
            player_id: Player identifier
            season: Season (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            LeagueDashPlayerStatsORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season == season
            ).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.player_id == player_id,
                cls.season == season
            ).first()
    
    @classmethod
    def get_all_by_season(cls, season: str = "2024-25",
                         db: Optional[Session] = None) -> List['LeagueDashPlayerStatsORM']:
        """Get all player stats for a season.
        
        Args:
            season: Season (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of LeagueDashPlayerStatsORM objects
        """
        if db:
            return db.query(cls).filter(cls.season == season).order_by(cls.pts.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.season == season).order_by(cls.pts.desc()).all()
    
    @classmethod
    def get_by_team(cls, team_id: int, season: str = "2024-25",
                   db: Optional[Session] = None) -> List['LeagueDashPlayerStatsORM']:
        """Get all player stats for a team in a season.
        
        Args:
            team_id: Team identifier
            season: Season (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of LeagueDashPlayerStatsORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season
            ).order_by(cls.pts.desc()).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season
            ).order_by(cls.pts.desc()).all()
    
    @classmethod
    def get_top_scorers(cls, season: str = "2024-25", limit: int = 10,
                       db: Optional[Session] = None) -> List['LeagueDashPlayerStatsORM']:
        """Get top scorers for a season.
        
        Args:
            season: Season (e.g., "2024-25")
            limit: Number of players to return
            db: Optional database session
            
        Returns:
            List of top scoring players
        """
        if db:
            return db.query(cls).filter(
                cls.season == season
            ).order_by(cls.pts.desc()).limit(limit).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.season == season
            ).order_by(cls.pts.desc()).limit(limit).all()
    
    @classmethod
    def search_by_name(cls, name: str, season: Optional[str] = None,
                      db: Optional[Session] = None) -> List['LeagueDashPlayerStatsORM']:
        """Search for player stats by name.
        
        Args:
            name: Player name (partial match)
            season: Optional season filter
            db: Optional database session
            
        Returns:
            List of matching players
        """
        def _query(session: Session):
            query = session.query(cls).filter(cls.player_name.ilike(f"%{name}%"))
            if season:
                query = query.filter(cls.season == season)
            return query.order_by(cls.pts.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create_from_dict(cls, stats: dict, db: Optional[Session] = None) -> 'LeagueDashPlayerStatsORM':
        """Create or update player stats from dictionary (upsert).
        
        Args:
            stats: Dictionary with stat names as keys
            db: Optional database session
            
        Returns:
            LeagueDashPlayerStatsORM: The created or updated stats object
        """
        def _create(session: Session) -> 'LeagueDashPlayerStatsORM':
            player_id = stats.get('player_id')
            season = stats.get('season')
            
            if not player_id or not season:
                raise ValueError("player_id and season are required")
            
            # Check if stats exist
            player_stats = session.query(cls).filter(
                cls.player_id == player_id,
                cls.season == season
            ).first()
            
            if player_stats:
                # Update existing stats
                for key, value in stats.items():
                    if hasattr(player_stats, key) and key not in ['player_id', 'season']:
                        setattr(player_stats, key, value)
                logger.info(f"Updated player stats: {stats.get('player_name')} {season}")
            else:
                # Create new stats
                player_stats = cls()
                for key, value in stats.items():
                    if hasattr(player_stats, key):
                        setattr(player_stats, key, value)
                session.add(player_stats)
                logger.info(f"Created new player stats: {stats.get('player_name')} {season}")
            
            session.flush()
            return player_stats
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            player_stats = _create(session)
            session.commit()
            return player_stats
    
    @classmethod
    def bulk_create(cls, stats_list: List[dict], db: Optional[Session] = None) -> int:
        """Bulk create or update player stats.
        
        Args:
            stats_list: List of stat dictionaries
            db: Optional database session
            
        Returns:
            int: Number of records created/updated
        """
        def _bulk_create(session: Session) -> int:
            count = 0
            for stats in stats_list:
                cls.create_from_dict(stats, db=session)
                count += 1
            return count
        
        if db:
            return _bulk_create(db)
        
        with get_db_context() as session:
            count = _bulk_create(session)
            session.commit()
            logger.info(f"Bulk created/updated {count} player stats records")
            return count
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this player stats record from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted player stats: {self.player_name} {self.season}")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility
def get_league_dash_player_stats_model():
    """Get the appropriate league dash player stats model (SQLAlchemy version).
    
    Returns:
        LeagueDashPlayerStatsORM class
    """
    return LeagueDashPlayerStatsORM

