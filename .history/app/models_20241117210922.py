from db_config import get_connection

# Establish connection to PostgreSQL database
conn = get_connection(schema="public")

# Create a cursor for executing SQL commands
cur = conn.cursor()


# Define the Player model
class Player:

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
        """Add a new player to the database."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO players (player_id, name, position, weight, born_date, age, exp, school, available_seasons)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id) DO NOTHING;
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
        return cls(player_id, name, available_seasons, position)

    @classmethod
    def get_all_players(cls):
        """Retrieve all players from the database."""
        cur.execute(
            "SELECT player_id, name, position, weight, born_date, age, exp, school, available_seasons FROM players;"
        )
        rows = cur.fetchall()
        return [cls(*row) for row in rows]

    @classmethod
    def get_player(cls, player_id):
        """Retrieve a player by ID."""
        cur.execute(
            """
            SELECT player_id, name, position
            FROM players
            WHERE player_id = %s;
            """,
            (player_id,),
        )
        row = cur.fetchone()
        if row:
            return cls(*row)
        return None

    # outdated
    @classmethod
    def update_player(
        cls, player_id, name, team, position, weight, born_date, age, exp,
        school
    ):
        """Update player information if it differs."""
        # Check current player data
        cur.execute(
            """
            SELECT name, team, position, weight, born_date, age, exp, school
            FROM players
            WHERE player_id = %s;
            """,
            (player_id,),
        )
        row = cur.fetchone()

        # If the player exists, compare fields and update as necessary
        if row:
            updates = []
            params = []
            fields = [
                "name",
                "team",
                "position",
                "weight",
                "born_date",
                "age",
                "exp",
                "school",
            ]
            new_data = [name, team, position, weight, born_date, age, exp,
                        school]

            for field, current_value, new_value in zip(fields, row, new_data):
                if current_value != new_value:
                    updates.append(f"{field} = %s")
                    params.append(new_value)

            if updates:
                params.append(player_id)
                cur.execute(
                    f"""
                    UPDATE players
                    SET {", ".join(updates)}
                    WHERE player_id = %s;
                    """,
                    tuple(params),
                )
                conn.commit()
                print(f"Player {name} (ID: {player_id}) updated.")
        else:
            print(f"Player ID {player_id} not found for update.")

    @classmethod
    def player_exists(cls, player_id):
        """Check if a player exists in the database by player_id."""
        cur.execute("SELECT 1 FROM players WHERE player_id = %s;", (player_id))
        return cur.fetchone() is not None





class Statistics:
    """
    The `Statistics` class provides methods to manage game statistics for
    players.

    This class represents individual game statistics and includes functionality
    for creating and managing the `statistics` table in the database. It offers
    methods to add new statistics, retrieve statistics by player, and check
    if statistics exist for a specific player.

    Attributes:
    - stat_id (int): Unique identifier for the statistic entry.
    - player_id (int): Identifier of the player associated with the statistic.
    - game_date (str): Date of the game in "YYYY-MM" format.
    - points (int): Points scored by the player.
    - rebounds (int): Number of rebounds by the player.
    - assists (int): Number of assists by the player.
    - steals (int): Number of steals by the player.
    - blocks (int): Number of blocks by the player.

    Methods:
    - create_table(): Ensures the `statistics` table exists in the database.
    - add_stat(player_id, game_date, points, rebounds, assists, steals, blocks
    ):
    Adds a new game statistic entry to the database and returns a `Statistics`
    instance.
    - get_stats_by_player(player_id):
    Retrieves all game statistics for a specific player from the database.
    - stats_exist_for_player(player_id):
    Checks whether statistics exist for a given player in the database.
    """
    def __init__(
        self, stat_id, player_id, game_date, points, rebounds, assists, steals,
        blocks
    ):
        self.stat_id = stat_id
        self.player_id = player_id
        self.game_date = game_date
        self.points = points
        self.rebounds = rebounds
        self.assists = assists
        self.steals = steals
        self.blocks = blocks

    @classmethod
    def create_table(cls):
        """Create the statistics table if it doesn't exist."""
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS statistics (
                stat_id SERIAL PRIMARY KEY,
                player_id INT REFERENCES players(player_id),
                game_date VARCHAR(7),
                points INT,
                rebounds INT,
                assists INT,
                steals INT,
                blocks INT
            );
        """
        )
        conn.commit()

    @classmethod
    def add_stat(cls, player_id, game_date, points, rebounds, assists, steals,
                 blocks):
        """Add a new game statistic entry."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO statistics (player_id, game_date, points, rebounds, assists, steals, blocks)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING stat_id;
            """,
            (player_id, game_date, points, rebounds, assists, steals, blocks),
        )
        stat_id = cur.fetchone()[0]
        conn.commit()
        return cls(
            stat_id, player_id, game_date, points, rebounds, assists, steals, blocks
        )

    @classmethod
    def get_stats_by_player(cls, player_id):
        """Retrieve all stats for a given player."""
        cur.execute(
            "SELECT stat_id, player_id, game_date, points, rebounds, assists, steals, blocks FROM statistics WHERE player_id = %s;",
            (player_id,),
        )
        rows = cur.fetchall()
        return [cls(*row) for row in rows]

    @classmethod
    def stats_exist_for_player(cls, player_id):
        """Check if statistics for a player exist in the database."""
        cur.execute(
            "SELECT 1 FROM statistics WHERE player_id = %s LIMIT 1;", (player_id,)
        )
        return cur.fetchone() is not None

# Define the Team model


class Team:
    """
    The `Team` class provides methods to manage basketball teams and their
    rosters.

    This class represents a basketball team and includes functionality for
    creating and managing the `teams` and `roster` tables in the database. It
    allows adding new teams, retrieving existing teams, and managing player
    rosters associated with teams.

    Attributes:
    - team_id (int): Unique identifier for the team.
    - name (str): Name of the team.
    - abbreviation (str): Abbreviation of the team's name.
    - roster (list): List of players in the team's roster, represented as
    tuples
    (player_id, player_name, player_number).

    Methods:
    - create_table():
    Ensures the `teams` and `roster` tables exist in the database.
    - add_team(name, abbreviation):
    Adds a new team to the database and returns a `Team` instance.
    - get_team(team_id):
    Retrieves a team by its ID and returns a `Team` instance.
    - add_to_roster(player_id, player_name, player_number, position,
    how_acquired, season):
    Adds a player to the team's roster, avoiding duplication through
    `ON CONFLICT`.
    - get_roster():
    Retrieves the roster for the current team from the database, returning a
    list of tuples (player_id, player_name, player_number).
    """

    def __init__(self, team_id, name, abbreviation):
        self.team_id = team_id
        self.name = name
        self.abbreviation = abbreviation
        self.roster = self.get_roster()

    @classmethod
    def create_table(cls):
        """Create the teams and roster tables if they don't exist."""
        # Create teams table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                team_id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                abbreviation VARCHAR(10)
            );
        """
        )

        # Create roster table with a foreign key reference to teams and players
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS roster (
                team_id INT REFERENCES teams(team_id),
                player_id INT REFERENCES players(player_id),
                player_name VARCHAR(255),
                player_number INT,
                position VARCHAR(50),
                how_acquired VARCHAR(255),
                season VARCHAR(10),
                PRIMARY KEY (team_id, player_id, season)
            );
        """
        )
        conn.commit()

    @classmethod
    def add_team(cls, name, abbreviation):
        """Add a new team to the database."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO teams (name, abbreviation)
            VALUES (%s, %s)
            RETURNING team_id;
            """,
            (name, abbreviation),
        )
        team_id = cur.fetchone()[0]
        conn.commit()
        return cls(team_id, name, abbreviation)

    @classmethod
    def get_team(cls, team_id):
        """Retrieve a team by ID."""
        cur.execute(
            "SELECT team_id, name, abbreviation FROM teams WHERE team_id = %s;",
            (team_id,),
        )
        row = cur.fetchone()
        if row:
            return cls(*row)
        return None

    def add_to_roster(
        self, player_id, player_name, player_number, position, how_acquired,
        season
    ):
        """Add a player to the team's roster."""
        cur.execute(
            """
            INSERT INTO roster (team_id, player_id, player_name, player_number, position, how_acquired, season)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (
                self.team_id,
                player_id,
                player_name,
                player_number,
                position,
                how_acquired,
                season,
            ),
        )
        conn.commit()

    def get_roster(self):
        """Retrieve the team's roster."""
        cur.execute(
            """
            SELECT player_id, player_name, player_number FROM roster
            WHERE team_id = %s;
            """,
            (self.team_id,),
        )
        return (
            cur.fetchall()
        )  # Returns a list of tuples (player_id, player_name, player_number)


class LeagueDashPlayerStats:
    """
    The `LeagueDashPlayerStats` class provides methods to manage and query league-wide player statistics.

    This class is responsible for creating and managing the `leaguedashplayerstats` table in the database. 
    It allows for adding new records, retrieving all statistics, and applying optional filters during data retrieval.

    Methods:
    - create_table():
    Ensures the `leaguedashplayerstats` table exists in the database.
    - add_stat(**kwargs):
    Adds a new record to the `leaguedashplayerstats` table. Accepts data as keyword arguments matching table columns.
    - get_all_stats(filters=None):
    Retrieves all player statistics from the database. Optional `filters` can be provided as a dictionary to filter results dynamically.

    Table Structure:
    - player_id (INT): Identifier for the player, references the `players` table.
    - player_name (VARCHAR): Name of the player.
    - season (VARCHAR): Season identifier in "YYYY-YY" format.
    - team_id (INT): Identifier for the player's team.
    - age (INT): Player's age.
    - gp (INT): Games played.
    - w (INT): Wins.
    - l (INT): Losses.
    - w_pct (FLOAT): Win percentage.
    - min (FLOAT): Minutes played.
    - fgm (FLOAT): Field goals made.
    - fga (FLOAT): Field goals attempted.
    - fg_pct (FLOAT): Field goal percentage.
    - fg3m (FLOAT): Three-point field goals made.
    - fg3a (FLOAT): Three-point field goals attempted.
    - fg3_pct (FLOAT): Three-point field goal percentage.
    - fta (FLOAT): Free throws attempted.
    - ft_pct (FLOAT): Free throw percentage.
    - oreb (FLOAT): Offensive rebounds.
    - dreb (FLOAT): Defensive rebounds.
    - reb (FLOAT): Total rebounds.
    - ast (FLOAT): Assists.
    - tov (FLOAT): Turnovers.
    - stl (FLOAT): Steals.
    - blk (FLOAT): Blocks.
    - blka (FLOAT): Blocked attempts.
    - pf (FLOAT): Personal fouls.
    - pfd (FLOAT): Personal fouls drawn.
    - pts (FLOAT): Points scored.
    - plus_minus (FLOAT): Plus-minus statistic.
    - nba_fantasy_points (FLOAT): NBA fantasy points.
    - dd (INT): Double-doubles.
    - td3 (INT): Triple-doubles.
    - Ranking Columns (e.g., `gp_rank`, `w_rank`, etc.): Ranking data for
    corresponding statistics.

    Examples:
    - Adding a new record:
        LeagueDashPlayerStats.add_stat(
            player_id=1, player_name="John Doe", season="2023-24", team_id=5,
            age=25, gp=10, w=8, l=2, w_pct=0.8, min=30.5, fgm=6.0, fga=12.0,
            fg_pct=0.5, fg3m=2.0, fg3a=5.0, fg3_pct=0.4, fta=4.0, ft_pct=0.9,
            oreb=1.0, dreb=5.0, reb=6.0, ast=4.0, tov=1.5, stl=1.2, blk=0.8,
            blka=0.3, pf=2.0, pfd=3.0, pts=18.0, plus_minus=10.0,
            nba_fantasy_points=35.6, dd=1, td3=0, gp_rank=50, w_rank=10
        )

    - Retrieving all stats with filters:
        stats = LeagueDashPlayerStats.get_all_stats(filters={"season":
        "2023-24", "team_id": 5})
    """

    @classmethod
    def create_table(cls):
        """Create the leaguedashplayerstats table."""
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS leaguedashplayerstats (
                player_id INT REFERENCES players(player_id),
                player_name VARCHAR(255),
                season VARCHAR(10),
                team_id INT,
                age INT,
                gp INT,
                w INT,
                l INT,
                w_pct FLOAT,
                min FLOAT,
                fgm FLOAT,
                fga FLOAT,
                fg_pct FLOAT,
                fg3m FLOAT,
                fg3a FLOAT,
                fg3_pct FLOAT,
                fta FLOAT,
                ft_pct FLOAT,
                oreb FLOAT,
                dreb FLOAT,
                reb FLOAT,
                ast FLOAT,
                tov FLOAT,
                stl FLOAT,
                blk FLOAT,
                blka FLOAT,
                pf FLOAT,
                pfd FLOAT,
                pts FLOAT,
                plus_minus FLOAT,
                nba_fantasy_points FLOAT,
                dd INT,
                td3 INT,
                gp_rank INT,
                w_rank INT,
                l_rank INT,
                w_pct_rank INT,
                min_rank INT,
                fgm_rank INT,
                fg_pct_rank INT,
                fg3m_rank INT,
                fg3a_rank INT,
                fg3_pct_rank INT,
                ftm_rank INT,
                fta_rank INT,
                ft_pct_rank INT,
                oreb_rank INT,
                dreb_rank INT,
                reb_rank INT,
                ast_rank INT,
                tov_rank INT,
                stl_rank INT,
                blk_rank INT,
                blka_rank INT,
                pf_rank INT,
                pfd_rank INT,
                pts_rank INT,
                plus_minus_rank INT,
                nba_fantasy_points_rank INT,
                dd2_rank INT,
                td3_rank INT
            );
        """
        )
        conn.commit()

    @classmethod
    def add_stat(cls, **kwargs):
        """Add a record to the leaguedashplayerstats table."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO leaguedashplayerstats (
                player_id, player_name,season, team_id, age, gp, w, l, w_pct,
                min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, fta, ft_pct, oreb,
                dreb, reb, ast, tov, stl, blk, blka,pf, pfd, pts, plus_minus,
                nba_fantasy_points, dd, td3, gp_rank, w_rank, l_rank,
                w_pct_rank, min_rank, fgm_rank, fg_pct_rank, fg3m_rank,
                fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank, ft_pct_rank,
                oreb_rank, dreb_rank, reb_rank, ast_rank, tov_rank, stl_rank,
                blk_rank, blka_rank, pf_rank, pfd_rank, pts_rank,
                plus_minus_rank, nba_fantasy_points_rank, dd2_rank, td3_rank
            ) VALUES (
                %(player_id)s, %(player_name)s,%(season)s, %(team_id)s,
                %(age)s, %(gp)s, %(w)s, %(l)s, %(w_pct)s, %(min)s, %(fgm)s,
                %(fga)s, %(fg_pct)s, %(fg3m)s, %(fg3a)s,%(fg3_pct)s, %(fta)s,
                %(ft_pct)s, %(oreb)s, %(dreb)s, %(reb)s, %(ast)s,%(tov)s,
                %(stl)s, %(blk)s, %(blka)s, %(pf)s, %(pfd)s, %(pts)s,
                %(plus_minus)s,%(nba_fantasy_points)s, %(dd)s, %(td3)s,
                %(gp_rank)s, %(w_rank)s, %(l_rank)s, %(w_pct_rank)s,
                %(min_rank)s, %(fgm_rank)s, %(fg_pct_rank)s, %(fg3m_rank)s,
                %(fg3a_rank)s, %(fg3_pct_rank)s, %(ftm_rank)s, %(fta_rank)s,
                %(ft_pct_rank)s,
                %(oreb_rank)s, %(dreb_rank)s, %(reb_rank)s, %(ast_rank)s,
                %(tov_rank)s,
                %(stl_rank)s, %(blk_rank)s, %(blka_rank)s, %(pf_rank)s,
                %(pfd_rank)s,
                %(pts_rank)s, %(plus_minus_rank)s, %(nba_fantasy_points_rank)s,
                %(dd2_rank)s, %(td3_rank)s
            );
            """,
            kwargs,
        )
        conn.commit()

    @classmethod
    def get_all_stats(cls, filters=None):
        """Fetch all stats with optional filters."""
        base_query = """
            SELECT player_id, player_name,season, team_id, age, gp, w, l,
            w_pct, min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, fta, ft_pct, 
            pts,oreb,dreb, reb, ast, tov,stl,blk,blka,pf,pfd,plus_minus,nba_fantasy_points,dd,td3,gp_rank,w_rank,l_rank,w_pct_rank, min_rank, fgm_rank, fg_pct_rank, fg3m_rank, fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank, oreb_rank, dreb_rank, reb_rank, ast_rank, tov_rank, stl_rank, blk_rank,blka_rank, pts_rank, pf_rank, pfd_rank, plus_minus_rank, nba_fantasy_points_rank, dd2_rank, td3_rank
            FROM leaguedashplayerstats
        """
        conditions = []
        params = []

        # Add filters dynamically
        if filters:
            for key, value in filters.items():
                conditions.append(f"{key} = %s")
                params.append(value)

        # Finalize query with conditions
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        print(base_query)

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]
