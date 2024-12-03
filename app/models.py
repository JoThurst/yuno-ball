"""
This module defines the data models for interacting with the basketball
database, including Player, Statistics, Team, and LeagueDashPlayerStats
classes. Each class provides methods for creating tables, adding records, and
retrieving data from the PostgreSQL database.
"""

from db_config import get_connection

# Establish connection to PostgreSQL database
conn = get_connection(schema="public")

# Create a cursor for executing SQL commands
cur = conn.cursor()


# Define the Player model
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
            INSERT INTO players (
                player_id, name, position, weight, born_date, age, exp, school,
                available_seasons
            )
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

    @classmethod
    def get_all_players(cls):
        """Retrieve all players from the database."""
        cur.execute(
            """
            SELECT player_id, name, position, weight, born_date, age, exp,
                   school, available_seasons
            FROM players;
            """
        )
        rows = cur.fetchall()
        return [cls(*row) for row in rows]

    @classmethod
    def get_player(cls, player_id):
        """Retrieve a player by ID."""
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
        if row:
            return cls(*row)
        return None

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
        """Update player information if it differs."""
        # Check current player data
        cur.execute(
            """
            SELECT name, position, weight, born_date, age, exp, school,
                   available_seasons
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
                "position",
                "weight",
                "born_date",
                "age",
                "exp",
                "school",
                "available_seasons",
            ]
            new_data = [
                name,
                position,
                weight,
                born_date,
                age,
                exp,
                school,
                available_seasons,
            ]

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
        cur.execute(
            "SELECT 1 FROM players WHERE player_id = %s;",
            (player_id,),
        )

        return cur.fetchone() is not None


# Define the Statistics model
class Statistics:
    """
    Represents the statistics of a player's game performance.

    Attributes:
        stat_id (int): The unique identifier for the statistics entry.
        player_id (int): The unique identifier for the player.
        game_date (str): The date of the game.
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
        game_date,
        points,
        rebounds,
        assists,
        steals,
        blocks,
    ):
        self.stat_id = stat_id
        self.player_id = player_id
        self.game_date = game_date
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
            "game_date": self.game_date,
            "points": self.points,
            "rebounds": self.rebounds,
            "assists": self.assists,
            "steals": self.steals,
            "blocks": self.blocks,
        }

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
    def add_stat(
        cls,
        player_id,
        game_date,
        points,
        rebounds,
        assists,
        steals,
        blocks,
    ):
        """Add a new game statistic entry."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO statistics (
                player_id, game_date, points, rebounds, assists, steals, blocks
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING stat_id;
            """,
            (player_id, game_date, points, rebounds, assists, steals, blocks),
        )
        stat_id = cur.fetchone()[0]
        conn.commit()
        return cls(
            stat_id,
            player_id,
            game_date,
            points,
            rebounds,
            assists,
            steals,
            blocks,
        )

    @classmethod
    def get_stats_by_player(cls, player_id):
        """
        Retrieve all stats for a given player.
        """
        cur.execute(
            """
            SELECT stat_id, player_id, game_date, points, rebounds, assists,
                steals, blocks
            FROM statistics
            WHERE player_id = %s;
            """,
            (player_id,),
        )
        rows = cur.fetchall()  # Fetch rows as tuples
        return [cls(*row) for row in rows]  # Instantiate Statistics objects

    @classmethod
    def stats_exist_for_player(cls, player_id):
        """Check if statistics for a player exist in the database."""
        cur.execute(
            "SELECT 1 FROM statistics WHERE player_id = %s LIMIT 1;",
            (player_id,),
        )
        return cur.fetchone() is not None


