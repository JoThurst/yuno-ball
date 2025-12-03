"""SQLAlchemy ORM model for PlayerGameStatus.

This module provides the PlayerGameStatusORM class which stores player
status/injury information captured from the Live BoxScore endpoint.

Data is captured per player per game, including:
- Active/Inactive status
- Injury reason and description
- Whether player actually played

Created: December 2, 2025
Part of: Phase 1.6 - Injury Tracking
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, Date, DateTime, Index, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class PlayerGameStatusORM(Base):
    """SQLAlchemy ORM model for player game status/injury tracking.
    
    This model stores status information for players in each game,
    captured from the NBA's Live BoxScore endpoint.
    
    Attributes:
        id: Auto-incrementing primary key
        game_id: NBA game identifier (10-digit)
        player_id: Reference to players table
        team_id: Team the player was on
        game_date: Date of the game
        season: Season string
        
        Status Fields:
        - status: 'ACTIVE' or 'INACTIVE'
        - not_playing_reason: Reason code ('INACTIVE_INJURY', 'INACTIVE_GLEAGUE_TWOWAY', etc.)
        - not_playing_description: Human-readable description ('Right Hamstring; Strain')
        - played: Whether player actually played in the game
        
        Metadata:
        - recorded_at: When this status was captured
        - updated_at: Last update time
        
    Unique Constraint:
        (game_id, player_id)
    """
    
    __tablename__ = 'player_game_status'
    __table_args__ = (
        UniqueConstraint('game_id', 'player_id', name='player_game_status_unique'),
        Index('idx_player_game_status_game_id', 'game_id'),
        Index('idx_player_game_status_player_id', 'player_id'),
        Index('idx_player_game_status_team_id', 'team_id'),
        Index('idx_player_game_status_game_date', 'game_date'),
        Index('idx_player_game_status_season', 'season'),
        Index('idx_player_game_status_reason', 'not_playing_reason'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identifiers
    game_id = Column(String(20), nullable=False)
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(Text, nullable=False)
    
    # Status Fields
    status = Column(String(20), nullable=True)  # ACTIVE, INACTIVE
    not_playing_reason = Column(String(50), nullable=True)  # INACTIVE_INJURY, INACTIVE_GLEAGUE_TWOWAY
    not_playing_description = Column(Text, nullable=True)  # "Right Hamstring; Strain"
    played = Column(Boolean, nullable=False, default=False)
    
    # For convenience - player name snapshot
    player_name = Column(Text, nullable=True)
    
    # Timestamps
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Common reason codes
    REASON_INJURY = 'INACTIVE_INJURY'
    REASON_GLEAGUE = 'INACTIVE_GLEAGUE_TWOWAY'
    REASON_REST = 'INACTIVE_REST'
    REASON_PERSONAL = 'INACTIVE_PERSONAL'
    REASON_SUSPENSION = 'INACTIVE_SUSPENSION'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'game_id': self.game_id,
            'player_id': self.player_id,
            'team_id': self.team_id,
            'game_date': self.game_date.isoformat() if self.game_date else None,
            'season': self.season,
            'status': self.status,
            'not_playing_reason': self.not_playing_reason,
            'not_playing_description': self.not_playing_description,
            'played': self.played,
            'player_name': self.player_name,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_injured(self) -> bool:
        """Check if player was injured for this game."""
        return self.not_playing_reason == self.REASON_INJURY
    
    def is_gleague(self) -> bool:
        """Check if player was in G-League."""
        return self.not_playing_reason == self.REASON_GLEAGUE
    
    def get_status_emoji(self) -> str:
        """Get emoji for status."""
        if self.played:
            return "✅"
        elif self.is_injured():
            return "🏥"
        elif self.is_gleague():
            return "🔄"
        elif self.status == 'INACTIVE':
            return "❌"
        else:
            return "➖"
    
    def get_display_status(self) -> str:
        """Get human-readable status string."""
        emoji = self.get_status_emoji()
        
        if self.played:
            return f"{emoji} Played"
        elif self.not_playing_description:
            return f"{emoji} {self.not_playing_description}"
        elif self.not_playing_reason:
            reason_display = {
                'INACTIVE_INJURY': 'Injured',
                'INACTIVE_GLEAGUE_TWOWAY': 'G-League',
                'INACTIVE_REST': 'Rest',
                'INACTIVE_PERSONAL': 'Personal',
                'INACTIVE_SUSPENSION': 'Suspended'
            }
            return f"{emoji} {reason_display.get(self.not_playing_reason, self.not_playing_reason)}"
        elif self.status == 'INACTIVE':
            return f"{emoji} Inactive"
        else:
            return f"{emoji} Did Not Play"
    
    @classmethod
    def bulk_create(
        cls,
        records: List[dict],
        db: Optional[Session] = None
    ) -> int:
        """Bulk create/update status records using PostgreSQL INSERT ... ON CONFLICT.
        
        Args:
            records: List of dictionaries with status data
            db: Optional database session
            
        Returns:
            int: Number of records created/updated
        """
        if not records:
            return 0
        
        def _bulk_create(session: Session) -> int:
            values = []
            now = datetime.utcnow()
            
            for record in records:
                value = {
                    'game_id': record['game_id'],
                    'player_id': record['player_id'],
                    'team_id': record['team_id'],
                    'game_date': record['game_date'],
                    'season': record['season'],
                    'status': record.get('status'),
                    'not_playing_reason': record.get('not_playing_reason'),
                    'not_playing_description': record.get('not_playing_description'),
                    'played': record.get('played', False),
                    'player_name': record.get('player_name'),
                    'recorded_at': now,
                    'updated_at': now
                }
                values.append(value)
            
            stmt = insert(cls).values(values)
            
            # On conflict, update status fields but preserve recorded_at
            update_dict = {
                'status': stmt.excluded.status,
                'not_playing_reason': stmt.excluded.not_playing_reason,
                'not_playing_description': stmt.excluded.not_playing_description,
                'played': stmt.excluded.played,
                'player_name': stmt.excluded.player_name,
                'updated_at': stmt.excluded.updated_at
            }
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['game_id', 'player_id'],
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
    def get_by_game(
        cls,
        game_id: str,
        db: Optional[Session] = None
    ) -> List['PlayerGameStatusORM']:
        """Get all player statuses for a game."""
        def _query(session: Session):
            return session.query(cls).filter(
                cls.game_id == game_id
            ).order_by(cls.team_id, cls.player_name).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_injuries_by_date(
        cls,
        game_date: date,
        db: Optional[Session] = None
    ) -> List['PlayerGameStatusORM']:
        """Get all injury records for a specific date."""
        def _query(session: Session):
            return session.query(cls).filter(
                cls.game_date == game_date,
                cls.not_playing_reason == cls.REASON_INJURY
            ).order_by(cls.team_id, cls.player_name).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_player_injury_history(
        cls,
        player_id: int,
        season: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List['PlayerGameStatusORM']:
        """Get injury history for a player."""
        def _query(session: Session):
            query = session.query(cls).filter(
                cls.player_id == player_id,
                cls.not_playing_reason == cls.REASON_INJURY
            )
            if season:
                query = query.filter(cls.season == season)
            return query.order_by(cls.game_date.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_games_with_status_data(
        cls,
        season: str,
        db: Optional[Session] = None
    ) -> List[str]:
        """Get list of game IDs that already have status data."""
        def _query(session: Session):
            result = session.query(cls.game_id).filter(
                cls.season == season
            ).distinct().all()
            return [r[0] for r in result]
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_current_injuries(
        cls,
        team_id: Optional[int] = None,
        db: Optional[Session] = None
    ) -> List['PlayerGameStatusORM']:
        """Get most recent injury status for each player.
        
        Returns the most recent game where a player was injured.
        """
        def _query(session: Session):
            from sqlalchemy import func
            
            # Subquery to get max game_date per player with injury
            subquery = session.query(
                cls.player_id,
                func.max(cls.game_date).label('max_date')
            ).filter(
                cls.not_playing_reason == cls.REASON_INJURY
            )
            
            if team_id:
                subquery = subquery.filter(cls.team_id == team_id)
            
            subquery = subquery.group_by(cls.player_id).subquery()
            
            # Join to get full records
            query = session.query(cls).join(
                subquery,
                (cls.player_id == subquery.c.player_id) & 
                (cls.game_date == subquery.c.max_date)
            ).filter(cls.not_playing_reason == cls.REASON_INJURY)
            
            return query.order_by(cls.game_date.desc()).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)

