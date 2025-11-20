"""
NBA Player Statistics Z-Score Calculator (SQLAlchemy Edition)

This module provides functionality to calculate and store Z-scores for NBA player 
statistics using SQLAlchemy ORM.

Retrieves raw player statistics, calculates Z-scores using R statistical computations,
and stores the results using SQLAlchemy ORM models.

Key Components:
    - SQLAlchemy ORM for database operations
    - R statistical integration for normal distribution fitting
    - Z-score calculation for various player statistics
    - Modern database operations via PlayerZScoresORM model

Dependencies:
    - pandas: For data manipulation
    - SQLAlchemy: For ORM database interactions
    - rpy2: For R statistical computations
    - os: For environment variable handling

Environment Requirements:
    - R installation (R 4.4.2)
    - PostgreSQL database
    - DATABASE_URL environment variable
    - Requires R installation with MASS package

Author: Refactored for SQLAlchemy Migration
Date: 2025-11-20
"""

import os
os.environ["R_HOME"] = r"C:\Program Files\R\R-4.4.2"

from nba_api.stats.endpoints import leaguedashplayerstats  # type: ignore
from rpy2 import robjects  # type: ignore
from rpy2.robjects import r  # type: ignore

# SQLAlchemy imports
from app.database import get_db_context
from app.models.player_z_scores_sqlalchemy import PlayerZScoresORM


def populate_z_scores(season: str = "2024-25") -> int:
    """
    Calculate and populate Z-scores for NBA player statistics using SQLAlchemy ORM.
    
    This function performs the following steps:
    1. Retrieves player statistics for the specified season using the NBA API
    2. Filters relevant statistical columns (PTS, REB, AST, STL, BLK, TOV, FG3M, DD2, FG_PCT, FT_PCT, FG3_PCT)
    3. For each statistical column:
        - Fits a normal distribution using R's fitdistr function
        - Calculates Z-scores based on the fitted distribution
        - Z-score = (value - mean) / standard_deviation
    4. Stores/updates the Z-scores in the database using PlayerZScoresORM.bulk_upsert()
    
    Args:
        season: NBA season string (e.g., "2024-25")
    
    Returns:
        int: Number of player Z-score records processed
        
    Raises:
        Exception: If R integration fails or database operations fail
    """
    print(f"Fetching player statistics for season {season}...")
    
    # Fetch player statistics from NBA API
    df = leaguedashplayerstats.LeagueDashPlayerStats(season=season).get_data_frames()[0]
    
    # Select relevant columns
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
    
    # Convert column names to lowercase
    df.columns = df.columns.str.lower()
    print(f"Processing {len(df)} players...")
    
    # Calculate Z-scores for each stat column
    updated_df = df.copy()
    
    for column in df.columns:
        if column != "player_id":
            print(f"  Calculating Z-scores for {column.upper()}...")
            
            # Convert column to R vector
            x = robjects.FloatVector(df[column].tolist())
            robjects.r.assign("x", x)
            
            # Load MASS package and fit normal distribution
            r(string="library(MASS)")
            fit_norm = r(string='fitdistr(x, "normal")')
            
            # Extract mean and standard deviation
            estimates = fit_norm.rx2("estimate")
            estimates_dict: dict[str, float] = {
                str(name): float(val)
                for name, val in zip(["mean", "sd"], list(estimates))
            }
            
            # Calculate Z-scores: (value - mean) / sd
            z_score_col: str = f"{column}_z_score"
            updated_df[z_score_col] = (
                df[column].astype(float) - estimates_dict["mean"]
            ) / estimates_dict["sd"]
    
    # Filter to keep only player_id and z_score columns
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
    
    # Convert DataFrame to list of dictionaries for bulk upsert
    z_scores_list = updated_df_filtered.to_dict('records')
    
    # Use SQLAlchemy ORM to insert/update Z-scores
    print(f"\nStoring Z-scores in database using SQLAlchemy ORM...")
    
    with get_db_context() as db:
        count = PlayerZScoresORM.bulk_upsert(db, z_scores_list)
        db.commit()
        print(f"[OK] Successfully processed {count} player Z-score records")
    
    return count


if __name__ == "__main__":
    populate_z_scores()