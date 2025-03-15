from db_config import get_db_connection
import logging

class LeagueDashTeamStats:
    """
    Stores NBA team statistics across all measure types, per modes, and season types.
    Column names are prefixed with MeasureType & PerMode for clarity.
    """

    @classmethod
    def create_table(cls):
        """Create the `league_dash_team_stats` table to store BASE Totals data first."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS league_dash_team_stats (
                    team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    team_name VARCHAR(50) NOT NULL,
                    season VARCHAR(10) NOT NULL,
                    season_type VARCHAR(15) NOT NULL CHECK (season_type IN ('Regular Season', 'Playoffs')),
                    --
                    --Base
                    --

                    Base_Totals_GP INT,
                    Base_Totals_W INT,
                    Base_Totals_L INT,
                    Base_Totals_W_PCT FLOAT,
                    Base_Totals_MIN FLOAT,
                    Base_Totals_FGM INT,
                    Base_Totals_FGA INT,
                    Base_Totals_FG_PCT FLOAT,
                    Base_Totals_FG3M INT,
                    Base_Totals_FG3A INT,
                    Base_Totals_FG3_PCT FLOAT,
                    Base_Totals_FTM INT,
                    Base_Totals_FTA INT,
                    Base_Totals_FT_PCT FLOAT,
                    Base_Totals_OREB INT,
                    Base_Totals_DREB INT,
                    Base_Totals_REB INT,
                    Base_Totals_AST INT,
                    Base_Totals_TOV INT,
                    Base_Totals_STL INT,
                    Base_Totals_BLK INT,
                    Base_Totals_BLKA INT,
                    Base_Totals_PF INT,
                    Base_Totals_PFD INT,
                    Base_Totals_PTS INT,
                    Base_Totals_PLUS_MINUS FLOAT,
                    
                    -- Rankings
                    Base_Totals_GP_RANK INT,
                    Base_Totals_W_RANK INT,
                    Base_Totals_L_RANK INT,
                    Base_Totals_W_PCT_RANK INT,
                    Base_Totals_MIN_RANK INT,
                    Base_Totals_FGM_RANK INT,
                    Base_Totals_FGA_RANK INT,
                    Base_Totals_FG_PCT_RANK INT,
                    Base_Totals_FG3M_RANK INT,
                    Base_Totals_FG3A_RANK INT,
                    Base_Totals_FG3_PCT_RANK INT,
                    Base_Totals_FTM_RANK INT,
                    Base_Totals_FTA_RANK INT,
                    Base_Totals_FT_PCT_RANK INT,
                    Base_Totals_OREB_RANK INT,
                    Base_Totals_DREB_RANK INT,
                    Base_Totals_REB_RANK INT,
                    Base_Totals_AST_RANK INT,
                    Base_Totals_TOV_RANK INT,
                    Base_Totals_STL_RANK INT,
                    Base_Totals_BLK_RANK INT,
                    Base_Totals_BLKA_RANK INT,
                    Base_Totals_PF_RANK INT,
                    Base_Totals_PFD_RANK INT,
                    Base_Totals_PTS_RANK INT,
                    Base_Totals_PLUS_MINUS_RANK INT,

                    Base_Per48_GP INT,
                    Base_Per48_L INT,
                    Base_Per48_W INT,
                    Base_Per48_W_PCT FLOAT,
                    Base_Per48_MIN FLOAT,
                    Base_Per48_FGM INT,
                    Base_Per48_FGA INT,
                    Base_Per48_FG_PCT FLOAT,
                    Base_Per48_FG3M INT,
                    Base_Per48_FG3A INT,
                    Base_Per48_FG3_PCT FLOAT,
                    Base_Per48_FTM INT,
                    Base_Per48_FTA INT,
                    Base_Per48_FT_PCT FLOAT,
                    Base_Per48_OREB INT,
                    Base_Per48_DREB INT,
                    Base_Per48_REB INT,
                    Base_Per48_AST INT,
                    Base_Per48_TOV INT,
                    Base_Per48_STL INT,
                    Base_Per48_BLK INT,
                    Base_Per48_BLKA INT,
                    Base_Per48_PF INT,
                    Base_Per48_PFD INT,
                    Base_Per48_PTS INT,
                    Base_Per48_PLUS_MINUS FLOAT,
                    
                    -- Rankings
                    Base_Per48_GP_RANK INT,
                    Base_Per48_W_RANK INT,
                    Base_Per48_L_RANK INT,
                    Base_Per48_W_PCT_RANK INT,
                    Base_Per48_MIN_RANK INT,
                    Base_Per48_FGM_RANK INT,
                    Base_Per48_FGA_RANK INT,
                    Base_Per48_FG_PCT_RANK INT,
                    Base_Per48_FG3M_RANK INT,
                    Base_Per48_FG3A_RANK INT,
                    Base_Per48_FG3_PCT_RANK INT,
                    Base_Per48_FTM_RANK INT,
                    Base_Per48_FTA_RANK INT,
                    Base_Per48_FT_PCT_RANK INT,
                    Base_Per48_OREB_RANK INT,
                    Base_Per48_DREB_RANK INT,
                    Base_Per48_REB_RANK INT,
                    Base_Per48_AST_RANK INT,
                    Base_Per48_TOV_RANK INT,
                    Base_Per48_STL_RANK INT,
                    Base_Per48_BLK_RANK INT,
                    Base_Per48_BLKA_RANK INT,
                    Base_Per48_PF_RANK INT,
                    Base_Per48_PFD_RANK INT,
                    Base_Per48_PTS_RANK INT,
                    Base_Per48_PLUS_MINUS_RANK INT,

                    Base_Per100Possessions_GP INT,
                    Base_Per100Possessions_L INT,
                    Base_Per100Possessions_W INT,
                    Base_Per100Possessions_W_PCT FLOAT,
                    Base_Per100Possessions_MIN FLOAT,
                    Base_Per100Possessions_FGM INT,
                    Base_Per100Possessions_FGA INT,
                    Base_Per100Possessions_FG_PCT FLOAT,
                    Base_Per100Possessions_FG3M INT,
                    Base_Per100Possessions_FG3A INT,
                    Base_Per100Possessions_FG3_PCT FLOAT,
                    Base_Per100Possessions_FTM INT,
                    Base_Per100Possessions_FTA INT,
                    Base_Per100Possessions_FT_PCT FLOAT,
                    Base_Per100Possessions_OREB INT,
                    Base_Per100Possessions_DREB INT,
                    Base_Per100Possessions_REB INT,
                    Base_Per100Possessions_AST INT,
                    Base_Per100Possessions_TOV INT,
                    Base_Per100Possessions_STL INT,
                    Base_Per100Possessions_BLK INT,
                    Base_Per100Possessions_BLKA INT,
                    Base_Per100Possessions_PF INT,
                    Base_Per100Possessions_PFD INT,
                    Base_Per100Possessions_PTS INT,
                    Base_Per100Possessions_PLUS_MINUS FLOAT,
                    
                    -- Rankings
                    Base_Per100Possessions_GP_RANK INT,
                    Base_Per100Possessions_W_RANK INT,
                    Base_Per100Possessions_L_RANK INT,
                    Base_Per100Possessions_W_PCT_RANK INT,
                    Base_Per100Possessions_MIN_RANK INT,
                    Base_Per100Possessions_FGM_RANK INT,
                    Base_Per100Possessions_FGA_RANK INT,
                    Base_Per100Possessions_FG_PCT_RANK INT,
                    Base_Per100Possessions_FG3M_RANK INT,
                    Base_Per100Possessions_FG3A_RANK INT,
                    Base_Per100Possessions_FG3_PCT_RANK INT,
                    Base_Per100Possessions_FTM_RANK INT,
                    Base_Per100Possessions_FTA_RANK INT,
                    Base_Per100Possessions_FT_PCT_RANK INT,
                    Base_Per100Possessions_OREB_RANK INT,
                    Base_Per100Possessions_DREB_RANK INT,
                    Base_Per100Possessions_REB_RANK INT,
                    Base_Per100Possessions_AST_RANK INT,
                    Base_Per100Possessions_TOV_RANK INT,
                    Base_Per100Possessions_STL_RANK INT,
                    Base_Per100Possessions_BLK_RANK INT,
                    Base_Per100Possessions_BLKA_RANK INT,
                    Base_Per100Possessions_PF_RANK INT,
                    Base_Per100Possessions_PFD_RANK INT,
                    Base_Per100Possessions_PTS_RANK INT,
                    Base_Per100Possessions_PLUS_MINUS_RANK INT,

                    --
                    -- Advanced
                    --
                    --Totals
                    Advanced_Totals_GP INT,
                    Advanced_Totals_W INT,
                    Advanced_Totals_L INT,
                    Advanced_Totals_W_PCT FLOAT,
                    Advanced_Totals_MIN FLOAT,
                    Advanced_Totals_E_OFF_RATING FLOAT,
                    Advanced_Totals_OFF_RATING FLOAT,
                    Advanced_Totals_E_DEF_RATING FLOAT,
                    Advanced_Totals_DEF_RATING FLOAT,
                    Advanced_Totals_E_NET_RATING FLOAT,
                    Advanced_Totals_NET_RATING FLOAT,
                    Advanced_Totals_AST_PCT FLOAT,
                    Advanced_Totals_AST_TO FLOAT,
                    Advanced_Totals_AST_RATIO FLOAT,
                    Advanced_Totals_OREB_PCT FLOAT,
                    Advanced_Totals_DREB_PCT FLOAT,
                    Advanced_Totals_REB_PCT FLOAT,
                    Advanced_Totals_TM_TOV_PCT FLOAT,
                    Advanced_Totals_EFG_PCT FLOAT,
                    Advanced_Totals_TS_PCT FLOAT,
                    Advanced_Totals_E_PACE FLOAT,
                    Advanced_Totals_PACE FLOAT,
                    Advanced_Totals_PACE_PER40 FLOAT,
                    Advanced_Totals_POSS INT,
                    Advanced_Totals_PIE FLOAT,
                    
                    -- Rankings
                    Advanced_Totals_GP_RANK INT,
                    Advanced_Totals_W_RANK INT,
                    Advanced_Totals_L_RANK INT,
                    Advanced_Totals_W_PCT_RANK INT,
                    Advanced_Totals_MIN_RANK INT,
                    Advanced_Totals_OFF_RATING_RANK INT,
                    Advanced_Totals_DEF_RATING_RANK INT,
                    Advanced_Totals_NET_RATING_RANK INT,
                    Advanced_Totals_AST_PCT_RANK INT,
                    Advanced_Totals_AST_TO_RANK INT,
                    Advanced_Totals_AST_RATIO_RANK INT,
                    Advanced_Totals_OREB_PCT_RANK INT,
                    Advanced_Totals_DREB_PCT_RANK INT,
                    Advanced_Totals_REB_PCT_RANK INT,
                    Advanced_Totals_TM_TOV_PCT_RANK INT,
                    Advanced_Totals_EFG_PCT_RANK INT,
                    Advanced_Totals_TS_PCT_RANK INT,
                    Advanced_Totals_PACE_RANK INT,
                    Advanced_Totals_PIE_RANK INT,

                    --Per48
                    Advanced_Per48_GP INT,
                    Advanced_Per48_W INT,
                    Advanced_Per48_L INT,
                    Advanced_Per48_W_PCT FLOAT,
                    Advanced_Per48_MIN FLOAT,
                    Advanced_Per48_E_OFF_RATING FLOAT,
                    Advanced_Per48_OFF_RATING FLOAT,
                    Advanced_Per48_E_DEF_RATING FLOAT,
                    Advanced_Per48_DEF_RATING FLOAT,
                    Advanced_Per48_E_NET_RATING FLOAT,
                    Advanced_Per48_NET_RATING FLOAT,
                    Advanced_Per48_AST_PCT FLOAT,
                    Advanced_Per48_AST_TO FLOAT,
                    Advanced_Per48_AST_RATIO FLOAT,
                    Advanced_Per48_OREB_PCT FLOAT,
                    Advanced_Per48_DREB_PCT FLOAT,
                    Advanced_Per48_REB_PCT FLOAT,
                    Advanced_Per48_TM_TOV_PCT FLOAT,
                    Advanced_Per48_EFG_PCT FLOAT,
                    Advanced_Per48_TS_PCT FLOAT,
                    Advanced_Per48_E_PACE FLOAT,
                    Advanced_Per48_PACE FLOAT,
                    Advanced_Per48_PACE_PER40 FLOAT,
                    Advanced_Per48_POSS INT,
                    Advanced_Per48_PIE FLOAT,

                    -- Rankings
                    Advanced_Per48_GP_RANK INT,
                    Advanced_Per48_W_RANK INT,
                    Advanced_Per48_L_RANK INT,
                    Advanced_Per48_W_PCT_RANK INT,
                    Advanced_Per48_MIN_RANK INT,
                    Advanced_Per48_OFF_RATING_RANK INT,
                    Advanced_Per48_DEF_RATING_RANK INT,
                    Advanced_Per48_NET_RATING_RANK INT,
                    Advanced_Per48_AST_PCT_RANK INT,
                    Advanced_Per48_AST_TO_RANK INT,
                    Advanced_Per48_AST_RATIO_RANK INT,
                    Advanced_Per48_OREB_PCT_RANK INT,
                    Advanced_Per48_DREB_PCT_RANK INT,
                    Advanced_Per48_REB_PCT_RANK INT,
                    Advanced_Per48_TM_TOV_PCT_RANK INT,
                    Advanced_Per48_EFG_PCT_RANK INT,
                    Advanced_Per48_TS_PCT_RANK INT,
                    Advanced_Per48_PACE_RANK INT,
                    Advanced_Per48_PIE_RANK INT,
                    
                    --Per100Possessions
                    Advanced_Per100Possessions_GP INT,
                    Advanced_Per100Possessions_W INT,
                    Advanced_Per100Possessions_L INT,
                    Advanced_Per100Possessions_W_PCT FLOAT,
                    Advanced_Per100Possessions_MIN FLOAT,
                    Advanced_Per100Possessions_E_OFF_RATING FLOAT,
                    Advanced_Per100Possessions_OFF_RATING FLOAT,
                    Advanced_Per100Possessions_E_DEF_RATING FLOAT,
                    Advanced_Per100Possessions_DEF_RATING FLOAT,
                    Advanced_Per100Possessions_E_NET_RATING FLOAT,
                    Advanced_Per100Possessions_NET_RATING FLOAT,
                    Advanced_Per100Possessions_AST_PCT FLOAT,
                    Advanced_Per100Possessions_AST_TO FLOAT,
                    Advanced_Per100Possessions_AST_RATIO FLOAT,
                    Advanced_Per100Possessions_OREB_PCT FLOAT,
                    Advanced_Per100Possessions_DREB_PCT FLOAT,
                    Advanced_Per100Possessions_REB_PCT FLOAT,
                    Advanced_Per100Possessions_TM_TOV_PCT FLOAT,
                    Advanced_Per100Possessions_EFG_PCT FLOAT,
                    Advanced_Per100Possessions_TS_PCT FLOAT,
                    Advanced_Per100Possessions_E_PACE FLOAT,
                    Advanced_Per100Possessions_PACE FLOAT,
                    Advanced_Per100Possessions_PACE_PER40 FLOAT,
                    Advanced_Per100Possessions_POSS INT,
                    Advanced_Per100Possessions_PIE FLOAT,
                    
                    -- Rankings
                    Advanced_Per100Possessions_GP_RANK INT,
                    Advanced_Per100Possessions_W_RANK INT,
                    Advanced_Per100Possessions_L_RANK INT,  
                    Advanced_Per100Possessions_W_PCT_RANK INT,
                    Advanced_Per100Possessions_MIN_RANK INT,
                    Advanced_Per100Possessions_OFF_RATING_RANK INT,
                    Advanced_Per100Possessions_DEF_RATING_RANK INT,
                    Advanced_Per100Possessions_NET_RATING_RANK INT,
                    Advanced_Per100Possessions_AST_PCT_RANK INT,
                    Advanced_Per100Possessions_AST_TO_RANK INT,
                    Advanced_Per100Possessions_AST_RATIO_RANK INT,
                    Advanced_Per100Possessions_OREB_PCT_RANK INT,
                    Advanced_Per100Possessions_DREB_PCT_RANK INT,
                    Advanced_Per100Possessions_REB_PCT_RANK INT,
                    Advanced_Per100Possessions_TM_TOV_PCT_RANK INT,
                    Advanced_Per100Possessions_EFG_PCT_RANK INT,
                    Advanced_Per100Possessions_TS_PCT_RANK INT,
                    Advanced_Per100Possessions_PACE_RANK INT,
                    Advanced_Per100Possessions_PIE_RANK INT,

                    --
                    -- Misc
                    --
                    --Totals
                    Misc_Totals_GP INT,
                    Misc_Totals_W INT,
                    Misc_Totals_L INT,
                    Misc_Totals_W_PCT FLOAT,
                    Misc_Totals_MIN FLOAT,
                    Misc_Totals_PTS_OFF_TOV INT,
                    Misc_Totals_PTS_2ND_CHANCE INT,
                    Misc_Totals_PTS_FB INT,
                    Misc_Totals_PTS_PAINT INT,
                    Misc_Totals_OPP_PTS_OFF_TOV INT,
                    Misc_Totals_OPP_PTS_2ND_CHANCE INT,
                    Misc_Totals_OPP_PTS_FB INT,
                    Misc_Totals_OPP_PTS_PAINT INT,
                    
                    -- Rankings
                    Misc_Totals_GP_RANK INT,
                    Misc_Totals_W_RANK INT,
                    Misc_Totals_L_RANK INT,
                    Misc_Totals_W_PCT_RANK INT,
                    Misc_Totals_MIN_RANK INT,
                    Misc_Totals_PTS_OFF_TOV_RANK INT,
                    Misc_Totals_PTS_2ND_CHANCE_RANK INT,
                    Misc_Totals_PTS_FB_RANK INT,
                    Misc_Totals_PTS_PAINT_RANK INT,
                    Misc_Totals_OPP_PTS_OFF_TOV_RANK INT,
                    Misc_Totals_OPP_PTS_2ND_CHANCE_RANK INT,
                    Misc_Totals_OPP_PTS_FB_RANK INT,
                    Misc_Totals_OPP_PTS_PAINT_RANK INT,

                    --Per48
                    Misc_Per48_GP INT,
                    Misc_Per48_W INT,
                    Misc_Per48_L INT,
                    Misc_Per48_W_PCT FLOAT,
                    Misc_Per48_MIN FLOAT,
                    Misc_Per48_PTS_OFF_TOV INT,
                    Misc_Per48_PTS_2ND_CHANCE INT,
                    Misc_Per48_PTS_FB INT,
                    Misc_Per48_PTS_PAINT INT,
                    Misc_Per48_OPP_PTS_OFF_TOV INT,
                    Misc_Per48_OPP_PTS_2ND_CHANCE INT,
                    Misc_Per48_OPP_PTS_FB INT,
                    Misc_Per48_OPP_PTS_PAINT INT,

                    -- Rankings
                    Misc_Per48_GP_RANK INT,
                    Misc_Per48_W_RANK INT,
                    Misc_Per48_L_RANK INT,
                    Misc_Per48_W_PCT_RANK INT,
                    Misc_Per48_MIN_RANK INT,
                    Misc_Per48_PTS_OFF_TOV_RANK INT,
                    Misc_Per48_PTS_2ND_CHANCE_RANK INT,
                    Misc_Per48_PTS_FB_RANK INT,
                    Misc_Per48_PTS_PAINT_RANK INT,
                    Misc_Per48_OPP_PTS_OFF_TOV_RANK INT,
                    Misc_Per48_OPP_PTS_2ND_CHANCE_RANK INT,
                    Misc_Per48_OPP_PTS_FB_RANK INT,
                    Misc_Per48_OPP_PTS_PAINT_RANK INT,

                    --Per100Possessions
                    Misc_Per100Possessions_GP INT,
                    Misc_Per100Possessions_W INT,
                    Misc_Per100Possessions_L INT,
                    Misc_Per100Possessions_W_PCT FLOAT,
                    Misc_Per100Possessions_MIN FLOAT,
                    Misc_Per100Possessions_PTS_OFF_TOV INT,
                    Misc_Per100Possessions_PTS_2ND_CHANCE INT,
                    Misc_Per100Possessions_PTS_FB INT,
                    Misc_Per100Possessions_PTS_PAINT INT,
                    Misc_Per100Possessions_OPP_PTS_OFF_TOV INT,
                    Misc_Per100Possessions_OPP_PTS_2ND_CHANCE INT,
                    Misc_Per100Possessions_OPP_PTS_FB INT,
                    Misc_Per100Possessions_OPP_PTS_PAINT INT,
                    
                    -- Rankings
                    Misc_Per100Possessions_GP_RANK INT,
                    Misc_Per100Possessions_W_RANK INT,
                    Misc_Per100Possessions_L_RANK INT,
                    Misc_Per100Possessions_W_PCT_RANK INT,
                    Misc_Per100Possessions_MIN_RANK INT,
                    Misc_Per100Possessions_PTS_OFF_TOV_RANK INT,
                    Misc_Per100Possessions_PTS_2ND_CHANCE_RANK INT,
                    Misc_Per100Possessions_PTS_FB_RANK INT,
                    Misc_Per100Possessions_PTS_PAINT_RANK INT,
                    Misc_Per100Possessions_OPP_PTS_OFF_TOV_RANK INT,
                    Misc_Per100Possessions_OPP_PTS_2ND_CHANCE_RANK INT,
                    Misc_Per100Possessions_OPP_PTS_FB_RANK INT,
                    Misc_Per100Possessions_OPP_PTS_PAINT_RANK INT,

                    --
                    -- Four Factors
                    --
                    --Totals
                    FourFactors_Totals_GP INT,
                    FourFactors_Totals_W INT,
                    FourFactors_Totals_L INT,
                    FourFactors_Totals_W_PCT FLOAT,
                    FourFactors_Totals_MIN FLOAT,
                    FourFactors_Totals_EFG_PCT FLOAT,
                    FourFactors_Totals_FTA_RATE FLOAT,
                    FourFactors_Totals_TM_TOV_PCT FLOAT,
                    FourFactors_Totals_OREB_PCT FLOAT,
                    FourFactors_Totals_OPP_EFG_PCT FLOAT,
                    FourFactors_Totals_OPP_FTA_RATE FLOAT,
                    FourFactors_Totals_OPP_TOV_PCT FLOAT,
                    FourFactors_Totals_OPP_OREB_PCT FLOAT,
                    --Per48
                    FourFactors_Per48_GP INT,
                    FourFactors_Per48_W INT,
                    FourFactors_Per48_L INT,
                    FourFactors_Per48_W_PCT FLOAT,
                    FourFactors_Per48_MIN FLOAT,
                    FourFactors_Per48_EFG_PCT FLOAT,
                    FourFactors_Per48_FTA_RATE FLOAT,
                    FourFactors_Per48_TM_TOV_PCT FLOAT,
                    FourFactors_Per48_OREB_PCT FLOAT,
                    FourFactors_Per48_OPP_EFG_PCT FLOAT,
                    FourFactors_Per48_OPP_FTA_RATE FLOAT,
                    FourFactors_Per48_OPP_TOV_PCT FLOAT,
                    FourFactors_Per48_OPP_OREB_PCT FLOAT,

                    --Per100Possessions
                    FourFactors_Per100Possessions_GP INT,
                    FourFactors_Per100Possessions_W INT,
                    FourFactors_Per100Possessions_L INT,
                    FourFactors_Per100Possessions_W_PCT FLOAT,
                    FourFactors_Per100Possessions_MIN FLOAT,
                    FourFactors_Per100Possessions_EFG_PCT FLOAT,
                    FourFactors_Per100Possessions_FTA_RATE FLOAT,
                    FourFactors_Per100Possessions_TM_TOV_PCT FLOAT,
                    FourFactors_Per100Possessions_OREB_PCT FLOAT,
                    FourFactors_Per100Possessions_OPP_EFG_PCT FLOAT,
                    FourFactors_Per100Possessions_OPP_FTA_RATE FLOAT,
                    FourFactors_Per100Possessions_OPP_TOV_PCT FLOAT,
                    FourFactors_Per100Possessions_OPP_OREB_PCT FLOAT,

                    --
                    -- Scoring
                    --
                    --Totals
                    Scoring_Totals_GP INT,
                    Scoring_Totals_W INT,
                    Scoring_Totals_L INT,
                    Scoring_Totals_W_PCT FLOAT,
                    Scoring_Totals_MIN FLOAT,
                    Scoring_Totals_PCT_FGA_2PT FLOAT,
                    Scoring_Totals_PCT_FGA_3PT FLOAT,
                    Scoring_Totals_PCT_PTS_2PT FLOAT,
                    Scoring_Totals_PCT_PTS_2PT_MR FLOAT,
                    Scoring_Totals_PCT_PTS_3PT FLOAT,
                    Scoring_Totals_PCT_PTS_FB FLOAT,
                    Scoring_Totals_PCT_PTS_FT FLOAT,
                    Scoring_Totals_PCT_PTS_OFF_TOV FLOAT,
                    Scoring_Totals_PCT_PTS_PAINT FLOAT,
                    Scoring_Totals_PCT_AST_2PM FLOAT,
                    Scoring_Totals_PCT_UAST_2PM FLOAT,
                    Scoring_Totals_PCT_AST_3PM FLOAT,
                    Scoring_Totals_PCT_UAST_3PM FLOAT,
                    Scoring_Totals_PCT_AST_FGM FLOAT,
                    Scoring_Totals_PCT_UAST_FGM FLOAT,

                    -- Rankings
                    Scoring_Totals_GP_RANK INT,
                    Scoring_Totals_W_RANK INT,
                    Scoring_Totals_L_RANK INT,
                    Scoring_Totals_W_PCT_RANK INT,
                    Scoring_Totals_MIN_RANK INT,
                    Scoring_Totals_PCT_FGA_2PT_RANK INT,
                    Scoring_Totals_PCT_FGA_3PT_RANK INT,
                    Scoring_Totals_PCT_PTS_2PT_RANK INT,
                    Scoring_Totals_PCT_PTS_2PT_MR_RANK INT,
                    Scoring_Totals_PCT_PTS_3PT_RANK INT,
                    Scoring_Totals_PCT_PTS_FB_RANK INT,
                    Scoring_Totals_PCT_PTS_FT_RANK INT,
                    Scoring_Totals_PCT_PTS_OFF_TOV_RANK INT,
                    Scoring_Totals_PCT_PTS_PAINT_RANK INT,
                    Scoring_Totals_PCT_AST_2PM_RANK INT,
                    Scoring_Totals_PCT_UAST_2PM_RANK INT,
                    Scoring_Totals_PCT_AST_3PM_RANK INT,
                    Scoring_Totals_PCT_UAST_3PM_RANK INT,
                    Scoring_Totals_PCT_AST_FGM_RANK INT,
                    Scoring_Totals_PCT_UAST_FGM_RANK INT,

                    --Per48
                    Scoring_Per48_GP INT,
                    Scoring_Per48_W INT,
                    Scoring_Per48_L INT,
                    Scoring_Per48_W_PCT FLOAT,
                    Scoring_Per48_MIN FLOAT,
                    Scoring_Per48_PCT_FGA_2PT FLOAT,
                    Scoring_Per48_PCT_FGA_3PT FLOAT,
                    Scoring_Per48_PCT_PTS_2PT FLOAT,
                    Scoring_Per48_PCT_PTS_2PT_MR FLOAT,
                    Scoring_Per48_PCT_PTS_3PT FLOAT,
                    Scoring_Per48_PCT_PTS_FB FLOAT,
                    Scoring_Per48_PCT_PTS_FT FLOAT,
                    Scoring_Per48_PCT_PTS_OFF_TOV FLOAT,
                    Scoring_Per48_PCT_PTS_PAINT FLOAT,
                    Scoring_Per48_PCT_AST_2PM FLOAT,
                    Scoring_Per48_PCT_UAST_2PM FLOAT,
                    Scoring_Per48_PCT_AST_3PM FLOAT,
                    Scoring_Per48_PCT_UAST_3PM FLOAT,
                    Scoring_Per48_PCT_AST_FGM FLOAT,
                    Scoring_Per48_PCT_UAST_FGM FLOAT,

                    -- Rankings
                    Scoring_Per48_GP_RANK INT,
                    Scoring_Per48_W_RANK INT,
                    Scoring_Per48_L_RANK INT,
                    Scoring_Per48_W_PCT_RANK INT,
                    Scoring_Per48_MIN_RANK INT,
                    Scoring_Per48_PCT_FGA_2PT_RANK INT,
                    Scoring_Per48_PCT_FGA_3PT_RANK INT,
                    Scoring_Per48_PCT_PTS_2PT_RANK INT,
                    Scoring_Per48_PCT_PTS_2PT_MR_RANK INT,
                    Scoring_Per48_PCT_PTS_3PT_RANK INT,
                    Scoring_Per48_PCT_PTS_FB_RANK INT,
                    Scoring_Per48_PCT_PTS_FT_RANK INT,
                    Scoring_Per48_PCT_PTS_OFF_TOV_RANK INT,
                    Scoring_Per48_PCT_PTS_PAINT_RANK INT,
                    Scoring_Per48_PCT_AST_2PM_RANK INT,
                    Scoring_Per48_PCT_UAST_2PM_RANK INT,
                    Scoring_Per48_PCT_AST_3PM_RANK INT,
                    Scoring_Per48_PCT_UAST_3PM_RANK INT,
                    Scoring_Per48_PCT_AST_FGM_RANK INT,
                    Scoring_Per48_PCT_UAST_FGM_RANK INT,

                    --Per100Possessions
                    Scoring_Per100Possessions_GP INT,
                    Scoring_Per100Possessions_W INT,
                    Scoring_Per100Possessions_L INT,
                    Scoring_Per100Possessions_W_PCT FLOAT,
                    Scoring_Per100Possessions_MIN FLOAT,
                    Scoring_Per100Possessions_PCT_FGA_2PT FLOAT,
                    Scoring_Per100Possessions_PCT_FGA_3PT FLOAT,
                    Scoring_Per100Possessions_PCT_PTS_2PT FLOAT,
                    Scoring_Per100Possessions_PCT_PTS_2PT_MR FLOAT,
                    Scoring_Per100Possessions_PCT_PTS_3PT FLOAT,
                    Scoring_Per100Possessions_PCT_PTS_FB FLOAT,
                    Scoring_Per100Possessions_PCT_PTS_FT FLOAT,
                    Scoring_Per100Possessions_PCT_PTS_OFF_TOV FLOAT,
                    Scoring_Per100Possessions_PCT_PTS_PAINT FLOAT,
                    Scoring_Per100Possessions_PCT_AST_2PM FLOAT,
                    Scoring_Per100Possessions_PCT_UAST_2PM FLOAT,
                    Scoring_Per100Possessions_PCT_AST_3PM FLOAT,
                    Scoring_Per100Possessions_PCT_UAST_3PM FLOAT,
                    Scoring_Per100Possessions_PCT_AST_FGM FLOAT,
                    Scoring_Per100Possessions_PCT_UAST_FGM FLOAT,

                    -- Rankings
                    Scoring_Per100Possessions_GP_RANK INT,
                    Scoring_Per100Possessions_W_RANK INT,
                    Scoring_Per100Possessions_L_RANK INT,
                    Scoring_Per100Possessions_W_PCT_RANK INT,
                    Scoring_Per100Possessions_MIN_RANK INT,
                    Scoring_Per100Possessions_PCT_FGA_2PT_RANK INT,
                    Scoring_Per100Possessions_PCT_FGA_3PT_RANK INT,
                    Scoring_Per100Possessions_PCT_PTS_2PT_RANK INT,
                    Scoring_Per100Possessions_PCT_PTS_2PT_MR_RANK INT,
                    Scoring_Per100Possessions_PCT_PTS_3PT_RANK INT,
                    Scoring_Per100Possessions_PCT_PTS_FB_RANK INT,
                    Scoring_Per100Possessions_PCT_PTS_FT_RANK INT,
                    Scoring_Per100Possessions_PCT_PTS_OFF_TOV_RANK INT,
                    Scoring_Per100Possessions_PCT_PTS_PAINT_RANK INT,
                    Scoring_Per100Possessions_PCT_AST_2PM_RANK INT,
                    Scoring_Per100Possessions_PCT_UAST_2PM_RANK INT,
                    Scoring_Per100Possessions_PCT_AST_3PM_RANK INT,
                    Scoring_Per100Possessions_PCT_UAST_3PM_RANK INT,
                    Scoring_Per100Possessions_PCT_AST_FGM_RANK INT,
                    Scoring_Per100Possessions_PCT_UAST_FGM_RANK INT,

                    
                    --
                    -- Opponent
                    --
                    --Totals

                    Opponent_Totals_GP INT,
                    Opponent_Totals_W INT,
                    Opponent_Totals_L INT,
                    Opponent_Totals_W_PCT FLOAT,
                    Opponent_Totals_MIN FLOAT,
                    Opponent_Totals_OPP_FGM INT,
                    Opponent_Totals_OPP_FGA INT,
                    Opponent_Totals_OPP_FG_PCT FLOAT,
                    Opponent_Totals_OPP_FG3M INT,
                    Opponent_Totals_OPP_FG3A INT,
                    Opponent_Totals_OPP_FG3_PCT FLOAT,
                    Opponent_Totals_OPP_FTM INT,
                    Opponent_Totals_OPP_FTA INT,
                    Opponent_Totals_OPP_FT_PCT FLOAT,
                    Opponent_Totals_OPP_OREB INT,
                    Opponent_Totals_OPP_DREB INT,
                    Opponent_Totals_OPP_REB INT,
                    Opponent_Totals_OPP_AST INT,
                    Opponent_Totals_OPP_TOV INT,
                    Opponent_Totals_OPP_STL INT,
                    Opponent_Totals_OPP_BLK INT,
                    Opponent_Totals_OPP_BLKA INT,
                    Opponent_Totals_OPP_PF INT,
                    Opponent_Totals_OPP_PFD INT,
                    Opponent_Totals_OPP_PTS INT,
                    Opponent_Totals_PLUS_MINUS FLOAT,

                    -- Rankings
                    Opponent_Totals_GP_RANK INT,
                    Opponent_Totals_W_RANK INT,
                    Opponent_Totals_L_RANK INT,
                    Opponent_Totals_W_PCT_RANK INT,
                    Opponent_Totals_MIN_RANK INT,
                    Opponent_Totals_OPP_FGM_RANK INT,
                    Opponent_Totals_OPP_FGA_RANK INT,
                    Opponent_Totals_OPP_FG_PCT_RANK INT,
                    Opponent_Totals_OPP_FG3M_RANK INT,
                    Opponent_Totals_OPP_FG3A_RANK INT,
                    Opponent_Totals_OPP_FG3_PCT_RANK INT,
                    Opponent_Totals_OPP_FTM_RANK INT,
                    Opponent_Totals_OPP_FTA_RANK INT,
                    Opponent_Totals_OPP_FT_PCT_RANK INT,
                    Opponent_Totals_OPP_OREB_RANK INT,
                    Opponent_Totals_OPP_DREB_RANK INT,
                    Opponent_Totals_OPP_REB_RANK INT,
                    Opponent_Totals_OPP_AST_RANK INT,
                    Opponent_Totals_OPP_TOV_RANK INT,
                    Opponent_Totals_OPP_STL_RANK INT,
                    Opponent_Totals_OPP_BLK_RANK INT,
                    Opponent_Totals_OPP_BLKA_RANK INT,
                    Opponent_Totals_OPP_PF_RANK INT,
                    Opponent_Totals_OPP_PFD_RANK INT,
                    Opponent_Totals_OPP_PFD1 INT,
                    Opponent_Totals_OPP_PTS_RANK INT,
                    Opponent_Totals_PLUS_MINUS_RANK INT,

                    --Per48
                    Opponent_Per48_GP INT,
                    Opponent_Per48_W INT,
                    Opponent_Per48_L INT,
                    Opponent_Per48_W_PCT FLOAT,
                    Opponent_Per48_MIN FLOAT,
                    Opponent_Per48_OPP_FGM INT,
                    Opponent_Per48_OPP_FGA INT,
                    Opponent_Per48_OPP_FG_PCT FLOAT,
                    Opponent_Per48_OPP_FG3M INT,
                    Opponent_Per48_OPP_FG3A INT,
                    Opponent_Per48_OPP_FG3_PCT FLOAT,
                    Opponent_Per48_OPP_FTM INT,
                    Opponent_Per48_OPP_FTA INT,
                    Opponent_Per48_OPP_FT_PCT FLOAT,
                    Opponent_Per48_OPP_OREB INT,
                    Opponent_Per48_OPP_DREB INT,
                    Opponent_Per48_OPP_REB INT,
                    Opponent_Per48_OPP_AST INT,
                    Opponent_Per48_OPP_TOV INT,
                    Opponent_Per48_OPP_STL INT, 
                    Opponent_Per48_OPP_BLK INT,
                    Opponent_Per48_OPP_BLKA INT,
                    Opponent_Per48_OPP_PF INT,
                    Opponent_Per48_OPP_PFD INT, 
                    Opponent_Per48_OPP_PTS INT, 
                    Opponent_Per48_PLUS_MINUS FLOAT,

                    -- Rankings
                    Opponent_Per48_GP_RANK INT,
                    Opponent_Per48_W_RANK INT,
                    Opponent_Per48_L_RANK INT,
                    Opponent_Per48_W_PCT_RANK INT,
                    Opponent_Per48_MIN_RANK INT,    
                    Opponent_Per48_OPP_FGM_RANK INT,
                    Opponent_Per48_OPP_FGA_RANK INT,
                    Opponent_Per48_OPP_FG_PCT_RANK INT,
                    Opponent_Per48_OPP_FG3M_RANK INT,
                    Opponent_Per48_OPP_FG3A_RANK INT,
                    Opponent_Per48_OPP_FG3_PCT_RANK INT,
                    Opponent_Per48_OPP_FTM_RANK INT,
                    Opponent_Per48_OPP_FTA_RANK INT,
                    Opponent_Per48_OPP_FT_PCT_RANK INT,
                    Opponent_Per48_OPP_OREB_RANK INT,
                    Opponent_Per48_OPP_DREB_RANK INT,
                    Opponent_Per48_OPP_REB_RANK INT,
                    Opponent_Per48_OPP_AST_RANK INT,
                    Opponent_Per48_OPP_TOV_RANK INT,
                    Opponent_Per48_OPP_STL_RANK INT,
                    Opponent_Per48_OPP_BLK_RANK INT,
                    Opponent_Per48_OPP_BLKA_RANK INT,
                    Opponent_Per48_OPP_PF_RANK INT,
                    Opponent_Per48_OPP_PFD_RANK INT,
                    Opponent_Per48_OPP_PFD1 INT,
                    Opponent_Per48_OPP_PTS_RANK INT,
                    Opponent_Per48_PLUS_MINUS_RANK INT, 

                    --Per100Possessions
                    Opponent_Per100Possessions_GP INT,
                    Opponent_Per100Possessions_W INT,
                    Opponent_Per100Possessions_L INT,
                    Opponent_Per100Possessions_W_PCT FLOAT,
                    Opponent_Per100Possessions_MIN FLOAT,
                    Opponent_Per100Possessions_OPP_FGM INT,
                    Opponent_Per100Possessions_OPP_FGA INT,
                    Opponent_Per100Possessions_OPP_FG_PCT FLOAT,
                    Opponent_Per100Possessions_OPP_FG3M INT,
                    Opponent_Per100Possessions_OPP_FG3A INT,
                    Opponent_Per100Possessions_OPP_FG3_PCT FLOAT,
                    Opponent_Per100Possessions_OPP_FTM INT,
                    Opponent_Per100Possessions_OPP_FTA INT,
                    Opponent_Per100Possessions_OPP_FT_PCT FLOAT,
                    Opponent_Per100Possessions_OPP_OREB INT,
                    Opponent_Per100Possessions_OPP_DREB INT,
                    Opponent_Per100Possessions_OPP_REB INT,
                    Opponent_Per100Possessions_OPP_AST INT,
                    Opponent_Per100Possessions_OPP_TOV INT,
                    Opponent_Per100Possessions_OPP_STL INT,
                    Opponent_Per100Possessions_OPP_BLK INT,
                    Opponent_Per100Possessions_OPP_BLKA INT,
                    Opponent_Per100Possessions_OPP_PF INT,
                    Opponent_Per100Possessions_OPP_PFD INT,
                    Opponent_Per100Possessions_OPP_PTS INT,
                    Opponent_Per100Possessions_PLUS_MINUS FLOAT,
                    
                    -- Rankings
                    Opponent_Per100Possessions_GP_RANK INT,
                    Opponent_Per100Possessions_W_RANK INT,
                    Opponent_Per100Possessions_L_RANK INT,
                    Opponent_Per100Possessions_W_PCT_RANK INT,
                    Opponent_Per100Possessions_MIN_RANK INT,
                    Opponent_Per100Possessions_OPP_FGM_RANK INT,
                    Opponent_Per100Possessions_OPP_FGA_RANK INT,
                    Opponent_Per100Possessions_OPP_FG_PCT_RANK INT,
                    Opponent_Per100Possessions_OPP_FG3M_RANK INT,
                    Opponent_Per100Possessions_OPP_FG3A_RANK INT,
                    Opponent_Per100Possessions_OPP_FG3_PCT_RANK INT,
                    Opponent_Per100Possessions_OPP_FTM_RANK INT,
                    Opponent_Per100Possessions_OPP_FTA_RANK INT,
                    Opponent_Per100Possessions_OPP_FT_PCT_RANK INT,
                    Opponent_Per100Possessions_OPP_OREB_RANK INT,
                    Opponent_Per100Possessions_OPP_DREB_RANK INT,
                    Opponent_Per100Possessions_OPP_REB_RANK INT,
                    Opponent_Per100Possessions_OPP_AST_RANK INT,
                    Opponent_Per100Possessions_OPP_TOV_RANK INT,
                    Opponent_Per100Possessions_OPP_STL_RANK INT,
                    Opponent_Per100Possessions_OPP_BLK_RANK INT,
                    Opponent_Per100Possessions_OPP_BLKA_RANK INT,
                    Opponent_Per100Possessions_OPP_PF_RANK INT,
                    Opponent_Per100Possessions_OPP_PFD_RANK INT,
                    Opponent_Per100Possessions_OPP_PFD1 INT,
                    Opponent_Per100Possessions_OPP_PTS_RANK INT,
                    Opponent_Per100Possessions_PLUS_MINUS_RANK INT,


                    --
                    -- Defense
                    --
                    --Totals
                    Defense_Totals_GP INT,
                    Defense_Totals_W INT,
                    Defense_Totals_L INT,
                    Defense_Totals_W_PCT FLOAT,
                    Defense_Totals_MIN FLOAT,
                    Defense_Totals_DEF_RATING FLOAT,
                    Defense_Totals_DREB INT,
                    Defense_Totals_DREB_PCT FLOAT,
                    Defense_Totals_STL INT,
                    Defense_Totals_BLK INT,
                    Defense_Totals_OPP_PTS_OFF_TOV INT,
                    Defense_Totals_OPP_PTS_2ND_CHANCE INT,
                    Defense_Totals_OPP_PTS_FB INT,
                    Defense_Totals_OPP_PTS_PAINT INT,

                    -- Rankings
                    Defense_Totals_GP_RANK INT,
                    Defense_Totals_W_RANK INT,
                    Defense_Totals_L_RANK INT,
                    Defense_Totals_W_PCT_RANK INT,
                    Defense_Totals_MIN_RANK INT,
                    Defense_Totals_DEF_RATING_RANK INT,
                    Defense_Totals_DREB_RANK INT,
                    Defense_Totals_DREB_PCT_RANK INT,
                    Defense_Totals_STL_RANK INT,
                    Defense_Totals_BLK_RANK INT,
                    Defense_Totals_OPP_PTS_OFF_TOV_RANK INT,
                    Defense_Totals_OPP_PTS_2ND_CHANCE_RANK INT,
                    Defense_Totals_OPP_PTS_FB_RANK INT,
                    Defense_Totals_OPP_PTS_PAINT_RANK INT,

                    --Per48
                    Defense_Per48_GP INT,
                    Defense_Per48_W INT,
                    Defense_Per48_L INT,
                    Defense_Per48_W_PCT FLOAT,
                    Defense_Per48_MIN FLOAT,
                    Defense_Per48_DEF_RATING FLOAT,
                    Defense_Per48_DREB INT,
                    Defense_Per48_DREB_PCT FLOAT,
                    Defense_Per48_STL INT,
                    Defense_Per48_BLK INT,
                    Defense_Per48_OPP_PTS_OFF_TOV INT,
                    Defense_Per48_OPP_PTS_2ND_CHANCE INT,
                    Defense_Per48_OPP_PTS_FB INT,
                    Defense_Per48_OPP_PTS_PAINT INT,

                    -- Rankings
                    Defense_Per48_GP_RANK INT,
                    Defense_Per48_W_RANK INT,
                    Defense_Per48_L_RANK INT,
                    Defense_Per48_W_PCT_RANK INT,
                    Defense_Per48_MIN_RANK INT,
                    Defense_Per48_DEF_RATING_RANK INT,
                    Defense_Per48_DREB_RANK INT,
                    Defense_Per48_DREB_PCT_RANK INT,
                    Defense_Per48_STL_RANK INT,
                    Defense_Per48_BLK_RANK INT,
                    Defense_Per48_OPP_PTS_OFF_TOV_RANK INT,
                    Defense_Per48_OPP_PTS_2ND_CHANCE_RANK INT,
                    Defense_Per48_OPP_PTS_FB_RANK INT,
                    Defense_Per48_OPP_PTS_PAINT_RANK INT,

                    --Per100Possessions
                    Defense_Per100Possessions_GP INT,
                    Defense_Per100Possessions_W INT,
                    Defense_Per100Possessions_L INT,
                    Defense_Per100Possessions_W_PCT FLOAT,
                    Defense_Per100Possessions_MIN FLOAT,
                    Defense_Per100Possessions_DEF_RATING FLOAT,
                    Defense_Per100Possessions_DREB INT,
                    Defense_Per100Possessions_DREB_PCT FLOAT,
                    Defense_Per100Possessions_STL INT,
                    Defense_Per100Possessions_BLK INT,
                    Defense_Per100Possessions_OPP_PTS_OFF_TOV INT,
                    Defense_Per100Possessions_OPP_PTS_2ND_CHANCE INT,
                    Defense_Per100Possessions_OPP_PTS_FB INT,
                    Defense_Per100Possessions_OPP_PTS_PAINT INT,

                    -- Rankings
                    Defense_Per100Possessions_GP_RANK INT,
                    Defense_Per100Possessions_W_RANK INT,
                    Defense_Per100Possessions_L_RANK INT,
                    Defense_Per100Possessions_W_PCT_RANK INT,
                    Defense_Per100Possessions_MIN_RANK INT,
                    Defense_Per100Possessions_DEF_RATING_RANK INT,
                    Defense_Per100Possessions_DREB_RANK INT,
                    Defense_Per100Possessions_DREB_PCT_RANK INT,
                    Defense_Per100Possessions_STL_RANK INT,
                    Defense_Per100Possessions_BLK_RANK INT,
                    Defense_Per100Possessions_OPP_PTS_OFF_TOV_RANK INT,
                    Defense_Per100Possessions_OPP_PTS_2ND_CHANCE_RANK INT,
                    Defense_Per100Possessions_OPP_PTS_FB_RANK INT,
                    Defense_Per100Possessions_OPP_PTS_PAINT_RANK INT,


                    PRIMARY KEY (team_id, season, season_type)
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_league_dash_team_stats_team_id ON league_dash_team_stats(team_id);
                CREATE INDEX IF NOT EXISTS idx_league_dash_team_stats_season ON league_dash_team_stats(season);
                CREATE INDEX IF NOT EXISTS idx_league_dash_team_stats_season_type ON league_dash_team_stats(season_type);
            """
            )

    @classmethod
    def add_team_season_stat(cls, team_stats):
        """
        Insert or update team season statistics in the database.

        Parameters:
            team_stats (dict): Dictionary containing team season statistics.
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            try:
                # ✅ Convert column names to lowercase to match PostgreSQL behavior
                columns = [col.lower() for col in team_stats.keys()]
                values = tuple(team_stats[col] if col in team_stats else None for col in team_stats.keys())

                # ✅ Ensure there's at least one column to update in `ON CONFLICT`
                updatable_columns = [col for col in columns if col not in ["team_id", "season", "season_type"]]
                if not updatable_columns:
                    logging.error(f" No valid columns to update for Team ID {team_stats.get('team_id', 'UNKNOWN')}.")
                    return

                # ✅ Format column names for SQL
                column_str = ", ".join(columns)  # No double quotes to avoid case sensitivity issues
                value_placeholders = ", ".join(["%s"] * len(values))

                # ✅ Format update statement
                update_str = ", ".join([f"{col} = EXCLUDED.{col}" for col in updatable_columns])

                # ✅ Dynamically build the SQL query
                sql = f"""
                    INSERT INTO league_dash_team_stats ({column_str})
                    VALUES ({value_placeholders})
                    ON CONFLICT (team_id, season, season_type) DO UPDATE SET
                    {update_str}
                    RETURNING team_id;
                """

                # ✅ Debug: Log full SQL query for troubleshooting
                logging.debug(f"SQL Query:\n{sql}")

                # ✅ Execute query with properly formatted values
                cur.execute(sql, values)
                return cur.fetchone() is not None

            except Exception as e:
                logging.error(f" Error inserting data for Team ID {team_stats.get('team_id', 'UNKNOWN')}: {e}")
                logging.debug(f"Full Query Attempted:\n{sql}")

    @classmethod
    def get_team_stats(cls, season, per_mode):
        """
        Fetch key Base measure type ranking stats for team comparison.

        Args:
            season (str): The season (e.g., "2023-24").
            per_mode (str): The PerMode type (Totals, Per48, Per100Possessions).

        Returns:
            list: List of team statistics dictionaries.
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            try:
                # Validate and normalize per_mode
                valid_per_modes = ["totals", "per48", "per100possessions"]
                per_mode_lower = per_mode.lower().replace(" ", "")
                
                if per_mode_lower not in valid_per_modes:
                    logging.warning(f"Invalid per_mode: {per_mode}. Using 'totals' instead.")
                    per_mode_lower = "totals"

                query = f"""
                    SELECT team_id, team_name, season, season_type,
                        base_{per_mode_lower}_w_pct_rank, base_{per_mode_lower}_fgm_rank, base_{per_mode_lower}_fg3m_rank, 
                        base_{per_mode_lower}_oreb_rank, base_{per_mode_lower}_reb_rank, base_{per_mode_lower}_ast_rank,
                        base_{per_mode_lower}_tov_rank, base_{per_mode_lower}_stl_rank, base_{per_mode_lower}_blk_rank,
                        base_{per_mode_lower}_plus_minus_rank, base_{per_mode_lower}_pts_rank
                    FROM league_dash_team_stats
                    WHERE season = %s
                    ORDER BY base_{per_mode_lower}_w_pct_rank ASC;
                """
                cur.execute(query, (season,))
                columns = [desc[0] for desc in cur.description]
                results = [dict(zip(columns, row)) for row in cur.fetchall()]

                # ✅ Debugging: Log what we're actually getting
                logging.debug(f"Fetched team stats: {results}")

                return results
            finally:
                cur.close()

    @classmethod
    def get_team_stats_by_id(cls, team_id, season="2024-25", per_mode="Totals"):
        """
        Fetch team statistics for a specific team.
        
        Args:
            team_id (int): The ID of the team.
            season (str): The season (e.g., "2024-25").
            per_mode (str): The PerMode type (Totals, Per48, Per100Possessions).
            
        Returns:
            dict: Team statistics or None if not found.
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            try:
                # Validate and normalize per_mode
                valid_per_modes = ["totals", "per48", "per100possessions"]
                per_mode_lower = per_mode.lower().replace(" ", "")
                
                if per_mode_lower not in valid_per_modes:
                    logging.warning(f"Invalid per_mode: {per_mode}. Using 'totals' instead.")
                    per_mode_lower = "totals"
                
                # Query for the specific team's stats
                query = f"""
                    SELECT 
                        team_id, team_name, season, season_type,
                        base_{per_mode_lower}_gp, base_{per_mode_lower}_w, base_{per_mode_lower}_l, base_{per_mode_lower}_w_pct,
                        base_{per_mode_lower}_fgm, base_{per_mode_lower}_fga, base_{per_mode_lower}_fg_pct,
                        base_{per_mode_lower}_fg3m, base_{per_mode_lower}_fg3a, base_{per_mode_lower}_fg3_pct,
                        base_{per_mode_lower}_ftm, base_{per_mode_lower}_fta, base_{per_mode_lower}_ft_pct,
                        base_{per_mode_lower}_oreb, base_{per_mode_lower}_dreb, base_{per_mode_lower}_reb,
                        base_{per_mode_lower}_ast, base_{per_mode_lower}_tov, base_{per_mode_lower}_stl,
                        base_{per_mode_lower}_blk, base_{per_mode_lower}_pf, base_{per_mode_lower}_pts,
                        base_{per_mode_lower}_plus_minus,
                        advanced_{per_mode_lower}_off_rating, advanced_{per_mode_lower}_def_rating,
                        advanced_{per_mode_lower}_net_rating, advanced_{per_mode_lower}_pace,
                        advanced_{per_mode_lower}_ts_pct
                    FROM league_dash_team_stats
                    WHERE team_id = %s AND season = %s
                """
                cur.execute(query, (team_id, season))
                row = cur.fetchone()
                
                if not row:
                    print("No row found")
                    return None
                
                # Convert to dictionary with column names
                columns = [desc[0] for desc in cur.description]
                stats = dict(zip(columns, row))
                
                # Simplify the keys by removing the per_mode prefix for easier access
                simplified_stats = {
                    "team_id": stats["team_id"],
                    "team_name": stats["team_name"],
                    "season": stats["season"],
                    "season_type": stats["season_type"],
                    "gp": stats[f"base_{per_mode_lower}_gp"],
                    "w": stats[f"base_{per_mode_lower}_w"],
                    "l": stats[f"base_{per_mode_lower}_l"],
                    "w_pct": stats[f"base_{per_mode_lower}_w_pct"],
                    "fgm": stats[f"base_{per_mode_lower}_fgm"],
                    "fga": stats[f"base_{per_mode_lower}_fga"],
                    "fg_pct": stats[f"base_{per_mode_lower}_fg_pct"],
                    "fg3m": stats[f"base_{per_mode_lower}_fg3m"],
                    "fg3a": stats[f"base_{per_mode_lower}_fg3a"],
                    "fg3_pct": stats[f"base_{per_mode_lower}_fg3_pct"],
                    "ftm": stats[f"base_{per_mode_lower}_ftm"],
                    "fta": stats[f"base_{per_mode_lower}_fta"],
                    "ft_pct": stats[f"base_{per_mode_lower}_ft_pct"],
                    "oreb": stats[f"base_{per_mode_lower}_oreb"],
                    "dreb": stats[f"base_{per_mode_lower}_dreb"],
                    "reb": stats[f"base_{per_mode_lower}_reb"],
                    "ast": stats[f"base_{per_mode_lower}_ast"],
                    "tov": stats[f"base_{per_mode_lower}_tov"],
                    "stl": stats[f"base_{per_mode_lower}_stl"],
                    "blk": stats[f"base_{per_mode_lower}_blk"],
                    "pf": stats[f"base_{per_mode_lower}_pf"],
                    "pts": stats[f"base_{per_mode_lower}_pts"],
                    "plus_minus": stats[f"base_{per_mode_lower}_plus_minus"],
                    "off_rtg": stats[f"advanced_{per_mode_lower}_off_rating"],
                    "def_rtg": stats[f"advanced_{per_mode_lower}_def_rating"],
                    "net_rtg": stats[f"advanced_{per_mode_lower}_net_rating"],
                    "pace": stats[f"advanced_{per_mode_lower}_pace"],
                    "ts_pct": stats[f"advanced_{per_mode_lower}_ts_pct"]
                }
                print(simplified_stats)
                return simplified_stats
            except Exception as e:
                logging.error(f"Error fetching team stats for team ID {team_id}: {e}")
                return None
            finally:
                cur.close()



