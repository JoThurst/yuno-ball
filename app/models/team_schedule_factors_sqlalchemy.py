"""SQLAlchemy ORM model for TeamScheduleFactors.

This module provides the TeamScheduleFactorsORM class which represents team
schedule factors per game (days rest, B2B, 3-in-4, rest edge, etc.).

Schedule factors are calculated per team per game to identify schedule
advantages and disadvantages for betting and analysis purposes.

Created: December 2, 2025
Part of: Phase 1.5 - Schedule Spot Analysis
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, Date, DateTime, Index, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class TeamScheduleFactorsORM(Base):
    """SQLAlchemy ORM model for team schedule factors.
    
    This model tracks schedule-related factors for each team in each game,
    such as days rest, back-to-back status, and rest advantages vs opponent.
    
    Key insight: Schedule disadvantages are per team per game, not just per game.
    One team can be on a B2B while the other is on 3 days rest.
    
    Attributes:
        id: Auto-incrementing primary key
        game_id: Reference to game_schedule
        team_id: The team this record is for
        opponent_id: The opposing team
        game_date: Date of the game (denormalized for easy range queries)
        season: Season string (e.g., "2024-25")
        
        Schedule Factors:
        - days_rest: Days since this team's last game (0 = B2B)
        - is_b2b: True if team played yesterday
        - is_3_in_4: True if 3 games in last 4 days
        - is_4_in_5: True if 4 games in last 5 days
        - is_5_in_7: True if 5 games in last 7 days
        - games_last_4: Number of games in last 4 days
        - games_last_7: Number of games in last 7 days
        
        Comparative Factors:
        - opponent_days_rest: Opponent's days of rest
        - rest_edge: 'advantage' | 'even' | 'disadvantage' compared to opponent
        - rest_diff: days_rest - opponent_days_rest (positive = more rest)
        
        created_at: Timestamp when record was created
        
    Unique Constraint:
        (game_id, team_id) - One record per team per game
    """
    
    __tablename__ = 'team_schedule_factors'
    __table_args__ = (
        UniqueConstraint('game_id', 'team_id',
                        name='team_schedule_factors_unique'),
        Index('idx_team_schedule_factors_team_id', 'team_id'),
        Index('idx_team_schedule_factors_game_date', 'game_date'),
        Index('idx_team_schedule_factors_season', 'season'),
        Index('idx_team_schedule_factors_is_b2b', 'is_b2b'),
        Index('idx_team_schedule_factors_rest_edge', 'rest_edge'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identifiers
    game_id = Column(String, ForeignKey('game_schedule.game_id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    opponent_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    game_date = Column(Date, nullable=False)  # Denormalized for easy queries
    season = Column(Text, nullable=False)
    
    # Schedule Factors - This Team
    days_rest = Column(Integer, nullable=True)  # Days since last game (0 = B2B)
    is_b2b = Column(Boolean, nullable=False, default=False)  # Played yesterday
    is_3_in_4 = Column(Boolean, nullable=False, default=False)  # 3 games in last 4 days
    is_4_in_5 = Column(Boolean, nullable=False, default=False)  # 4 games in last 5 days
    is_5_in_7 = Column(Boolean, nullable=False, default=False)  # 5 games in last 7 days
    games_last_4 = Column(Integer, nullable=True)  # Count of games in last 4 days
    games_last_7 = Column(Integer, nullable=True)  # Count of games in last 7 days
    
    # Comparative Factors
    opponent_days_rest = Column(Integer, nullable=True)  # Opponent's days rest
    rest_edge = Column(Text, nullable=True)  # 'advantage' | 'even' | 'disadvantage'
    rest_diff = Column(Integer, nullable=True)  # days_rest - opponent_days_rest
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary with all schedule factors
        """
        return {
            'id': self.id,
            'game_id': self.game_id,
            'team_id': self.team_id,
            'opponent_id': self.opponent_id,
            'game_date': self.game_date.isoformat() if self.game_date else None,
            'season': self.season,
            'days_rest': self.days_rest,
            'is_b2b': self.is_b2b,
            'is_3_in_4': self.is_3_in_4,
            'is_4_in_5': self.is_4_in_5,
            'is_5_in_7': self.is_5_in_7,
            'games_last_4': self.games_last_4,
            'games_last_7': self.games_last_7,
            'opponent_days_rest': self.opponent_days_rest,
            'rest_edge': self.rest_edge,
            'rest_diff': self.rest_diff,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_schedule_description(self) -> str:
        """Get a human-readable description of the schedule situation.
        
        Returns:
            String description like "B2B (0 days rest)" or "Well rested (3+ days)"
        """
        if self.is_b2b:
            return "Back-to-Back"
        elif self.is_3_in_4:
            return f"3-in-4 nights ({self.days_rest} days rest)"
        elif self.is_4_in_5:
            return f"4-in-5 nights ({self.days_rest} days rest)"
        elif self.is_5_in_7:
            return f"5-in-7 nights ({self.days_rest} days rest)"
        elif self.days_rest is not None:
            if self.days_rest >= 3:
                return f"Well rested ({self.days_rest} days rest)"
            elif self.days_rest == 2:
                return f"Normal rest ({self.days_rest} days rest)"
            elif self.days_rest == 1:
                return f"Short rest ({self.days_rest} day rest)"
            else:
                return f"{self.days_rest} days rest"
        return "Unknown"
    
    def get_rest_edge_description(self) -> str:
        """Get a human-readable description of rest advantage.
        
        Returns:
            String description of rest edge vs opponent
        """
        if self.rest_edge == 'advantage':
            return f"Rest advantage (+{self.rest_diff} days vs opponent)"
        elif self.rest_edge == 'disadvantage':
            return f"Rest disadvantage ({self.rest_diff} days vs opponent)"
        else:
            return "Even rest"
    
    # ==================== Class Methods for CRUD Operations ====================
    
    @classmethod
    def create(
        cls,
        game_id: str,
        team_id: int,
        opponent_id: int,
        game_date: date,
        season: str,
        days_rest: Optional[int] = None,
        is_b2b: bool = False,
        is_3_in_4: bool = False,
        is_4_in_5: bool = False,
        is_5_in_7: bool = False,
        games_last_4: Optional[int] = None,
        games_last_7: Optional[int] = None,
        opponent_days_rest: Optional[int] = None,
        rest_edge: Optional[str] = None,
        rest_diff: Optional[int] = None,
        db: Optional[Session] = None
    ) -> 'TeamScheduleFactorsORM':
        """Create or update a schedule factors record (upsert).
        
        Args:
            game_id: Game identifier
            team_id: Team identifier
            opponent_id: Opponent team identifier
            game_date: Date of the game
            season: Season string
            days_rest: Days since last game
            is_b2b: Back-to-back flag
            is_3_in_4: 3 games in 4 days flag
            is_4_in_5: 4 games in 5 days flag
            is_5_in_7: 5 games in 7 days flag
            games_last_4: Games count in last 4 days
            games_last_7: Games count in last 7 days
            opponent_days_rest: Opponent's days rest
            rest_edge: Rest edge classification
            rest_diff: Rest differential
            db: Optional database session
            
        Returns:
            TeamScheduleFactorsORM: The created or updated record
        """
        def _create(session: Session) -> 'TeamScheduleFactorsORM':
            # Check if record exists
            existing = session.query(cls).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
            
            if existing:
                # Update existing record (preserve created_at)
                existing.opponent_id = opponent_id
                existing.game_date = game_date
                existing.season = season
                existing.days_rest = days_rest
                existing.is_b2b = is_b2b
                existing.is_3_in_4 = is_3_in_4
                existing.is_4_in_5 = is_4_in_5
                existing.is_5_in_7 = is_5_in_7
                existing.games_last_4 = games_last_4
                existing.games_last_7 = games_last_7
                existing.opponent_days_rest = opponent_days_rest
                existing.rest_edge = rest_edge
                existing.rest_diff = rest_diff
                logger.debug(f"Updated schedule factors: Game {game_id}, Team {team_id}")
            else:
                # Create new record
                existing = cls(
                    game_id=game_id,
                    team_id=team_id,
                    opponent_id=opponent_id,
                    game_date=game_date,
                    season=season,
                    days_rest=days_rest,
                    is_b2b=is_b2b,
                    is_3_in_4=is_3_in_4,
                    is_4_in_5=is_4_in_5,
                    is_5_in_7=is_5_in_7,
                    games_last_4=games_last_4,
                    games_last_7=games_last_7,
                    opponent_days_rest=opponent_days_rest,
                    rest_edge=rest_edge,
                    rest_diff=rest_diff
                )
                session.add(existing)
                logger.debug(f"Created schedule factors: Game {game_id}, Team {team_id}")
            
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
        """Bulk create/update schedule factors using PostgreSQL INSERT ... ON CONFLICT.
        
        Args:
            records: List of dictionaries with schedule factors data
            db: Optional database session
            
        Returns:
            int: Number of records created/updated
        """
        if not records:
            return 0
        
        def _bulk_create(session: Session) -> int:
            # Prepare data for bulk insert
            values = []
            for record in records:
                value = {
                    'game_id': record['game_id'],
                    'team_id': record['team_id'],
                    'opponent_id': record['opponent_id'],
                    'game_date': record['game_date'],
                    'season': record['season'],
                    'days_rest': record.get('days_rest'),
                    'is_b2b': record.get('is_b2b', False),
                    'is_3_in_4': record.get('is_3_in_4', False),
                    'is_4_in_5': record.get('is_4_in_5', False),
                    'is_5_in_7': record.get('is_5_in_7', False),
                    'games_last_4': record.get('games_last_4'),
                    'games_last_7': record.get('games_last_7'),
                    'opponent_days_rest': record.get('opponent_days_rest'),
                    'rest_edge': record.get('rest_edge'),
                    'rest_diff': record.get('rest_diff'),
                    'created_at': datetime.utcnow()
                }
                values.append(value)
            
            # Use PostgreSQL INSERT ... ON CONFLICT for true bulk upsert
            # Note: created_at is NOT updated on conflict to preserve original creation timestamp
            stmt = insert(cls).values(values)
            
            # Build set dictionary for on_conflict_do_update (exclude created_at)
            update_dict = {col: stmt.excluded[col] for col in values[0].keys() 
                          if col not in ['game_id', 'team_id', 'created_at']}
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['game_id', 'team_id'],
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
    def get_by_game_and_team(
        cls,
        game_id: str,
        team_id: int,
        db: Optional[Session] = None
    ) -> Optional['TeamScheduleFactorsORM']:
        """Get schedule factors for a specific game and team.
        
        Args:
            game_id: Game identifier
            team_id: Team identifier
            db: Optional database session
            
        Returns:
            TeamScheduleFactorsORM record or None
        """
        def _query(session: Session):
            return session.query(cls).filter(
                cls.game_id == game_id,
                cls.team_id == team_id
            ).first()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_by_team(
        cls,
        team_id: int,
        season: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List['TeamScheduleFactorsORM']:
        """Get all schedule factors for a team.
        
        Args:
            team_id: Team identifier
            season: Optional season filter
            db: Optional database session
            
        Returns:
            List of TeamScheduleFactorsORM records
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
    def get_by_date(
        cls,
        game_date: date,
        db: Optional[Session] = None
    ) -> List['TeamScheduleFactorsORM']:
        """Get all schedule factors for a specific date.
        
        Args:
            game_date: Date to filter by
            db: Optional database session
            
        Returns:
            List of TeamScheduleFactorsORM records
        """
        def _query(session: Session):
            return session.query(cls).filter(
                cls.game_date == game_date
            ).order_by(cls.team_id).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_b2b_games(
        cls,
        season: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> List['TeamScheduleFactorsORM']:
        """Get all back-to-back games in a season or date range.
        
        Args:
            season: Season string
            start_date: Optional start date filter
            end_date: Optional end date filter
            db: Optional database session
            
        Returns:
            List of TeamScheduleFactorsORM records where is_b2b=True
        """
        def _query(session: Session):
            query = session.query(cls).filter(
                cls.season == season,
                cls.is_b2b == True
            )
            if start_date:
                query = query.filter(cls.game_date >= start_date)
            if end_date:
                query = query.filter(cls.game_date <= end_date)
            return query.order_by(cls.game_date.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_rest_advantages(
        cls,
        season: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> List['TeamScheduleFactorsORM']:
        """Get games where a team has a rest advantage.
        
        Args:
            season: Season string
            start_date: Optional start date filter
            end_date: Optional end date filter
            db: Optional database session
            
        Returns:
            List of TeamScheduleFactorsORM records with rest advantage
        """
        def _query(session: Session):
            query = session.query(cls).filter(
                cls.season == season,
                cls.rest_edge == 'advantage'
            )
            if start_date:
                query = query.filter(cls.game_date >= start_date)
            if end_date:
                query = query.filter(cls.game_date <= end_date)
            return query.order_by(cls.rest_diff.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def clear_by_season(cls, season: str, db: Optional[Session] = None) -> int:
        """Clear all schedule factors for a specific season.
        
        This is useful before recalculating to ensure no stale data remains.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            int: Number of records deleted
        """
        def _clear(session: Session) -> int:
            deleted_count = session.query(cls).filter(cls.season == season).delete()
            session.flush()
            logger.info(f"Cleared {deleted_count} schedule factors records for season {season}")
            return deleted_count
        
        if db:
            return _clear(db)
        
        with get_db_context() as session:
            count = _clear(session)
            session.commit()
            return count
    
    @classmethod
    def get_team_schedule_summary(
        cls,
        team_id: int,
        season: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get a summary of schedule factors for a team in a season.
        
        Args:
            team_id: Team identifier
            season: Season string
            db: Optional database session
            
        Returns:
            Dictionary with summary statistics
        """
        def _query(session: Session) -> Dict[str, Any]:
            from sqlalchemy import func
            
            records = session.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season
            ).all()
            
            if not records:
                return {}
            
            b2b_count = sum(1 for r in records if r.is_b2b)
            three_in_four = sum(1 for r in records if r.is_3_in_4)
            five_in_seven = sum(1 for r in records if r.is_5_in_7)
            advantages = sum(1 for r in records if r.rest_edge == 'advantage')
            disadvantages = sum(1 for r in records if r.rest_edge == 'disadvantage')
            avg_rest = sum(r.days_rest or 0 for r in records) / len(records) if records else 0
            
            return {
                'team_id': team_id,
                'season': season,
                'total_games': len(records),
                'b2b_games': b2b_count,
                'b2b_pct': round(b2b_count / len(records) * 100, 1) if records else 0,
                'three_in_four_games': three_in_four,
                'five_in_seven_games': five_in_seven,
                'rest_advantages': advantages,
                'rest_disadvantages': disadvantages,
                'avg_days_rest': round(avg_rest, 2)
            }
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)

