from db_config import get_db_connection

class GameSchedule:
    """Represents the schedule and results for NBA games."""

    @staticmethod
    def create_table():
        """Create the GameSchedule table if it doesn't exist."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_schedule (
                    game_id VARCHAR NOT NULL,
                    season VARCHAR NOT NULL,
                    team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    opponent_team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    game_date TIMESTAMP NOT NULL,
                    home_or_away CHAR(1) NOT NULL CHECK (home_or_away IN ('H', 'A')),
                    result CHAR(1) CHECK (result IN ('W', 'L', NULL)),
                    score VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (game_id, team_id) 
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_game_schedule_game_id ON game_schedule(game_id);
                CREATE INDEX IF NOT EXISTS idx_game_schedule_team_id ON game_schedule(team_id);
                CREATE INDEX IF NOT EXISTS idx_game_schedule_game_date ON game_schedule(game_date);
                CREATE INDEX IF NOT EXISTS idx_game_schedule_season ON game_schedule(season);
            """)

    @staticmethod
    def insert_game_schedule(game_schedules):
        """
        Insert game schedules into the database.
        
        Args:
            game_schedules (list): List of game schedule dictionaries
            
        Returns:
            int: Number of games inserted/updated
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            values = [
                (
                    game["game_id"],
                    game["season"],
                    game["team_id"],
                    game["opponent_team_id"],
                    game["game_date"],
                    game["home_or_away"],
                    game.get("result"),
                    game.get("score")
                )
                for game in game_schedules
            ]
            
            cur.executemany("""
                INSERT INTO game_schedule (
                    game_id, season, team_id, opponent_team_id,
                    game_date, home_or_away, result, score
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id, team_id) DO UPDATE SET  
                    season = EXCLUDED.season,
                    opponent_team_id = EXCLUDED.opponent_team_id,
                    game_date = EXCLUDED.game_date,
                    home_or_away = EXCLUDED.home_or_away,
                    result = EXCLUDED.result,
                    score = EXCLUDED.score,
                    updated_at = CURRENT_TIMESTAMP;
            """, values)
            
            return len(values)

    @staticmethod
    def get_games_by_date(game_date):
        """
        Get all games for a specific date.
        
        Args:
            game_date (str): Date in YYYY-MM-DD format
            
        Returns:
            list: List of game dictionaries
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    gs.*, 
                    t1.name as team_name,
                    t1.abbreviation as team_abbreviation,
                    t2.name as opponent_name,
                    t2.abbreviation as opponent_abbreviation
                FROM game_schedule gs
                JOIN teams t1 ON gs.team_id = t1.team_id
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id
                WHERE DATE(game_date) = %s
                ORDER BY game_date;
            """, (game_date,))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @staticmethod
    def get_opponent_team_id(game_id, team_id):
        """
        Get the opponent team ID for a game.
        
        Args:
            game_id (str): The game ID
            team_id (int): The team ID
            
        Returns:
            int: Opponent team ID if found, None otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT opponent_team_id
                FROM game_schedule
                WHERE game_id = %s AND team_id = %s;
            """, (game_id, team_id))
            
            result = cur.fetchone()
            return result[0] if result else None

    @staticmethod
    def get_last_n_games_by_team(team_id, n=10):
        """
        Get the last N games for a team.
        
        Args:
            team_id (int): The team ID
            n (int): Number of games to return
            
        Returns:
            list: List of game dictionaries
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                WITH team_games AS (
                    -- Get games where team was home
                    SELECT 
                        gs.game_id,
                        gs.game_date,
                        t1.team_id as home_team_id,
                        t1.name as home_team_name,
                        t1.abbreviation as home_team_abbr,
                        t2.team_id as away_team_id,
                        t2.name as away_team_name,
                        t2.abbreviation as away_team_abbr,
                        CASE 
                            WHEN gs.result = 'W' THEN gs.score
                            ELSE (
                                -- Split score and swap parts
                                CASE 
                                    WHEN position('-' in gs.score) > 0 
                                    THEN split_part(gs.score, '-', 2) || '-' || split_part(gs.score, '-', 1)
                                    ELSE gs.score
                                END
                            )
                        END as score,
                        gs.result
                    FROM game_schedule gs
                    JOIN teams t1 ON gs.team_id = t1.team_id
                    JOIN teams t2 ON gs.opponent_team_id = t2.team_id
                    WHERE gs.team_id = %s AND gs.home_or_away = 'H'
                    
                    UNION ALL
                    
                    -- Get games where team was away
                    SELECT 
                        gs.game_id,
                        gs.game_date,
                        t2.team_id as home_team_id,
                        t2.name as home_team_name,
                        t2.abbreviation as home_team_abbr,
                        t1.team_id as away_team_id,
                        t1.name as away_team_name,
                        t1.abbreviation as away_team_abbr,
                        CASE 
                            WHEN gs.result = 'W' THEN (
                                -- Split score and swap parts
                                CASE 
                                    WHEN position('-' in gs.score) > 0 
                                    THEN split_part(gs.score, '-', 2) || '-' || split_part(gs.score, '-', 1)
                                    ELSE gs.score
                                END
                            )
                            ELSE gs.score
                        END as score,
                        CASE 
                            WHEN gs.result = 'W' THEN 'L'
                            WHEN gs.result = 'L' THEN 'W'
                            ELSE NULL
                        END as result
                    FROM game_schedule gs
                    JOIN teams t1 ON gs.team_id = t1.team_id
                    JOIN teams t2 ON gs.opponent_team_id = t2.team_id
                    WHERE gs.team_id = %s AND gs.home_or_away = 'A'
                )
                SELECT *
                FROM team_games
                WHERE DATE(game_date) < CURRENT_DATE
                  AND result IS NOT NULL
                ORDER BY game_date DESC
                LIMIT %s;
            """, (team_id, team_id, n))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @staticmethod
    def get_upcoming_n_games_by_team(team_id, n=5):
        """
        Get the next N games for a team.
        
        Args:
            team_id (int): The team ID
            n (int): Number of games to return
            
        Returns:
            list: List of game dictionaries
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                WITH team_games AS (
                    -- Get games where team is home
                    SELECT 
                        gs.game_id,
                        gs.game_date,
                        t1.team_id as home_team_id,
                        t1.name as home_team_name,
                        t1.abbreviation as home_team_abbr,
                        t2.team_id as away_team_id,
                        t2.name as away_team_name,
                        t2.abbreviation as away_team_abbr
                    FROM game_schedule gs
                    JOIN teams t1 ON gs.team_id = t1.team_id
                    JOIN teams t2 ON gs.opponent_team_id = t2.team_id
                    WHERE gs.team_id = %s AND gs.home_or_away = 'H'
                    
                    UNION ALL
                    
                    -- Get games where team is away
                    SELECT 
                        gs.game_id,
                        gs.game_date,
                        t2.team_id as home_team_id,
                        t2.name as home_team_name,
                        t2.abbreviation as home_team_abbr,
                        t1.team_id as away_team_id,
                        t1.name as away_team_name,
                        t1.abbreviation as away_team_abbr
                    FROM game_schedule gs
                    JOIN teams t1 ON gs.team_id = t1.team_id
                    JOIN teams t2 ON gs.opponent_team_id = t2.team_id
                    WHERE gs.team_id = %s AND gs.home_or_away = 'A'
                )
                SELECT *
                FROM team_games
                WHERE DATE(game_date) >= CURRENT_DATE
                ORDER BY game_date ASC
                LIMIT %s;
            """, (team_id, team_id, n))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]           

