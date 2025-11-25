"""SQLAlchemy ORM model for PlayerHeatIndex.

This module provides the PlayerHeatIndexORM class which represents heat index
data (hot & cold detection) in the database using SQLAlchemy ORM.

Created: December 2024
Part of: Enhanced Analytics Engine (Phase 1.2)
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class PlayerHeatIndexORM(Base):
    """SQLAlchemy ORM model for player heat index results.
    
    This model tracks heat index calculations (Z-scores comparing recent form
    to season averages) for identifying hot and cold players.
    
    Attributes:
        id: Auto-incrementing primary key
        player_id: Reference to player (NBA API ID)
        player_name: Name of the player
        stat: Type of statistic (PTS, REB, AST, PRA)
        season: Season year (e.g., "2024-25")
        window_size: Number of recent games used for calculation
        season_avg: Season average for this stat
        season_std: Season standard deviation for this stat
        recent_avg: Recent average (last N games) for this stat
        z_score: Z-score (standard deviations from season average)
        status: Heat status ('on_fire', 'ice_cold', or 'normal')
        created_at: Timestamp when record was created/updated
        
    Unique Constraint:
        (player_id, stat, season, window_size) - One record per player/stat/season/window
    """
    
    __tablename__ = 'player_heat_index'
    __table_args__ = (
        UniqueConstraint('player_id', 'stat', 'season', 'window_size',
                        name='player_heat_index_unique'),
        Index('idx_heat_index_player_id', 'player_id'),
        Index('idx_heat_index_season', 'season'),
        Index('idx_heat_index_stat', 'stat'),
        Index('idx_heat_index_status', 'status'),
        Index('idx_heat_index_z_score', 'z_score'),
        Index('idx_heat_index_window_size', 'window_size'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Player Information
    player_id = Column(Integer, nullable=False)
    player_name = Column(Text, nullable=False)
    
    # Heat Index Information
    stat = Column(Text, nullable=False)
    season = Column(Text, nullable=False)
    window_size = Column(Integer, nullable=False)
    
    # Statistical Values
    season_avg = Column(Float, nullable=False)
    season_std = Column(Float, nullable=False)
    recent_avg = Column(Float, nullable=False)
    z_score = Column(Float, nullable=False)
    status = Column(Text, nullable=False)  # 'on_fire', 'ice_cold', 'normal'
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    @classmethod
    def create(
        cls,
        player_id: int,
        player_name: str,
        stat: str,
        season: str,
        window_size: int,
        season_avg: float,
        season_std: float,
        recent_avg: float,
        z_score: float,
        status: str,
        db: Optional[Session] = None
    ) -> 'PlayerHeatIndexORM':
        """Create or update a heat index record (upsert).
        
        Args:
            player_id: Player identifier
            player_name: Player name
            stat: Statistic name
            season: Season string
            window_size: Window size
            season_avg: Season average
            season_std: Season standard deviation
            recent_avg: Recent average
            z_score: Z-score
            status: Heat status
            db: Optional database session
            
        Returns:
            PlayerHeatIndexORM: The created or updated record
        """
        def _create(session: Session) -> 'PlayerHeatIndexORM':
            # Check if record exists
            existing = session.query(cls).filter(
                cls.player_id == player_id,
                cls.stat == stat,
                cls.season == season,
                cls.window_size == window_size
            ).first()
            
            if existing:
                # Update existing record
                existing.player_name = player_name
                existing.season_avg = season_avg
                existing.season_std = season_std
                existing.recent_avg = recent_avg
                existing.z_score = z_score
                existing.status = status
                existing.created_at = datetime.utcnow()
                logger.debug(f"Updated heat index: {player_name} - {stat} ({season}, {window_size}g)")
            else:
                # Create new record
                existing = cls(
                    player_id=player_id,
                    player_name=player_name,
                    stat=stat,
                    season=season,
                    window_size=window_size,
                    season_avg=season_avg,
                    season_std=season_std,
                    recent_avg=recent_avg,
                    z_score=z_score,
                    status=status
                )
                session.add(existing)
                logger.debug(f"Created heat index: {player_name} - {stat} ({season}, {window_size}g)")
            
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
        """Bulk create/update heat index records using PostgreSQL INSERT ... ON CONFLICT.
        
        Args:
            records: List of dictionaries with heat index data
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
                values.append({
                    'player_id': record['player_id'],
                    'player_name': record['player_name'],
                    'stat': record['stat'],
                    'season': record['season'],
                    'window_size': record['window_size'],
                    'season_avg': record['season_avg'],
                    'season_std': record['season_std'],
                    'recent_avg': record['recent_avg'],
                    'z_score': record['z_score'],
                    'status': record['status'],
                    'created_at': datetime.utcnow()
                })
            
            # Use PostgreSQL INSERT ... ON CONFLICT for true bulk upsert
            stmt = insert(cls).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['player_id', 'stat', 'season', 'window_size'],
                set_=dict(
                    player_name=stmt.excluded.player_name,
                    season_avg=stmt.excluded.season_avg,
                    season_std=stmt.excluded.season_std,
                    recent_avg=stmt.excluded.recent_avg,
                    z_score=stmt.excluded.z_score,
                    status=stmt.excluded.status,
                    created_at=stmt.excluded.created_at
                )
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
    def get_by_player(
        cls,
        player_id: int,
        season: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List['PlayerHeatIndexORM']:
        """Get heat index records for a player.
        
        Args:
            player_id: Player identifier
            season: Optional season filter
            db: Optional database session
            
        Returns:
            List of PlayerHeatIndexORM records
        """
        def _query(session: Session):
            query = session.query(cls).filter(cls.player_id == player_id)
            if season:
                query = query.filter(cls.season == season)
            return query.order_by(cls.stat, cls.window_size).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_hot_players(
        cls,
        season: str,
        stat: str = 'PTS',
        window_size: int = 5,
        limit: int = 20,
        db: Optional[Session] = None
    ) -> List['PlayerHeatIndexORM']:
        """Get hottest players (On Fire) for a stat.
        
        Args:
            season: Season string
            stat: Statistic name
            window_size: Window size
            limit: Maximum number of players
            db: Optional database session
            
        Returns:
            List of PlayerHeatIndexORM records, sorted by Z-score descending
        """
        def _query(session: Session):
            return session.query(cls).filter(
                cls.season == season,
                cls.stat == stat,
                cls.window_size == window_size,
                cls.status == 'on_fire'
            ).order_by(cls.z_score.desc()).limit(limit).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_cold_players(
        cls,
        season: str,
        stat: str = 'PTS',
        window_size: int = 5,
        limit: int = 20,
        db: Optional[Session] = None
    ) -> List['PlayerHeatIndexORM']:
        """Get coldest players (Ice Cold) for a stat.
        
        Args:
            season: Season string
            stat: Statistic name
            window_size: Window size
            limit: Maximum number of players
            db: Optional database session
            
        Returns:
            List of PlayerHeatIndexORM records, sorted by Z-score ascending
        """
        def _query(session: Session):
            return session.query(cls).filter(
                cls.season == season,
                cls.stat == stat,
                cls.window_size == window_size,
                cls.status == 'ice_cold'
            ).order_by(cls.z_score.asc()).limit(limit).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)

