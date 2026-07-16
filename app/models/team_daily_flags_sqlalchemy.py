"""SQLAlchemy ORM model for TeamDailyFlags.

This module provides the TeamDailyFlagsORM class which represents qualitative
flags/tags for teams based on their performance trends.

"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, Index, UniqueConstraint, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class TeamDailyFlagsORM(Base):
    """SQLAlchemy ORM model for team daily flags.
    
    This model tracks qualitative flags/tags for teams based on performance trends.
    Flags are determined by analyzing deltas from team_daily_metrics.
    
    Flag Types:
        - offense_on_fire: OffRtg delta >= +5
        - defense_slipping: DefRtg delta >= +5 (positive = worse defense)
        - pace_up: Pace delta >= +3
        - shooting_surge: eFG% delta significant
        - paint_attack: High paint scoring delta
        - threes_team: High 3PT% delta
        - transition_team: High fastbreak delta
        - glass_bully: High ORB% delta
        - style_shift: Multiple scoring profile changes
    
    Attributes:
        id: Auto-incrementing primary key
        stat_date: Date of flag calculation
        season: Season year (e.g., "2024-25")
        team_id: Reference to team (NBA API ID)
        team_name: Name of the team
        flag_type: Type of flag (see above)
        severity: Magnitude of the trend (delta value or z-score)
        details_json: Additional context/metrics as JSON
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (stat_date, team_id, flag_type) - One flag per team/date/type
    """
    
    __tablename__ = 'team_daily_flags'
    __table_args__ = (
        UniqueConstraint('stat_date', 'team_id', 'flag_type',
                        name='team_daily_flags_unique'),
        Index('idx_team_daily_flags_team_id', 'team_id'),
        Index('idx_team_daily_flags_season', 'season'),
        Index('idx_team_daily_flags_stat_date', 'stat_date'),
        Index('idx_team_daily_flags_flag_type', 'flag_type'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identifiers
    stat_date = Column(Date, nullable=False)
    season = Column(Text, nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    team_name = Column(Text, nullable=False)
    
    # Flag Information
    flag_type = Column(Text, nullable=False)
    severity = Column(Float, nullable=True)  # Magnitude of trend
    details_json = Column(JSONB, nullable=True)  # Additional context
    
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
            'stat_date': self.stat_date.isoformat() if self.stat_date else None,
            'season': self.season,
            'team_id': self.team_id,
            'team_name': self.team_name,
            'flag_type': self.flag_type,
            'severity': self.severity,
            'details_json': self.details_json,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create(
        cls,
        stat_date: date,
        season: str,
        team_id: int,
        team_name: str,
        flag_type: str,
        severity: Optional[float] = None,
        details_json: Optional[Dict] = None,
        db: Optional[Session] = None
    ) -> 'TeamDailyFlagsORM':
        """Create or update a flag record (upsert).
        
        Args:
            stat_date: Date of flag
            season: Season string
            team_id: Team identifier
            team_name: Team name
            flag_type: Type of flag
            severity: Magnitude of trend
            details_json: Additional context
            db: Optional database session
            
        Returns:
            TeamDailyFlagsORM: The created or updated record
        """
        def _create(session: Session) -> 'TeamDailyFlagsORM':
            # Check if record exists
            existing = session.query(cls).filter(
                cls.stat_date == stat_date,
                cls.team_id == team_id,
                cls.flag_type == flag_type
            ).first()
            
            if existing:
                # Update existing record (preserve created_at)
                existing.season = season
                existing.team_name = team_name
                existing.severity = severity
                existing.details_json = details_json
                logger.debug(f"Updated flag: {team_name} - {flag_type}")
            else:
                # Create new record
                existing = cls(
                    stat_date=stat_date,
                    season=season,
                    team_id=team_id,
                    team_name=team_name,
                    flag_type=flag_type,
                    severity=severity,
                    details_json=details_json
                )
                session.add(existing)
                logger.debug(f"Created flag: {team_name} - {flag_type}")
            
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
        """Bulk create/update flags using PostgreSQL INSERT ... ON CONFLICT.
        
        Args:
            records: List of dictionaries with flag data
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
                    'stat_date': record['stat_date'],
                    'season': record['season'],
                    'team_id': record['team_id'],
                    'team_name': record['team_name'],
                    'flag_type': record['flag_type'],
                    'severity': record.get('severity'),
                    'details_json': record.get('details_json'),
                    'created_at': datetime.utcnow()
                })
            
            # Use PostgreSQL INSERT ... ON CONFLICT for true bulk upsert
            stmt = insert(cls).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['stat_date', 'team_id', 'flag_type'],
                set_=dict(
                    season=stmt.excluded.season,
                    team_name=stmt.excluded.team_name,
                    severity=stmt.excluded.severity,
                    details_json=stmt.excluded.details_json
                    # created_at is NOT updated - preserve original creation timestamp
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
    def get_by_team_and_date(
        cls,
        team_id: int,
        stat_date: date,
        db: Optional[Session] = None
    ) -> List['TeamDailyFlagsORM']:
        """Get all flags for a team on a specific date.
        
        Args:
            team_id: Team identifier
            stat_date: Date of flags
            db: Optional database session
            
        Returns:
            List of TeamDailyFlagsORM records
        """
        def _query(session: Session):
            return session.query(cls).filter(
                cls.team_id == team_id,
                cls.stat_date == stat_date
            ).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_by_flag_type(
        cls,
        season: str,
        flag_type: str,
        limit: Optional[int] = None,
        db: Optional[Session] = None
    ) -> List['TeamDailyFlagsORM']:
        """Get all teams with a specific flag type.
        
        Args:
            season: Season string
            flag_type: Type of flag
            limit: Optional limit on results
            db: Optional database session
            
        Returns:
            List of TeamDailyFlagsORM records sorted by severity desc
        """
        def _query(session: Session):
            query = session.query(cls).filter(
                cls.season == season,
                cls.flag_type == flag_type
            ).order_by(cls.severity.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def clear_by_season(cls, season: str, db: Optional[Session] = None) -> int:
        """Clear all flags for a specific season.
        
        This is useful before recalculating flags to ensure no stale data remains.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            int: Number of records deleted
        """
        def _clear(session: Session) -> int:
            deleted_count = session.query(cls).filter(cls.season == season).delete()
            session.flush()
            logger.info(f"Cleared {deleted_count} team flags for season {season}")
            return deleted_count
        
        if db:
            return _clear(db)
        
        with get_db_context() as session:
            count = _clear(session)
            session.commit()
            return count

