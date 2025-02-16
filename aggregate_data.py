"""This function performs the following steps:
1. Retrieves player statistics from the 'leaguedashplayerstats' table for the 2024-25 season
2. Calculates per-game averages for various statistics
3. Creates a pandas DataFrame from the retrieved data
4. For each statistic (excluding 'player_id'), fits a normal distribution and calculates Z-scores
5. Creates a new table 'player_z_scores' in the database with the calculated Z-scores
6. Inserts the Z-scores into the new table
The function uses R via the `rpy2` library to fit normal distributions and calculate Z-scores.
The following statistics are processed:
- Points per game (pts)
- Rebounds per game (reb)
- Assists per game (ast)
- Steals per game (stl)
- Blocks per game (blk)
- Turnovers per game (tov)
- 3-pointers made per game (fg3m)
- Double-doubles per game (dd2)
- Field goal percentage (fg_pct)
- Free throw percentage (ft_pct)
- 3-point percentage (fg3_pct)
    - Assumes that a connection pool is available via `get_connection` and `release_connection`
    - The function uses the `psycopg2` library to interact with the PostgreSQL database
    - Requires R to be installed with the MASS package available

Returns:
    None
    Exception: If any database operation fails or if R environment is not properly configured
"""

import os
from typing import LiteralString
import pandas as pd
from pandas import DataFrame
import psycopg2
from rpy2 import robjects
from rpy2.robjects import r
from db_config import get_connection, release_connection


def populate_z_scores():
    """Populate Z-scores for player statistics and store them in a PostgreSQL database.
    Retrieves player statistics from the 'leaguedashplayerstats' table for the 2024-25 season,
    calculates Z-scores for each statistic, and stores the results in a new table 'player_z_scores'.
    The steps are as follows:
    1. Retrieve player statistics from the database.
    2. Calculate per-game averages for various statistics.
    3. Create a pandas DataFrame from the retrieved data.
    4. For each statistic (excluding 'player_id'), fit a normal distribution and calculate Z-scores.
    5. Create a new table 'player_z_scores' in the database with the calculated Z-scores.
    6. Insert the Z-scores into the new table.
    The function uses R  via the `rpy2` library to fit normal distributions and calculate Z-scores.
    Note:
    - Assumes that a connection pool is available via `get_connection` and `release_connection`.
    - The function uses the `psycopg2` library to interact with the PostgreSQL database.
    Raises:
        Exception: If any database operation fails.
    """
    os.environ["R_HOME"] = r"C:\Program Files\R\R-4.4.2"
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                    player_id,
                    CASE WHEN gp > 0 THEN pts*1.0 / gp ELSE 0 END AS pts,
                    CASE WHEN gp > 0 THEN reb*1.0 / gp ELSE 0 END AS reb,
                    CASE WHEN gp > 0 THEN ast*1.0 / gp ELSE 0 END ast,
                    CASE WHEN gp > 0 THEN stl*1.0 / gp ELSE 0 END AS stl,
                    CASE WHEN gp > 0 THEN blk*1.0 / gp ELSE 0 END AS blk,
                    CASE WHEN gp > 0 THEN tov*1.0 / gp ELSE 0 END AS tov,
                    CASE WHEN gp > 0 THEN fg3m*1.0 / gp ELSE 0 END AS fg3m,
                    CASE WHEN gp > 0 THEN dd2*1.0 / gp ELSE 0 END AS dd2,
                    fg_pct,
                    ft_pct,
                    fg3_pct
            FROM leaguedashplayerstats
            WHERE season = '2024-25'
        """,
        )
        modded_data = cur.fetchall(), [desc[0] for desc in cur.description]
    finally:
        cur.close()
        release_connection(conn=conn)
    # Create DataFrame
    df = pd.DataFrame(data=modded_data[0], columns=modded_data[1])
    # Pass each column (as Series) to your function
    updated_df: DataFrame = df
    for column in df.columns:
        if column != "player_id":
            x = robjects.FloatVector(df[column].tolist())
            robjects.r.assign("x", x)
            # Load the MASS package (if not already loaded)
            r("library(MASS)")
            # Fit a normal distribution
            fit_norm = r('fitdistr(x, "normal")')
            # Extract the 'estimate' element (a named vector with 'mean' and 'sd')
            estimates = fit_norm.rx2("estimate")
            estimates_dict = {
                str(name): float(val)
                for name, val in zip(["mean", "sd"], list(estimates))
            }
            z_score_col: str = f"{column}_z_score"
            updated_df[z_score_col] = (
                df[column] - estimates_dict["mean"]
            ) / estimates_dict["sd"]
    # Build the column definitions for the CREATE TABLE query by mapping DataFrame dtypes.
    col_defs = []
    for col in updated_df.columns:
        dtype = updated_df[col].dtype
        if pd.api.types.is_integer_dtype(arr_or_dtype=dtype):
            pg_type = "INTEGER"
        elif pd.api.types.is_float_dtype(arr_or_dtype=dtype):
            pg_type = "DOUBLE PRECISION"
        elif pd.api.types.is_bool_dtype(arr_or_dtype=dtype):
            pg_type = "BOOLEAN"
        elif pd.api.types.is_datetime64_any_dtype(arr_or_dtype=dtype):
            pg_type = "TIMESTAMP"
        else:
            pg_type = "TEXT"
        col_defs.append(f'"{col}" {pg_type}')
    col_defs_str = ", ".join(col_defs)

    # Build SQL queries.
    drop_query: LiteralString = f"DROP TABLE IF EXISTS {'player_z_scores'};"
    create_table_query: LiteralString = (
        f"CREATE TABLE {'player_z_scores'} ({col_defs_str});"
    )
    columns_str: str = ", ".join(f'"{col}"' for col in updated_df.columns)
    insert_query: str = f"INSERT INTO {'player_z_scores'} ({columns_str}) VALUES %s"

    # Convert DataFrame rows to a list of tuples.
    rows = list(updated_df.itertuples(index=False, name=None))
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(drop_query)
        cur.execute(create_table_query)
        psycopg2.extras.execute_values(cur, insert_query, rows)
        conn.commit()
    finally:
        cur.close()
        release_connection(conn=conn)


populate_z_scores()
