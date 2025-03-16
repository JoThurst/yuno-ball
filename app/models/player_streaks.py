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
        
    #Need to Test this function
    @staticmethod
    def clean_duplicate_streaks():
        """
        Deletes unnecessary streak rows where a player has the same streak_games count
        at a lower threshold compared to a higher threshold for the same stat.
        """
        query = """
        DELETE FROM player_streaks p1
        USING player_streaks p2
        WHERE p1.player_id = p2.player_id 
        AND p1.stat = p2.stat
        AND p1.season = p2.season
        AND p1.streak_games = p2.streak_games
        AND p1.threshold < p2.threshold;
        """
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(query)
            deleted_count = cur.rowcount
        conn.commit()
        conn.close()
        release_connection(conn)
        logger.info(f"Cleaned {deleted_count} duplicate streak rows from player_streaks table.")


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

    @staticmethod
    def get_hot_player_streaks(limit=None, threshold=10):
        """
        Get players who are on hot streaks with threshold greater than specified value.
        
        Args:
            limit (int, optional): Maximum number of players to return.
            threshold (int, optional): Minimum threshold value for a streak to be considered "hot". Default is 10.
            
        Returns:
            list: A list of dictionaries containing player streak information.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Get player streaks from the player_streaks table with threshold > specified value
            # Note: We're not joining with teams table here to avoid the missing column issue
            query = """
                SELECT 
                    ps.player_id,
                    ps.player_name,
                    ps.stat as streak_type,
                    ps.threshold as streak_value,
                    ps.streak_games as streak_count
                FROM 
                    player_streaks ps
                WHERE 
                    ps.threshold > %s
                ORDER BY 
                    ps.threshold DESC, ps.streak_games DESC
            """
            
            params = [threshold]
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
                
            cur.execute(query, params)
            
            # Convert to list of dictionaries
            columns = [desc[0] for desc in cur.description]
            streaks = [dict(zip(columns, row)) for row in cur.fetchall()]
            
            # For now, we'll just set team_abbreviation to an empty string
            # In a real implementation, you would need to add the proper team lookup logic
            # based on your database schema
            for streak in streaks:
                streak['team_abbreviation'] = ""
            
            return streaks
        except Exception as e:
            logger.error(f"Error getting hot player streaks: {str(e)}")
            return []
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_all_player_streaks(min_streak_games=7):
        """
        Get all player streaks from the database.
        
        Args:
            min_streak_games (int, optional): Minimum number of games for a streak to be included. Default is 7.
            
        Returns:
            list: A list of dictionaries containing player streak information.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Get all player streaks from the player_streaks table
            query = """
                SELECT 
                    ps.player_id,
                    ps.player_name,
                    ps.stat as streak_type,
                    ps.threshold as streak_value,
                    ps.streak_games as streak_count,
                    ps.season
                FROM 
                    player_streaks ps
                WHERE 
                    ps.streak_games >= %s
                ORDER BY 
                    ps.stat, ps.threshold DESC, ps.streak_games DESC
            """
            
            logger.debug(f"Executing query to get all player streaks with min_streak_games={min_streak_games}")
            cur.execute(query, (min_streak_games,))
            
            # Convert to list of dictionaries
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            logger.debug(f"Found {len(rows)} streak records in database")
            
            if not rows:
                logger.warning("No streaks found in database matching criteria")
                return []
                
            streaks = [dict(zip(columns, row)) for row in rows]
            
            # For now, we'll just set team_abbreviation to an empty string
            # In a real implementation, you would need to add the proper team lookup logic
            # based on your database schema
            for streak in streaks:
                streak['team_abbreviation'] = ""
            
            # Log a sample streak for debugging
            if streaks:
                logger.debug(f"Sample streak: {streaks[0]}")
            
            return streaks
        except Exception as e:
            logger.error(f"Error getting all player streaks: {str(e)}")
            logger.error(f"Query that failed: {query}")
            return []
        finally:
            cur.close()
            release_connection(conn)

