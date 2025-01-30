"""
This module defines the data models for interacting with the basketball
database, including Player, Statistics, Team, and LeagueDashPlayerStats
classes. Each class provides methods for creating tables, adding records, and
retrieving data from the PostgreSQL database.
"""

from db_config import get_connection, release_connection

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
            release_connection(conn)

    @classmethod
    def add_player(cls, player_id, name, position, weight, born_date, age, exp, school, available_seasons):
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
                (player_id, name, position, weight, born_date, age, exp, school, available_seasons),
            )
            conn.commit()
            return cls(player_id, name, position, weight, born_date, age, exp, school, available_seasons)
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_all_players(cls):
        """Retrieve all players from the database."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT player_id, name, position, weight, born_date, age, exp,
                       school, available_seasons
                FROM players;
            """)
            rows = cur.fetchall()
            return [cls(*row) for row in rows]
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_player(cls, player_id):
        """Retrieve a player by ID."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT player_id, name, position, weight, born_date, age, exp,
                       school, available_seasons
                FROM players
                WHERE player_id = %s;
            """, (player_id,))
            row = cur.fetchone()
            return cls(*row) if row else None
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def update_player(cls, player_id, name, position, weight, born_date, age, exp, school, available_seasons):
        """Update player information if it differs."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE players
                SET name = %s, position = %s, weight = %s, born_date = %s,
                    age = %s, exp = %s, school = %s, available_seasons = %s
                WHERE player_id = %s;
            """, (name, position, weight, born_date, age, exp, school, available_seasons, player_id))
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def player_exists(cls, player_id):
        """Check if a player exists in the database by player_id."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM players WHERE player_id = %s;", (player_id,))
            return cur.fetchone() is not None
        finally:
            cur.close()
            release_connection(conn)

# Define the Statistics model
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
            release_connection(conn)

    @classmethod
    def add_stat(cls, player_id, season_year, points, rebounds, assists, steals, blocks):
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
            release_connection(conn)

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
                (player_id,)
            )
            rows = cur.fetchall()
            return [cls(*row) for row in rows]
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def stats_exist_for_player(cls, player_id):
        """Check if statistics for a player exist in the database."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1 FROM statistics WHERE player_id = %s LIMIT 1;", (player_id,))
            return cur.fetchone() is not None
        finally:
            cur.close()
            release_connection(conn)


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
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS teams (
                    team_id SERIAL PRIMARY KEY,
                    name VARCHAR(255),
                    abbreviation VARCHAR(10)
                );
                """
            )
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
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def add_team(cls, name, abbreviation):
        """Add a new team to the database."""
        conn = get_connection()
        cur = conn.cursor()
        try:
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
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_team(cls, team_id):
        """Retrieve a team by ID."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT team_id, name, abbreviation
                FROM teams
                WHERE team_id = %s;
                """,
                (team_id,)
            )
            row = cur.fetchone()
            return cls(*row) if row else None
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def clear_roster(cls, team_id):
        """Remove all players from a team's roster before updating."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                DELETE FROM roster WHERE team_id = %s;
                """,
                (team_id,)
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    def add_to_roster(self, player_id, player_name, player_number, position, how_acquired, season):
        """Add a player to the team's roster."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO roster (
                    team_id, player_id, player_name, player_number, position, how_acquired, season
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (team_id, player_id, season) DO UPDATE
                SET 
                    player_name = EXCLUDED.player_name,
                    player_number = EXCLUDED.player_number,
                    position = EXCLUDED.position,
                    how_acquired = EXCLUDED.how_acquired;
                """,
                (self.team_id, player_id, player_name, player_number, position, how_acquired, season),
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    def get_roster(self):
        """Retrieve the team's roster."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT player_id, player_name, player_number
                FROM roster
                WHERE team_id = %s;
                """,
                (self.team_id,)
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_all_teams(cls):
        """Retrieve all teams from the database."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT team_id, name, abbreviation
                FROM teams;
                """
            )
            rows = cur.fetchall()
            return [cls(*row) for row in rows]
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_team_id_by_abbreviation(abbreviation):
        """Retrieve the team_id for a given team abbreviation."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT team_id
                FROM teams
                WHERE abbreviation = %s;
                """,
                (abbreviation,)
            )
            result = cur.fetchone()
            return result[0] if result else None
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_roster_by_player(player_id):
        """Fetch roster information for a specific player."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT * FROM roster WHERE player_id = %s;
                """,
                (player_id,)
            )
            return cur.fetchone()
        finally:
            cur.close()
            release_connection(conn)


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
        conn = get_connection()
        cur = conn.cursor()
        try:
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
                    PRIMARY KEY (player_id, season)
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def add_stat(cls, **kwargs):
        """Add or update a record in the leaguedashplayerstats table."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO leaguedashplayerstats (
                    player_id, player_name, season, team_id, age, gp, w, l, w_pct,
                    min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, fta, ft_pct, oreb,
                    dreb, reb, ast, tov, stl, blk, blka, pf, pfd, pts, plus_minus,
                    nba_fantasy_points, dd, td3
                ) VALUES (
                    %(player_id)s, %(player_name)s, %(season)s, %(team_id)s,
                    %(age)s, %(gp)s, %(w)s, %(l)s, %(w_pct)s, %(min)s, %(fgm)s,
                    %(fga)s, %(fg_pct)s, %(fg3m)s, %(fg3a)s, %(fg3_pct)s,
                    %(fta)s, %(ft_pct)s, %(oreb)s, %(dreb)s, %(reb)s, %(ast)s,
                    %(tov)s, %(stl)s, %(blk)s, %(blka)s, %(pf)s, %(pfd)s,
                    %(pts)s, %(plus_minus)s, %(nba_fantasy_points)s, %(dd)s,
                    %(td3)s
                )
                ON CONFLICT (player_id, season) DO UPDATE SET
                    team_id = EXCLUDED.team_id,
                    age = EXCLUDED.age,
                    gp = EXCLUDED.gp,
                    w = EXCLUDED.w,
                    l = EXCLUDED.l,
                    w_pct = EXCLUDED.w_pct,
                    min = EXCLUDED.min,
                    fgm = EXCLUDED.fgm,
                    fga = EXCLUDED.fga,
                    fg_pct = EXCLUDED.fg_pct,
                    fg3m = EXCLUDED.fg3m,
                    fg3a = EXCLUDED.fg3a,
                    fg3_pct = EXCLUDED.fg3_pct,
                    fta = EXCLUDED.fta,
                    ft_pct = EXCLUDED.ft_pct,
                    oreb = EXCLUDED.oreb,
                    dreb = EXCLUDED.dreb,
                    reb = EXCLUDED.reb,
                    ast = EXCLUDED.ast,
                    tov = EXCLUDED.tov,
                    stl = EXCLUDED.stl,
                    blk = EXCLUDED.blk,
                    blka = EXCLUDED.blka,
                    pf = EXCLUDED.pf,
                    pfd = EXCLUDED.pfd,
                    pts = EXCLUDED.pts,
                    plus_minus = EXCLUDED.plus_minus,
                    nba_fantasy_points = EXCLUDED.nba_fantasy_points,
                    dd = EXCLUDED.dd,
                    td3 = EXCLUDED.td3;
                """,
                kwargs,
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_all_stats(cls, filters=None):
        """Fetch all stats with optional filters."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM leaguedashplayerstats"
            params = []
            if filters:
                conditions = [f"{key} = %s" for key in filters]
                query += " WHERE " + " AND ".join(conditions)
                params = list(filters.values())
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(zip([desc[0] for desc in cur.description], row)) for row in rows]
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_league_stats_by_player(player_id):
        """Fetch league stats for a specific player."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM leaguedashplayerstats WHERE player_id = %s;", (player_id,))
            return cur.fetchone()
        finally:
            cur.close()
            release_connection(conn)

# models.py

class PlayerGameLog:
    """Handles inserting and retrieving player game logs."""

    @staticmethod
    def create_table():
        """Create the gamelogs table if it does not exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def insert_game_logs(player_game_logs, batch_size=100):
        """Insert game logs into the database in batches."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            sql = """
                INSERT INTO gamelogs (player_id, game_id, team_id, points, assists, rebounds, steals, blocks, turnovers, minutes_played, season)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, game_id) DO NOTHING;
            """
            for i in range(0, len(player_game_logs), batch_size):
                batch = player_game_logs[i:i + batch_size]
                values = [
                    (
                        log['PLAYER_ID'], log['GAME_ID'], log['TEAM_ID'],
                        log.get('PTS', 0), log.get('AST', 0), log.get('REB', 0),
                        log.get('STL', 0), log.get('BLK', 0), log.get('TO', 0),
                        log.get('MIN', '00:00'), log['SEASON_YEAR']
                    )
                    for log in batch
                ]
                cur.executemany(sql, values)
                conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_game_logs_by_player(player_id):
        """Fetch game logs for a specific player."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM gamelogs WHERE player_id = %s ORDER BY game_id DESC LIMIT 10;", (player_id,))
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)

