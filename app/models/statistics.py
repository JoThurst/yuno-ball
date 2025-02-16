"""
NBA Player Statistics Module
This module provides a Statistics class for managing NBA player statistics in a database.
It includes functionality for creating statistics records, updating them, and retrieving
player statistics data.
The module interfaces with a PostgreSQL database through the db_config connection pool.
Classes:
    Statistics: Represents and manages player game performance statistics.
Database Schema:
    The statistics table contains:
    - stat_id (SERIAL PRIMARY KEY)
    - player_id (INT, FOREIGN KEY)
    - season_year (VARCHAR)
    - points (INT)
    - rebounds (INT)
    - assists (INT)
    - steals (INT)
    - blocks (INT)
    With a unique constraint on (player_id, season_year)
Dependencies:
    - db_config: Provides database connection pool management
"""

from db_config import get_connection, release_connection


class Statistics:
    """
    Represents the statistics of a player's game performance.

    Attributes:
        stat_id (int): The unique identifier for the statistics entry.
        player_id (int): The unique identifier for the player.
        season_year (str): The season year of the statistics.
        points (int): Number of points scored.
        rebounds (int): Number of rebounds.
        assists (int): Number of assists.
        steals (int): Number of steals.
        blocks (int): Number of blocks.
    """

    def __init__(
        self,
        stat_id,
        player_id,
        season_year,
        points,
        rebounds,
        assists,
        steals,
        blocks,
    ):
        self.stat_id = stat_id
        self.player_id = player_id
        self.season_year = season_year
        self.points = points
        self.rebounds = rebounds
        self.assists = assists
        self.steals = steals
        self.blocks = blocks

    def to_dict(self):
        """Convert the Statistics object to a dictionary."""
        return {
            "stat_id": self.stat_id,
            "player_id": self.player_id,
            "season_year": self.season_year,
            "points": self.points,
            "rebounds": self.rebounds,
            "assists": self.assists,
            "steals": self.steals,
            "blocks": self.blocks,
        }

    @classmethod
    def create_table(cls):
        """Create the statistics table if it doesn't exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS statistics (
                    stat_id SERIAL PRIMARY KEY,
                    player_id INT REFERENCES players(player_id),
                    season_year VARCHAR(7),
                    points INT,
                    rebounds INT,
                    assists INT,
                    steals INT,
                    blocks INT,
                    UNIQUE (player_id, season_year)
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn=conn)

    @classmethod
    def add_stat(
        cls, player_id, season_year, points, rebounds, assists, steals, blocks
    ) -> None:
        """Add or update a player's statistics."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO statistics (
                    player_id, season_year, points, rebounds, assists, steals, blocks
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, season_year) DO UPDATE
                SET 
                    points = EXCLUDED.points,
                    rebounds = EXCLUDED.rebounds,
                    assists = EXCLUDED.assists,
                    steals = EXCLUDED.steals,
                    blocks = EXCLUDED.blocks;
                """,
                (player_id, season_year, points, rebounds, assists, steals, blocks),
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn=conn)

    @classmethod
    def get_stats_by_player(cls, player_id):
        """Retrieve all stats for a given player."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT stat_id, player_id, season_year, points, rebounds, assists,
                       steals, blocks
                FROM statistics
                WHERE player_id = %s;
                """,
                (player_id,),
            )
            rows = cur.fetchall()
            return [cls(*row) for row in rows]
        finally:
            cur.close()
            release_connection(conn=conn)

    @classmethod
    def stats_exist_for_player(cls, player_id) -> bool:
        """Check if statistics for a player exist in the database."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT 1 FROM statistics WHERE player_id = %s LIMIT 1;", (player_id,)
            )
            return cur.fetchone() is not None
        finally:
            cur.close()
            release_connection(conn=conn)
