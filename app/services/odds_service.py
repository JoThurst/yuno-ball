"""Service layer for odds data operations.

This is a thin wrapper around OddsFetcher for backward compatibility
and to provide additional business logic operations.

The heavy lifting (API calls) is done by OddsFetcher.

Created: December 2, 2025
Part of: Phase 1.6 - Game Odds Ingestion
"""

from typing import Dict, Optional, List, Any
from datetime import date

from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.game_odds_sqlalchemy import GameOddsORM
from app.utils.fetch.odds_fetcher import OddsFetcher
from app.utils.config_utils import logger


class OddsService:
    """Service for odds data operations.
    
    Delegates fetching to OddsFetcher, provides business logic methods.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service."""
        self.db = db
        self._fetcher = OddsFetcher()
    
    def fetch_and_store_todays_odds(self, season: str) -> tuple:
        """Fetch and store odds for today's games. Delegates to OddsFetcher."""
        return self._fetcher.fetch_todays_odds(season=season)
    
    def get_game_odds_summary(self, game_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Get odds summary for a specific game."""
        return self._fetcher.get_game_odds_summary(game_id)
    
    def get_odds_by_date(
        self,
        game_date: date,
        country_code: str = 'US',
        db: Optional[Session] = None
    ) -> List[GameOddsORM]:
        """Get all odds for games on a specific date."""
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return GameOddsORM.get_by_date(game_date, country_code, db=session)
        else:
            return GameOddsORM.get_by_date(game_date, country_code, db=session)
    
    def format_odds_for_report(self, game_id: str, db: Optional[Session] = None) -> List[str]:
        """Format odds data for text report output."""
        summary = self.get_game_odds_summary(game_id, db=db)
        
        if not summary.get('has_odds'):
            return ["    No odds available"]
        
        lines = []
        
        consensus = summary.get('consensus', {})
        if consensus:
            avg_spread = consensus.get('avg_spread')
            if avg_spread is not None:
                spread_str = f"+{avg_spread}" if avg_spread > 0 else str(avg_spread)
                lines.append(f"    Consensus Spread: {spread_str} ({consensus.get('num_books', 0)} books)")
        
        by_book = summary.get('by_book', [])
        for book_data in by_book[:2]:
            home_ml = book_data.get('home_ml')
            away_ml = book_data.get('away_ml')
            spread = book_data.get('spread')
            
            if home_ml and away_ml:
                home_str = f"+{home_ml}" if home_ml > 0 else str(home_ml)
                away_str = f"+{away_ml}" if away_ml > 0 else str(away_ml)
                
                spread_part = ""
                if spread is not None:
                    spread_str = f"+{spread}" if spread > 0 else str(spread)
                    spread_part = f" | Spread: {spread_str}"
                
                lines.append(f"    {book_data['book']}: Home {home_str} / Away {away_str}{spread_part}")
        
        return lines if lines else ["    No odds available"]
