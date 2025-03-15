from db_config import get_db_connection

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
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    stat_id SERIAL PRIMARY KEY,
                    player_id INT REFERENCES players(player_id),
                    season_year VARCHAR(10),
                    points INT,
                    rebounds INT,
                    assists INT,
                    steals INT,
                    blocks INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_statistics_player_id ON statistics(player_id);
                CREATE INDEX IF NOT EXISTS idx_statistics_season_year ON statistics(season_year);
            """)

    @classmethod
    def add_stat(cls, player_id, season_year, points, rebounds, assists, steals, blocks):
        """
        Add a new statistics entry.
        
        Args:
            player_id (int): The player ID
            season_year (str): The season year
            points (int): Number of points scored
            rebounds (int): Number of rebounds
            assists (int): Number of assists
            steals (int): Number of steals
            blocks (int): Number of blocks
            
        Returns:
            Statistics: The created statistics object
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO statistics (
                    player_id, season_year, points, rebounds, assists, steals, blocks
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING stat_id;
            """, (player_id, season_year, points, rebounds, assists, steals, blocks))
            
            stat_id = cur.fetchone()[0]
            return cls(
                stat_id, player_id, season_year, points, rebounds, assists, steals, blocks
            )

    @classmethod
    def get_stats_by_player(cls, player_id):
        """
        Get all statistics for a player.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            list: List of Statistics objects for the player
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM statistics
                WHERE player_id = %s
                ORDER BY season_year DESC;
            """, (player_id,))
            
            return [
                cls(
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]
                )
                for row in cur.fetchall()
            ]

    @classmethod
    def stats_exist_for_player(cls, player_id):
        """
        Check if statistics exist for a player.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            bool: True if statistics exist, False otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 
                    FROM statistics 
                    WHERE player_id = %s
                );
            """, (player_id,))
            
            return cur.fetchone()[0]