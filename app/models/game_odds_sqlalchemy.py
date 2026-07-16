"""SQLAlchemy ORM model for GameOdds.

This module provides the GameOddsORM class which stores betting odds
captured from the NBA's live odds endpoint.

The NBA provides free odds data for today's games including:
- Moneyline (2-way)
- Spread
- Opening and current odds
- Odds movement trends

Created: December 2, 2025
Part of: Phase 1.6 - Game Odds Ingestion
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Float, Text, Date, DateTime, Index, UniqueConstraint, ForeignKey, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert, JSONB

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class GameOddsORM(Base):
    """SQLAlchemy ORM model for game betting odds.
    
    This model stores odds data from the NBA's live odds endpoint.
    Each record represents odds for a specific game from a specific sportsbook.
    
    Attributes:
        id: Auto-incrementing primary key
        game_id: NBA game identifier
        game_date: Date of the game
        season: Season string
        home_team_id: Home team ID
        away_team_id: Away team ID
        
        Source Info:
        - sportsbook_id: Sportsbook identifier
        - sportsbook_name: Sportsbook name (e.g., 'DraftKings')
        - country_code: Country code for sportsbook
        
        Moneyline Odds:
        - home_ml_odds: Current home moneyline
        - away_ml_odds: Current away moneyline
        - home_ml_opening: Opening home moneyline
        - away_ml_opening: Opening away moneyline
        - home_ml_trend: 'up', 'down', or null
        - away_ml_trend: 'up', 'down', or null
        
        Spread Odds:
        - home_spread: Home team spread (e.g., -6.5)
        - away_spread: Away team spread (e.g., +6.5)
        - home_spread_opening: Opening home spread
        - away_spread_opening: Opening away spread
        - spread_home_odds: Odds for home spread
        - spread_away_odds: Odds for away spread
        
        Metadata:
        - raw_data: Full JSON response for reference
        - recorded_at: When odds were captured
        - updated_at: Last update time
        
    Unique Constraint:
        (game_id, sportsbook_id)
    """
    
    __tablename__ = 'game_odds'
    __table_args__ = (
        UniqueConstraint('game_id', 'sportsbook_id', name='game_odds_unique'),
        Index('idx_game_odds_game_id', 'game_id'),
        Index('idx_game_odds_game_date', 'game_date'),
        Index('idx_game_odds_season', 'season'),
        Index('idx_game_odds_sportsbook', 'sportsbook_id'),
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Game Identifiers
    game_id = Column(String(20), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(Text, nullable=False)
    home_team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    away_team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    
    # Sportsbook Info
    sportsbook_id = Column(String(50), nullable=False)  # e.g., 'sr:book:108'
    sportsbook_name = Column(Text, nullable=True)
    country_code = Column(String(10), nullable=True)
    sportsbook_url = Column(Text, nullable=True)
    
    # Moneyline Odds (stored as decimal odds, e.g., 1.370)
    home_ml_odds = Column(Float, nullable=True)
    away_ml_odds = Column(Float, nullable=True)
    home_ml_opening = Column(Float, nullable=True)
    away_ml_opening = Column(Float, nullable=True)
    home_ml_trend = Column(String(10), nullable=True)  # 'up', 'down'
    away_ml_trend = Column(String(10), nullable=True)
    
    # Spread Odds
    home_spread = Column(Float, nullable=True)  # e.g., -6.5
    away_spread = Column(Float, nullable=True)  # e.g., +6.5
    home_spread_opening = Column(Float, nullable=True)
    away_spread_opening = Column(Float, nullable=True)
    spread_home_odds = Column(Float, nullable=True)
    spread_away_odds = Column(Float, nullable=True)
    
    # Raw data for reference
    raw_data = Column(JSONB, nullable=True)
    
    # Timestamps
    recorded_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, server_default=func.now()
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'game_id': self.game_id,
            'game_date': self.game_date.isoformat() if self.game_date else None,
            'season': self.season,
            'home_team_id': self.home_team_id,
            'away_team_id': self.away_team_id,
            'sportsbook_id': self.sportsbook_id,
            'sportsbook_name': self.sportsbook_name,
            'country_code': self.country_code,
            'home_ml_odds': self.home_ml_odds,
            'away_ml_odds': self.away_ml_odds,
            'home_ml_opening': self.home_ml_opening,
            'away_ml_opening': self.away_ml_opening,
            'home_ml_trend': self.home_ml_trend,
            'away_ml_trend': self.away_ml_trend,
            'home_spread': self.home_spread,
            'away_spread': self.away_spread,
            'home_spread_opening': self.home_spread_opening,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }
    
    def decimal_to_american(self, decimal_odds: float) -> int:
        """Convert decimal odds to American odds.
        
        Args:
            decimal_odds: Decimal odds (e.g., 1.370)
            
        Returns:
            American odds (e.g., -270 or +370)
        """
        if decimal_odds >= 2.0:
            # Underdog: positive American odds
            return int((decimal_odds - 1) * 100)
        else:
            # Favorite: negative American odds
            return int(-100 / (decimal_odds - 1))
    
    def get_home_ml_american(self) -> Optional[int]:
        """Get home moneyline in American format."""
        if self.home_ml_odds:
            return self.decimal_to_american(self.home_ml_odds)
        return None
    
    def get_away_ml_american(self) -> Optional[int]:
        """Get away moneyline in American format."""
        if self.away_ml_odds:
            return self.decimal_to_american(self.away_ml_odds)
        return None
    
    def get_display_odds(self) -> str:
        """Get human-readable odds summary."""
        parts = []
        
        # Moneyline
        if self.home_ml_odds and self.away_ml_odds:
            home_am = self.get_home_ml_american()
            away_am = self.get_away_ml_american()
            home_str = f"+{home_am}" if home_am > 0 else str(home_am)
            away_str = f"+{away_am}" if away_am > 0 else str(away_am)
            parts.append(f"ML: Home {home_str} / Away {away_str}")
        
        # Spread
        if self.home_spread is not None:
            home_spread_str = f"+{self.home_spread}" if self.home_spread > 0 else str(self.home_spread)
            parts.append(f"Spread: Home {home_spread_str}")
        
        return " | ".join(parts) if parts else "No odds available"
    
    @classmethod
    def bulk_create(
        cls,
        records: List[dict],
        db: Optional[Session] = None
    ) -> int:
        """Bulk create/update odds records."""
        if not records:
            return 0
        
        def _bulk_create(session: Session) -> int:
            values = []
            now = datetime.utcnow()
            
            for record in records:
                value = {
                    'game_id': record['game_id'],
                    'game_date': record['game_date'],
                    'season': record['season'],
                    'home_team_id': record['home_team_id'],
                    'away_team_id': record['away_team_id'],
                    'sportsbook_id': record['sportsbook_id'],
                    'sportsbook_name': record.get('sportsbook_name'),
                    'country_code': record.get('country_code'),
                    'sportsbook_url': record.get('sportsbook_url'),
                    'home_ml_odds': record.get('home_ml_odds'),
                    'away_ml_odds': record.get('away_ml_odds'),
                    'home_ml_opening': record.get('home_ml_opening'),
                    'away_ml_opening': record.get('away_ml_opening'),
                    'home_ml_trend': record.get('home_ml_trend'),
                    'away_ml_trend': record.get('away_ml_trend'),
                    'home_spread': record.get('home_spread'),
                    'away_spread': record.get('away_spread'),
                    'home_spread_opening': record.get('home_spread_opening'),
                    'away_spread_opening': record.get('away_spread_opening'),
                    'spread_home_odds': record.get('spread_home_odds'),
                    'spread_away_odds': record.get('spread_away_odds'),
                    'raw_data': record.get('raw_data'),
                    'recorded_at': now,
                    'updated_at': now
                }
                values.append(value)
            
            stmt = insert(cls).values(values)
            
            # Update all fields except identifiers and recorded_at on conflict
            update_dict = {col: stmt.excluded[col] for col in values[0].keys() 
                          if col not in ['game_id', 'sportsbook_id', 'recorded_at']}
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['game_id', 'sportsbook_id'],
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
    ) -> List['GameOddsORM']:
        """Get all odds for a game (from all sportsbooks)."""
        def _query(session: Session):
            return session.query(cls).filter(
                cls.game_id == game_id
            ).order_by(cls.sportsbook_name).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_by_date(
        cls,
        game_date: date,
        country_code: Optional[str] = 'US',
        db: Optional[Session] = None
    ) -> List['GameOddsORM']:
        """Get all odds for games on a specific date."""
        def _query(session: Session):
            query = session.query(cls).filter(cls.game_date == game_date)
            if country_code:
                query = query.filter(cls.country_code == country_code)
            return query.order_by(cls.game_id, cls.sportsbook_name).all()
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    @classmethod
    def get_consensus_odds(
        cls,
        game_id: str,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get consensus (average) odds across all US sportsbooks.
        
        Args:
            game_id: Game ID
            db: Optional database session
            
        Returns:
            Dictionary with consensus odds
        """
        def _query(session: Session) -> Dict[str, Any]:
            odds = session.query(cls).filter(
                cls.game_id == game_id,
                cls.country_code == 'US'
            ).all()
            
            if not odds:
                return {}
            
            # Calculate averages
            home_ml = [o.home_ml_odds for o in odds if o.home_ml_odds]
            away_ml = [o.away_ml_odds for o in odds if o.away_ml_odds]
            spreads = [o.home_spread for o in odds if o.home_spread is not None]
            
            return {
                'game_id': game_id,
                'num_books': len(odds),
                'avg_home_ml': round(sum(home_ml) / len(home_ml), 3) if home_ml else None,
                'avg_away_ml': round(sum(away_ml) / len(away_ml), 3) if away_ml else None,
                'avg_spread': round(sum(spreads) / len(spreads), 1) if spreads else None,
                'books': [o.sportsbook_name for o in odds]
            }
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)

