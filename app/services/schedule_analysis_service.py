"""Service for calculating team schedule factors (B2B, rest days, etc.).

This service analyzes game schedules to identify schedule advantages and
disadvantages for each team in each game. Key insight: schedule factors
are per team per game - one team can be on a B2B while the other is well-rested.

Created: December 2, 2025
Part of: Phase 1.5 - Schedule Spot Analysis
"""

from typing import List, Dict, Optional, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import get_db_context
from app.models.team_sqlalchemy import TeamORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
from app.utils.config_utils import logger


class ScheduleAnalysisService:
    """Service for calculating team schedule factors (B2B, rest days, etc.)."""
    
    # Rest edge thresholds
    REST_ADVANTAGE_THRESHOLD = 2  # If you have 2+ more rest days, you have an advantage
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service.
        
        Args:
            db: Optional database session
        """
        self.db = db
    
    def calculate_days_rest(
        self,
        team_id: int,
        game_date: date,
        team_games: List[GameScheduleORM]
    ) -> Optional[int]:
        """Calculate days since the team's last game.
        
        Args:
            team_id: Team identifier
            game_date: Date of the current game
            team_games: List of team's games (sorted by date desc)
            
        Returns:
            Number of days since last game, or None if no previous game found
        """
        # Find the most recent game before this one
        for game in team_games:
            game_date_only = game.game_date.date() if isinstance(game.game_date, datetime) else game.game_date
            if game_date_only < game_date:
                days = (game_date - game_date_only).days
                return days
        
        return None  # No previous game found (first game of season)
    
    def count_games_in_window(
        self,
        game_date: date,
        team_games: List[GameScheduleORM],
        days_back: int
    ) -> int:
        """Count games in the last N days (including current game date).
        
        Args:
            game_date: Date of the current game
            team_games: List of team's games
            days_back: Number of days to look back
            
        Returns:
            Number of games in the window (excluding current game)
        """
        window_start = game_date - timedelta(days=days_back)
        count = 0
        
        for game in team_games:
            game_date_only = game.game_date.date() if isinstance(game.game_date, datetime) else game.game_date
            # Count games between window_start and day before game_date
            if window_start <= game_date_only < game_date:
                count += 1
        
        return count
    
    def calculate_rest_edge(
        self,
        team_days_rest: Optional[int],
        opponent_days_rest: Optional[int]
    ) -> Tuple[Optional[str], Optional[int]]:
        """Calculate rest edge compared to opponent.
        
        Args:
            team_days_rest: Team's days of rest
            opponent_days_rest: Opponent's days of rest
            
        Returns:
            Tuple of (rest_edge, rest_diff)
            - rest_edge: 'advantage' | 'even' | 'disadvantage' | None
            - rest_diff: team_days_rest - opponent_days_rest
        """
        if team_days_rest is None or opponent_days_rest is None:
            return None, None
        
        rest_diff = team_days_rest - opponent_days_rest
        
        if rest_diff >= self.REST_ADVANTAGE_THRESHOLD:
            return 'advantage', rest_diff
        elif rest_diff <= -self.REST_ADVANTAGE_THRESHOLD:
            return 'disadvantage', rest_diff
        else:
            return 'even', rest_diff
    
    def calculate_schedule_factors_for_game(
        self,
        game: GameScheduleORM,
        team_games: List[GameScheduleORM],
        opponent_games: List[GameScheduleORM],
        season: str
    ) -> Dict:
        """Calculate schedule factors for a single team in a single game.
        
        Args:
            game: The game to analyze
            team_games: All games for this team in the season
            opponent_games: All games for the opponent in the season
            season: Season string
            
        Returns:
            Dictionary with schedule factors
        """
        game_date = game.game_date.date() if isinstance(game.game_date, datetime) else game.game_date
        
        # Calculate days rest
        days_rest = self.calculate_days_rest(game.team_id, game_date, team_games)
        opponent_days_rest = self.calculate_days_rest(game.opponent_team_id, game_date, opponent_games)
        
        # Count games in windows
        games_last_4 = self.count_games_in_window(game_date, team_games, 4)
        games_last_7 = self.count_games_in_window(game_date, team_games, 7)
        
        # Determine flags
        is_b2b = days_rest == 0 if days_rest is not None else False
        is_3_in_4 = games_last_4 >= 2  # 2 games in last 4 days + current = 3 in 4
        is_4_in_5 = self.count_games_in_window(game_date, team_games, 5) >= 3  # 3 + current = 4 in 5
        is_5_in_7 = games_last_7 >= 4  # 4 + current = 5 in 7
        
        # Calculate rest edge
        rest_edge, rest_diff = self.calculate_rest_edge(days_rest, opponent_days_rest)
        
        return {
            'game_id': game.game_id,
            'team_id': game.team_id,
            'opponent_id': game.opponent_team_id,
            'game_date': game_date,
            'season': season,
            'days_rest': days_rest,
            'is_b2b': is_b2b,
            'is_3_in_4': is_3_in_4,
            'is_4_in_5': is_4_in_5,
            'is_5_in_7': is_5_in_7,
            'games_last_4': games_last_4,
            'games_last_7': games_last_7,
            'opponent_days_rest': opponent_days_rest,
            'rest_edge': rest_edge,
            'rest_diff': rest_diff
        }
    
    def calculate_for_season(
        self,
        season: str,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Calculate schedule factors for all games in a season.
        
        Args:
            season: Season string (e.g., "2024-25")
            db: Optional database session
            
        Returns:
            List of schedule factor dictionaries
        """
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._calculate_for_season_internal(season, session)
        else:
            return self._calculate_for_season_internal(season, session)
    
    def _calculate_for_season_internal(
        self,
        season: str,
        db: Session
    ) -> List[Dict]:
        """Internal method to calculate schedule factors for a season."""
        logger.info(f"Starting schedule factors calculation for season {season}")
        
        # Clear existing records for this season
        logger.info(f"Clearing existing schedule factors for season {season}...")
        deleted_count = TeamScheduleFactorsORM.clear_by_season(season, db=db)
        logger.info(f"Cleared {deleted_count} existing schedule factors records")
        
        # Get all teams
        teams = TeamORM.get_all(db=db)
        team_ids = {team.team_id for team in teams}
        logger.info(f"Found {len(teams)} teams")
        
        # Pre-fetch all games for the season, grouped by team
        all_games = db.query(GameScheduleORM).filter(
            GameScheduleORM.season == season
        ).order_by(GameScheduleORM.game_date.desc()).all()
        
        # Group games by team
        games_by_team: Dict[int, List[GameScheduleORM]] = {}
        for game in all_games:
            if game.team_id not in games_by_team:
                games_by_team[game.team_id] = []
            games_by_team[game.team_id].append(game)
        
        logger.info(f"Fetched {len(all_games)} games for {len(games_by_team)} teams")
        
        # Calculate factors for each team's games
        all_factors = []
        games_processed = 0
        
        for team_id, team_games in games_by_team.items():
            for game in team_games:
                # Get opponent's games
                opponent_games = games_by_team.get(game.opponent_team_id, [])
                
                # Calculate factors
                factors = self.calculate_schedule_factors_for_game(
                    game=game,
                    team_games=team_games,
                    opponent_games=opponent_games,
                    season=season
                )
                all_factors.append(factors)
                games_processed += 1
            
            if games_processed % 100 == 0:
                logger.info(f"Processed {games_processed} game-team combinations")
        
        # Persist to database using bulk upsert
        if all_factors:
            try:
                count = TeamScheduleFactorsORM.bulk_create(all_factors, db=db)
                db.commit()
                logger.info(f"Persisted {count} schedule factors records to database")
            except Exception as e:
                logger.error(f"Error persisting schedule factors: {e}")
                db.rollback()
                raise
        
        logger.info(f"Schedule factors calculation complete: {len(all_factors)} records")
        return all_factors
    
    def calculate_for_date_range(
        self,
        season: str,
        start_date: date,
        end_date: date,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Calculate schedule factors for games in a date range.
        
        Args:
            season: Season string
            start_date: Start date
            end_date: End date
            db: Optional database session
            
        Returns:
            List of schedule factor dictionaries
        """
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._calculate_for_date_range_internal(
                    season, start_date, end_date, session
                )
        else:
            return self._calculate_for_date_range_internal(
                season, start_date, end_date, session
            )
    
    def _calculate_for_date_range_internal(
        self,
        season: str,
        start_date: date,
        end_date: date,
        db: Session
    ) -> List[Dict]:
        """Internal method to calculate for a date range."""
        logger.info(f"Calculating schedule factors for {start_date} to {end_date}")
        
        # Get all teams
        teams = TeamORM.get_all(db=db)
        
        # Pre-fetch all games for the season (needed for lookback)
        all_games = db.query(GameScheduleORM).filter(
            GameScheduleORM.season == season
        ).order_by(GameScheduleORM.game_date.desc()).all()
        
        # Group games by team
        games_by_team: Dict[int, List[GameScheduleORM]] = {}
        for game in all_games:
            if game.team_id not in games_by_team:
                games_by_team[game.team_id] = []
            games_by_team[game.team_id].append(game)
        
        # Get games in the date range
        games_in_range = db.query(GameScheduleORM).filter(
            GameScheduleORM.season == season,
            func.date(GameScheduleORM.game_date) >= start_date,
            func.date(GameScheduleORM.game_date) <= end_date
        ).all()
        
        logger.info(f"Found {len(games_in_range)} games in date range")
        
        # Calculate factors for each game
        all_factors = []
        
        for game in games_in_range:
            team_games = games_by_team.get(game.team_id, [])
            opponent_games = games_by_team.get(game.opponent_team_id, [])
            
            factors = self.calculate_schedule_factors_for_game(
                game=game,
                team_games=team_games,
                opponent_games=opponent_games,
                season=season
            )
            all_factors.append(factors)
        
        # Persist using bulk upsert
        if all_factors:
            try:
                count = TeamScheduleFactorsORM.bulk_create(all_factors, db=db)
                db.commit()
                logger.info(f"Persisted {count} schedule factors records")
            except Exception as e:
                logger.error(f"Error persisting schedule factors: {e}")
                db.rollback()
                raise
        
        return all_factors
    
    def calculate_for_date(
        self,
        target_date: date,
        season: str,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Calculate schedule factors for all games on a specific date.
        
        Args:
            target_date: Date to calculate factors for
            season: Season string
            db: Optional database session
            
        Returns:
            List of schedule factor dictionaries
        """
        return self.calculate_for_date_range(
            season=season,
            start_date=target_date,
            end_date=target_date,
            db=db
        )
    
    def get_schedule_summary_for_date(
        self,
        target_date: date,
        db: Optional[Session] = None
    ) -> Dict:
        """Get a summary of schedule factors for a specific date.
        
        Args:
            target_date: Date to get summary for
            db: Optional database session
            
        Returns:
            Dictionary with summary statistics
        """
        session = db or self.db
        if not session:
            with get_db_context() as session:
                return self._get_schedule_summary_for_date_internal(target_date, session)
        else:
            return self._get_schedule_summary_for_date_internal(target_date, session)
    
    def _get_schedule_summary_for_date_internal(
        self,
        target_date: date,
        db: Session
    ) -> Dict:
        """Internal method to get schedule summary."""
        factors = TeamScheduleFactorsORM.get_by_date(target_date, db=db)
        
        if not factors:
            return {
                'date': target_date.isoformat(),
                'total_team_games': 0,
                'b2b_teams': [],
                'rest_advantages': [],
                'rest_disadvantages': []
            }
        
        b2b_teams = []
        rest_advantages = []
        rest_disadvantages = []
        
        for factor in factors:
            if factor.is_b2b:
                b2b_teams.append({
                    'team_id': factor.team_id,
                    'opponent_id': factor.opponent_id,
                    'game_id': factor.game_id
                })
            
            if factor.rest_edge == 'advantage':
                rest_advantages.append({
                    'team_id': factor.team_id,
                    'opponent_id': factor.opponent_id,
                    'rest_diff': factor.rest_diff,
                    'team_rest': factor.days_rest,
                    'opponent_rest': factor.opponent_days_rest
                })
            elif factor.rest_edge == 'disadvantage':
                rest_disadvantages.append({
                    'team_id': factor.team_id,
                    'opponent_id': factor.opponent_id,
                    'rest_diff': factor.rest_diff,
                    'team_rest': factor.days_rest,
                    'opponent_rest': factor.opponent_days_rest
                })
        
        return {
            'date': target_date.isoformat(),
            'total_team_games': len(factors),
            'total_games': len(factors) // 2,  # Each game has 2 team entries
            'b2b_count': len(b2b_teams),
            'b2b_teams': b2b_teams,
            'rest_advantages': rest_advantages,
            'rest_disadvantages': rest_disadvantages
        }

