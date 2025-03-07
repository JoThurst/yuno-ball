from db_config import get_connection, release_connection
import logging

class LeagueDashTeamStats:
    """
    Stores NBA team statistics across all measure types, per modes, and season types.
    Column names are prefixed with MeasureType & PerMode for clarity.
    """

    @classmethod
    def create_table(cls):
        """Create the `league_dash_team_stats` table to store BASE Totals data first."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS league_dash_team_stats (
                    team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    team_name VARCHAR(50) NOT NULL,
                    season VARCHAR(10) NOT NULL,
                    season_type VARCHAR(15) NOT NULL CHECK (season_type IN ('Regular Season', 'Playoffs')),
                    
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

                    PRIMARY KEY (team_id, season, season_type)
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def add_team_season_stat(cls, team_stats):
        """
        Insert or update team season statistics in the database.

        Parameters:
            team_stats (dict): Dictionary containing team season statistics.
        """
        conn = get_connection()
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
                {update_str};
            """

            # ✅ Debug: Log full SQL query for troubleshooting
            logging.debug(f"SQL Query:\n{sql}")

            # ✅ Execute query with properly formatted values
            cur.execute(sql, values)
            conn.commit()

        except Exception as e:
            logging.error(f" Error inserting data for Team ID {team_stats.get('team_id', 'UNKNOWN')}: {e}")
            logging.debug(f"Full Query Attempted:\n{sql}")

        finally:
            cur.close()
            release_connection(conn)

