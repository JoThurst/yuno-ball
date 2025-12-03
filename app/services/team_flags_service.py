"""Service for generating team daily flags based on performance trends.

This service analyzes team metrics deltas to generate qualitative flags
(e.g., "offense_on_fire", "defense_slipping").

Created: December 2024
Part of: Enhanced Analytics Engine (Phase 1.4 - Team Trend Analysis)
"""

from typing import List, Dict, Optional
from datetime import date
from sqlalchemy.orm import Session

from app.database import get_db_context
from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
from app.models.team_daily_flags_sqlalchemy import TeamDailyFlagsORM
from app.utils.config_utils import logger


class TeamFlagsService:
    """Service for generating team performance flags."""
    
    # Tightened thresholds for flag detection (more selective)
    # Note: Thresholds are now stricter to ensure flags are meaningful
    THRESHOLDS = {
        # Offensive performance (directional)
        'offense_rising': {
            'metric': 'off_rtg_delta', 
            'threshold': 5.0,  # +5 OffRtg improvement
            'direction': 'positive',
            'require_above_league': False  # Can improve even if below average
        },
        'offense_falling': {
            'metric': 'off_rtg_delta', 
            'threshold': -5.0,  # -5 OffRtg decline
            'direction': 'negative',
            'require_below_league': False
        },
        
        # Defensive performance (directional)
        'defense_improving': {
            'metric': 'def_rtg_delta', 
            'threshold': -4.0,  # -5 DefRtg (lower is better)
            'direction': 'negative',
            'require_below_league': False
        },
        'defense_declining': {
            'metric': 'def_rtg_delta', 
            'threshold': 5.0,  # +5 DefRtg (higher is worse)
            'direction': 'positive',
            'require_above_league': False
        },
        
        # Pace (directional)
        'pace_up': {
            'metric': 'pace_delta', 
            'threshold': 4.0,  # +4 possessions/game (stricter than before)
            'direction': 'positive',
            'require_above_league': False
        },
        'pace_down': {
            'metric': 'pace_delta', 
            'threshold': -4.0,  # -4 possessions/game
            'direction': 'negative',
            'require_below_league': False
        },
        
        # Shooting efficiency (directional)
        'shooting_hot': {
            'metric': 'efg_delta', 
            'threshold': 0.03,  # +3 percentage points (stricter)
            'direction': 'positive',
            'require_above_league': False
        },
        'shooting_cold': {
            'metric': 'efg_delta', 
            'threshold': -0.03,  # -3 percentage points
            'direction': 'negative',
            'require_below_league': False
        },
        
        # Turnovers (directional)
        'turnover_prone': {
            'metric': 'tov_pct_delta', 
            'threshold': 0.02,  # +2 percentage points (stricter)
            'direction': 'positive',
            'require_above_league': False
        },
        'ball_secure': {
            'metric': 'tov_pct_delta', 
            'threshold': -0.03,  # -2 percentage points (stricter)
            'direction': 'negative',
            'require_below_league': False
        },
        
        # Style flags (optional - only for significant shifts)
        'three_point_heavy': {
            'metric': 'pct_pts_3pt_delta', 
            'threshold': 0.05,  # +5 percentage points
            'direction': 'positive',
            'require_above_league': False
        },
        'paint_attack': {
            'metric': 'pct_pts_paint_delta', 
            'threshold': 0.03,  # +5 percentage points
            'direction': 'positive',
            'require_above_league': False
        },
        'transition_heavy': {
            'metric': 'pct_pts_fb_delta', 
            'threshold': 0.03,  # +5 percentage points
            'direction': 'positive',
            'require_above_league': False
        },
    }
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service.
        
        Args:
            db: Optional database session
        """
        self.db = db
    
    def generate_flags_for_team(
        self,
        team_metrics: TeamDailyMetricsORM,
        db: Session
    ) -> List[Dict]:
        """Generate flags for a single team based on their metrics.
        
        Args:
            team_metrics: TeamDailyMetricsORM record with calculated deltas
            db: Database session
            
        Returns:
            List of flag dictionaries
        """
        flags = []
        
        for flag_type, config in self.THRESHOLDS.items():
            metric_name = config['metric']
            threshold = config['threshold']
            direction = config['direction']
            
            # Get the delta value
            delta_value = getattr(team_metrics, metric_name, None)
            
            if delta_value is None:
                continue
            
            # Check if threshold is met
            flag_triggered = False
            if direction == 'positive' and delta_value >= threshold:
                flag_triggered = True
            elif direction == 'negative' and delta_value <= threshold:
                flag_triggered = True
            
            if flag_triggered:
                # Get additional context metrics
                details = {
                    'delta': round(delta_value, 4),
                    'threshold': threshold,
                    'metric': metric_name
                }
                
                # Add season and lastN values for context
                season_metric = metric_name.replace('_delta', '_season')
                lastn_metric = metric_name.replace('_delta', '_lastn')
                
                if hasattr(team_metrics, season_metric):
                    season_val = getattr(team_metrics, season_metric)
                    if season_val is not None:
                        details['season_value'] = round(season_val, 4)
                
                if hasattr(team_metrics, lastn_metric):
                    lastn_val = getattr(team_metrics, lastn_metric)
                    if lastn_val is not None:
                        details['lastn_value'] = round(lastn_val, 4)
                
                flags.append({
                    'stat_date': team_metrics.stat_date,
                    'season': team_metrics.season,
                    'team_id': team_metrics.team_id,
                    'team_name': team_metrics.team_name,
                    'flag_type': flag_type,
                    'severity': abs(delta_value),  # Use absolute value as severity
                    'details_json': details
                })
        
        return flags
    
    def generate_all_flags(
        self,
        season: str,
        window_size: int = 10,
        stat_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Generate flags for all teams in a season.
        
        Args:
            season: Season string (e.g., "2024-25")
            window_size: Window size to match metrics calculation (default 10)
            stat_date: Date to filter metrics (default None = all dates)
            db: Optional database session
            
        Returns:
            List of flag dictionaries
        """
        session = db or self.db if hasattr(self, 'db') else None
        if not session:
            with get_db_context() as session:
                return self._generate_all_flags_internal(season, window_size, stat_date, session)
        else:
            return self._generate_all_flags_internal(season, window_size, stat_date, session)
    
    def _generate_all_flags_internal(
        self,
        season: str,
        window_size: int,
        stat_date: Optional[date],
        db: Session
    ) -> List[Dict]:
        """Internal method to generate all flags."""
        logger.info(f"Starting flag generation for season {season} (window={window_size})")
        
        # Note: We no longer clear existing flags - upsert handles updates
        # Historical data is preserved for ML training and trend analysis
        # Unique constraint (stat_date, team_id, flag_type) prevents duplicates
        
        # Get all team metrics for this season/window
        query = db.query(TeamDailyMetricsORM).filter(
            TeamDailyMetricsORM.season == season,
            TeamDailyMetricsORM.window_size == window_size
        )
        
        if stat_date:
            query = query.filter(TeamDailyMetricsORM.stat_date == stat_date)
        
        team_metrics_list = query.all()
        logger.info(f"Found {len(team_metrics_list)} team metrics records to process")
        
        if not team_metrics_list:
            logger.warning(f"No team metrics found for season {season}. Run TeamMetricsService first.")
            return []
        
        # Generate flags for each team
        all_flags = []
        for team_metrics in team_metrics_list:
            try:
                flags = self.generate_flags_for_team(team_metrics, db)
                all_flags.extend(flags)
            except Exception as e:
                logger.error(f"Error generating flags for team {team_metrics.team_id}: {e}")
                continue
        
        # Persist flags to database
        if all_flags:
            try:
                TeamDailyFlagsORM.bulk_create(all_flags, db=db)
                db.commit()
                logger.info(f"Persisted {len(all_flags)} flags to database")
            except Exception as e:
                logger.error(f"Error persisting flags: {e}")
                db.rollback()
                raise
        
        # Count by flag type
        flag_counts = {}
        for flag in all_flags:
            flag_type = flag['flag_type']
            flag_counts[flag_type] = flag_counts.get(flag_type, 0) + 1
        
        logger.info(f"Flag generation complete: {len(all_flags)} total flags")
        for flag_type, count in sorted(flag_counts.items()):
            logger.info(f"  {flag_type}: {count}")
        
        return all_flags

