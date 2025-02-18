from db_config import get_connection, release_connection

class GameSchedule:
    """Represents the schedule and results for NBA games."""

    @staticmethod
    def create_table():
        """Create the GameSchedule table if it doesn't exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS game_schedule (
                    game_id VARCHAR NOT NULL,
                    season VARCHAR NOT NULL,
                    team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    opponent_team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    game_date TIMESTAMP NOT NULL,
                    home_or_away CHAR(1) NOT NULL CHECK (home_or_away IN ('H', 'A')),
                    result CHAR(1) CHECK (result IN ('W', 'L', NULL)),
                    score VARCHAR,
                    PRIMARY KEY (game_id, team_id) 
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)


    @staticmethod
    def insert_game_schedule(game_schedules):
        """Insert game schedules into the database, updating records if they exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            sql = """
                INSERT INTO game_schedule (game_id, season, team_id, opponent_team_id, game_date, home_or_away, result, score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id, team_id) DO UPDATE SET  
                    season = EXCLUDED.season,
                    opponent_team_id = EXCLUDED.opponent_team_id,
                    game_date = EXCLUDED.game_date,
                    home_or_away = EXCLUDED.home_or_away,
                    result = EXCLUDED.result,
                    score = EXCLUDED.score;
            """
            values = [
                (
                    game["game_id"],
                    game["season"],
                    game["team_id"],  
                    game["opponent_team_id"],
                    game["game_date"],
                    game["home_or_away"],
                    game.get("result"),
                    game.get("score"),
                )
                for game in game_schedules
            ]
            cur.executemany(sql, values)
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_games_by_date(game_date):
        """Fetch games by a specific date."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT game_id, team_id, opponent_team_id, game_date, home_or_away, result, score
                FROM game_schedule
                WHERE DATE(game_date) = %s;
            """,
                (game_date,),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_opponent_team_id(game_id, team_id):
        """
        Retrieve the opponent team ID for a given game and team.

        Args:
            game_id (str): The game ID.
            team_id (int): The team ID.

        Returns:
            int or None: Opponent team ID or None if not found.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT opponent_team_id FROM game_schedule
                WHERE game_id = %s AND team_id = %s;
                """,
                (game_id, team_id),
            )
            result = cur.fetchone()
            return result[0] if result else None
        finally:
            cur.close()
            release_connection(conn)

