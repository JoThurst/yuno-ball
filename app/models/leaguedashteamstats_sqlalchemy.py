"""SQLAlchemy ORM model for LeagueDashTeamStats.

This module provides the LeagueDashTeamStatsORM class which represents comprehensive
NBA team statistics across all measure types, per modes, and season types.
It maintains backward compatibility with the existing psycopg2-based LeagueDashTeamStats class.

The table stores extensive team statistics including:
- Base stats (Totals, Per48, Per100Possessions)
- Advanced stats (Offensive/Defensive ratings, Pace, etc.)
- Misc stats (Points off turnovers, fastbreak, etc.)
- Four Factors (EFG%, FTA Rate, TOV%, OREB%)
- Scoring breakdown
- Opponent stats
- Defense stats

Created: November 20, 2025
Part of: SQLAlchemy migration (Day 2 extended - final push!)
"""

from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Index, PrimaryKeyConstraint, CheckConstraint
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.config_utils import logger


class LeagueDashTeamStatsORM(Base):
    """SQLAlchemy ORM model for comprehensive team statistics.
    
    This model represents extensive team statistics from the NBA API's LeagueDashTeamStats endpoint.
    It stores data across multiple measure types and per modes for comprehensive team analysis.
    
    The table uses a naming convention: {MeasureType}_{PerMode}_{StatName}
    Example: Base_Totals_PTS, Advanced_Per48_OFF_RATING, etc.
    
    Primary Key: (team_id, season, season_type)
    
    Measure Types:
    - Base: Traditional box score stats
    - Advanced: Advanced metrics (ratings, pace, efficiency)
    - Misc: Miscellaneous stats (points off turnovers, second chance, etc.)
    - FourFactors: Dean Oliver's Four Factors
    - Scoring: Shooting breakdowns and assisted percentages
    - Opponent: Opponent statistics
    - Defense: Defensive metrics
    
    Per Modes:
    - Totals: Season totals
    - Per48: Per 48 minutes
    - Per100Possessions: Per 100 possessions
    """
    
    __tablename__ = 'league_dash_team_stats'
    __table_args__ = (
        PrimaryKeyConstraint('team_id', 'season', 'season_type'),
        CheckConstraint("season_type IN ('Regular Season', 'Playoffs')",
                       name='league_dash_team_stats_season_type_check'),
        Index('idx_league_dash_team_stats_team_id', 'team_id'),
        Index('idx_league_dash_team_stats_season', 'season'),
        Index('idx_league_dash_team_stats_season_type', 'season_type'),
    )
    
    # ==================== Primary Key & Identifiers ====================
    team_id = Column(Integer, ForeignKey('teams.team_id'), nullable=False)
    team_name = Column(String(50), nullable=False)
    season = Column(String(10), nullable=False)
    season_type = Column(String(15), nullable=False)
    
    # ==================== Base Stats - Totals ====================
    base_totals_gp = Column(Integer)
    base_totals_w = Column(Integer)
    base_totals_l = Column(Integer)
    base_totals_w_pct = Column(Float)
    base_totals_min = Column(Float)
    base_totals_fgm = Column(Integer)
    base_totals_fga = Column(Integer)
    base_totals_fg_pct = Column(Float)
    base_totals_fg3m = Column(Integer)
    base_totals_fg3a = Column(Integer)
    base_totals_fg3_pct = Column(Float)
    base_totals_ftm = Column(Integer)
    base_totals_fta = Column(Integer)
    base_totals_ft_pct = Column(Float)
    base_totals_oreb = Column(Integer)
    base_totals_dreb = Column(Integer)
    base_totals_reb = Column(Integer)
    base_totals_ast = Column(Integer)
    base_totals_tov = Column(Integer)
    base_totals_stl = Column(Integer)
    base_totals_blk = Column(Integer)
    base_totals_blka = Column(Integer)
    base_totals_pf = Column(Integer)
    base_totals_pfd = Column(Integer)
    base_totals_pts = Column(Integer)
    base_totals_plus_minus = Column(Float)
    
    # Base Totals Rankings
    base_totals_gp_rank = Column(Integer)
    base_totals_w_rank = Column(Integer)
    base_totals_l_rank = Column(Integer)
    base_totals_w_pct_rank = Column(Integer)
    base_totals_min_rank = Column(Integer)
    base_totals_fgm_rank = Column(Integer)
    base_totals_fga_rank = Column(Integer)
    base_totals_fg_pct_rank = Column(Integer)
    base_totals_fg3m_rank = Column(Integer)
    base_totals_fg3a_rank = Column(Integer)
    base_totals_fg3_pct_rank = Column(Integer)
    base_totals_ftm_rank = Column(Integer)
    base_totals_fta_rank = Column(Integer)
    base_totals_ft_pct_rank = Column(Integer)
    base_totals_oreb_rank = Column(Integer)
    base_totals_dreb_rank = Column(Integer)
    base_totals_reb_rank = Column(Integer)
    base_totals_ast_rank = Column(Integer)
    base_totals_tov_rank = Column(Integer)
    base_totals_stl_rank = Column(Integer)
    base_totals_blk_rank = Column(Integer)
    base_totals_blka_rank = Column(Integer)
    base_totals_pf_rank = Column(Integer)
    base_totals_pfd_rank = Column(Integer)
    base_totals_pts_rank = Column(Integer)
    base_totals_plus_minus_rank = Column(Integer)
    
    # ==================== Base Stats - Per48 ====================
    base_per48_gp = Column(Integer)
    base_per48_l = Column(Integer)
    base_per48_w = Column(Integer)
    base_per48_w_pct = Column(Float)
    base_per48_min = Column(Float)
    base_per48_fgm = Column(Integer)
    base_per48_fga = Column(Integer)
    base_per48_fg_pct = Column(Float)
    base_per48_fg3m = Column(Integer)
    base_per48_fg3a = Column(Integer)
    base_per48_fg3_pct = Column(Float)
    base_per48_ftm = Column(Integer)
    base_per48_fta = Column(Integer)
    base_per48_ft_pct = Column(Float)
    base_per48_oreb = Column(Integer)
    base_per48_dreb = Column(Integer)
    base_per48_reb = Column(Integer)
    base_per48_ast = Column(Integer)
    base_per48_tov = Column(Integer)
    base_per48_stl = Column(Integer)
    base_per48_blk = Column(Integer)
    base_per48_blka = Column(Integer)
    base_per48_pf = Column(Integer)
    base_per48_pfd = Column(Integer)
    base_per48_pts = Column(Integer)
    base_per48_plus_minus = Column(Float)
    
    # Base Per48 Rankings
    base_per48_gp_rank = Column(Integer)
    base_per48_w_rank = Column(Integer)
    base_per48_l_rank = Column(Integer)
    base_per48_w_pct_rank = Column(Integer)
    base_per48_min_rank = Column(Integer)
    base_per48_fgm_rank = Column(Integer)
    base_per48_fga_rank = Column(Integer)
    base_per48_fg_pct_rank = Column(Integer)
    base_per48_fg3m_rank = Column(Integer)
    base_per48_fg3a_rank = Column(Integer)
    base_per48_fg3_pct_rank = Column(Integer)
    base_per48_ftm_rank = Column(Integer)
    base_per48_fta_rank = Column(Integer)
    base_per48_ft_pct_rank = Column(Integer)
    base_per48_oreb_rank = Column(Integer)
    base_per48_dreb_rank = Column(Integer)
    base_per48_reb_rank = Column(Integer)
    base_per48_ast_rank = Column(Integer)
    base_per48_tov_rank = Column(Integer)
    base_per48_stl_rank = Column(Integer)
    base_per48_blk_rank = Column(Integer)
    base_per48_blka_rank = Column(Integer)
    base_per48_pf_rank = Column(Integer)
    base_per48_pfd_rank = Column(Integer)
    base_per48_pts_rank = Column(Integer)
    base_per48_plus_minus_rank = Column(Integer)
    
    # ==================== Base Stats - Per100Possessions ====================
    base_per100possessions_gp = Column(Integer)
    base_per100possessions_l = Column(Integer)
    base_per100possessions_w = Column(Integer)
    base_per100possessions_w_pct = Column(Float)
    base_per100possessions_min = Column(Float)
    base_per100possessions_fgm = Column(Integer)
    base_per100possessions_fga = Column(Integer)
    base_per100possessions_fg_pct = Column(Float)
    base_per100possessions_fg3m = Column(Integer)
    base_per100possessions_fg3a = Column(Integer)
    base_per100possessions_fg3_pct = Column(Float)
    base_per100possessions_ftm = Column(Integer)
    base_per100possessions_fta = Column(Integer)
    base_per100possessions_ft_pct = Column(Float)
    base_per100possessions_oreb = Column(Integer)
    base_per100possessions_dreb = Column(Integer)
    base_per100possessions_reb = Column(Integer)
    base_per100possessions_ast = Column(Integer)
    base_per100possessions_tov = Column(Integer)
    base_per100possessions_stl = Column(Integer)
    base_per100possessions_blk = Column(Integer)
    base_per100possessions_blka = Column(Integer)
    base_per100possessions_pf = Column(Integer)
    base_per100possessions_pfd = Column(Integer)
    base_per100possessions_pts = Column(Integer)
    base_per100possessions_plus_minus = Column(Float)
    
    # Base Per100Possessions Rankings
    base_per100possessions_gp_rank = Column(Integer)
    base_per100possessions_w_rank = Column(Integer)
    base_per100possessions_l_rank = Column(Integer)
    base_per100possessions_w_pct_rank = Column(Integer)
    base_per100possessions_min_rank = Column(Integer)
    base_per100possessions_fgm_rank = Column(Integer)
    base_per100possessions_fga_rank = Column(Integer)
    base_per100possessions_fg_pct_rank = Column(Integer)
    base_per100possessions_fg3m_rank = Column(Integer)
    base_per100possessions_fg3a_rank = Column(Integer)
    base_per100possessions_fg3_pct_rank = Column(Integer)
    base_per100possessions_ftm_rank = Column(Integer)
    base_per100possessions_fta_rank = Column(Integer)
    base_per100possessions_ft_pct_rank = Column(Integer)
    base_per100possessions_oreb_rank = Column(Integer)
    base_per100possessions_dreb_rank = Column(Integer)
    base_per100possessions_reb_rank = Column(Integer)
    base_per100possessions_ast_rank = Column(Integer)
    base_per100possessions_tov_rank = Column(Integer)
    base_per100possessions_stl_rank = Column(Integer)
    base_per100possessions_blk_rank = Column(Integer)
    base_per100possessions_blka_rank = Column(Integer)
    base_per100possessions_pf_rank = Column(Integer)
    base_per100possessions_pfd_rank = Column(Integer)
    base_per100possessions_pts_rank = Column(Integer)
    base_per100possessions_plus_minus_rank = Column(Integer)
    
    # ==================== Advanced Stats - Totals ====================
    advanced_totals_gp = Column(Integer)
    advanced_totals_w = Column(Integer)
    advanced_totals_l = Column(Integer)
    advanced_totals_w_pct = Column(Float)
    advanced_totals_min = Column(Float)
    advanced_totals_e_off_rating = Column(Float)
    advanced_totals_off_rating = Column(Float)
    advanced_totals_e_def_rating = Column(Float)
    advanced_totals_def_rating = Column(Float)
    advanced_totals_e_net_rating = Column(Float)
    advanced_totals_net_rating = Column(Float)
    advanced_totals_ast_pct = Column(Float)
    advanced_totals_ast_to = Column(Float)
    advanced_totals_ast_ratio = Column(Float)
    advanced_totals_oreb_pct = Column(Float)
    advanced_totals_dreb_pct = Column(Float)
    advanced_totals_reb_pct = Column(Float)
    advanced_totals_tm_tov_pct = Column(Float)
    advanced_totals_efg_pct = Column(Float)
    advanced_totals_ts_pct = Column(Float)
    advanced_totals_e_pace = Column(Float)
    advanced_totals_pace = Column(Float)
    advanced_totals_pace_per40 = Column(Float)
    advanced_totals_poss = Column(Integer)
    advanced_totals_pie = Column(Float)
    
    # Advanced Totals Rankings
    advanced_totals_gp_rank = Column(Integer)
    advanced_totals_w_rank = Column(Integer)
    advanced_totals_l_rank = Column(Integer)
    advanced_totals_w_pct_rank = Column(Integer)
    advanced_totals_min_rank = Column(Integer)
    advanced_totals_off_rating_rank = Column(Integer)
    advanced_totals_def_rating_rank = Column(Integer)
    advanced_totals_net_rating_rank = Column(Integer)
    advanced_totals_ast_pct_rank = Column(Integer)
    advanced_totals_ast_to_rank = Column(Integer)
    advanced_totals_ast_ratio_rank = Column(Integer)
    advanced_totals_oreb_pct_rank = Column(Integer)
    advanced_totals_dreb_pct_rank = Column(Integer)
    advanced_totals_reb_pct_rank = Column(Integer)
    advanced_totals_tm_tov_pct_rank = Column(Integer)
    advanced_totals_efg_pct_rank = Column(Integer)
    advanced_totals_ts_pct_rank = Column(Integer)
    advanced_totals_pace_rank = Column(Integer)
    advanced_totals_pie_rank = Column(Integer)
    
    # ==================== Advanced Stats - Per48 ====================
    advanced_per48_gp = Column(Integer)
    advanced_per48_w = Column(Integer)
    advanced_per48_l = Column(Integer)
    advanced_per48_w_pct = Column(Float)
    advanced_per48_min = Column(Float)
    advanced_per48_e_off_rating = Column(Float)
    advanced_per48_off_rating = Column(Float)
    advanced_per48_e_def_rating = Column(Float)
    advanced_per48_def_rating = Column(Float)
    advanced_per48_e_net_rating = Column(Float)
    advanced_per48_net_rating = Column(Float)
    advanced_per48_ast_pct = Column(Float)
    advanced_per48_ast_to = Column(Float)
    advanced_per48_ast_ratio = Column(Float)
    advanced_per48_oreb_pct = Column(Float)
    advanced_per48_dreb_pct = Column(Float)
    advanced_per48_reb_pct = Column(Float)
    advanced_per48_tm_tov_pct = Column(Float)
    advanced_per48_efg_pct = Column(Float)
    advanced_per48_ts_pct = Column(Float)
    advanced_per48_e_pace = Column(Float)
    advanced_per48_pace = Column(Float)
    advanced_per48_pace_per40 = Column(Float)
    advanced_per48_poss = Column(Integer)
    advanced_per48_pie = Column(Float)
    
    # Advanced Per48 Rankings
    advanced_per48_gp_rank = Column(Integer)
    advanced_per48_w_rank = Column(Integer)
    advanced_per48_l_rank = Column(Integer)
    advanced_per48_w_pct_rank = Column(Integer)
    advanced_per48_min_rank = Column(Integer)
    advanced_per48_off_rating_rank = Column(Integer)
    advanced_per48_def_rating_rank = Column(Integer)
    advanced_per48_net_rating_rank = Column(Integer)
    advanced_per48_ast_pct_rank = Column(Integer)
    advanced_per48_ast_to_rank = Column(Integer)
    advanced_per48_ast_ratio_rank = Column(Integer)
    advanced_per48_oreb_pct_rank = Column(Integer)
    advanced_per48_dreb_pct_rank = Column(Integer)
    advanced_per48_reb_pct_rank = Column(Integer)
    advanced_per48_tm_tov_pct_rank = Column(Integer)
    advanced_per48_efg_pct_rank = Column(Integer)
    advanced_per48_ts_pct_rank = Column(Integer)
    advanced_per48_pace_rank = Column(Integer)
    advanced_per48_pie_rank = Column(Integer)
    
    # ==================== Advanced Stats - Per100Possessions ====================
    advanced_per100possessions_gp = Column(Integer)
    advanced_per100possessions_w = Column(Integer)
    advanced_per100possessions_l = Column(Integer)
    advanced_per100possessions_w_pct = Column(Float)
    advanced_per100possessions_min = Column(Float)
    advanced_per100possessions_e_off_rating = Column(Float)
    advanced_per100possessions_off_rating = Column(Float)
    advanced_per100possessions_e_def_rating = Column(Float)
    advanced_per100possessions_def_rating = Column(Float)
    advanced_per100possessions_e_net_rating = Column(Float)
    advanced_per100possessions_net_rating = Column(Float)
    advanced_per100possessions_ast_pct = Column(Float)
    advanced_per100possessions_ast_to = Column(Float)
    advanced_per100possessions_ast_ratio = Column(Float)
    advanced_per100possessions_oreb_pct = Column(Float)
    advanced_per100possessions_dreb_pct = Column(Float)
    advanced_per100possessions_reb_pct = Column(Float)
    advanced_per100possessions_tm_tov_pct = Column(Float)
    advanced_per100possessions_efg_pct = Column(Float)
    advanced_per100possessions_ts_pct = Column(Float)
    advanced_per100possessions_e_pace = Column(Float)
    advanced_per100possessions_pace = Column(Float)
    advanced_per100possessions_pace_per40 = Column(Float)
    advanced_per100possessions_poss = Column(Integer)
    advanced_per100possessions_pie = Column(Float)
    
    # Advanced Per100Possessions Rankings
    advanced_per100possessions_gp_rank = Column(Integer)
    advanced_per100possessions_w_rank = Column(Integer)
    advanced_per100possessions_l_rank = Column(Integer)
    advanced_per100possessions_w_pct_rank = Column(Integer)
    advanced_per100possessions_min_rank = Column(Integer)
    advanced_per100possessions_off_rating_rank = Column(Integer)
    advanced_per100possessions_def_rating_rank = Column(Integer)
    advanced_per100possessions_net_rating_rank = Column(Integer)
    advanced_per100possessions_ast_pct_rank = Column(Integer)
    advanced_per100possessions_ast_to_rank = Column(Integer)
    advanced_per100possessions_ast_ratio_rank = Column(Integer)
    advanced_per100possessions_oreb_pct_rank = Column(Integer)
    advanced_per100possessions_dreb_pct_rank = Column(Integer)
    advanced_per100possessions_reb_pct_rank = Column(Integer)
    advanced_per100possessions_tm_tov_pct_rank = Column(Integer)
    advanced_per100possessions_efg_pct_rank = Column(Integer)
    advanced_per100possessions_ts_pct_rank = Column(Integer)
    advanced_per100possessions_pace_rank = Column(Integer)
    advanced_per100possessions_pie_rank = Column(Integer)
    
    # ==================== Misc Stats - Totals ====================
    misc_totals_gp = Column(Integer)
    misc_totals_w = Column(Integer)
    misc_totals_l = Column(Integer)
    misc_totals_w_pct = Column(Float)
    misc_totals_min = Column(Float)
    misc_totals_pts_off_tov = Column(Integer)
    misc_totals_pts_2nd_chance = Column(Integer)
    misc_totals_pts_fb = Column(Integer)
    misc_totals_pts_paint = Column(Integer)
    misc_totals_opp_pts_off_tov = Column(Integer)
    misc_totals_opp_pts_2nd_chance = Column(Integer)
    misc_totals_opp_pts_fb = Column(Integer)
    misc_totals_opp_pts_paint = Column(Integer)
    
    # Misc Totals Rankings
    misc_totals_gp_rank = Column(Integer)
    misc_totals_w_rank = Column(Integer)
    misc_totals_l_rank = Column(Integer)
    misc_totals_w_pct_rank = Column(Integer)
    misc_totals_min_rank = Column(Integer)
    misc_totals_pts_off_tov_rank = Column(Integer)
    misc_totals_pts_2nd_chance_rank = Column(Integer)
    misc_totals_pts_fb_rank = Column(Integer)
    misc_totals_pts_paint_rank = Column(Integer)
    misc_totals_opp_pts_off_tov_rank = Column(Integer)
    misc_totals_opp_pts_2nd_chance_rank = Column(Integer)
    misc_totals_opp_pts_fb_rank = Column(Integer)
    misc_totals_opp_pts_paint_rank = Column(Integer)
    
    # ==================== Misc Stats - Per48 ====================
    misc_per48_gp = Column(Integer)
    misc_per48_w = Column(Integer)
    misc_per48_l = Column(Integer)
    misc_per48_w_pct = Column(Float)
    misc_per48_min = Column(Float)
    misc_per48_pts_off_tov = Column(Integer)
    misc_per48_pts_2nd_chance = Column(Integer)
    misc_per48_pts_fb = Column(Integer)
    misc_per48_pts_paint = Column(Integer)
    misc_per48_opp_pts_off_tov = Column(Integer)
    misc_per48_opp_pts_2nd_chance = Column(Integer)
    misc_per48_opp_pts_fb = Column(Integer)
    misc_per48_opp_pts_paint = Column(Integer)
    
    # Misc Per48 Rankings
    misc_per48_gp_rank = Column(Integer)
    misc_per48_w_rank = Column(Integer)
    misc_per48_l_rank = Column(Integer)
    misc_per48_w_pct_rank = Column(Integer)
    misc_per48_min_rank = Column(Integer)
    misc_per48_pts_off_tov_rank = Column(Integer)
    misc_per48_pts_2nd_chance_rank = Column(Integer)
    misc_per48_pts_fb_rank = Column(Integer)
    misc_per48_pts_paint_rank = Column(Integer)
    misc_per48_opp_pts_off_tov_rank = Column(Integer)
    misc_per48_opp_pts_2nd_chance_rank = Column(Integer)
    misc_per48_opp_pts_fb_rank = Column(Integer)
    misc_per48_opp_pts_paint_rank = Column(Integer)
    
    # ==================== Misc Stats - Per100Possessions ====================
    misc_per100possessions_gp = Column(Integer)
    misc_per100possessions_w = Column(Integer)
    misc_per100possessions_l = Column(Integer)
    misc_per100possessions_w_pct = Column(Float)
    misc_per100possessions_min = Column(Float)
    misc_per100possessions_pts_off_tov = Column(Integer)
    misc_per100possessions_pts_2nd_chance = Column(Integer)
    misc_per100possessions_pts_fb = Column(Integer)
    misc_per100possessions_pts_paint = Column(Integer)
    misc_per100possessions_opp_pts_off_tov = Column(Integer)
    misc_per100possessions_opp_pts_2nd_chance = Column(Integer)
    misc_per100possessions_opp_pts_fb = Column(Integer)
    misc_per100possessions_opp_pts_paint = Column(Integer)
    
    # Misc Per100Possessions Rankings
    misc_per100possessions_gp_rank = Column(Integer)
    misc_per100possessions_w_rank = Column(Integer)
    misc_per100possessions_l_rank = Column(Integer)
    misc_per100possessions_w_pct_rank = Column(Integer)
    misc_per100possessions_min_rank = Column(Integer)
    misc_per100possessions_pts_off_tov_rank = Column(Integer)
    misc_per100possessions_pts_2nd_chance_rank = Column(Integer)
    misc_per100possessions_pts_fb_rank = Column(Integer)
    misc_per100possessions_pts_paint_rank = Column(Integer)
    misc_per100possessions_opp_pts_off_tov_rank = Column(Integer)
    misc_per100possessions_opp_pts_2nd_chance_rank = Column(Integer)
    misc_per100possessions_opp_pts_fb_rank = Column(Integer)
    misc_per100possessions_opp_pts_paint_rank = Column(Integer)
    
    # ==================== Four Factors - Totals ====================
    fourfactors_totals_gp = Column(Integer)
    fourfactors_totals_w = Column(Integer)
    fourfactors_totals_l = Column(Integer)
    fourfactors_totals_w_pct = Column(Float)
    fourfactors_totals_min = Column(Float)
    fourfactors_totals_efg_pct = Column(Float)
    fourfactors_totals_fta_rate = Column(Float)
    fourfactors_totals_tm_tov_pct = Column(Float)
    fourfactors_totals_oreb_pct = Column(Float)
    fourfactors_totals_opp_efg_pct = Column(Float)
    fourfactors_totals_opp_fta_rate = Column(Float)
    fourfactors_totals_opp_tov_pct = Column(Float)
    fourfactors_totals_opp_oreb_pct = Column(Float)
    
    # ==================== Four Factors - Per48 ====================
    fourfactors_per48_gp = Column(Integer)
    fourfactors_per48_w = Column(Integer)
    fourfactors_per48_l = Column(Integer)
    fourfactors_per48_w_pct = Column(Float)
    fourfactors_per48_min = Column(Float)
    fourfactors_per48_efg_pct = Column(Float)
    fourfactors_per48_fta_rate = Column(Float)
    fourfactors_per48_tm_tov_pct = Column(Float)
    fourfactors_per48_oreb_pct = Column(Float)
    fourfactors_per48_opp_efg_pct = Column(Float)
    fourfactors_per48_opp_fta_rate = Column(Float)
    fourfactors_per48_opp_tov_pct = Column(Float)
    fourfactors_per48_opp_oreb_pct = Column(Float)
    
    # ==================== Four Factors - Per100Possessions ====================
    fourfactors_per100possessions_gp = Column(Integer)
    fourfactors_per100possessions_w = Column(Integer)
    fourfactors_per100possessions_l = Column(Integer)
    fourfactors_per100possessions_w_pct = Column(Float)
    fourfactors_per100possessions_min = Column(Float)
    fourfactors_per100possessions_efg_pct = Column(Float)
    fourfactors_per100possessions_fta_rate = Column(Float)
    fourfactors_per100possessions_tm_tov_pct = Column(Float)
    fourfactors_per100possessions_oreb_pct = Column(Float)
    fourfactors_per100possessions_opp_efg_pct = Column(Float)
    fourfactors_per100possessions_opp_fta_rate = Column(Float)
    fourfactors_per100possessions_opp_tov_pct = Column(Float)
    fourfactors_per100possessions_opp_oreb_pct = Column(Float)
    
    # ==================== Scoring Stats - Totals ====================
    scoring_totals_gp = Column(Integer)
    scoring_totals_w = Column(Integer)
    scoring_totals_l = Column(Integer)
    scoring_totals_w_pct = Column(Float)
    scoring_totals_min = Column(Float)
    scoring_totals_pct_fga_2pt = Column(Float)
    scoring_totals_pct_fga_3pt = Column(Float)
    scoring_totals_pct_pts_2pt = Column(Float)
    scoring_totals_pct_pts_2pt_mr = Column(Float)
    scoring_totals_pct_pts_3pt = Column(Float)
    scoring_totals_pct_pts_fb = Column(Float)
    scoring_totals_pct_pts_ft = Column(Float)
    scoring_totals_pct_pts_off_tov = Column(Float)
    scoring_totals_pct_pts_paint = Column(Float)
    scoring_totals_pct_ast_2pm = Column(Float)
    scoring_totals_pct_uast_2pm = Column(Float)
    scoring_totals_pct_ast_3pm = Column(Float)
    scoring_totals_pct_uast_3pm = Column(Float)
    scoring_totals_pct_ast_fgm = Column(Float)
    scoring_totals_pct_uast_fgm = Column(Float)
    
    # Scoring Totals Rankings
    scoring_totals_gp_rank = Column(Integer)
    scoring_totals_w_rank = Column(Integer)
    scoring_totals_l_rank = Column(Integer)
    scoring_totals_w_pct_rank = Column(Integer)
    scoring_totals_min_rank = Column(Integer)
    scoring_totals_pct_fga_2pt_rank = Column(Integer)
    scoring_totals_pct_fga_3pt_rank = Column(Integer)
    scoring_totals_pct_pts_2pt_rank = Column(Integer)
    scoring_totals_pct_pts_2pt_mr_rank = Column(Integer)
    scoring_totals_pct_pts_3pt_rank = Column(Integer)
    scoring_totals_pct_pts_fb_rank = Column(Integer)
    scoring_totals_pct_pts_ft_rank = Column(Integer)
    scoring_totals_pct_pts_off_tov_rank = Column(Integer)
    scoring_totals_pct_pts_paint_rank = Column(Integer)
    scoring_totals_pct_ast_2pm_rank = Column(Integer)
    scoring_totals_pct_uast_2pm_rank = Column(Integer)
    scoring_totals_pct_ast_3pm_rank = Column(Integer)
    scoring_totals_pct_uast_3pm_rank = Column(Integer)
    scoring_totals_pct_ast_fgm_rank = Column(Integer)
    scoring_totals_pct_uast_fgm_rank = Column(Integer)
    
    # ==================== Scoring Stats - Per48 ====================
    scoring_per48_gp = Column(Integer)
    scoring_per48_w = Column(Integer)
    scoring_per48_l = Column(Integer)
    scoring_per48_w_pct = Column(Float)
    scoring_per48_min = Column(Float)
    scoring_per48_pct_fga_2pt = Column(Float)
    scoring_per48_pct_fga_3pt = Column(Float)
    scoring_per48_pct_pts_2pt = Column(Float)
    scoring_per48_pct_pts_2pt_mr = Column(Float)
    scoring_per48_pct_pts_3pt = Column(Float)
    scoring_per48_pct_pts_fb = Column(Float)
    scoring_per48_pct_pts_ft = Column(Float)
    scoring_per48_pct_pts_off_tov = Column(Float)
    scoring_per48_pct_pts_paint = Column(Float)
    scoring_per48_pct_ast_2pm = Column(Float)
    scoring_per48_pct_uast_2pm = Column(Float)
    scoring_per48_pct_ast_3pm = Column(Float)
    scoring_per48_pct_uast_3pm = Column(Float)
    scoring_per48_pct_ast_fgm = Column(Float)
    scoring_per48_pct_uast_fgm = Column(Float)
    
    # Scoring Per48 Rankings
    scoring_per48_gp_rank = Column(Integer)
    scoring_per48_w_rank = Column(Integer)
    scoring_per48_l_rank = Column(Integer)
    scoring_per48_w_pct_rank = Column(Integer)
    scoring_per48_min_rank = Column(Integer)
    scoring_per48_pct_fga_2pt_rank = Column(Integer)
    scoring_per48_pct_fga_3pt_rank = Column(Integer)
    scoring_per48_pct_pts_2pt_rank = Column(Integer)
    scoring_per48_pct_pts_2pt_mr_rank = Column(Integer)
    scoring_per48_pct_pts_3pt_rank = Column(Integer)
    scoring_per48_pct_pts_fb_rank = Column(Integer)
    scoring_per48_pct_pts_ft_rank = Column(Integer)
    scoring_per48_pct_pts_off_tov_rank = Column(Integer)
    scoring_per48_pct_pts_paint_rank = Column(Integer)
    scoring_per48_pct_ast_2pm_rank = Column(Integer)
    scoring_per48_pct_uast_2pm_rank = Column(Integer)
    scoring_per48_pct_ast_3pm_rank = Column(Integer)
    scoring_per48_pct_uast_3pm_rank = Column(Integer)
    scoring_per48_pct_ast_fgm_rank = Column(Integer)
    scoring_per48_pct_uast_fgm_rank = Column(Integer)
    
    # ==================== Scoring Stats - Per100Possessions ====================
    scoring_per100possessions_gp = Column(Integer)
    scoring_per100possessions_w = Column(Integer)
    scoring_per100possessions_l = Column(Integer)
    scoring_per100possessions_w_pct = Column(Float)
    scoring_per100possessions_min = Column(Float)
    scoring_per100possessions_pct_fga_2pt = Column(Float)
    scoring_per100possessions_pct_fga_3pt = Column(Float)
    scoring_per100possessions_pct_pts_2pt = Column(Float)
    scoring_per100possessions_pct_pts_2pt_mr = Column(Float)
    scoring_per100possessions_pct_pts_3pt = Column(Float)
    scoring_per100possessions_pct_pts_fb = Column(Float)
    scoring_per100possessions_pct_pts_ft = Column(Float)
    scoring_per100possessions_pct_pts_off_tov = Column(Float)
    scoring_per100possessions_pct_pts_paint = Column(Float)
    scoring_per100possessions_pct_ast_2pm = Column(Float)
    scoring_per100possessions_pct_uast_2pm = Column(Float)
    scoring_per100possessions_pct_ast_3pm = Column(Float)
    scoring_per100possessions_pct_uast_3pm = Column(Float)
    scoring_per100possessions_pct_ast_fgm = Column(Float)
    scoring_per100possessions_pct_uast_fgm = Column(Float)
    
    # Scoring Per100Possessions Rankings
    scoring_per100possessions_gp_rank = Column(Integer)
    scoring_per100possessions_w_rank = Column(Integer)
    scoring_per100possessions_l_rank = Column(Integer)
    scoring_per100possessions_w_pct_rank = Column(Integer)
    scoring_per100possessions_min_rank = Column(Integer)
    scoring_per100possessions_pct_fga_2pt_rank = Column(Integer)
    scoring_per100possessions_pct_fga_3pt_rank = Column(Integer)
    scoring_per100possessions_pct_pts_2pt_rank = Column(Integer)
    scoring_per100possessions_pct_pts_2pt_mr_rank = Column(Integer)
    scoring_per100possessions_pct_pts_3pt_rank = Column(Integer)
    scoring_per100possessions_pct_pts_fb_rank = Column(Integer)
    scoring_per100possessions_pct_pts_ft_rank = Column(Integer)
    scoring_per100possessions_pct_pts_off_tov_rank = Column(Integer)
    scoring_per100possessions_pct_pts_paint_rank = Column(Integer)
    scoring_per100possessions_pct_ast_2pm_rank = Column(Integer)
    scoring_per100possessions_pct_uast_2pm_rank = Column(Integer)
    scoring_per100possessions_pct_ast_3pm_rank = Column(Integer)
    scoring_per100possessions_pct_uast_3pm_rank = Column(Integer)
    scoring_per100possessions_pct_ast_fgm_rank = Column(Integer)
    scoring_per100possessions_pct_uast_fgm_rank = Column(Integer)
    
    # ==================== Opponent Stats - Totals ====================
    opponent_totals_gp = Column(Integer)
    opponent_totals_w = Column(Integer)
    opponent_totals_l = Column(Integer)
    opponent_totals_w_pct = Column(Float)
    opponent_totals_min = Column(Float)
    opponent_totals_opp_fgm = Column(Integer)
    opponent_totals_opp_fga = Column(Integer)
    opponent_totals_opp_fg_pct = Column(Float)
    opponent_totals_opp_fg3m = Column(Integer)
    opponent_totals_opp_fg3a = Column(Integer)
    opponent_totals_opp_fg3_pct = Column(Float)
    opponent_totals_opp_ftm = Column(Integer)
    opponent_totals_opp_fta = Column(Integer)
    opponent_totals_opp_ft_pct = Column(Float)
    opponent_totals_opp_oreb = Column(Integer)
    opponent_totals_opp_dreb = Column(Integer)
    opponent_totals_opp_reb = Column(Integer)
    opponent_totals_opp_ast = Column(Integer)
    opponent_totals_opp_tov = Column(Integer)
    opponent_totals_opp_stl = Column(Integer)
    opponent_totals_opp_blk = Column(Integer)
    opponent_totals_opp_blka = Column(Integer)
    opponent_totals_opp_pf = Column(Integer)
    opponent_totals_opp_pfd = Column(Integer)
    opponent_totals_opp_pts = Column(Integer)
    opponent_totals_plus_minus = Column(Float)
    
    # Opponent Totals Rankings
    opponent_totals_gp_rank = Column(Integer)
    opponent_totals_w_rank = Column(Integer)
    opponent_totals_l_rank = Column(Integer)
    opponent_totals_w_pct_rank = Column(Integer)
    opponent_totals_min_rank = Column(Integer)
    opponent_totals_opp_fgm_rank = Column(Integer)
    opponent_totals_opp_fga_rank = Column(Integer)
    opponent_totals_opp_fg_pct_rank = Column(Integer)
    opponent_totals_opp_fg3m_rank = Column(Integer)
    opponent_totals_opp_fg3a_rank = Column(Integer)
    opponent_totals_opp_fg3_pct_rank = Column(Integer)
    opponent_totals_opp_ftm_rank = Column(Integer)
    opponent_totals_opp_fta_rank = Column(Integer)
    opponent_totals_opp_ft_pct_rank = Column(Integer)
    opponent_totals_opp_oreb_rank = Column(Integer)
    opponent_totals_opp_dreb_rank = Column(Integer)
    opponent_totals_opp_reb_rank = Column(Integer)
    opponent_totals_opp_ast_rank = Column(Integer)
    opponent_totals_opp_tov_rank = Column(Integer)
    opponent_totals_opp_stl_rank = Column(Integer)
    opponent_totals_opp_blk_rank = Column(Integer)
    opponent_totals_opp_blka_rank = Column(Integer)
    opponent_totals_opp_pf_rank = Column(Integer)
    opponent_totals_opp_pfd_rank = Column(Integer)
    opponent_totals_opp_pfd1 = Column(Integer)
    opponent_totals_opp_pts_rank = Column(Integer)
    opponent_totals_plus_minus_rank = Column(Integer)
    
    # ==================== Opponent Stats - Per48 ====================
    opponent_per48_gp = Column(Integer)
    opponent_per48_w = Column(Integer)
    opponent_per48_l = Column(Integer)
    opponent_per48_w_pct = Column(Float)
    opponent_per48_min = Column(Float)
    opponent_per48_opp_fgm = Column(Integer)
    opponent_per48_opp_fga = Column(Integer)
    opponent_per48_opp_fg_pct = Column(Float)
    opponent_per48_opp_fg3m = Column(Integer)
    opponent_per48_opp_fg3a = Column(Integer)
    opponent_per48_opp_fg3_pct = Column(Float)
    opponent_per48_opp_ftm = Column(Integer)
    opponent_per48_opp_fta = Column(Integer)
    opponent_per48_opp_ft_pct = Column(Float)
    opponent_per48_opp_oreb = Column(Integer)
    opponent_per48_opp_dreb = Column(Integer)
    opponent_per48_opp_reb = Column(Integer)
    opponent_per48_opp_ast = Column(Integer)
    opponent_per48_opp_tov = Column(Integer)
    opponent_per48_opp_stl = Column(Integer)
    opponent_per48_opp_blk = Column(Integer)
    opponent_per48_opp_blka = Column(Integer)
    opponent_per48_opp_pf = Column(Integer)
    opponent_per48_opp_pfd = Column(Integer)
    opponent_per48_opp_pts = Column(Integer)
    opponent_per48_plus_minus = Column(Float)
    
    # Opponent Per48 Rankings
    opponent_per48_gp_rank = Column(Integer)
    opponent_per48_w_rank = Column(Integer)
    opponent_per48_l_rank = Column(Integer)
    opponent_per48_w_pct_rank = Column(Integer)
    opponent_per48_min_rank = Column(Integer)
    opponent_per48_opp_fgm_rank = Column(Integer)
    opponent_per48_opp_fga_rank = Column(Integer)
    opponent_per48_opp_fg_pct_rank = Column(Integer)
    opponent_per48_opp_fg3m_rank = Column(Integer)
    opponent_per48_opp_fg3a_rank = Column(Integer)
    opponent_per48_opp_fg3_pct_rank = Column(Integer)
    opponent_per48_opp_ftm_rank = Column(Integer)
    opponent_per48_opp_fta_rank = Column(Integer)
    opponent_per48_opp_ft_pct_rank = Column(Integer)
    opponent_per48_opp_oreb_rank = Column(Integer)
    opponent_per48_opp_dreb_rank = Column(Integer)
    opponent_per48_opp_reb_rank = Column(Integer)
    opponent_per48_opp_ast_rank = Column(Integer)
    opponent_per48_opp_tov_rank = Column(Integer)
    opponent_per48_opp_stl_rank = Column(Integer)
    opponent_per48_opp_blk_rank = Column(Integer)
    opponent_per48_opp_blka_rank = Column(Integer)
    opponent_per48_opp_pf_rank = Column(Integer)
    opponent_per48_opp_pfd_rank = Column(Integer)
    opponent_per48_opp_pfd1 = Column(Integer)
    opponent_per48_opp_pts_rank = Column(Integer)
    opponent_per48_plus_minus_rank = Column(Integer)
    
    # ==================== Opponent Stats - Per100Possessions ====================
    opponent_per100possessions_gp = Column(Integer)
    opponent_per100possessions_w = Column(Integer)
    opponent_per100possessions_l = Column(Integer)
    opponent_per100possessions_w_pct = Column(Float)
    opponent_per100possessions_min = Column(Float)
    opponent_per100possessions_opp_fgm = Column(Integer)
    opponent_per100possessions_opp_fga = Column(Integer)
    opponent_per100possessions_opp_fg_pct = Column(Float)
    opponent_per100possessions_opp_fg3m = Column(Integer)
    opponent_per100possessions_opp_fg3a = Column(Integer)
    opponent_per100possessions_opp_fg3_pct = Column(Float)
    opponent_per100possessions_opp_ftm = Column(Integer)
    opponent_per100possessions_opp_fta = Column(Integer)
    opponent_per100possessions_opp_ft_pct = Column(Float)
    opponent_per100possessions_opp_oreb = Column(Integer)
    opponent_per100possessions_opp_dreb = Column(Integer)
    opponent_per100possessions_opp_reb = Column(Integer)
    opponent_per100possessions_opp_ast = Column(Integer)
    opponent_per100possessions_opp_tov = Column(Integer)
    opponent_per100possessions_opp_stl = Column(Integer)
    opponent_per100possessions_opp_blk = Column(Integer)
    opponent_per100possessions_opp_blka = Column(Integer)
    opponent_per100possessions_opp_pf = Column(Integer)
    opponent_per100possessions_opp_pfd = Column(Integer)
    opponent_per100possessions_opp_pts = Column(Integer)
    opponent_per100possessions_plus_minus = Column(Float)
    
    # Opponent Per100Possessions Rankings
    opponent_per100possessions_gp_rank = Column(Integer)
    opponent_per100possessions_w_rank = Column(Integer)
    opponent_per100possessions_l_rank = Column(Integer)
    opponent_per100possessions_w_pct_rank = Column(Integer)
    opponent_per100possessions_min_rank = Column(Integer)
    opponent_per100possessions_opp_fgm_rank = Column(Integer)
    opponent_per100possessions_opp_fga_rank = Column(Integer)
    opponent_per100possessions_opp_fg_pct_rank = Column(Integer)
    opponent_per100possessions_opp_fg3m_rank = Column(Integer)
    opponent_per100possessions_opp_fg3a_rank = Column(Integer)
    opponent_per100possessions_opp_fg3_pct_rank = Column(Integer)
    opponent_per100possessions_opp_ftm_rank = Column(Integer)
    opponent_per100possessions_opp_fta_rank = Column(Integer)
    opponent_per100possessions_opp_ft_pct_rank = Column(Integer)
    opponent_per100possessions_opp_oreb_rank = Column(Integer)
    opponent_per100possessions_opp_dreb_rank = Column(Integer)
    opponent_per100possessions_opp_reb_rank = Column(Integer)
    opponent_per100possessions_opp_ast_rank = Column(Integer)
    opponent_per100possessions_opp_tov_rank = Column(Integer)
    opponent_per100possessions_opp_stl_rank = Column(Integer)
    opponent_per100possessions_opp_blk_rank = Column(Integer)
    opponent_per100possessions_opp_blka_rank = Column(Integer)
    opponent_per100possessions_opp_pf_rank = Column(Integer)
    opponent_per100possessions_opp_pfd_rank = Column(Integer)
    opponent_per100possessions_opp_pfd1 = Column(Integer)
    opponent_per100possessions_opp_pts_rank = Column(Integer)
    opponent_per100possessions_plus_minus_rank = Column(Integer)
    
    # ==================== Defense Stats - Totals ====================
    defense_totals_gp = Column(Integer)
    defense_totals_w = Column(Integer)
    defense_totals_l = Column(Integer)
    defense_totals_w_pct = Column(Float)
    defense_totals_min = Column(Float)
    defense_totals_def_rating = Column(Float)
    defense_totals_dreb = Column(Integer)
    defense_totals_dreb_pct = Column(Float)
    defense_totals_stl = Column(Integer)
    defense_totals_blk = Column(Integer)
    defense_totals_opp_pts_off_tov = Column(Integer)
    defense_totals_opp_pts_2nd_chance = Column(Integer)
    defense_totals_opp_pts_fb = Column(Integer)
    defense_totals_opp_pts_paint = Column(Integer)
    
    # Defense Totals Rankings
    defense_totals_gp_rank = Column(Integer)
    defense_totals_w_rank = Column(Integer)
    defense_totals_l_rank = Column(Integer)
    defense_totals_w_pct_rank = Column(Integer)
    defense_totals_min_rank = Column(Integer)
    defense_totals_def_rating_rank = Column(Integer)
    defense_totals_dreb_rank = Column(Integer)
    defense_totals_dreb_pct_rank = Column(Integer)
    defense_totals_stl_rank = Column(Integer)
    defense_totals_blk_rank = Column(Integer)
    defense_totals_opp_pts_off_tov_rank = Column(Integer)
    defense_totals_opp_pts_2nd_chance_rank = Column(Integer)
    defense_totals_opp_pts_fb_rank = Column(Integer)
    defense_totals_opp_pts_paint_rank = Column(Integer)
    
    # ==================== Defense Stats - Per48 ====================
    defense_per48_gp = Column(Integer)
    defense_per48_w = Column(Integer)
    defense_per48_l = Column(Integer)
    defense_per48_w_pct = Column(Float)
    defense_per48_min = Column(Float)
    defense_per48_def_rating = Column(Float)
    defense_per48_dreb = Column(Integer)
    defense_per48_dreb_pct = Column(Float)
    defense_per48_stl = Column(Integer)
    defense_per48_blk = Column(Integer)
    defense_per48_opp_pts_off_tov = Column(Integer)
    defense_per48_opp_pts_2nd_chance = Column(Integer)
    defense_per48_opp_pts_fb = Column(Integer)
    defense_per48_opp_pts_paint = Column(Integer)
    
    # Defense Per48 Rankings
    defense_per48_gp_rank = Column(Integer)
    defense_per48_w_rank = Column(Integer)
    defense_per48_l_rank = Column(Integer)
    defense_per48_w_pct_rank = Column(Integer)
    defense_per48_min_rank = Column(Integer)
    defense_per48_def_rating_rank = Column(Integer)
    defense_per48_dreb_rank = Column(Integer)
    defense_per48_dreb_pct_rank = Column(Integer)
    defense_per48_stl_rank = Column(Integer)
    defense_per48_blk_rank = Column(Integer)
    defense_per48_opp_pts_off_tov_rank = Column(Integer)
    defense_per48_opp_pts_2nd_chance_rank = Column(Integer)
    defense_per48_opp_pts_fb_rank = Column(Integer)
    defense_per48_opp_pts_paint_rank = Column(Integer)
    
    # ==================== Defense Stats - Per100Possessions ====================
    defense_per100possessions_gp = Column(Integer)
    defense_per100possessions_w = Column(Integer)
    defense_per100possessions_l = Column(Integer)
    defense_per100possessions_w_pct = Column(Float)
    defense_per100possessions_min = Column(Float)
    defense_per100possessions_def_rating = Column(Float)
    defense_per100possessions_dreb = Column(Integer)
    defense_per100possessions_dreb_pct = Column(Float)
    defense_per100possessions_stl = Column(Integer)
    defense_per100possessions_blk = Column(Integer)
    defense_per100possessions_opp_pts_off_tov = Column(Integer)
    defense_per100possessions_opp_pts_2nd_chance = Column(Integer)
    defense_per100possessions_opp_pts_fb = Column(Integer)
    defense_per100possessions_opp_pts_paint = Column(Integer)
    
    # Defense Per100Possessions Rankings
    defense_per100possessions_gp_rank = Column(Integer)
    defense_per100possessions_w_rank = Column(Integer)
    defense_per100possessions_l_rank = Column(Integer)
    defense_per100possessions_w_pct_rank = Column(Integer)
    defense_per100possessions_min_rank = Column(Integer)
    defense_per100possessions_def_rating_rank = Column(Integer)
    defense_per100possessions_dreb_rank = Column(Integer)
    defense_per100possessions_dreb_pct_rank = Column(Integer)
    defense_per100possessions_stl_rank = Column(Integer)
    defense_per100possessions_blk_rank = Column(Integer)
    defense_per100possessions_opp_pts_off_tov_rank = Column(Integer)
    defense_per100possessions_opp_pts_2nd_chance_rank = Column(Integer)
    defense_per100possessions_opp_pts_fb_rank = Column(Integer)
    defense_per100possessions_opp_pts_paint_rank = Column(Integer)
    
    def __repr__(self) -> str:
        """String representation of the team stats."""
        return (f"<LeagueDashTeamStatsORM(team_id={self.team_id}, team='{self.team_name}', "
                f"season='{self.season}', type='{self.season_type}')>")
    
    def to_dict(self, measure_type: str = 'Base', per_mode: str = 'Totals') -> dict:
        """Convert team stats to dictionary for a specific measure type and per mode.
        
        Args:
            measure_type: Type of stats (Base, Advanced, etc.)
            per_mode: Per mode (Totals, Per48, Per100Possessions)
            
        Returns:
            dict: Dictionary with team stats for specified measure/per mode
        """
        prefix = f"{measure_type.lower()}_{per_mode.lower().replace(' ', '')}"
        
        result = {
            'team_id': self.team_id,
            'team_name': self.team_name,
            'season': self.season,
            'season_type': self.season_type
        }
        
        # Add all columns matching the prefix
        for column in self.__table__.columns:
            col_name = column.name
            if col_name.startswith(prefix):
                stat_name = col_name[len(prefix)+1:]  # Remove prefix and underscore
                result[stat_name] = getattr(self, col_name)
        
        return result
    
    # ==================== Class Methods (Query Operations) ====================
    
    @classmethod
    def get_by_team(cls, team_id: int, season: str = "2024-25",
                   season_type: str = "Regular Season",
                   db: Optional[Session] = None) -> Optional['LeagueDashTeamStatsORM']:
        """Get team stats for a specific team, season, and season type.
        
        Args:
            team_id: Team identifier
            season: Season (e.g., "2024-25")
            season_type: "Regular Season" or "Playoffs"
            db: Optional database session
            
        Returns:
            LeagueDashTeamStatsORM object if found, None otherwise
        """
        if db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season,
                cls.season_type == season_type
            ).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season,
                cls.season_type == season_type
            ).first()
    
    @classmethod
    def get_all_teams(cls, season: str = "2024-25", season_type: str = "Regular Season",
                     db: Optional[Session] = None) -> List['LeagueDashTeamStatsORM']:
        """Get stats for all teams in a season.
        
        Args:
            season: Season (e.g., "2024-25")
            season_type: "Regular Season" or "Playoffs"
            db: Optional database session
            
        Returns:
            List of LeagueDashTeamStatsORM objects
        """
        if db:
            return db.query(cls).filter(
                cls.season == season,
                cls.season_type == season_type
            ).order_by(cls.base_totals_w_pct_rank).all()
        
        with get_db_context() as db:
            return db.query(cls).filter(
                cls.season == season,
                cls.season_type == season_type
            ).order_by(cls.base_totals_w_pct_rank).all()
    
    @classmethod
    def get_team_rankings(cls, season: str = "2024-25", per_mode: str = "Totals",
                         db: Optional[Session] = None) -> List[dict]:
        """Get key ranking stats for team comparison.
        
        Args:
            season: Season (e.g., "2024-25")
            per_mode: "Totals", "Per48", or "Per100Possessions"
            db: Optional database session
            
        Returns:
            List of dictionaries with team rankings
        """
        per_mode_key = per_mode.lower().replace(" ", "")
        
        def _query(session: Session):
            teams = session.query(cls).filter(cls.season == season).all()
            
            results = []
            for team in teams:
                result = {
                    'team_id': team.team_id,
                    'team_name': team.team_name,
                    'season': team.season,
                    'season_type': team.season_type,
                    'w_pct_rank': getattr(team, f'base_{per_mode_key}_w_pct_rank'),
                    'pts_rank': getattr(team, f'base_{per_mode_key}_pts_rank'),
                    'fgm_rank': getattr(team, f'base_{per_mode_key}_fgm_rank'),
                    'fg3m_rank': getattr(team, f'base_{per_mode_key}_fg3m_rank'),
                    'ast_rank': getattr(team, f'base_{per_mode_key}_ast_rank'),
                    'reb_rank': getattr(team, f'base_{per_mode_key}_reb_rank'),
                    'stl_rank': getattr(team, f'base_{per_mode_key}_stl_rank'),
                    'blk_rank': getattr(team, f'base_{per_mode_key}_blk_rank'),
                    'tov_rank': getattr(team, f'base_{per_mode_key}_tov_rank'),
                }
                results.append(result)
            
            # Sort by win percentage rank
            results.sort(key=lambda x: x['w_pct_rank'] if x['w_pct_rank'] else 999)
            return results
        
        if db:
            return _query(db)
        
        with get_db_context() as session:
            return _query(session)
    
    # ==================== CRUD Operations ====================
    
    @classmethod
    def create_from_dict(cls, team_stats: dict, db: Optional[Session] = None) -> 'LeagueDashTeamStatsORM':
        """Create or update team stats from dictionary (upsert).
        
        Args:
            team_stats: Dictionary with stat names as keys (case insensitive)
            db: Optional database session
            
        Returns:
            LeagueDashTeamStatsORM: The created or updated stats object
        """
        def _create(session: Session) -> 'LeagueDashTeamStatsORM':
            # Normalize keys to lowercase
            normalized_stats = {k.lower(): v for k, v in team_stats.items()}
            
            # Extract primary key values
            team_id = normalized_stats.get('team_id')
            season = normalized_stats.get('season')
            season_type = normalized_stats.get('season_type', 'Regular Season')
            
            if not team_id or not season:
                raise ValueError("team_id and season are required")
            
            # Check if stats exist
            stats = session.query(cls).filter(
                cls.team_id == team_id,
                cls.season == season,
                cls.season_type == season_type
            ).first()
            
            if stats:
                # Update existing stats
                for key, value in normalized_stats.items():
                    if hasattr(stats, key) and key not in ['team_id', 'season', 'season_type']:
                        setattr(stats, key, value)
                logger.info(f"Updated team stats: {normalized_stats.get('team_name')} {season}")
            else:
                # Create new stats
                stats = cls()
                for key, value in normalized_stats.items():
                    if hasattr(stats, key):
                        setattr(stats, key, value)
                session.add(stats)
                logger.info(f"Created new team stats: {normalized_stats.get('team_name')} {season}")
            
            session.flush()
            return stats
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            stats = _create(session)
            session.commit()
            return stats
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete this team stats record from the database.
        
        Args:
            db: Optional database session
        """
        def _delete(session: Session) -> None:
            if self not in session:
                self = session.merge(self)
            session.delete(self)
            session.flush()
            logger.info(f"Deleted team stats: {self.team_name} {self.season}")
        
        if db:
            _delete(db)
        else:
            with get_db_context() as session:
                _delete(session)
                session.commit()


# Backward compatibility
def get_league_dash_team_stats_model():
    """Get the appropriate league dash team stats model (SQLAlchemy version).
    
    Returns:
        LeagueDashTeamStatsORM class
    """
    return LeagueDashTeamStatsORM

