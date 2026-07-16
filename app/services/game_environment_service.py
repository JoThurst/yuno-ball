"""Service for analyzing game environments by combining team metrics.

This service combines metrics from both teams in a matchup to characterize
the game environment (pace, scoring, style matchups).

"""

from typing import List, Dict, Optional, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
from app.utils.config_utils import logger


class GameEnvironmentService:
    """Service for calculating game environment metrics."""
    
    # League average benchmarks (approximate NBA averages)
    LEAGUE_AVG_OFF_RTG = 115.0
    LEAGUE_AVG_DEF_RTG = 108.0
    LEAGUE_AVG_PACE = 99.0
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service.
        
        Args:
            db: Optional database session
        """
        self.db = db
    
    def calculate_pace_projection(
        self,
        home_pace: float,
        away_pace: float
    ) -> float:
        """Calculate projected pace for the game.
        
        Uses a weighted average favoring the faster team slightly.
        
        Args:
            home_pace: Home team's recent pace
            away_pace: Away team's recent pace
            
        Returns:
            Projected pace
        """
        # Simple average with slight weight to the faster team
        avg_pace = (home_pace + away_pace) / 2
        max_pace = max(home_pace, away_pace)
        
        # Blend: 70% average, 30% max (faster team influences more)
        return round(0.7 * avg_pace + 0.3 * max_pace, 2)
    
    def calculate_scoring_env_index(
        self,
        home_off_rtg: float,
        home_def_rtg: float,
        away_off_rtg: float,
        away_def_rtg: float,
        pace: float
    ) -> float:
        """Calculate scoring environment index.
        
        High index = high-scoring game expected.
        Factors: both teams' offense vs defense, pace.
        
        Args:
            home_off_rtg: Home offensive rating
            home_def_rtg: Home defensive rating
            away_off_rtg: Away offensive rating
            away_def_rtg: Away defensive rating
            pace: Projected pace
            
        Returns:
            Scoring environment index (normalized around 100)
        """
        # Expected points: offense vs opponent's defense
        home_expected = (home_off_rtg + away_def_rtg) / 2
        away_expected = (away_off_rtg + home_def_rtg) / 2
        
        # Average expected scoring
        avg_expected = (home_expected + away_expected) / 2
        
        # Adjust for pace (normalize to league average)
        pace_factor = pace / self.LEAGUE_AVG_PACE
        
        # Scoring index: expected scoring * pace factor
        scoring_index = avg_expected * pace_factor
        
        # Normalize to ~100 scale
        normalized = (scoring_index / self.LEAGUE_AVG_OFF_RTG) * 100
        
        return round(normalized, 2)
    
    def calculate_three_env_index(
        self,
        home_pct_3pt: Optional[float],
        away_pct_3pt: Optional[float]
    ) -> Optional[float]:
        """Calculate 3-point environment index.
        
        High index = both teams shoot lots of 3s.
        
        Args:
            home_pct_3pt: Home team % points from 3PT
            away_pct_3pt: Away team % points from 3PT
            
        Returns:
            3-point environment index or None if data unavailable
        """
        if home_pct_3pt is None or away_pct_3pt is None:
            return None
        
        # Average of both teams
        avg_3pt_pct = (home_pct_3pt + away_pct_3pt) / 2
        
        # Normalize to 100 scale (assuming league avg ~35% of points from 3)
        normalized = (avg_3pt_pct / 0.35) * 100
        
        return round(normalized, 2)
    
    def calculate_chaos_index(
        self,
        pace: float,
        home_tov_pct: Optional[float],
        away_tov_pct: Optional[float]
    ) -> float:
        """Calculate chaos index.
        
        High index = fast pace + turnovers = chaotic game.
        
        Args:
            pace: Projected pace
            home_tov_pct: Home team turnover %
            away_tov_pct: Away team turnover %
            
        Returns:
            Chaos index
        """
        # Pace component (normalized)
        pace_component = (pace / self.LEAGUE_AVG_PACE) * 50
        
        # Turnover component (if available)
        tov_component = 0
        if home_tov_pct is not None and away_tov_pct is not None:
            avg_tov = (home_tov_pct + away_tov_pct) / 2
            # League avg TOV% ~14%
            tov_component = (avg_tov / 0.14) * 50
        else:
            tov_component = 50  # Neutral if no data
        
        chaos_index = pace_component + tov_component
        
        return round(chaos_index, 2)
    
    def calculate_environment_for_game(
        self,
        game_id: int,
        game_date: date,
        season: str,
        home_team_id: int,
        away_team_id: int,
        window_size: int,
        db: Session
    ) -> Optional[Dict]:
        """Calculate environment metrics for a single game.
        
        Args:
            game_id: Game identifier
            game_date: Date of game
            season: Season string
            home_team_id: Home team identifier
            away_team_id: Away team identifier
            window_size: Window size for metrics
            db: Database session
            
        Returns:
            Dictionary with environment data or None if insufficient data
        """
        # Get recent metrics for both teams
        home_metrics = db.query(TeamDailyMetricsORM).filter(
            TeamDailyMetricsORM.team_id == home_team_id,
            TeamDailyMetricsORM.season == season,
            TeamDailyMetricsORM.window_size == window_size
        ).order_by(TeamDailyMetricsORM.stat_date.desc()).first()
        
        away_metrics = db.query(TeamDailyMetricsORM).filter(
            TeamDailyMetricsORM.team_id == away_team_id,
            TeamDailyMetricsORM.season == season,
            TeamDailyMetricsORM.window_size == window_size
        ).order_by(TeamDailyMetricsORM.stat_date.desc()).first()
        
        if not home_metrics or not away_metrics:
            logger.warning(
                f"Insufficient metrics for game {game_id}: "
                f"home={home_team_id if not home_metrics else 'OK'}, "
                f"away={away_team_id if not away_metrics else 'OK'}"
            )
            return None
        
        # Extract lastN metrics
        home_off = home_metrics.off_rtg_lastn
        home_def = home_metrics.def_rtg_lastn
        home_pace = home_metrics.pace_lastn
        away_off = away_metrics.off_rtg_lastn
        away_def = away_metrics.def_rtg_lastn
        away_pace = away_metrics.pace_lastn
        
        # Check for required metrics
        if None in [home_off, home_def, home_pace, away_off, away_def, away_pace]:
            logger.warning(f"Missing core metrics for game {game_id}")
            return None
        
        # Calculate environment indices
        pace_proj = self.calculate_pace_projection(home_pace, away_pace)
        scoring_env = self.calculate_scoring_env_index(
            home_off, home_def, away_off, away_def, pace_proj
        )
        three_env = self.calculate_three_env_index(
            home_metrics.pct_pts_3pt_lastn,
            away_metrics.pct_pts_3pt_lastn
        )
        chaos = self.calculate_chaos_index(
            pace_proj,
            home_metrics.tov_pct_lastn,
            away_metrics.tov_pct_lastn
        )
        
        # Calculate boolean flags
        pace_up_home = (home_pace > home_metrics.pace_season + 2) if home_metrics.pace_season else False
        pace_up_away = (away_pace > away_metrics.pace_season + 2) if away_metrics.pace_season else False
        
        three_point_fest = (
            three_env is not None and three_env > 110  # Both teams 10%+ above league avg
        )
        
        # Paint battle: both teams emphasize paint
        paint_battle = False
        if home_metrics.pct_pts_paint_lastn and away_metrics.pct_pts_paint_lastn:
            avg_paint = (home_metrics.pct_pts_paint_lastn + away_metrics.pct_pts_paint_lastn) / 2
            paint_battle = avg_paint > 0.40  # Both teams get 40%+ from paint
        
        # Glass war: both teams high ORB%
        glass_war = False
        if home_metrics.orb_pct_lastn and away_metrics.orb_pct_lastn:
            avg_orb = (home_metrics.orb_pct_lastn + away_metrics.orb_pct_lastn) / 2
            glass_war = avg_orb > 0.28  # League avg ~26%
        
        # Whistle heavy: both teams high FTR
        whistle_heavy = False
        if home_metrics.ftr_lastn and away_metrics.ftr_lastn:
            avg_ftr = (home_metrics.ftr_lastn + away_metrics.ftr_lastn) / 2
            whistle_heavy = avg_ftr > 0.30  # Both teams frequent FT attempts
        
        # Generate tags with stricter thresholds
        # Note: Will be further refined with percentile-based thresholds in batch processing
        tags = []
        
        # Pace tags - stricter thresholds (top/bottom 20-25% of games)
        if pace_proj > 105:  # ~75th percentile
            tags.append("fast_pace")
        elif pace_proj < 94:  # ~25th percentile
            tags.append("slow_pace")
        
        # Scoring tags - stricter thresholds
        if scoring_env > 108:  # ~80th percentile
            tags.append("high_scoring")
        elif scoring_env < 92:  # ~20th percentile
            tags.append("defensive_battle")
        
        # Special matchup flags (keep these as absolute thresholds)
        if three_point_fest:
            tags.append("three_point_fest")
        if paint_battle:
            tags.append("paint_battle")
        if glass_war:
            tags.append("glass_war")
        if whistle_heavy:
            tags.append("whistle_heavy")
        
        # Chaos - stricter threshold
        if chaos > 115:  # ~top 15%
            tags.append("chaotic")
        
        # Build environment data
        environment_data = {
            'home_off_rtg_lastn': home_off,
            'home_def_rtg_lastn': home_def,
            'home_pace_lastn': home_pace,
            'away_off_rtg_lastn': away_off,
            'away_def_rtg_lastn': away_def,
            'away_pace_lastn': away_pace,
            'pace_projection': pace_proj,
            'scoring_env_index': scoring_env,
            'three_env_index': three_env,
            'reb_env_index': None,  # Future: calculate from ORB/DRB matchups
            'ft_env_index': None,  # Future: calculate from FTR matchups
            'chaos_index': chaos,
            'pace_up_for_home': pace_up_home,
            'pace_up_for_away': pace_up_away,
            'three_point_fest': three_point_fest,
            'paint_battle': paint_battle,
            'glass_war': glass_war,
            'whistle_heavy': whistle_heavy,
            'tags': tags,
            'details_json': {
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'window_size': window_size
            }
        }
        
        return {
            'game_id': game_id,
            'game_date': game_date,
            'season': season,
            'home_team_id': home_team_id,
            'away_team_id': away_team_id,
            **environment_data
        }
    
    def calculate_for_date(
        self,
        target_date: date,
        season: str,
        window_size: int = 10,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Calculate game environments for all games on a specific date.
        
        Args:
            target_date: Date to calculate for
            season: Season string
            window_size: Window size for metrics
            db: Optional database session
            
        Returns:
            List of environment dictionaries
        """
        session = db or self.db if hasattr(self, 'db') else None
        if not session:
            with get_db_context() as session:
                return self._calculate_for_date_internal(target_date, season, window_size, session)
        else:
            return self._calculate_for_date_internal(target_date, season, window_size, session)
    
    def _calculate_for_date_internal(
        self,
        target_date: date,
        season: str,
        window_size: int,
        db: Session
    ) -> List[Dict]:
        """Internal method to calculate for a date."""
        logger.info(f"Calculating game environments for {target_date} ({season})")
        
        # Get all games for this date
        # Note: GameScheduleORM has 2 rows per game (one for each team)
        # We need to group by game_id and determine home/away teams
        # Must convert UTC to EST/EDT before comparing dates (games stored in UTC)
        from sqlalchemy import text
        
        game_rows = db.query(GameScheduleORM).filter(
            text(f"DATE((game_schedule.game_date AT TIME ZONE 'UTC') AT TIME ZONE 'America/New_York') = '{target_date}'"),
            GameScheduleORM.season == season
        ).all()
        
        if not game_rows:
            logger.info(f"No games scheduled for {target_date}")
            return []
        
        logger.info(f"Found {len(game_rows)} game schedule rows for {target_date}")
        
        # Group by game_id and extract home/away teams
        games_dict = {}
        for row in game_rows:
            game_id = row.game_id
            if game_id not in games_dict:
                games_dict[game_id] = {'home_team_id': None, 'away_team_id': None, 'home_count': 0, 'away_count': 0}
            
            if row.home_or_away == 'H':
                games_dict[game_id]['home_team_id'] = row.team_id
                games_dict[game_id]['home_count'] += 1
            elif row.home_or_away == 'A':
                games_dict[game_id]['away_team_id'] = row.team_id
                games_dict[game_id]['away_count'] += 1
            else:
                logger.warning(f"Game {game_id} has unknown home_or_away value: {row.home_or_away}")
        
        logger.info(f"Grouped into {len(games_dict)} unique game IDs")
        
        # Filter out incomplete games (missing home or away)
        complete_games = {}
        incomplete_games = []
        for gid, teams in games_dict.items():
            if teams['home_team_id'] is not None and teams['away_team_id'] is not None:
                complete_games[gid] = teams
            else:
                incomplete_games.append({
                    'game_id': gid,
                    'home_team_id': teams['home_team_id'],
                    'away_team_id': teams['away_team_id'],
                    'home_count': teams['home_count'],
                    'away_count': teams['away_count']
                })
        
        if incomplete_games:
            logger.warning(f"Found {len(incomplete_games)} incomplete games:")
            for game in incomplete_games[:5]:  # Log first 5
                logger.warning(f"  Game {game['game_id']}: home={game['home_team_id']} (count={game['home_count']}), away={game['away_team_id']} (count={game['away_count']})")
        
        logger.info(f"Found {len(complete_games)} complete games for {target_date}")
        
        # Calculate environment for each game
        all_environments = []
        for game_id, teams in complete_games.items():
            try:
                environment = self.calculate_environment_for_game(
                    game_id=int(game_id),
                    game_date=target_date,
                    season=season,
                    home_team_id=teams['home_team_id'],
                    away_team_id=teams['away_team_id'],
                    window_size=window_size,
                    db=db
                )
                
                if environment:
                    all_environments.append(environment)
            except Exception as e:
                logger.error(f"Error calculating environment for game {game_id}: {e}")
                continue
        
        # Persist to database
        if all_environments:
            try:
                GameEnvironmentDailyORM.bulk_create(all_environments, db=db)
                db.commit()
                logger.info(f"Persisted {len(all_environments)} game environments")
            except Exception as e:
                logger.error(f"Error persisting game environments: {e}")
                db.rollback()
                raise
        
        logger.info(f"Game environment calculation complete: {len(all_environments)} games")
        
        return all_environments

