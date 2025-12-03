"""Service layer for injury data operations.

This is a thin wrapper around InjuryFetcher for backward compatibility
and to provide additional business logic operations.

The heavy lifting (API calls, batch processing) is done by InjuryFetcher.

Created: December 2, 2025
Part of: Phase 1.6 - Injury Tracking
"""

from typing import Dict, Optional, List
from datetime import date

from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.player_game_status_sqlalchemy import PlayerGameStatusORM
from app.utils.fetch.injury_fetcher import InjuryFetcher
from app.utils.config_utils import logger


class InjuryService:
    """Service for injury data operations.
    
    Delegates fetching to InjuryFetcher, provides business logic methods.
    """
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service."""
        self.db = db
        self._fetcher = InjuryFetcher()
    
    def fetch_for_completed_games(
        self,
        season: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> tuple:
        """Fetch injury data for completed games. Delegates to InjuryFetcher."""
        return self._fetcher.fetch_injury_data(
            season=season,
            start_date=start_date,
            end_date=end_date
        )
    
    def fetch_for_date(self, target_date: date, season: str) -> tuple:
        """Fetch injury data for a specific date."""
        return self._fetcher.fetch_for_date(target_date, season)
    
    def backfill_season(self, season: str) -> tuple:
        """Backfill injury data for an entire season."""
        return self._fetcher.backfill_season(season)
    
    def get_injury_summary(self, target_date: date, db: Optional[Session] = None) -> Dict:
        """Get a summary of injuries for a specific date."""
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._get_injury_summary_internal(target_date, session)
        else:
            return self._get_injury_summary_internal(target_date, session)
    
    def _get_injury_summary_internal(self, target_date: date, db: Session) -> Dict:
        """Internal method for injury summary."""
        injuries = PlayerGameStatusORM.get_injuries_by_date(target_date, db=db)
        
        # Group by team
        by_team: Dict[int, List[Dict]] = {}
        for injury in injuries:
            team_id = injury.team_id
            if team_id not in by_team:
                by_team[team_id] = []
            by_team[team_id].append({
                'player_id': injury.player_id,
                'player_name': injury.player_name,
                'description': injury.not_playing_description
            })
        
        return {
            'date': target_date.isoformat(),
            'total_injuries': len(injuries),
            'teams_affected': len(by_team),
            'by_team': by_team
        }
    
    def get_player_injury_history(
        self,
        player_id: int,
        season: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[PlayerGameStatusORM]:
        """Get injury history for a specific player."""
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return PlayerGameStatusORM.get_player_injury_history(player_id, season, db=session)
        else:
            return PlayerGameStatusORM.get_player_injury_history(player_id, season, db=session)
    
    def get_current_team_injuries(
        self,
        team_id: int,
        db: Optional[Session] = None
    ) -> List[PlayerGameStatusORM]:
        """Get current injuries for a team."""
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return PlayerGameStatusORM.get_current_injuries(team_id, db=session)
        else:
            return PlayerGameStatusORM.get_current_injuries(team_id, db=session)
