from db_config import get_db_connection

class LeagueDashPlayerStats:
    """
    Represents the league-wide player statistics for a given season.

    This class provides methods to create the `leaguedashplayerstats` table,
    add records to it, and fetch all stats with optional filters.

    Methods:
        create_table(): Creates the `leaguedashplayerstats` table in the
        database.
        add_stat(**kwargs): Adds a new record to the table.
        get_all_stats(filters=None): Retrieves all stats with optional
        filtering.

    Usage:
        LeagueDashPlayerStats.create_table()
        LeagueDashPlayerStats.add_stat(
            player_id=1, player_name='John Doe', ...)
        stats = LeagueDashPlayerStats.get_all_stats(filters={
            'season': '2021-22'})
    """

    @classmethod
    def create_table(cls):
        """Create the leaguedashplayerstats table with all fields."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS leaguedashplayerstats (
                    player_id INT REFERENCES players(player_id),
                    player_name VARCHAR(255),
                    season VARCHAR(10),
                    team_id INT,
                    team_abbreviation VARCHAR(10),
                    age INT,
                    gp INT,
                    w INT,
                    l INT,
                    w_pct FLOAT,
                    min FLOAT,
                    fgm FLOAT,
                    fga FLOAT,
                    fg_pct FLOAT,
                    fg3m FLOAT,
                    fg3a FLOAT,
                    fg3_pct FLOAT,
                    ftm FLOAT,
                    fta FLOAT,
                    ft_pct FLOAT,
                    oreb FLOAT,
                    dreb FLOAT,
                    reb FLOAT,
                    ast FLOAT,
                    tov FLOAT,
                    stl FLOAT,
                    blk FLOAT,
                    blka FLOAT,
                    pf FLOAT,
                    pfd FLOAT,
                    pts FLOAT,
                    plus_minus FLOAT,
                    nba_fantasy_pts FLOAT,
                    wnba_fantasy_pts FLOAT,
                    dd2 INT,
                    td3 INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (player_id, season)
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_leaguedashplayerstats_player_id ON leaguedashplayerstats(player_id);
                CREATE INDEX IF NOT EXISTS idx_leaguedashplayerstats_season ON leaguedashplayerstats(season);
                CREATE INDEX IF NOT EXISTS idx_leaguedashplayerstats_team_id ON leaguedashplayerstats(team_id);
            """)

    @classmethod
    def add_stat(cls, **kwargs):
        """
        Add or update player statistics.
        
        Args:
            **kwargs: Player statistics fields
            
        Returns:
            bool: True if successful, False otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Get column names and values
            columns = list(kwargs.keys())
            values = [kwargs[col] for col in columns]
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join(columns)
            
            # Build the update part
            update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns 
                                  if col not in ['player_id', 'season']])
            
            query = f"""
                INSERT INTO leaguedashplayerstats ({column_names})
                VALUES ({placeholders})
                ON CONFLICT (player_id, season) DO UPDATE
                SET {update_set},
                    updated_at = CURRENT_TIMESTAMP
                RETURNING player_id;
            """
            
            cur.execute(query, values)
            return cur.fetchone() is not None

    @classmethod
    def get_all_stats(cls, filters=None):
        """
        Get all player statistics with optional filtering.
        
        Args:
            filters (dict, optional): Dictionary of column:value pairs to filter by
            
        Returns:
            list: List of dictionaries containing player statistics
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            query = "SELECT * FROM leaguedashplayerstats"
            values = []
            
            if filters:
                conditions = []
                for column, value in filters.items():
                    conditions.append(f"{column} = %s")
                    values.append(value)
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY pts DESC"
            cur.execute(query, values)
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @staticmethod
    def get_league_stats_by_player(player_id):
        """
        Get all statistics for a specific player.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            dict: Player statistics if found, None otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM leaguedashplayerstats
                WHERE player_id = %s
                ORDER BY season DESC;
            """, (player_id,))
            
            columns = [desc[0] for desc in cur.description]
            result = cur.fetchone()
            
            return dict(zip(columns, result)) if result else None

    @staticmethod
    def get_top_players(limit=10):
        """
        Get top players by points scored.
        
        Args:
            limit (int): Number of players to return
            
        Returns:
            list: List of dictionaries containing player statistics
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    player_id,
                    player_name,
                    team_abbreviation,
                    gp,
                    min,
                    pts,
                    reb,
                    ast,
                    stl,
                    blk,
                    fg_pct,
                    fg3_pct,
                    ft_pct,
                    plus_minus
                FROM leaguedashplayerstats
                WHERE season = '2024-25'  -- Current season
                AND gp >= 10  -- Minimum games played
                ORDER BY pts DESC
                LIMIT %s;
            """, (limit,))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
