from db_config import get_connection, release_connection
from app.utils.config_utils import logger


class PlayerStreaks:
    """Handles inserting and retrieving player streak data from the database."""

    @staticmethod
    def create_table():
        """Creates the player_streaks table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS player_streaks (
            id SERIAL PRIMARY KEY,
            player_id INT NOT NULL,
            player_name TEXT NOT NULL,
            stat TEXT NOT NULL,
            threshold INT NOT NULL,
            streak_games INT NOT NULL,
            season TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (player_id, stat, season, threshold)  -- Ensures multiple streaks per stat but prevents duplicates
        );
        """
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()
        conn.close()
        release_connection(conn)
        logger.info("Created (or verified) the player_streaks table schema.")


    @staticmethod
    def store_streaks(streaks):
        """Stores player streaks in the database, ensuring all threshold levels are stored."""
        query = """
        INSERT INTO player_streaks (player_id, player_name, stat, threshold, streak_games, season)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;  -- Prevents duplicate rows if they already exist
        """
        conn = get_connection()
        with conn.cursor() as cur:
            cur.executemany(query, [
                (
                    int(s["player_id"]),  # Convert to Python int
                    s["player_name"],
                    s["stat"],
                    int(s["threshold"]),  # Convert to Python int
                    int(s["streak_games"]),  # Convert to Python int
                    s["season"]
                )
                for s in streaks
            ])
        conn.commit()
        conn.close()
        release_connection(conn)
        logger.info(f"✅ Inserted {len(streaks)} streaks into player_streaks table.")

    @staticmethod
    def clear_streaks():
        """Deletes all rows from the player_streaks table."""
        query = "DELETE FROM player_streaks;"
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()
        conn.close()
        release_connection(conn)
        logger.info("Cleared all rows from player_streaks table.")



    @staticmethod
    def get_streaks(season="2024-25"):
        """Fetches player streaks for a given season."""
        query = "SELECT * FROM player_streaks WHERE season = %s;"
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query, (season,))
            results = cur.fetchall()
        conn.close()
        release_connection(conn)
        return results
    
    @staticmethod
    def get_streaks_by_player_ids(player_ids, season="2024-25"):
        """Fetches player streaks for specific player IDs in a given season and returns as dictionaries."""
        query = """
        SELECT id, player_id, player_name, stat, threshold, streak_games, season, created_at 
        FROM player_streaks
        WHERE season = %s AND player_id = ANY(%s::int[]);
        """
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query, (season, list(map(int, player_ids))))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]  # Extract column names

        conn.close()
        release_connection(conn)

        # Convert each row tuple into a dictionary
        streaks = [dict(zip(columns, row)) for row in rows]
        return streaks

