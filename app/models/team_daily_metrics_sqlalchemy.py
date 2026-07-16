"""SQLAlchemy ORM model for TeamDailyMetrics.

This module provides the TeamDailyMetricsORM class which represents team
performance metrics comparing season-to-date statistics with recent form.

"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, Index, UniqueConstraint, ForeignKey, func, text
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class TeamDailyMetricsORM(Base):
    """SQLAlchemy ORM model for team daily metrics.
    
    This model tracks team performance metrics comparing season-to-date
    statistics with recent form (last N games).
    
    Attributes:
        id: Auto-incrementing primary key
        stat_date: Date of metric calculation
        season: Season year (e.g., "2024-25")
        team_id: Reference to team (NBA API ID)
        team_name: Name of the team
        window_size: Number of recent games used for calculation (default 10)
        
        Season Stats (from LeagueDashTeamStatsORM):
        - off_rtg_season, def_rtg_season, net_rtg_season, pace_season
        - efg_season, tov_pct_season, orb_pct_season, ftr_season
        - pct_pts_3pt_season, pct_pts_paint_season, pct_pts_mid_season
        - pct_pts_ft_season, pct_pts_fb_season, pct_pts_off_tov_season
        - sec_chance_pts_per100_season, fb_pts_per100_season, paint_pts_per100_season
        - opp_sec_chance_pts_per100_season, opp_fb_pts_per100_season, opp_paint_pts_per100_season
        
        Last N Stats (calculated from TeamGameStatsORM):
        - Same metrics with _lastn suffix
        
        Deltas (lastN - season):
        - Same metrics with _delta suffix
        
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (stat_date, team_id, window_size) - One record per team/date/window
    """
    
    __tablename__ = 'team_daily_metrics'
    __table_args__ = (
        UniqueConstraint('stat_date', 'team_id', 'window_size',
                        name='team_daily_metrics_unique'),
        Index('idx_team_daily_metrics_team_id', 'team_id'),
        Index('idx_team_daily_metrics_season', 'season'),
        Index('idx_team_daily_metrics_stat_date', 'stat_date'),
        Index('idx_team_daily_metrics_window_size', 'window_size'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identifiers
    stat_date = Column(Date, nullable=False)
    season = Column(Text, nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    team_name = Column(Text, nullable=False)
    window_size = Column(Integer, nullable=False, default=10, server_default=text("10"))
    
    # ==================== Core Efficiency & Pace (Season) ====================
    off_rtg_season = Column(Float, nullable=True)
    def_rtg_season = Column(Float, nullable=True)
    net_rtg_season = Column(Float, nullable=True)
    pace_season = Column(Float, nullable=True)
    
    # ==================== Four Factors (Season) ====================
    efg_season = Column(Float, nullable=True)  # Effective FG%
    tov_pct_season = Column(Float, nullable=True)  # Turnover %
    orb_pct_season = Column(Float, nullable=True)  # Offensive Rebound %
    ftr_season = Column(Float, nullable=True)  # Free Throw Rate
    
    # ==================== Scoring Profile (Season) ====================
    pct_pts_3pt_season = Column(Float, nullable=True)  # % of points from 3PT
    pct_pts_paint_season = Column(Float, nullable=True)  # % of points from paint
    pct_pts_mid_season = Column(Float, nullable=True)  # % of points from mid-range
    pct_pts_ft_season = Column(Float, nullable=True)  # % of points from FT
    pct_pts_fb_season = Column(Float, nullable=True)  # % of points from fastbreak
    pct_pts_off_tov_season = Column(Float, nullable=True)  # % of points off turnovers
    
    # ==================== Extra Scoring per 100 (Season) ====================
    sec_chance_pts_per100_season = Column(Float, nullable=True)  # 2nd chance pts per 100 poss
    fb_pts_per100_season = Column(Float, nullable=True)  # Fastbreak pts per 100
    paint_pts_per100_season = Column(Float, nullable=True)  # Paint pts per 100
    opp_sec_chance_pts_per100_season = Column(Float, nullable=True)  # Opp 2nd chance per 100
    opp_fb_pts_per100_season = Column(Float, nullable=True)  # Opp fastbreak per 100
    opp_paint_pts_per100_season = Column(Float, nullable=True)  # Opp paint per 100
    
    # ==================== Core Efficiency & Pace (Last N) ====================
    off_rtg_lastn = Column(Float, nullable=True)
    def_rtg_lastn = Column(Float, nullable=True)
    net_rtg_lastn = Column(Float, nullable=True)
    pace_lastn = Column(Float, nullable=True)
    
    # ==================== Four Factors (Last N) ====================
    efg_lastn = Column(Float, nullable=True)
    tov_pct_lastn = Column(Float, nullable=True)
    orb_pct_lastn = Column(Float, nullable=True)
    ftr_lastn = Column(Float, nullable=True)
    
    # ==================== Scoring Profile (Last N) ====================
    pct_pts_3pt_lastn = Column(Float, nullable=True)
    pct_pts_paint_lastn = Column(Float, nullable=True)
    pct_pts_mid_lastn = Column(Float, nullable=True)
    pct_pts_ft_lastn = Column(Float, nullable=True)
    pct_pts_fb_lastn = Column(Float, nullable=True)
    pct_pts_off_tov_lastn = Column(Float, nullable=True)
    
    # ==================== Extra Scoring per 100 (Last N) ====================
    sec_chance_pts_per100_lastn = Column(Float, nullable=True)
    fb_pts_per100_lastn = Column(Float, nullable=True)
    paint_pts_per100_lastn = Column(Float, nullable=True)
    opp_sec_chance_pts_per100_lastn = Column(Float, nullable=True)
    opp_fb_pts_per100_lastn = Column(Float, nullable=True)
    opp_paint_pts_per100_lastn = Column(Float, nullable=True)
    
    # ==================== Core Efficiency & Pace (Deltas) ====================
    off_rtg_delta = Column(Float, nullable=True)
    def_rtg_delta = Column(Float, nullable=True)
    net_rtg_delta = Column(Float, nullable=True)
    pace_delta = Column(Float, nullable=True)
    
    # ==================== Four Factors (Deltas) ====================
    efg_delta = Column(Float, nullable=True)
    tov_pct_delta = Column(Float, nullable=True)
    orb_pct_delta = Column(Float, nullable=True)
    ftr_delta = Column(Float, nullable=True)
    
    # ==================== Scoring Profile (Deltas) ====================
    pct_pts_3pt_delta = Column(Float, nullable=True)
    pct_pts_paint_delta = Column(Float, nullable=True)
    pct_pts_mid_delta = Column(Float, nullable=True)
    pct_pts_ft_delta = Column(Float, nullable=True)
    pct_pts_fb_delta = Column(Float, nullable=True)
    pct_pts_off_tov_delta = Column(Float, nullable=True)
    
    # ==================== Extra Scoring per 100 (Deltas) ====================
    sec_chance_pts_per100_delta = Column(Float, nullable=True)
    fb_pts_per100_delta = Column(Float, nullable=True)
    paint_pts_per100_delta = Column(Float, nullable=True)
    opp_sec_chance_pts_per100_delta = Column(Float, nullable=True)
    opp_fb_pts_per100_delta = Column(Float, nullable=True)
    opp_paint_pts_per100_delta = Column(Float, nullable=True)
    
    # ==================== Strength of Schedule ====================
    # SoS is based on average opponent NetRtg - higher = faced tougher opponents
    sos_net_season = Column(Float, nullable=True)  # Avg opponent NetRtg for all games
    sos_net_last10 = Column(Float, nullable=True)  # Avg opponent NetRtg last 10 games
    sos_net_delta = Column(Float, nullable=True)   # last10 - season (positive = harder recent schedule)
    
    # Optional: Offensive/Defensive SoS
    sos_off_season = Column(Float, nullable=True)  # Avg opponent OffRtg for all games
    sos_def_season = Column(Float, nullable=True)  # Avg opponent DefRtg for all games
    sos_off_last10 = Column(Float, nullable=True)  # Avg opponent OffRtg last 10 games
    sos_def_last10 = Column(Float, nullable=True)  # Avg opponent DefRtg last 10 games
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, server_default=func.now()
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary with all metrics
        """
        return {
            'id': self.id,
            'stat_date': self.stat_date.isoformat() if self.stat_date else None,
            'season': self.season,
            'team_id': self.team_id,
            'team_name': self.team_name,
            'window_size': self.window_size,
            # Season stats
            'off_rtg_season': self.off_rtg_season,
            'def_rtg_season': self.def_rtg_season,
            'net_rtg_season': self.net_rtg_season,
            'pace_season': self.pace_season,
            'efg_season': self.efg_season,
            'tov_pct_season': self.tov_pct_season,
            'orb_pct_season': self.orb_pct_season,
            'ftr_season': self.ftr_season,
            # Last N stats
            'off_rtg_lastn': self.off_rtg_lastn,
            'def_rtg_lastn': self.def_rtg_lastn,
            'net_rtg_lastn': self.net_rtg_lastn,
            'pace_lastn': self.pace_lastn,
            'efg_lastn': self.efg_lastn,
            'tov_pct_lastn': self.tov_pct_lastn,
            'orb_pct_lastn': self.orb_pct_lastn,
            'ftr_lastn': self.ftr_lastn,
            # Deltas
            'off_rtg_delta': self.off_rtg_delta,
            'def_rtg_delta': self.def_rtg_delta,
            'net_rtg_delta': self.net_rtg_delta,
            'pace_delta': self.pace_delta,
            'efg_delta': self.efg_delta,
            'tov_pct_delta': self.tov_pct_delta,
            'orb_pct_delta': self.orb_pct_delta,
            'ftr_delta': self.ftr_delta,
            # Strength of Schedule
            'sos_net_season': self.sos_net_season,
            'sos_net_last10': self.sos_net_last10,
            'sos_net_delta': self.sos_net_delta,
            'sos_off_season': self.sos_off_season,
            'sos_def_season': self.sos_def_season,
            'sos_off_last10': self.sos_off_last10,
            'sos_def_last10': self.sos_def_last10,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create(
        cls,
        stat_date: date,
        season: str,
        team_id: int,
        team_name: str,
        window_size: int,
        metrics: Dict[str, Optional[float]],
        db: Optional[Session] = None
    ) -> 'TeamDailyMetricsORM':
        """Create or update a team metrics record (upsert).
        
        Args:
            stat_date: Date of calculation
            season: Season string
            team_id: Team identifier
            team_name: Team name
            window_size: Window size for last N games
            metrics: Dictionary of metric values
            db: Optional database session
            
        Returns:
            TeamDailyMetricsORM: The created or updated record
        """
        def _create(session: Session) -> 'TeamDailyMetricsORM':
            # Check if record exists
            existing = session.query(cls).filter(
                cls.stat_date == stat_date,
                cls.team_id == team_id,
                cls.window_size == window_size
            ).first()
            
            if existing:
                # Update existing record (preserve created_at)
                existing.season = season
                existing.team_name = team_name
                for key, value in metrics.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                logger.debug(f"Updated team metrics: {team_name} ({season}, {window_size}g)")
            else:
                # Create new record
                existing = cls(
                    stat_date=stat_date,
                    season=season,
                    team_id=team_id,
                    team_name=team_name,
                    window_size=window_size,
                    **metrics
                )
                session.add(existing)
                logger.debug(f"Created team metrics: {team_name} ({season}, {window_size}g)")
            
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
        """Bulk create/update team metrics using PostgreSQL INSERT ... ON CONFLICT.
        
        Args:
            records: List of dictionaries with team metrics data
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
                # Extract metrics from the record
                metrics_dict = {k: v for k, v in record.items() 
                              if k not in ['stat_date', 'season', 'team_id', 'team_name', 'window_size']}
                
                value = {
                    'stat_date': record['stat_date'],
                    'season': record['season'],
                    'team_id': record['team_id'],
                    'team_name': record['team_name'],
                    'window_size': record['window_size'],
                    'created_at': datetime.utcnow()
                }
                value.update(metrics_dict)
                values.append(value)
            
            # Use PostgreSQL INSERT ... ON CONFLICT for true bulk upsert
            # Note: created_at is NOT updated on conflict to preserve original creation timestamp
            stmt = insert(cls).values(values)
            
            # Build set dictionary for on_conflict_do_update (exclude created_at)
            update_dict = {col: stmt.excluded[col] for col in values[0].keys() 
                          if col not in ['stat_date', 'team_id', 'window_size', 'created_at']}
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['stat_date', 'team_id', 'window_size'],
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
    def get_by_team_and_date(
        cls,
        team_id: int,
        stat_date: date,
        window_size: Optional[int] = None,
        db: Optional[Session] = None
    ) -> Optional['TeamDailyMetricsORM']:
        """Get team metrics for a specific date.
        
        Args:
            team_id: Team identifier
            stat_date: Date of metrics
            window_size: Optional window size filter
            db: Optional database session
            
        Returns:
            TeamDailyMetricsORM record or None
        """
        def _query(session: Session):
            query = session.query(cls).filter(
                cls.team_id == team_id,
                cls.stat_date == stat_date
            )
            if window_size is not None:
                query = query.filter(cls.window_size == window_size)
            return query.first()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_by_season(
        cls,
        season: str,
        window_size: Optional[int] = None,
        db: Optional[Session] = None
    ) -> List['TeamDailyMetricsORM']:
        """Get all team metrics for a season.
        
        Args:
            season: Season string
            window_size: Optional window size filter
            db: Optional database session
            
        Returns:
            List of TeamDailyMetricsORM records
        """
        def _query(session: Session):
            query = session.query(cls).filter(cls.season == season)
            if window_size is not None:
                query = query.filter(cls.window_size == window_size)
            return query.order_by(cls.stat_date.desc(), cls.team_name).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def clear_by_season(cls, season: str, db: Optional[Session] = None) -> int:
        """Clear all team metrics for a specific season.
        
        This is useful before recalculating metrics to ensure no stale data remains.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            int: Number of records deleted
        """
        def _clear(session: Session) -> int:
            deleted_count = session.query(cls).filter(cls.season == season).delete()
            session.flush()
            logger.info(f"Cleared {deleted_count} team metrics records for season {season}")
            return deleted_count
        
        if db:
            return _clear(db)
        
        with get_db_context() as session:
            count = _clear(session)
            session.commit()
            return count
    
    @classmethod
    def get_teams_by_delta(
        cls,
        season: str,
        metric: str,
        window_size: int = 10,
        limit: int = 10,
        ascending: bool = False,
        db: Optional[Session] = None
    ) -> List['TeamDailyMetricsORM']:
        """Get teams sorted by a specific delta metric.
        
        Args:
            season: Season string
            metric: Metric name (e.g., 'off_rtg_delta', 'net_rtg_delta')
            window_size: Window size
            limit: Maximum number of teams
            ascending: Sort ascending (default descending for biggest positive deltas)
            db: Optional database session
            
        Returns:
            List of TeamDailyMetricsORM records
        """
        def _query(session: Session):
            if not hasattr(cls, metric):
                raise ValueError(f"Invalid metric: {metric}")
            
            column = getattr(cls, metric)
            query = session.query(cls).filter(
                cls.season == season,
                cls.window_size == window_size,
                column.isnot(None)
            )
            
            if ascending:
                query = query.order_by(column.asc())
            else:
                query = query.order_by(column.desc())
            
            return query.limit(limit).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)

