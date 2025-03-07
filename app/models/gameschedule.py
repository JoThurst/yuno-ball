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

    @staticmethod
    def get_last_n_games_by_team(team_id, n=10):
        """
        Retrieve the last N games played by a team.
        
        Args:
            team_id (int): The team ID.
            n (int): Number of past games to retrieve (default=10).
        
        Returns:
            list: A list of dictionaries containing game details.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT game_id, season, opponent_team_id, game_date, home_or_away, result, score
                FROM game_schedule
                WHERE team_id = %s AND result IS NOT NULL
                ORDER BY game_date DESC
                LIMIT %s;
                """,
                (team_id, n),
            )
            rows = cur.fetchall()
            games = []
            
            for row in rows:
                game_id, season, opponent_team_id, game_date, home_or_away, result, score = row

                # ✅ Fix: Extract numeric values from score
                team_score, opponent_score = None, None
                if score:
                    score_parts = score.replace(" ", "").split("-")  # Remove spaces and split
                    if len(score_parts) == 2:
                        try:
                            team_score = int(float(score_parts[0]))  # Convert from string to int
                            opponent_score = int(float(score_parts[1]))  # Handle decimal issue
                        except ValueError:
                            print(f"⚠️ Invalid score format: {score}")

                games.append({
                    "game_id": game_id,
                    "season": season,
                    "opponent_team_id": opponent_team_id,
                    "game_date": game_date.strftime("%Y-%m-%d"),
                    "home_or_away": home_or_away,
                    "result": result,
                    "team_score": team_score,
                    "opponent_score": opponent_score
                })

            return games

        finally:
            cur.close()
            release_connection(conn)



    @staticmethod
    def get_upcoming_n_games_by_team(team_id, n=5):
        """
        Retrieve the next N upcoming games for a team.

        Args:
            team_id (int): The team ID.
            n (int): Number of upcoming games to retrieve (default=5).

        Returns:
            list: A list of dictionaries containing upcoming game details.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT game_id, season, opponent_team_id, game_date, home_or_away
                FROM game_schedule
                WHERE team_id = %s AND game_date > NOW()
                ORDER BY game_date ASC
                LIMIT %s;
                """,
                (team_id, n),
            )
            rows = cur.fetchall()
            return [
                {
                    "game_id": row[0],
                    "season": row[1],
                    "opponent_team_id": row[2],
                    "game_date": row[3].strftime("%Y-%m-%d"),
                    "home_or_away": row[4],
                }
                for row in rows
            ]
        finally:
            cur.close()
            release_connection(conn)           

