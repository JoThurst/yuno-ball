from db_config import get_connection, release_connection


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
    def create_table(cls) -> None:
        """Create the players table if it doesn't exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    player_id INT PRIMARY KEY,
                    name VARCHAR(255),
                    position VARCHAR(50),
                    weight INT,
                    born_date VARCHAR(25),
                    age INT,
                    exp INT,
                    school VARCHAR(255),
                    available_seasons TEXT
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn=conn)

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
        """Add or update a player in the database."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO players (
                    player_id, name, position, weight, born_date, age, exp, school, available_seasons
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id) DO UPDATE
                SET
                    name = EXCLUDED.name,
                    position = EXCLUDED.position,
                    weight = EXCLUDED.weight,
                    born_date = EXCLUDED.born_date,
                    age = EXCLUDED.age,
                    exp = EXCLUDED.exp,
                    school = EXCLUDED.school,
                    available_seasons = EXCLUDED.available_seasons;
                """,
                (
                    player_id,
                    name,
                    position,
                    weight,
                    born_date,
                    age,
                    exp,
                    school,
                    available_seasons,
                ),
            )
            conn.commit()
            return cls(
                player_id,
                name,
                position,
                weight,
                born_date,
                age,
                exp,
                school,
                available_seasons,
            )
        finally:
            cur.close()
            release_connection(conn=conn)

    @classmethod
    def get_all_players(cls):
        """Retrieve all players from the database."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT player_id, name, position, weight, born_date, age, exp,
                       school, available_seasons
                FROM players;
            """
            )
            rows = cur.fetchall()
            return [cls(*row) for row in rows]
        finally:
            cur.close()
            release_connection(conn=conn)

    @classmethod
    def get_player(cls, player_id):
        """Retrieve a player by ID."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT player_id, name, position, weight, born_date, age, exp,
                       school, available_seasons
                FROM players
                WHERE player_id = %s;
            """,
                (player_id,),
            )
            row = cur.fetchone()
            return cls(*row) if row else None
        finally:
            cur.close()
            release_connection(conn=conn)

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
    ) -> None:
        """Update player information if it differs."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE players
                SET name = %s, position = %s, weight = %s, born_date = %s,
                    age = %s, exp = %s, school = %s, available_seasons = %s
                WHERE player_id = %s;
            """,
                (
                    name,
                    position,
                    weight,
                    born_date,
                    age,
                    exp,
                    school,
                    available_seasons,
                    player_id,
                ),
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn=conn)

    @classmethod
    def player_exists(cls, player_id) -> bool:
        """Check if a player exists in the database by player_id."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM players WHERE player_id = %s;", (player_id,))
            return cur.fetchone() is not None
        finally:
            cur.close()
            release_connection(conn=conn)