class GameSchedule:
    """Represents the schedule and results for NBA games."""

    @staticmethod
    def create_table():
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
            release_connection(conn)

    @staticmethod
    def insert_game_schedule(game_schedules):
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
                    game['game_id'], game['season'], game['team_id'], game['opponent_team_id'],
                    game['game_date'], game['home_or_away'], game.get('result'), game.get('score')
                )
                for game in game_schedules
            ]
            cur.executemany(sql, values)
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_games_by_date(game_date):
        """Fetch games by a specific date."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT game_id, team_id, opponent_team_id, game_date, home_or_away, result, score
                FROM game_schedule
                WHERE DATE(game_date) = %s;
            """, (game_date,))
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)
    
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
    league_stats_headers = ["player_id", "Player Name", "Season", "team_id", "Age", "GP" ,"W", "L", "w_pct", "min", "FGM", "FGA", "fg_pct", "3PM", "3PA", "3P%",
                            "fta","ft_pct", "pts", "o-reb", "d-reb" ,"reb", "ast", "to",  "stl", "blk", "blk-a", "pf", "pfd", "+/-","Fantasy Pts","DD", "TD3", "GP Rank",
                            "Win Rank", "Loss Rank", "Win % Rank", "Mins Rank", "FGM Rank", "FG % Rank", "3PM Rank", "3P% Rank", "FTM Rank", "FTA Rank", "FT% Rank","o-reb Rank", "d-reb Rank", "Reb Rank", "Ast Rank", "TO Rank",
                            "STL Rank", "BLK Rank", "BLKA Rank", "PTS Rank", "PF Rank", "PFD Rank", "+/- Rank", "Fantasy Pts Rank", " DD Rank", "TD3 Rank"]
    game_logs_headers = ["player_id", "game_id", "team_id", "points", "assists", "rebounds", "steals",
                         "blocks", "turnovers", "minutes_played", "season"]

    return {
        "statistics": [stat.to_dict() for stat in statistics],  # Convert objects to dictionaries
        "roster": dict(zip(["team_id", "player_id", "player_name", "jersey", "position", "note", "season"], roster)) if roster else {},
        "league_stats": normalize_row(league_stats, league_stats_headers) if league_stats else {},
        "game_logs": [normalize_row(row, game_logs_headers) for row in game_logs],
    }


