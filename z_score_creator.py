"""
NBA Player Statistics Z-Score Calculator
This module provides functionality to calculate and store Z-scores for NBA player statistics in a
PostgreSQL database.
Retrieves raw player statistics, calculates Z-scores using R statistical computations,
and stores the results in a dedicated database table.
Module uses connection pooling for database access and R integration via rpy2.
Key Components:
    - Database connection pool management
    - R statistical integration for normal distribution fitting
    - Z-score calculation for various player statistics
    - PostgreSQL database operations for data storage
Dependencies:
    - pandas: For data manipulation
    - psycopg2: For PostgreSQL database interactions
    - rpy2: For R statistical computations
    - os: For environment variable handling
Environment Requirements:
    - R installation (R 4.4.2)
    - PostgreSQL database
    - DATABASE_URL environment variable (or defaults to local connection)
    Requires appropriate database credentials and R installation with MASS package.
"""

import os

import pandas as pd
import psycopg2
from psycopg2 import extras, pool

os.environ["R_HOME"] = r"C:\Program Files\R\R-4.4.2"
from nba_api.stats.endpoints import leaguedashplayerstats  # Type: ignore
from rpy2 import robjects  # type: ignore
from rpy2.robjects import r  # type: ignore

from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from db_config import get_connection, release_connection

DATABASE_URL: str = os.getenv(
    key="DATABASE_URL",
    default="postgresql://basketball_owner:SZ13ILuWpXhQ@ep-twilight-snowflake-a518cxn2-pooler.us-east-2.aws.neon.tech/basketball?sslmode=require",
)

# Initialize the connections pool globally
connection_pool = pool.SimpleConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)

if connection_pool:
    print("Connection pool created successfully")


def populate_z_scores() -> None:
    """Populates z-scores for NBA player statistics and inserts/updates them in the 'player_z_scores' database table.
    This function performs the following steps:
    1. Retrieves player statistics for the season "2024-25" using the LeagueDashPlayerStats API.
    2. Filters and selects relevant columns: "PLAYER_ID", "PTS", "REB", "AST", "STL", "BLK", "TOV", "FG3M", "DD2", "FG_PCT", "FT_PCT", "FG3_PCT".
    3. Renames the DataFrame columns to lowercase.
    4. For each statistical column (excluding "player_id"):
        - Converts the column data to an R vector.
        - Loads the MASS package in R.
        - Fits a normal distribution to the data using R's 'fitdistr' function.
        - Extracts the estimated mean and standard deviation.
        - Computes the z-score for each entry in the column.
        - Appends a new column with the z-scores, naming it with the suffix "_z_score".
    5. Filters the DataFrame to retain only "player_id" and the computed z-score columns.
    6. Prepares an SQL INSERT query with an ON CONFLICT clause to update existing records.
    7. Executes the query to insert or update the z-scores in the database.
    8. Commits the transaction and properly closes the database connection.
    Returns: None
    """
    df = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2024-25"
    ).get_data_frames()[0]

    df = df[
        [
            "PLAYER_ID",
            "PTS",
            "REB",
            "AST",
            "STL",
            "BLK",
            "TOV",
            "FG3M",
            "DD2",
            "FG_PCT",
            "FT_PCT",
            "FG3_PCT",
        ]
    ]
    df.columns = df.columns.str.lower()
    updated_df = df
    for column in df.columns:
        if column != "player_id":
            x = robjects.FloatVector(df[column].tolist())
            robjects.r.assign("x", x)
            # Load the MASS package (if not already loaded)
            r(string="library(MASS)")
            # Fit a normal distribution
            fit_norm = r(string='fitdistr(x, "normal")')
            # Extract the 'estimate' element (a named vector with 'mean' and 'sd')
            estimates = fit_norm.rx2("estimate")
            estimates_dict: dict[str, float] = {
                str(object=name): float(val)
                for name, val in zip(["mean", "sd"], list(estimates))
            }
            z_score_col = f"{column}_z_score"
            updated_df[z_score_col] = (
                df[column].astype(float) - estimates_dict["mean"]
            ) / estimates_dict["sd"]
    updated_df_filtered = updated_df[
        [
            "player_id",
            "pts_z_score",
            "reb_z_score",
            "ast_z_score",
            "stl_z_score",
            "blk_z_score",
            "tov_z_score",
            "fg3m_z_score",
            "dd2_z_score",
            "fg_pct_z_score",
            "ft_pct_z_score",
            "fg3_pct_z_score",
        ]
    ]
    insert_query = """
    INSERT INTO player_z_scores (
    player_id, pts_z_score, reb_z_score, ast_z_score, stl_z_score,
    blk_z_score, tov_z_score, fg3m_z_score, dd2_z_score, fg_pct_z_score,
    ft_pct_z_score, fg3_pct_z_score
) VALUES %s
ON CONFLICT (player_id) DO UPDATE SET
    pts_z_score = EXCLUDED.pts_z_score,
    reb_z_score = EXCLUDED.reb_z_score,
    ast_z_score = EXCLUDED.ast_z_score,
    stl_z_score = EXCLUDED.stl_z_score,
    blk_z_score = EXCLUDED.blk_z_score,
    tov_z_score = EXCLUDED.tov_z_score,
    fg3m_z_score = EXCLUDED.fg3m_z_score,
    dd2_z_score = EXCLUDED.dd2_z_score,
    fg_pct_z_score = EXCLUDED.fg_pct_z_score,
    ft_pct_z_score = EXCLUDED.ft_pct_z_score,
    fg3_pct_z_score = EXCLUDED.fg3_pct_z_score
"""

    # Convert DataFrame rows to a list of tuples.
    rows = list(updated_df_filtered.itertuples(index=False, name=None))
    try:
        conn = get_connection()
        cur = conn.cursor()
        extras.execute_values(cur=cur, sql=insert_query, argslist=rows)
        conn.commit()
    finally:
        cur.close()
        release_connection(conn=conn)


if __name__ == "__main__":
    populate_z_scores()