# Define the Team model
class Team:
    """
    Represents a sports team with its roster.

    Attributes:
        team_id (int): The unique identifier for the team.
        name (str): The name of the team.
        abbreviation (str): The team's abbreviation.
        roster (list): The list of players in the team.
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
    def add_team(cls, team_id, name, abbreviation):
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

        conn.commit()
        return cls(team_id, name, abbreviation)

    @classmethod
    def get_team(cls, team_id):
        """Retrieve a team by ID."""
        cur.execute(
            """
            SELECT team_id, name, abbreviation
            FROM teams
            WHERE team_id = %s;
            """,
            (team_id,),
        )
        row = cur.fetchone()
        if row:
            return cls(*row)
        return None

    def add_to_roster(
        self,
        player_id,
        player_name,
        player_number,
        position,
        how_acquired,
        season,
    ):
        """Add a player to the team's roster."""
        cur.execute(
            """
            INSERT INTO roster (
                team_id, player_id, player_name, player_number, position,
                how_acquired, season
            )
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
        """Retrieve the team's roster.

        Returns:
            list: A list of tuples (player_id, player_name, player_number)
        """
        cur.execute(
            """
            SELECT player_id, player_name, player_number
            FROM roster
            WHERE team_id = %s;
            """,
            (self.team_id,),
        )
        return cur.fetchall()
    
    @staticmethod
    def get_roster_by_player(player_id):
        """
        Fetch roster information for a specific player.
        """
        sql = "SELECT * FROM roster WHERE player_id = %s;"
        cur.execute(sql, (player_id,))
        return cur.fetchone()


class LeagueDashPlayerStats:
    """
    Represents the league-wide player statistics for a given season.

    This class provides methods to create the `leaguedashplayerstats` table,
    add records to it, and fetch all stats with optional filters.

    Methods:
        create_table(): Creates the `leaguedashplayerstats` table in the
        database.
        add_stat(**kwargs): Adds a new record to the table.
        get_all_stats(filters=None): Retrieves all stats with optional
        filtering.

    Usage:
        LeagueDashPlayerStats.create_table()
        LeagueDashPlayerStats.add_stat(
            player_id=1, player_name='John Doe', ...)
        stats = LeagueDashPlayerStats.get_all_stats(filters={
            'season': '2021-22'})
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
                player_id, player_name, season, team_id, age, gp, w, l, w_pct,
                min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, fta, ft_pct, oreb,
                dreb, reb, ast, tov, stl, blk, blka, pf, pfd, pts, plus_minus,
                nba_fantasy_points, dd, td3, gp_rank, w_rank, l_rank,
                w_pct_rank, min_rank, fgm_rank, fg_pct_rank, fg3m_rank,
                fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank, ft_pct_rank,
                oreb_rank, dreb_rank, reb_rank, ast_rank, tov_rank, stl_rank,
                blk_rank, blka_rank, pf_rank, pfd_rank, pts_rank,
                plus_minus_rank, nba_fantasy_points_rank, dd2_rank, td3_rank
            ) VALUES (
                %(player_id)s, %(player_name)s, %(season)s, %(team_id)s,
                %(age)s, %(gp)s, %(w)s, %(l)s, %(w_pct)s, %(min)s, %(fgm)s,
                %(fga)s, %(fg_pct)s, %(fg3m)s, %(fg3a)s, %(fg3_pct)s,
                %(fta)s, %(ft_pct)s, %(oreb)s, %(dreb)s, %(reb)s, %(ast)s,
                %(tov)s, %(stl)s, %(blk)s, %(blka)s, %(pf)s, %(pfd)s,
                %(pts)s, %(plus_minus)s, %(nba_fantasy_points)s, %(dd)s,
                %(td3)s, %(gp_rank)s, %(w_rank)s, %(l_rank)s, %(w_pct_rank)s,
                %(min_rank)s, %(fgm_rank)s, %(fg_pct_rank)s, %(fg3m_rank)s,
                %(fg3a_rank)s, %(fg3_pct_rank)s, %(ftm_rank)s, %(fta_rank)s,
                %(ft_pct_rank)s, %(oreb_rank)s, %(dreb_rank)s, %(reb_rank)s,
                %(ast_rank)s, %(tov_rank)s, %(stl_rank)s, %(blk_rank)s,
                %(blka_rank)s, %(pf_rank)s, %(pfd_rank)s, %(pts_rank)s,
                %(plus_minus_rank)s, %(nba_fantasy_points_rank)s,
                %(dd2_rank)s, %(td3_rank)s
            );
            """,
            kwargs,
        )
        conn.commit()

    @classmethod
    def get_all_stats(cls, filters=None):
        """Fetch all stats with optional filters.

        Args:
            filters (dict, optional): A dictionary of conditions to filter the
                stats. Example: {'season': '2021-22', 'team_id': 1610612737}

        Returns:
            list: A list of dictionaries containing the stats records.
        """
        base_query = """
            SELECT player_id, player_name, season, team_id, age, gp, w, l,
                   w_pct, min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, fta,
                   ft_pct, pts, oreb, dreb, reb, ast, tov, stl, blk, blka, pf,
                   pfd, plus_minus, nba_fantasy_points, dd, td3, gp_rank,
                   w_rank, l_rank, w_pct_rank, min_rank, fgm_rank, fg_pct_rank,
                   fg3m_rank, fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank,
                   ft_pct_rank, oreb_rank, dreb_rank, reb_rank, ast_rank,
                   tov_rank, stl_rank, blk_rank, blka_rank, pts_rank, pf_rank,
                   pfd_rank, plus_minus_rank, nba_fantasy_points_rank,
                   dd2_rank, td3_rank
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

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]
    @staticmethod
    def get_league_stats_by_player(player_id):
        """
        Fetch league stats for a specific player.
        """
        sql = "SELECT * FROM leaguedashplayerstats WHERE player_id = %s;"
        cur.execute(sql, (player_id,))
        return cur.fetchone()

