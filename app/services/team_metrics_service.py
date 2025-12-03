"""Service for calculating team daily metrics (season vs recent form).

This service compares season-to-date statistics with recent form (last N games)
to identify teams that are trending hot or cold.

"""

from typing import List, Dict, Optional, Tuple
from datetime import date, datetime
from sqlalchemy.orm import Session
import statistics

from app.database import get_db_context
from app.models.team_sqlalchemy import TeamORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
from app.utils.config_utils import logger


class TeamMetricsService:
    """Service for calculating team performance metrics (season vs recent form)."""
    
    # Default window size for last N games
    DEFAULT_WINDOW_SIZE = 10
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service.
        
        Args:
            db: Optional database session
        """
        self.db = db
    
    def normalize_percentage(self, value: Optional[float], expected_range=(0, 1)) -> Optional[float]:
        """Normalize a percentage value to fraction format (0-1).
        
        Handles cases where values might be stored as:
        - Fractions (0.54) ← correct format
        - Percentages (54.0) ← needs division by 100
        - Ranks (25) ← this indicates wrong column was queried
        
        Args:
            value: Raw value from database
            expected_range: Expected range tuple (min, max) for fraction format
            
        Returns:
            Normalized value as fraction (0-1) or None
        """
        if value is None:
            return None
        
        # If value is already in expected range (0-1), return as-is
        if expected_range[0] <= value <= expected_range[1]:
            return value
        
        # If value looks like a percentage (1-100), convert to fraction
        if 1 < value <= 100:
            return value / 100.0
        
        # If value is suspiciously large (>100), it might be a rank - log warning
        if value > 100:
            logger.warning(f"Suspicious value {value} - might be rank instead of percentage")
            return None
        
        return value
    
    def get_season_stats(
        self,
        team_id: int,
        season: str,
        db: Session
    ) -> Optional[Dict[str, Optional[float]]]:
        """Extract season-to-date stats from LeagueDashTeamStatsORM.
        
        Args:
            team_id: Team identifier
            season: Season string (e.g., "2024-25")
            db: Database session
            
        Returns:
            Dictionary of season stats or None if not found
        """
        # Query LeagueDashTeamStats for Regular Season stats
        team_stats = db.query(LeagueDashTeamStatsORM).filter(
            LeagueDashTeamStatsORM.team_id == team_id,
            LeagueDashTeamStatsORM.season == season,
            LeagueDashTeamStatsORM.season_type == 'Regular Season'
        ).first()
        
        if not team_stats:
            logger.warning(f"No season stats found for team {team_id} in {season}")
            return None
        
        # Extract metrics from the ORM model and normalize percentages
        return {
            # Core efficiency & pace (these are already in correct units)
            'off_rtg_season': team_stats.advanced_totals_off_rating,
            'def_rtg_season': team_stats.advanced_totals_def_rating,
            'net_rtg_season': team_stats.advanced_totals_net_rating,
            'pace_season': team_stats.advanced_totals_pace,
            
            # Four Factors - use advanced_totals columns (stored as fractions 0-1)
            # NOTE: fourfactors_totals columns return RANKS, not actual values!
            'efg_season': team_stats.advanced_totals_efg_pct,
            'tov_pct_season': team_stats.advanced_totals_tm_tov_pct,
            'orb_pct_season': team_stats.advanced_totals_oreb_pct,
            
            # FTR (Free Throw Rate) - calculate from base_totals
            # FTR = FTA / FGA
            'ftr_season': (
                team_stats.base_totals_fta / team_stats.base_totals_fga 
                if team_stats.base_totals_fga and team_stats.base_totals_fga > 0 
                else None
            ),
            
            # Scoring profile - normalize to fractions (0-1)
            'pct_pts_3pt_season': self.normalize_percentage(team_stats.scoring_totals_pct_pts_3pt, (0.20, 0.50)),
            'pct_pts_paint_season': self.normalize_percentage(team_stats.scoring_totals_pct_pts_paint, (0.25, 0.55)),
            'pct_pts_mid_season': self.normalize_percentage(team_stats.scoring_totals_pct_pts_2pt_mr, (0.10, 0.35)),
            'pct_pts_ft_season': self.normalize_percentage(team_stats.scoring_totals_pct_pts_ft, (0.10, 0.30)),
            'pct_pts_fb_season': self.normalize_percentage(team_stats.scoring_totals_pct_pts_fb, (0.05, 0.25)),
            'pct_pts_off_tov_season': self.normalize_percentage(team_stats.scoring_totals_pct_pts_off_tov, (0.10, 0.25)),
            
            # Extra scoring per 100 possessions
            'sec_chance_pts_per100_season': team_stats.misc_per100possessions_pts_2nd_chance,
            'fb_pts_per100_season': team_stats.misc_per100possessions_pts_fb,
            'paint_pts_per100_season': team_stats.misc_per100possessions_pts_paint,
            'opp_sec_chance_pts_per100_season': team_stats.misc_per100possessions_opp_pts_2nd_chance,
            'opp_fb_pts_per100_season': team_stats.misc_per100possessions_opp_pts_fb,
            'opp_paint_pts_per100_season': team_stats.misc_per100possessions_opp_pts_paint,
        }
    
    def calculate_possessions(
        self,
        fga: int,
        fta: int,
        oreb: int,
        tov: int
    ) -> float:
        """Calculate possessions using the standard formula.
        
        Possessions = FGA + 0.44 * FTA - OREB + TOV
        
        Args:
            fga: Field goal attempts
            fta: Free throw attempts
            oreb: Offensive rebounds
            tov: Turnovers
            
        Returns:
            Estimated possessions
        """
        return fga + (0.44 * fta) - oreb + tov
    
    def calculate_last_n_stats(
        self,
        team_id: int,
        season: str,
        window_size: int,
        db: Session
    ) -> Optional[Dict[str, Optional[float]]]:
        """Calculate stats from last N games using TeamGameStatsORM.
        
        Args:
            team_id: Team identifier
            season: Season string
            window_size: Number of recent games
            db: Database session
            
        Returns:
            Dictionary of last N stats or None if insufficient games
        """
        # Get last N games for the team (ordered by game_date desc)
        game_stats = TeamGameStatsORM.get_by_team(team_id, season, db=db)
        
        if not game_stats or len(game_stats) < window_size:
            logger.warning(
                f"Insufficient games for team {team_id} in {season}: "
                f"found {len(game_stats) if game_stats else 0}, need {window_size}"
            )
            return None
        
        # Take last N games
        last_n_games = game_stats[:window_size]
        
        # Initialize accumulators
        total_pts = 0
        total_fgm = 0
        total_fga = 0
        total_fg3m = 0
        total_fg3a = 0
        total_ftm = 0
        total_fta = 0
        total_oreb = 0
        total_dreb = 0
        total_tov = 0
        total_possessions = 0
        total_minutes = 0
        
        # Opponent stats for defensive rating and ORB%
        total_opp_pts = 0
        total_opp_possessions = 0
        total_opp_dreb = 0  # For ORB% calculation
        
        # For tracking various point types (approximations)
        # Note: TeamGameStatsORM doesn't have all the detailed breakdowns,
        # so we'll calculate what we can and leave others as None
        
        for game in last_n_games:
            # Team stats
            fga = game.fga or 0
            fta = game.fta or 0
            fgm = game.fg or 0
            oreb = game.oreb or 0  # Now using actual OREB from database!
            dreb = game.dreb or 0
            tov = game.tov or 0
            
            # Calculate possessions for this game using actual OREB
            poss = self.calculate_possessions(fga, fta, oreb, tov)
            
            total_pts += game.pts or 0
            total_fgm += game.fg or 0
            total_fga += fga
            total_fg3m += game.fg3 or 0
            total_fg3a += game.fg3a or 0
            total_ftm += game.ft or 0
            total_fta += fta
            total_oreb += oreb  # Now using actual OREB!
            total_dreb += dreb  # Tracking DREB too
            total_tov += tov
            total_possessions += poss
            
            # Get opponent stats for defensive rating and ORB% calculation
            opp_stats = TeamGameStatsORM.get_by_game_and_team(
                game.game_id, game.opponent_team_id, db=db
            )
            if opp_stats:
                opp_fga = opp_stats.fga or 0
                opp_fta = opp_stats.fta or 0
                opp_oreb = opp_stats.oreb or 0
                opp_dreb = opp_stats.dreb or 0
                opp_tov = opp_stats.tov or 0
                opp_poss = self.calculate_possessions(opp_fga, opp_fta, opp_oreb, opp_tov)
                
                total_opp_pts += opp_stats.pts or 0
                total_opp_possessions += opp_poss
                total_opp_dreb += opp_dreb  # Track opponent DREB for ORB% calculation
        
        # Calculate averages and advanced metrics
        games_played = len(last_n_games)
        
        # Offensive & Defensive Ratings
        off_rtg = (total_pts / total_possessions * 100) if total_possessions > 0 else None
        def_rtg = (total_opp_pts / total_opp_possessions * 100) if total_opp_possessions > 0 else None
        net_rtg = (off_rtg - def_rtg) if (off_rtg is not None and def_rtg is not None) else None
        
        # Pace (possessions per 48 minutes)
        # Note: Each game is 48 minutes, so pace = possessions per 48 min
        # This is actually possessions per game since games are 48 minutes
        # To match NBA.com's pace calculation, we use possessions per game
        pace = (total_possessions / games_played) if games_played > 0 else None
        
        # eFG% = (FGM + 0.5 * 3PM) / FGA
        efg = ((total_fgm + 0.5 * total_fg3m) / total_fga) if total_fga > 0 else None
        
        # TOV% = TOV / (FGA + 0.44 * FTA + TOV)
        tov_pct = (total_tov / (total_fga + 0.44 * total_fta + total_tov)) if (total_fga + 0.44 * total_fta + total_tov) > 0 else None
        
        # ORB% = Team_OREB / (Team_OREB + Opponent_DREB)
        orb_pct = (
            (total_oreb / (total_oreb + total_opp_dreb))
            if (total_oreb + total_opp_dreb) > 0
            else None
        )
        
        # FTR (Free Throw Rate) = FTA / FGA
        ftr = (total_fta / total_fga) if total_fga > 0 else None
        
        # Scoring percentages - approximations based on shot distribution
        # These are rough estimates since we don't have detailed shot location data
        total_2pt_makes = total_fgm - total_fg3m
        total_3pt_pts = total_fg3m * 3
        total_2pt_pts = total_2pt_makes * 2
        total_ft_pts = total_ftm
        
        pct_pts_3pt = (total_3pt_pts / total_pts) if total_pts > 0 else None
        pct_pts_ft = (total_ft_pts / total_pts) if total_pts > 0 else None
        
        # Cannot accurately calculate paint, mid-range, fastbreak, off turnovers without detailed data
        pct_pts_paint = None
        pct_pts_mid = None
        pct_pts_fb = None
        pct_pts_off_tov = None
        
        # Per-100 possession stats - Cannot calculate without detailed play-by-play data
        sec_chance_pts_per100 = None
        fb_pts_per100 = None
        paint_pts_per100 = None
        opp_sec_chance_pts_per100 = None
        opp_fb_pts_per100 = None
        opp_paint_pts_per100 = None
        
        return {
            'off_rtg_lastn': round(off_rtg, 2) if off_rtg is not None else None,
            'def_rtg_lastn': round(def_rtg, 2) if def_rtg is not None else None,
            'net_rtg_lastn': round(net_rtg, 2) if net_rtg is not None else None,
            'pace_lastn': round(pace, 2) if pace is not None else None,
            'efg_lastn': round(efg, 4) if efg is not None else None,
            'tov_pct_lastn': round(tov_pct, 4) if tov_pct is not None else None,
            'orb_pct_lastn': orb_pct,
            'ftr_lastn': round(ftr, 4) if ftr is not None else None,
            'pct_pts_3pt_lastn': round(pct_pts_3pt, 4) if pct_pts_3pt is not None else None,
            'pct_pts_paint_lastn': pct_pts_paint,
            'pct_pts_mid_lastn': pct_pts_mid,
            'pct_pts_ft_lastn': round(pct_pts_ft, 4) if pct_pts_ft is not None else None,
            'pct_pts_fb_lastn': pct_pts_fb,
            'pct_pts_off_tov_lastn': pct_pts_off_tov,
            'sec_chance_pts_per100_lastn': sec_chance_pts_per100,
            'fb_pts_per100_lastn': fb_pts_per100,
            'paint_pts_per100_lastn': paint_pts_per100,
            'opp_sec_chance_pts_per100_lastn': opp_sec_chance_pts_per100,
            'opp_fb_pts_per100_lastn': opp_fb_pts_per100,
            'opp_paint_pts_per100_lastn': opp_paint_pts_per100,
        }
    
    def calculate_strength_of_schedule(
        self,
        team_id: int,
        season: str,
        window_size: int,
        db: Session
    ) -> Dict[str, Optional[float]]:
        """Calculate Strength of Schedule metrics.
        
        SoS is based on average opponent NetRtg - higher = faced tougher opponents.
        
        Args:
            team_id: Team identifier
            season: Season string
            window_size: Window size for last N games
            db: Database session
            
        Returns:
            Dictionary with SoS metrics
        """
        # Get team's game stats to find opponents
        game_stats = TeamGameStatsORM.get_by_team(team_id, season, db=db)
        
        if not game_stats:
            logger.warning(f"No game stats found for team {team_id} in {season}")
            return {
                'sos_net_season': None,
                'sos_net_last10': None,
                'sos_net_delta': None,
                'sos_off_season': None,
                'sos_def_season': None,
                'sos_off_last10': None,
                'sos_def_last10': None,
            }
        
        # Build a lookup of opponent ratings from LeagueDashTeamStats
        # This gets each team's season-to-date ratings
        opponent_ratings = {}
        all_team_stats = db.query(LeagueDashTeamStatsORM).filter(
            LeagueDashTeamStatsORM.season == season,
            LeagueDashTeamStatsORM.season_type == 'Regular Season'
        ).all()
        
        for stats in all_team_stats:
            opponent_ratings[stats.team_id] = {
                'net_rtg': stats.advanced_totals_net_rating,
                'off_rtg': stats.advanced_totals_off_rating,
                'def_rtg': stats.advanced_totals_def_rating,
            }
        
        # Calculate SoS for all games (season)
        season_opp_net = []
        season_opp_off = []
        season_opp_def = []
        
        for game in game_stats:
            opp_id = game.opponent_team_id
            if opp_id in opponent_ratings:
                ratings = opponent_ratings[opp_id]
                if ratings['net_rtg'] is not None:
                    season_opp_net.append(ratings['net_rtg'])
                if ratings['off_rtg'] is not None:
                    season_opp_off.append(ratings['off_rtg'])
                if ratings['def_rtg'] is not None:
                    season_opp_def.append(ratings['def_rtg'])
        
        # Calculate SoS for last N games
        last_n_games = game_stats[:window_size]
        lastn_opp_net = []
        lastn_opp_off = []
        lastn_opp_def = []
        
        for game in last_n_games:
            opp_id = game.opponent_team_id
            if opp_id in opponent_ratings:
                ratings = opponent_ratings[opp_id]
                if ratings['net_rtg'] is not None:
                    lastn_opp_net.append(ratings['net_rtg'])
                if ratings['off_rtg'] is not None:
                    lastn_opp_off.append(ratings['off_rtg'])
                if ratings['def_rtg'] is not None:
                    lastn_opp_def.append(ratings['def_rtg'])
        
        # Calculate averages
        sos_net_season = round(sum(season_opp_net) / len(season_opp_net), 2) if season_opp_net else None
        sos_off_season = round(sum(season_opp_off) / len(season_opp_off), 2) if season_opp_off else None
        sos_def_season = round(sum(season_opp_def) / len(season_opp_def), 2) if season_opp_def else None
        
        sos_net_last10 = round(sum(lastn_opp_net) / len(lastn_opp_net), 2) if lastn_opp_net else None
        sos_off_last10 = round(sum(lastn_opp_off) / len(lastn_opp_off), 2) if lastn_opp_off else None
        sos_def_last10 = round(sum(lastn_opp_def) / len(lastn_opp_def), 2) if lastn_opp_def else None
        
        # Calculate delta (positive = harder recent schedule)
        sos_net_delta = None
        if sos_net_season is not None and sos_net_last10 is not None:
            sos_net_delta = round(sos_net_last10 - sos_net_season, 2)
        
        return {
            'sos_net_season': sos_net_season,
            'sos_net_last10': sos_net_last10,
            'sos_net_delta': sos_net_delta,
            'sos_off_season': sos_off_season,
            'sos_def_season': sos_def_season,
            'sos_off_last10': sos_off_last10,
            'sos_def_last10': sos_def_last10,
        }
    
    def calculate_deltas(
        self,
        season_stats: Dict[str, Optional[float]],
        lastn_stats: Dict[str, Optional[float]]
    ) -> Dict[str, Optional[float]]:
        """Calculate delta metrics (lastN - season).
        
        Args:
            season_stats: Season-to-date statistics
            lastn_stats: Last N games statistics
            
        Returns:
            Dictionary of delta metrics
        """
        deltas = {}
        
        # List of metrics to calculate deltas for
        metrics = [
            'off_rtg', 'def_rtg', 'net_rtg', 'pace',
            'efg', 'tov_pct', 'orb_pct', 'ftr',
            'pct_pts_3pt', 'pct_pts_paint', 'pct_pts_mid',
            'pct_pts_ft', 'pct_pts_fb', 'pct_pts_off_tov',
            'sec_chance_pts_per100', 'fb_pts_per100', 'paint_pts_per100',
            'opp_sec_chance_pts_per100', 'opp_fb_pts_per100', 'opp_paint_pts_per100'
        ]
        
        for metric in metrics:
            season_key = f"{metric}_season"
            lastn_key = f"{metric}_lastn"
            delta_key = f"{metric}_delta"
            
            season_val = season_stats.get(season_key)
            lastn_val = lastn_stats.get(lastn_key)
            
            if season_val is not None and lastn_val is not None:
                delta = lastn_val - season_val
                deltas[delta_key] = round(delta, 4)
            else:
                deltas[delta_key] = None
        
        return deltas
    
    def calculate_team_metrics(
        self,
        team_id: int,
        season: str,
        window_size: int,
        stat_date: date,
        db: Session
    ) -> Optional[Dict[str, any]]:
        """Calculate complete metrics for a single team.
        
        Args:
            team_id: Team identifier
            season: Season string
            window_size: Window size for last N games
            stat_date: Date of calculation
            db: Database session
            
        Returns:
            Dictionary with all metrics or None if insufficient data
        """
        # Get team name
        team = TeamORM.get_by_id(team_id, db=db)
        if not team:
            logger.warning(f"Team {team_id} not found")
            return None
        
        team_name = team.name
        
        # Get season stats
        season_stats = self.get_season_stats(team_id, season, db)
        if not season_stats:
            return None
        
        # Calculate last N stats
        lastn_stats = self.calculate_last_n_stats(team_id, season, window_size, db)
        if not lastn_stats:
            return None
        
        # Calculate deltas
        deltas = self.calculate_deltas(season_stats, lastn_stats)
        
        # Calculate Strength of Schedule
        sos_stats = self.calculate_strength_of_schedule(team_id, season, window_size, db)
        
        # Combine all metrics
        metrics = {
            'stat_date': stat_date,
            'season': season,
            'team_id': team_id,
            'team_name': team_name,
            'window_size': window_size,
        }
        metrics.update(season_stats)
        metrics.update(lastn_stats)
        metrics.update(deltas)
        metrics.update(sos_stats)
        
        return metrics
    
    def calculate_all_teams(
        self,
        season: str,
        window_size: int = DEFAULT_WINDOW_SIZE,
        stat_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> List[Dict]:
        """Calculate metrics for all teams in a season.
        
        Args:
            season: Season string (e.g., "2024-25")
            window_size: Window size for last N games (default 10)
            stat_date: Date of calculation (default today)
            db: Optional database session
            
        Returns:
            List of metrics dictionaries
        """
        if stat_date is None:
            stat_date = date.today()
        
        session = db or self.db if hasattr(self, 'db') else None
        if not session:
            with get_db_context() as session:
                return self._calculate_all_teams_internal(season, window_size, stat_date, session)
        else:
            return self._calculate_all_teams_internal(season, window_size, stat_date, session)
    
    def _calculate_all_teams_internal(
        self,
        season: str,
        window_size: int,
        stat_date: date,
        db: Session
    ) -> List[Dict]:
        """Internal method to calculate for all teams."""
        logger.info(f"Starting team metrics calculation for season {season} (window={window_size})")
        
        # Note: We no longer clear existing records - upsert handles updates
        # Historical data is preserved for ML training and trend analysis
        # Unique constraint (stat_date, team_id, window_size) prevents duplicates
        
        # Get all teams
        teams = TeamORM.get_all(db=db)
        logger.info(f"Found {len(teams)} teams")
        
        all_metrics = []
        teams_processed = 0
        teams_skipped = 0
        
        for team in teams:
            team_id = team.team_id
            
            try:
                metrics = self.calculate_team_metrics(
                    team_id, season, window_size, stat_date, db
                )
                
                if metrics:
                    all_metrics.append(metrics)
                    teams_processed += 1
                else:
                    teams_skipped += 1
                    logger.warning(f"Skipped team {team.name} (ID: {team_id}) - insufficient data")
                
                if teams_processed % 10 == 0:
                    logger.info(f"Processed {teams_processed}/{len(teams)} teams")
                
            except Exception as e:
                logger.error(f"Error calculating metrics for team {team_id}: {e}")
                teams_skipped += 1
                continue
        
        # Persist results to database using bulk upsert
        if all_metrics:
            try:
                TeamDailyMetricsORM.bulk_create(all_metrics, db=db)
                db.commit()
                logger.info(f"Persisted {len(all_metrics)} team metrics records to database")
            except Exception as e:
                logger.error(f"Error persisting team metrics records: {e}")
                db.rollback()
                raise
        
        logger.info(
            f"Team metrics calculation complete: {teams_processed} teams processed, "
            f"{teams_skipped} skipped"
        )
        
        return all_metrics

