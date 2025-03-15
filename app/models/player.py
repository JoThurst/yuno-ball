from db_config import get_db_connection
from app.utils.config_utils import logger

class Player:
    """A class representing a basketball player with methods to interact with
    a database.

    Attributes:
        player_id (int): Unique identifier for the player.
        name (str): Name of the player.
        position (str): Playing position of the player.
        weight (int): Weight of the player.
        born_date (str): Birth date of the player.
        age (int): Age of the player.
        exp (int): Years of experience.
        school (str): School attended by the player.
        available_seasons (list): Seasons in which the player was available.

    Class Methods:
        create_table(): Creates the players table in the database if it
            doesn't exist.
        add_player(...): Adds a new player to the database.
        get_all_players(): Retrieves all players from the database.
        get_player(player_id): Retrieves a player by their ID.
        update_player(...): Updates player information if it has changed.
        player_exists(player_id): Checks if a player exists in the database.
    """

    def __init__(
        self,
        player_id,
        name,
        position,
        weight,
        born_date,
        age,
        exp,
        school,
        available_seasons,
    ):
        self.player_id = player_id
        self.name = name
        self.position = position
        self.weight = weight
        self.born_date = born_date
        self.age = age
        self.exp = exp
        self.school = school
        self.available_seasons = available_seasons

    @classmethod
    def create_table(cls):
        """Create the players table if it doesn't exist."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    player_id INT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    position VARCHAR(50),
                    weight INT,
                    born_date DATE,
                    age INT,
                    exp INT,
                    school VARCHAR(255),
                    available_seasons TEXT[],
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);
                CREATE INDEX IF NOT EXISTS idx_players_position ON players(position);
            """)
            logger.info("Created (or verified) players table schema.")

    @classmethod
    def add_player(
        cls,
        player_id,
        name,
        position,
        weight,
        born_date,
        age,
        exp,
        school,
        available_seasons,
    ):
        """
        Add a new player or update if exists.
        
        Args:
            player_id (int): The player ID
            name (str): Player name
            position (str): Player position
            weight (int): Player weight
            born_date (str): Player birth date
            age (int): Player age
            exp (int): Years of experience
            school (str): Player's school
            available_seasons (list): List of available seasons
            
        Returns:
            Player: The created or updated player object
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO players (
                    player_id, name, position, weight, born_date,
                    age, exp, school, available_seasons
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    position = EXCLUDED.position,
                    weight = EXCLUDED.weight,
                    born_date = EXCLUDED.born_date,
                    age = EXCLUDED.age,
                    exp = EXCLUDED.exp,
                    school = EXCLUDED.school,
                    available_seasons = EXCLUDED.available_seasons,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *;
            """, (
                player_id,
                name,
                position,
                weight,
                born_date,
                age,
                exp,
                school,
                available_seasons,
            ))
            
            result = cur.fetchone()
            logger.info(f"Added/updated player: {name} (ID: {player_id})")
            return cls(*result[:-2])  # Exclude created_at and updated_at

    @classmethod
    def get_all_players(cls):
        """
        Get all players from the database.
        
        Returns:
            list: List of Player objects
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    player_id, name, position, weight, born_date,
                    age, exp, school, available_seasons
                FROM players
                ORDER BY name;
            """)
            return [cls(*row) for row in cur.fetchall()]

    @classmethod
    def get_player(cls, player_id):
        """
        Get a player by their ID.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            Player: The player object if found, None otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    player_id, name, position, weight, born_date,
                    age, exp, school, available_seasons
                FROM players
                WHERE player_id = %s;
            """, (player_id,))
            
            result = cur.fetchone()
            return cls(*result) if result else None

    @classmethod
    def update_player(
        cls,
        player_id,
        name,
        position,
        weight,
        born_date,
        age,
        exp,
        school,
        available_seasons,
    ):
        """
        Update a player's information.
        
        Args:
            player_id (int): The player ID
            name (str): Player name
            position (str): Player position
            weight (int): Player weight
            born_date (str): Player birth date
            age (int): Player age
            exp (int): Years of experience
            school (str): Player's school
            available_seasons (list): List of available seasons
            
        Returns:
            Player: The updated player object
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE players SET
                    name = %s,
                    position = %s,
                    weight = %s,
                    born_date = %s,
                    age = %s,
                    exp = %s,
                    school = %s,
                    available_seasons = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE player_id = %s
                RETURNING *;
            """, (
                name,
                position,
                weight,
                born_date,
                age,
                exp,
                school,
                available_seasons,
                player_id,
            ))
            
            result = cur.fetchone()
            if result:
                logger.info(f"Updated player: {name} (ID: {player_id})")
                return cls(*result[:-2])  # Exclude created_at and updated_at
            return None

    @classmethod
    def player_exists(cls, player_id):
        """
        Check if a player exists in the database.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            bool: True if player exists, False otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 
                    FROM players 
                    WHERE player_id = %s
                );
            """, (player_id,))
            return cur.fetchone()[0]

    @classmethod
    def get_player_name(cls, player_id):
        """
        Get a player's name by their ID.
        
        Args:
            player_id (int): The player ID
            
        Returns:
            str: Player name if found, None otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT name 
                FROM players 
                WHERE player_id = %s;
            """, (player_id,))
            
            result = cur.fetchone()
            return result[0] if result else None
