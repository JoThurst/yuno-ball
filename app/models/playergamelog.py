from db_config import get_db_connection

class PlayerGameLog:
    """Handles inserting and retrieving player game logs."""

    @staticmethod
    def create_table():
        """Create the gamelogs table if it does not exist."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gamelogs (
                    player_id BIGINT NOT NULL,
                    game_id VARCHAR NOT NULL,
                    team_id BIGINT NOT NULL,
                    points INT DEFAULT 0,
                    assists INT DEFAULT 0,
                    rebounds INT DEFAULT 0,
                    steals INT DEFAULT 0,
                    blocks INT DEFAULT 0,
                    turnovers INT DEFAULT 0,
                    minutes_played VARCHAR DEFAULT '00:00',
                    season VARCHAR NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (player_id, game_id)
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_gamelogs_player_id ON gamelogs(player_id);
                CREATE INDEX IF NOT EXISTS idx_gamelogs_game_id ON gamelogs(game_id);
                CREATE INDEX IF NOT EXISTS idx_gamelogs_team_id ON gamelogs(team_id);
                CREATE INDEX IF NOT EXISTS idx_gamelogs_season ON gamelogs(season);
            """)

    @staticmethod
    def insert_game_logs(player_game_logs, batch_size=100):
        """
        Insert game logs into the database in batches.
        
        Args:
            player_game_logs (list): List of game log dictionaries
            batch_size (int): Number of logs to insert per batch
            
        Returns:
            int: Number of logs inserted
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            inserted_count = 0
            
            for i in range(0, len(player_game_logs), batch_size):
                batch = player_game_logs[i:i + batch_size]
                values = [
                    (
                        log["PLAYER_ID"],
                        log["GAME_ID"],
                        log["TEAM_ID"],
                        log.get("PTS", 0),
                        log.get("AST", 0),
                        log.get("REB", 0),
                        log.get("STL", 0),
                        log.get("BLK", 0),
                        log.get("TOV", 0),
                        log.get("MIN", "00:00"),
                        log["SEASON"]
                    )
                    for log in batch
                ]
                
                cur.executemany("""
                    INSERT INTO gamelogs (
                        player_id, game_id, team_id, points, assists,
                        rebounds, steals, blocks, turnovers,
                        minutes_played, season
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_id, game_id) DO UPDATE SET
                        team_id = EXCLUDED.team_id,
                        points = EXCLUDED.points,
                        assists = EXCLUDED.assists,
                        rebounds = EXCLUDED.rebounds,
                        steals = EXCLUDED.steals,
                        blocks = EXCLUDED.blocks,
                        turnovers = EXCLUDED.turnovers,
                        minutes_played = EXCLUDED.minutes_played,
                        season = EXCLUDED.season,
                        updated_at = CURRENT_TIMESTAMP;
                """, values)
                
                inserted_count += len(batch)
            
            return inserted_count

    @staticmethod
    def get_game_logs_by_player(player_id):
        """
        Get all game logs for a player.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            list: List of game log dictionaries
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM gamelogs
                WHERE player_id = %s
                ORDER BY game_id DESC;
            """, (player_id,))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @staticmethod
    def get_game_logs_by_player_and_season(player_id, season):
        """
        Get game logs for a player in a specific season.
        
        Args:
            player_id (int): The player ID
            season (str): The season year (e.g., "2023-24")
            
        Returns:
            list: List of game log dictionaries
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM gamelogs
                WHERE player_id = %s 
                AND season = %s
                ORDER BY game_id DESC;
            """, (player_id, season))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @staticmethod
    def get_game_logs_by_team(team_id):
        """
        Get all game logs for a team.
        
        Args:
            team_id (int): The team ID
            
        Returns:
            list: List of game log dictionaries
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM gamelogs
                WHERE team_id = %s
                ORDER BY game_id DESC;
            """, (team_id,))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @staticmethod
    def get_best_game_by_points(player_id):
        """
        Get the game with the highest points for a player.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            dict: Game log dictionary for the best game
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM gamelogs
                WHERE player_id = %s
                ORDER BY points DESC
                LIMIT 1;
            """, (player_id,))
            
            columns = [desc[0] for desc in cur.description]
            result = cur.fetchone()
            return dict(zip(columns, result)) if result else None

    @staticmethod
    def get_last_n_games_by_player(player_id, n=10):
        """
        Get the last N games for a player.
        
        Args:
            player_id (int): The player ID
            n (int): Number of games to return
            
        Returns:
            list: List of game log dictionaries
        """
        print(f"[DEBUG] get_last_n_games_by_player: Starting for player_id={player_id}, n={n}")
        try:
            with get_db_connection() as conn:
                print(f"[DEBUG] get_last_n_games_by_player: Got DB connection")
                cur = conn.cursor()
                print(f"[DEBUG] get_last_n_games_by_player: Executing query")
                cur.execute("""
                    SELECT 
                        g.*,
                        gs.game_date,
                        gs.home_or_away,
                        gs.result,
                        CASE
                            WHEN gs.result = 'W' THEN TRIM(REGEXP_REPLACE(gs.score, '\.0', '', 'g'))
                            ELSE REGEXP_REPLACE(TRIM(REGEXP_REPLACE(gs.score, '\.0', '', 'g')), '(\d+)-(\d+)', '\2-\1')
                        END as formatted_score,
                        t1.abbreviation as team_abbreviation,
                        t2.abbreviation as opponent_abbreviation,
                        CASE
                            WHEN gs.result = 'W' THEN TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 1))::integer
                            ELSE TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 2))::integer
                        END as team_score,
                        CASE
                            WHEN gs.result = 'W' THEN TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 2))::integer
                            ELSE TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 1))::integer
                        END as opponent_score
                    FROM gamelogs g
                    JOIN game_schedule gs ON g.game_id = gs.game_id AND g.team_id = gs.team_id
                    JOIN teams t1 ON gs.team_id = t1.team_id
                    JOIN teams t2 ON gs.opponent_team_id = t2.team_id
                    WHERE g.player_id = %s
                    ORDER BY gs.game_date DESC
                    LIMIT %s;
                """, (player_id, n))
                
                columns = [desc[0] for desc in cur.description]
                results = [dict(zip(columns, row)) for row in cur.fetchall()]
                print(f"[DEBUG] get_last_n_games_by_player: Retrieved {len(results)} game logs")
                return results
        except Exception as e:
            print(f"[ERROR] get_last_n_games_by_player: Exception occurred: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def get_game_logs_by_date_range(player_id, start_date, end_date):
        """
        Get game logs for a player within a date range.
        
        Args:
            player_id (int): The player ID
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            
        Returns:
            list: List of game log dictionaries
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT g.*
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                WHERE g.player_id = %s
                AND gs.game_date BETWEEN %s AND %s
                ORDER BY gs.game_date DESC;
            """, (player_id, start_date, end_date))
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @staticmethod
    def get_game_logs_vs_opponent(player_id, opponent_team_id):
        """
        Get game logs for a player against a specific opponent.
        
        Args:
            player_id (int): The player ID
            opponent_team_id (int): The opponent team ID
            
        Returns:
            list: List of game log dictionaries
        """
        print(f"[DEBUG] get_game_logs_vs_opponent: Starting for player_id={player_id}, opponent_team_id={opponent_team_id}")
        try:
            with get_db_connection() as conn:
                print(f"[DEBUG] get_game_logs_vs_opponent: Got DB connection")
                cur = conn.cursor()
                # First find all game_ids where the player's team played against the opponent
                print(f"[DEBUG] get_game_logs_vs_opponent: Executing first query to find game_ids")
                cur.execute("""
                    SELECT DISTINCT g.game_id 
                    FROM gamelogs g
                    JOIN game_schedule gs ON g.game_id = gs.game_id
                    WHERE g.player_id = %s
                    AND gs.opponent_team_id = %s
                """, (player_id, opponent_team_id))
                
                game_ids = [row[0] for row in cur.fetchall()]
                print(f"[DEBUG] get_game_logs_vs_opponent: Found {len(game_ids)} game_ids")
                
                if not game_ids:
                    print(f"[DEBUG] get_game_logs_vs_opponent: No games found, returning empty list")
                    return []
                
                # Now get the game logs for those specific games
                placeholders = ','.join(['%s'] * len(game_ids))
                query = f"""
                    SELECT 
                        g.*,
                        gs.game_date,
                        gs.home_or_away,
                        gs.result,
                        CASE
                            WHEN gs.result = 'W' THEN TRIM(REGEXP_REPLACE(gs.score, '\.0', '', 'g'))
                            ELSE REGEXP_REPLACE(TRIM(REGEXP_REPLACE(gs.score, '\.0', '', 'g')), '(\d+)-(\d+)', '\2-\1')
                        END as formatted_score,
                        t1.abbreviation as team_abbreviation,
                        t2.abbreviation as opponent_abbreviation,
                        CASE
                            WHEN gs.result = 'W' THEN TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 1))::integer
                            ELSE TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 2))::integer
                        END as team_score,
                        CASE
                            WHEN gs.result = 'W' THEN TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 2))::integer
                            ELSE TRIM(SPLIT_PART(REGEXP_REPLACE(gs.score, '\.0', '', 'g'), '-', 1))::integer
                        END as opponent_score
                    FROM gamelogs g
                    JOIN game_schedule gs ON g.game_id = gs.game_id AND g.team_id = gs.team_id
                    JOIN teams t1 ON gs.team_id = t1.team_id
                    JOIN teams t2 ON gs.opponent_team_id = t2.team_id
                    WHERE g.player_id = %s
                    AND g.game_id IN ({placeholders})
                    ORDER BY gs.game_date DESC
                """
                
                params = [player_id] + game_ids
                print(f"[DEBUG] get_game_logs_vs_opponent: Executing second query with {len(params)} parameters")
                cur.execute(query, params)
                
                columns = [desc[0] for desc in cur.description]
                results = [dict(zip(columns, row)) for row in cur.fetchall()]
                print(f"[DEBUG] get_game_logs_vs_opponent: Retrieved {len(results)} game logs")
                return results
        except Exception as e:
            print(f"[ERROR] get_game_logs_vs_opponent: Exception occurred: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

