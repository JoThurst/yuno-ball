"""SQLAlchemy ORM model for PlayerConsistency.

This module provides the PlayerConsistencyORM class which stores player
consistency/volatility metrics calculated from game logs.

Consistency is measured using Coefficient of Variation (CV = stddev / mean).
Lower CV = more consistent/steady player
Higher CV = more volatile/boom-bust player

Created: December 2, 2025
Part of: Phase 1.6 - Consistency/Volatility Metrics
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Text, Date, DateTime, Index, UniqueConstraint, ForeignKey, func, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class PlayerConsistencyORM(Base):
    """SQLAlchemy ORM model for player consistency metrics.
    
    This model stores consistency/volatility metrics for each player per stat,
    calculated from their game logs over different windows.
    
    Attributes:
        id: Auto-incrementing primary key
        player_id: Reference to players table
        player_name: Player's full name
        season: Season string (e.g., "2024-25")
        stat_name: Name of the stat (pts, reb, ast, pra, fg3m, etc.)
        window_size: Number of games used (0 = full season)
        
        Stats:
        - games_played: Number of games in calculation
        - mean: Average value
        - stddev: Standard deviation
        - cv: Coefficient of variation (stddev / mean)
        - min_val: Minimum value
        - max_val: Maximum value
        - median: Median value
        
        Flags:
        - consistency_tier: 'steady' | 'average' | 'volatile'
        
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (player_id, season, stat_name, window_size)
    """
    
    __tablename__ = 'player_consistency'
    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'stat_name', 'window_size',
                        name='player_consistency_unique'),
        Index('idx_player_consistency_player_id', 'player_id'),
        Index('idx_player_consistency_season', 'season'),
        Index('idx_player_consistency_stat_name', 'stat_name'),
        Index('idx_player_consistency_cv', 'cv'),
        Index('idx_player_consistency_tier', 'consistency_tier'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identifiers
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    player_name = Column(Text, nullable=False)
    season = Column(Text, nullable=False)
    stat_name = Column(Text, nullable=False)  # pts, reb, ast, pra, fg3m, etc.
    window_size = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )  # 0 = full season
    
    # Calculated Metrics
    games_played = Column(Integer, nullable=False)
    mean = Column(Float, nullable=False)
    stddev = Column(Float, nullable=False)
    cv = Column(Float, nullable=False)  # Coefficient of Variation (stddev / mean)
    min_val = Column(Float, nullable=True)
    max_val = Column(Float, nullable=True)
    median = Column(Float, nullable=True)
    
    # Classification
    consistency_tier = Column(Text, nullable=True)  # 'steady', 'average', 'volatile'
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, server_default=func.now()
    )
    
    # CV Thresholds for tier classification
    CV_STEADY_THRESHOLD = 0.35  # CV < 0.35 = steady
    CV_VOLATILE_THRESHOLD = 0.55  # CV > 0.55 = volatile
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'season': self.season,
            'stat_name': self.stat_name,
            'window_size': self.window_size,
            'games_played': self.games_played,
            'mean': self.mean,
            'stddev': self.stddev,
            'cv': self.cv,
            'min_val': self.min_val,
            'max_val': self.max_val,
            'median': self.median,
            'consistency_tier': self.consistency_tier,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_display_summary(self) -> str:
        """Get a human-readable summary of consistency."""
        tier_emoji = {
            'steady': '🎯',
            'average': '➖',
            'volatile': '🎰'
        }
        emoji = tier_emoji.get(self.consistency_tier, '❓')
        return f"{emoji} {self.stat_name.upper()}: {self.mean:.1f} ± {self.stddev:.1f} (CV: {self.cv:.2f})"
    
    @classmethod
    def classify_tier(cls, cv: float) -> str:
        """Classify CV into consistency tier.
        
        Args:
            cv: Coefficient of variation
            
        Returns:
            Tier string: 'steady', 'average', or 'volatile'
        """
        if cv < cls.CV_STEADY_THRESHOLD:
            return 'steady'
        elif cv > cls.CV_VOLATILE_THRESHOLD:
            return 'volatile'
        else:
            return 'average'
    
    @classmethod
    def bulk_create(
        cls,
        records: List[dict],
        db: Optional[Session] = None
    ) -> int:
        """Bulk create/update consistency records using PostgreSQL INSERT ... ON CONFLICT.
        
        Args:
            records: List of dictionaries with consistency data
            db: Optional database session
            
        Returns:
            int: Number of records created/updated
        """
        if not records:
            return 0
        
        def _bulk_create(session: Session) -> int:
            values = []
            for record in records:
                value = {
                    'player_id': record['player_id'],
                    'player_name': record['player_name'],
                    'season': record['season'],
                    'stat_name': record['stat_name'],
                    'window_size': record.get('window_size', 0),
                    'games_played': record['games_played'],
                    'mean': record['mean'],
                    'stddev': record['stddev'],
                    'cv': record['cv'],
                    'min_val': record.get('min_val'),
                    'max_val': record.get('max_val'),
                    'median': record.get('median'),
                    'consistency_tier': record.get('consistency_tier'),
                    'created_at': datetime.utcnow()
                }
                values.append(value)
            
            stmt = insert(cls).values(values)
            
            update_dict = {col: stmt.excluded[col] for col in values[0].keys() 
                          if col not in ['player_id', 'season', 'stat_name', 'window_size', 'created_at']}
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['player_id', 'season', 'stat_name', 'window_size'],
                set_=update_dict
            )
            
            session.execute(stmt)
            session.flush()
            return len(values)
        
        if db:
            return _bulk_create(db)
        
        with get_db_context() as session:
            count = _bulk_create(session)
            session.commit()
            return count
    
    @classmethod
    def get_by_player(
        cls,
        player_id: int,
        season: Optional[str] = None,
        window_size: Optional[int] = None,
        db: Optional[Session] = None
    ) -> List['PlayerConsistencyORM']:
        """Get consistency records for a player."""
        def _query(session: Session):
            query = session.query(cls).filter(cls.player_id == player_id)
            if season:
                query = query.filter(cls.season == season)
            if window_size is not None:
                query = query.filter(cls.window_size == window_size)
            return query.order_by(cls.stat_name).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_most_volatile(
        cls,
        season: str,
        stat_name: str,
        window_size: int = 0,
        limit: int = 20,
        min_games: int = 10,
        db: Optional[Session] = None
    ) -> List['PlayerConsistencyORM']:
        """Get most volatile players for a stat."""
        def _query(session: Session):
            return session.query(cls).filter(
                cls.season == season,
                cls.stat_name == stat_name,
                cls.window_size == window_size,
                cls.games_played >= min_games
            ).order_by(cls.cv.desc()).limit(limit).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_most_steady(
        cls,
        season: str,
        stat_name: str,
        window_size: int = 0,
        limit: int = 20,
        min_games: int = 10,
        db: Optional[Session] = None
    ) -> List['PlayerConsistencyORM']:
        """Get most consistent players for a stat."""
        def _query(session: Session):
            return session.query(cls).filter(
                cls.season == season,
                cls.stat_name == stat_name,
                cls.window_size == window_size,
                cls.games_played >= min_games
            ).order_by(cls.cv.asc()).limit(limit).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def clear_by_season(cls, season: str, db: Optional[Session] = None) -> int:
        """Clear all consistency records for a season."""
        def _clear(session: Session) -> int:
            deleted_count = session.query(cls).filter(cls.season == season).delete()
            session.flush()
            logger.info(f"Cleared {deleted_count} consistency records for season {season}")
            return deleted_count
        
        if db:
            return _clear(db)
        
        with get_db_context() as session:
            count = _clear(session)
            session.commit()
            return count