# models.py

class PlayerGameLog:
    """
    Handles inserting player game logs into the database.
    """

    @staticmethod
    def create_table():
        """
        Create the gamelogs table if it does not exist.
        """
        sql = """
        CREATE TABLE IF NOT EXISTS gamelogs (
            player_id BIGINT NOT NULL,
            game_id VARCHAR NOT NULL,
            team_id BIGINT NOT NULL,
            points INT DEFAULT 0,
            assists INT DEFAULT 0,
            rebounds INT DEFAULT 0,
            steals INT DEFAULT 0,
            blocks INT DEFAULT 0,
            turnovers INT DEFAULT 0,
            minutes_played VARCHAR DEFAULT '00:00',
            season VARCHAR NOT NULL,
            PRIMARY KEY (player_id, game_id)
        );
        """
        cur.execute(sql)
        conn.commit()

    @staticmethod
    def insert_game_logs(player_game_logs, batch_size=100):
        """
        Inserts game logs into the gamelogs table in batches.

        Args:
            player_game_logs (list): List of dictionaries containing game log data.
            batch_size (int): Number of rows to insert per batch.
        """
        sql = """
        INSERT INTO gamelogs (player_id, game_id, team_id, points, assists, rebounds, steals, blocks, turnovers, minutes_played, season)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (player_id, game_id) DO NOTHING;
        """
        for i in range(0, len(player_game_logs), batch_size):
            batch = player_game_logs[i:i + batch_size]
            values = [
                (
                    log['PLAYER_ID'],
                    log['GAME_ID'],
                    log['TEAM_ID'],
                    log.get('PTS', 0),
                    log.get('AST', 0),
                    log.get('REB', 0),
                    log.get('STL', 0),
                    log.get('BLK', 0),
                    log.get('TO', 0),
                    log.get('MIN', '00:00'),
                    log['SEASON_YEAR']
                )
                for log in batch
            ]
            cur.executemany(sql, values)
            conn.commit()

    @staticmethod
    def get_game_logs_by_player(player_id):
        """
        Fetch game logs for a specific player.
        """
        sql = "SELECT * FROM gamelogs WHERE player_id = %s ORDER BY game_id DESC LIMIT 10;"
        cur.execute(sql, (player_id,))
        return cur.fetchall()
    
def normalize_row(row, headers):
    """Helper function to convert a row and headers into a dictionary."""
    return dict(zip(headers, row))


    
def get_player_data(player_id):
    """
    Consolidate player data from multiple tables for the player dashboard.
    """
    statistics = Statistics.get_stats_by_player(player_id) or []
    roster = Team.get_roster_by_player(player_id) or {}
    league_stats = LeagueDashPlayerStats.get_league_stats_by_player(player_id) or {}
    game_logs = PlayerGameLog.get_game_logs_by_player(player_id) or []

    # Normalize data
    league_stats_headers = ["player_id", "player_name", "season", "team_id", "gp", "w", "l", "min", "fg_pct",
                            "ft_pct", "reb", "ast", "pts", "stl", "blk", "to", "pf", "etc..."]
    game_logs_headers = ["player_id", "game_id", "team_id", "points", "assists", "rebounds", "steals",
                         "blocks", "turnovers", "minutes_played", "season"]

    return {
        "statistics": [stat.to_dict() for stat in statistics],  # Convert objects to dictionaries
        "roster": dict(zip(["team_id", "player_id", "player_name", "jersey", "position", "note", "season"], roster)) if roster else {},
        "league_stats": normalize_row(league_stats, league_stats_headers) if league_stats else {},
        "game_logs": [normalize_row(row, game_logs_headers) for row in game_logs],
    }


