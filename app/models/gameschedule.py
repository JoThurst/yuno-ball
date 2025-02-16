"""
A module for managing NBA game schedules in a database.
This module provides functionality to create, insert, and retrieve game schedules
through the GameSchedule class. It interfaces with a PostgreSQL database to store
and manage game-related information including game IDs, seasons, team information,
dates, locations, results, and scores.
The module handles:
- Table creation for game schedules
- Batch insertion/updating of game schedule records
- Retrieval of games by specific dates
Dependencies:
    db_config: Provides database connection management through get_connection and 
              release_connection functions
Tables:
    game_schedule:
        - game_id (VARCHAR): Primary key identifying each game
        - season (VARCHAR): NBA season identifier
        - team_id (BIGINT): Foreign key reference to teams table
        - opponent_team_id (BIGINT): Foreign key reference to teams table
        - game_date (TIMESTAMP): Date and time of the game
        - home_or_away (CHAR): 'H' for home games, 'A' for away games
        - result (CHAR): 'W' for win, 'L' for loss, NULL for unplayed games
        - score (VARCHAR): Game score representation
"""

from db_config import get_connection, release_connection


class GameSchedule:
    """Represents the schedule and results for NBA games."""

    @staticmethod
    def create_table() -> None:
        """Create the GameSchedule table if it doesn't exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS game_schedule (
                    game_id VARCHAR PRIMARY KEY,
                    season VARCHAR NOT NULL,
                    team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    opponent_team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    game_date TIMESTAMP NOT NULL,
                    home_or_away CHAR(1) NOT NULL CHECK (home_or_away IN ('H', 'A')),
                    result CHAR(1) CHECK (result IN ('W', 'L', NULL)),
                    score VARCHAR
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn=conn)

    @staticmethod
    def insert_game_schedule(game_schedules) -> None:
        """Insert game schedules into the database, updating records if they exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            sql = """
                INSERT INTO game_schedule (game_id, season, team_id, opponent_team_id, game_date, home_or_away, result, score)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id) DO UPDATE SET
                    season = EXCLUDED.season,
                    team_id = EXCLUDED.team_id,
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
            release_connection(conn=conn)

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
            release_connection(conn=conn)
