from db_config import get_db_connection
from app.utils.config_utils import logger


class PlayerStreaks:
    """Handles inserting and retrieving player streak data from the database."""

    STAT_DISPLAY_NAMES = {
        "PTS": "Points",
        "REB": "Rebounds",
        "AST": "Assists",
        "STL": "Steals",
        "BLK": "Blocks",
        "FG3M": "3-Pointers"
    }

    @staticmethod
    def create_table():
        """Creates the player_streaks table if it doesn't exist."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
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
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_player_streaks_player_id ON player_streaks(player_id);
                CREATE INDEX IF NOT EXISTS idx_player_streaks_season ON player_streaks(season);
                CREATE INDEX IF NOT EXISTS idx_player_streaks_stat ON player_streaks(stat);
            """)
            logger.info("Created (or verified) the player_streaks table schema.")

    @staticmethod
    def store_streaks(streaks):
        """Stores player streaks in the database, ensuring all threshold levels are stored."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.executemany("""
                INSERT INTO player_streaks (
                    player_id, player_name, stat, threshold, streak_games, season
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, stat, season, threshold) 
                DO UPDATE SET 
                    streak_games = EXCLUDED.streak_games,
                    created_at = CURRENT_TIMESTAMP;
            """, [
                (
                    int(s["player_id"]),
                    s["player_name"],
                    s["stat"],
                    int(s["threshold"]),
                    int(s["streak_games"]),
                    s["season"]
                )
                for s in streaks
            ])

    @staticmethod
    def clear_streaks():
        """Clears all streaks from the database."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("TRUNCATE TABLE player_streaks;")
            logger.info("Cleared all player streaks from the database.")

    @staticmethod
    def clean_duplicate_streaks():
        """Removes duplicate streaks, keeping only the most recent one for each player/stat/threshold combination."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                WITH ranked_streaks AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY player_id, stat, season, threshold
                               ORDER BY created_at DESC
                           ) as rn
                    FROM player_streaks
                )
                DELETE FROM player_streaks
                WHERE id IN (
                    SELECT id 
                    FROM ranked_streaks 
                    WHERE rn > 1
                );
            """)
            logger.info("Cleaned duplicate player streaks from the database.")

    @staticmethod
    def get_streaks(season="2024-25"):
        """Gets all streaks for a given season."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM player_streaks 
                WHERE season = %s 
                ORDER BY streak_games DESC;
            """, (season,))
            return cur.fetchall()

    @staticmethod
    def get_streaks_by_player_ids(player_ids, season="2024-25"):
        """Gets all streaks for a list of player IDs in a given season."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            placeholders = ','.join(['%s'] * len(player_ids))
            cur.execute(f"""
                SELECT * FROM player_streaks 
                WHERE player_id IN ({placeholders})
                AND season = %s 
                ORDER BY streak_games DESC;
            """, tuple(player_ids) + (season,))
            return cur.fetchall()

    @staticmethod
    def get_hot_player_streaks(limit=None, threshold=10):
        """
        Gets the current hot streaks for players.
        
        Args:
            limit (int, optional): Maximum number of streaks to return
            threshold (int): Minimum streak games to consider
            
        Returns:
            list: List of player streaks meeting the criteria
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Get all active streaks above the threshold
            query = """
                SELECT 
                    ps.player_id,
                    ps.player_name,
                    ps.stat,
                    ps.streak_games,
                    ps.season,
                    t.abbreviation as team
                FROM player_streaks ps
                LEFT JOIN roster r ON ps.player_id = r.player_id
                LEFT JOIN teams t ON r.team_id = t.team_id
                WHERE ps.streak_games >= %s
                AND ps.season = '2024-25'  -- Current season
                ORDER BY ps.streak_games DESC
            """
            
            if limit:
                query += " LIMIT %s"
                cur.execute(query, (threshold, limit))
            else:
                cur.execute(query, (threshold,))
            
            streaks = []
            for row in cur.fetchall():
                streak = {
                    'player_id': row[0],
                    'player_name': row[1],
                    'stat': row[2],
                    'streak_games': row[3],
                    'season': row[4],
                    'team': row[5] if row[5] else 'N/A'
                }
                streaks.append(streak)
            
            return streaks

    @staticmethod
    def get_all_player_streaks(min_streak_games=7):
        """
        Gets all player streaks meeting the minimum games threshold.
        
        Args:
            min_streak_games (int): Minimum number of games for a streak
            
        Returns:
            dict: Dictionary of streaks grouped by stat type
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    ps.player_id,
                    ps.player_name,
                    ps.stat,
                    ps.threshold,
                    ps.streak_games,
                    ps.season,
                    t.abbreviation as team
                FROM player_streaks ps
                LEFT JOIN roster r ON ps.player_id = r.player_id
                LEFT JOIN teams t ON r.team_id = t.team_id
                WHERE ps.streak_games >= %s
                AND ps.season = '2024-25'  -- Current season
                ORDER BY ps.stat, ps.streak_games DESC;
            """, (min_streak_games,))
            
            streaks_by_stat = {}
            for row in cur.fetchall():
                streak = {
                    'player_id': row[0],
                    'player_name': row[1],
                    'stat': row[2],
                    'stat_display': PlayerStreaks.STAT_DISPLAY_NAMES.get(row[2], row[2]),
                    'threshold': row[3],
                    'streak_games': row[4],
                    'season': row[5],
                    'team_abbreviation': row[6] if row[6] else 'N/A'
                }
                
                stat = row[2]
                if stat not in streaks_by_stat:
                    streaks_by_stat[stat] = []
                streaks_by_stat[stat].append(streak)
            
            return streaks_by_stat

