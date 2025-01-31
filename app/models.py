"""
This module defines the data models for interacting with the basketball
database, including Player, Statistics, Team, and LeagueDashPlayerStats
classes. Each class provides methods for creating tables, adding records, and
retrieving data from the PostgreSQL database.
"""

from db_config import get_connection, release_connection
from datetime import datetime
import re
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
            return [{"team_id": row[0], "name": row[1], "abbreviation": row[2]} for row in rows]
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_team_with_details(cls, team_id):
        """Retrieve a team's full details, including roster and full standings data."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Fetch Team Info
            cur.execute(
                """
                SELECT team_id, name, abbreviation
                FROM teams
                WHERE team_id = %s;
                """,
                (team_id,)
            )
            team = cur.fetchone()
            if not team:
                return None

            team_data = {
                "team_id": team[0], 
                "name": team[1], 
                "abbreviation": team[2],
                "record": "N/A",  # Default until updated
                "games_played": None,
                "win_pct": None,
                "conference": None,
                "home_record": None,
                "road_record": None,
                "season": None,
                "standings_date": None
            }

            # Fetch Roster
            cur.execute(
                """
                SELECT player_id, player_name, position
                FROM roster
                WHERE team_id = %s;
                """,
                (team_id,)
            )
            team_data["roster"] = [
                {"player_id": row[0], "player_name": row[1], "position": row[2]}
                for row in cur.fetchall()
            ]

            # **Lazy Import to Prevent Circular Import**
            from app.utils import get_todays_games_and_standings  

            # Fetch Standings
            standings = get_todays_games_and_standings()

            for conf in standings.get("standings", {}):
                for team_standing in standings["standings"][conf]:
                    if team_standing["TEAM_ID"] == team_id:
                        # ✅ Extract and Store Full Standings Data
                        team_data.update({
                            "record": f"{team_standing['W']} - {team_standing['L']}",
                            "games_played": team_standing["G"],
                            "win_pct": team_standing["W_PCT"],
                            "conference": team_standing["CONFERENCE"],
                            "home_record": team_standing["HOME_RECORD"],
                            "road_record": team_standing["ROAD_RECORD"],
                            "season": team_standing["SEASON_ID"],
                            "standings_date": team_standing["STANDINGSDATE"]
                        })
                        break

            return team_data
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
        """Create the leaguedashplayerstats table with all 65 fields."""
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
                    team_abbreviation VARCHAR(10),
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
                    ftm FLOAT,
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
                    dd2 INT,
                    td3 INT,
                    gp_rank INT,
                    w_rank INT,
                    l_rank INT,
                    w_pct_rank INT,
                    min_rank INT,
                    fgm_rank INT,
                    fga_rank INT,
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
                    td3_rank INT,
                    cfid INT,
                    cfparams VARCHAR(255),
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
        """Add or update a record in the leaguedashplayerstats table with all 65 fields."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO leaguedashplayerstats (
                    player_id, player_name, season, team_id, team_abbreviation, age, gp, w, l, w_pct,
                    min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct, oreb, dreb, reb, 
                    ast, tov, stl, blk, blka, pf, pfd, pts, plus_minus, nba_fantasy_points, dd2, td3,
                    gp_rank, w_rank, l_rank, w_pct_rank, min_rank, fgm_rank, fga_rank, fg_pct_rank,
                    fg3m_rank, fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank, ft_pct_rank, oreb_rank,
                    dreb_rank, reb_rank, ast_rank, tov_rank, stl_rank, blk_rank, blka_rank, pf_rank,
                    pfd_rank, pts_rank, plus_minus_rank, nba_fantasy_points_rank, dd2_rank, td3_rank,
                    cfid, cfparams
                ) VALUES (
                    %(player_id)s, %(player_name)s, %(season)s, %(team_id)s, %(team_abbreviation)s, 
                    %(age)s, %(gp)s, %(w)s, %(l)s, %(w_pct)s, %(min)s, %(fgm)s, %(fga)s, %(fg_pct)s, 
                    %(fg3m)s, %(fg3a)s, %(fg3_pct)s, %(ftm)s, %(fta)s, %(ft_pct)s, %(oreb)s, %(dreb)s, 
                    %(reb)s, %(ast)s, %(tov)s, %(stl)s, %(blk)s, %(blka)s, %(pf)s, %(pfd)s, %(pts)s, 
                    %(plus_minus)s, %(nba_fantasy_points)s, %(dd2)s, %(td3)s, %(gp_rank)s, %(w_rank)s, 
                    %(l_rank)s, %(w_pct_rank)s, %(min_rank)s, %(fgm_rank)s, %(fga_rank)s, %(fg_pct_rank)s, 
                    %(fg3m_rank)s, %(fg3a_rank)s, %(fg3_pct_rank)s, %(ftm_rank)s, %(fta_rank)s, %(ft_pct_rank)s, 
                    %(oreb_rank)s, %(dreb_rank)s, %(reb_rank)s, %(ast_rank)s, %(tov_rank)s, %(stl_rank)s, 
                    %(blk_rank)s, %(blka_rank)s, %(pf_rank)s, %(pfd_rank)s, %(pts_rank)s, %(plus_minus_rank)s, 
                    %(nba_fantasy_points_rank)s, %(dd2_rank)s, %(td3_rank)s, %(cfid)s, %(cfparams)s
                )
                ON CONFLICT (player_id, season) DO UPDATE SET
                    team_id = EXCLUDED.team_id, team_abbreviation = EXCLUDED.team_abbreviation,
                    age = EXCLUDED.age, gp = EXCLUDED.gp, w = EXCLUDED.w, l = EXCLUDED.l, w_pct = EXCLUDED.w_pct,
                    min = EXCLUDED.min, fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, fg_pct = EXCLUDED.fg_pct,
                    fg3m = EXCLUDED.fg3m, fg3a = EXCLUDED.fg3a, fg3_pct = EXCLUDED.fg3_pct, ftm = EXCLUDED.ftm,
                    fta = EXCLUDED.fta, ft_pct = EXCLUDED.ft_pct, oreb = EXCLUDED.oreb, dreb = EXCLUDED.dreb,
                    reb = EXCLUDED.reb, ast = EXCLUDED.ast, tov = EXCLUDED.tov, stl = EXCLUDED.stl, 
                    blk = EXCLUDED.blk, blka = EXCLUDED.blka, pf = EXCLUDED.pf, pfd = EXCLUDED.pfd, 
                    pts = EXCLUDED.pts, plus_minus = EXCLUDED.plus_minus, nba_fantasy_points = EXCLUDED.nba_fantasy_points,
                    dd2 = EXCLUDED.dd2, td3 = EXCLUDED.td3, gp_rank = EXCLUDED.gp_rank, w_rank = EXCLUDED.w_rank,
                    l_rank = EXCLUDED.l_rank, w_pct_rank = EXCLUDED.w_pct_rank, min_rank = EXCLUDED.min_rank, 
                    fgm_rank = EXCLUDED.fgm_rank, fga_rank = EXCLUDED.fga_rank, fg_pct_rank = EXCLUDED.fg_pct_rank, 
                    fg3m_rank = EXCLUDED.fg3m_rank, fg3a_rank = EXCLUDED.fg3a_rank, fg3_pct_rank = EXCLUDED.fg3_pct_rank, 
                    ftm_rank = EXCLUDED.ftm_rank, fta_rank = EXCLUDED.fta_rank, ft_pct_rank = EXCLUDED.ft_pct_rank, 
                    oreb_rank = EXCLUDED.oreb_rank, dreb_rank = EXCLUDED.dreb_rank, reb_rank = EXCLUDED.reb_rank, 
                    ast_rank = EXCLUDED.ast_rank, tov_rank = EXCLUDED.tov_rank, stl_rank = EXCLUDED.stl_rank, 
                    blk_rank = EXCLUDED.blk_rank, blka_rank = EXCLUDED.blka_rank, pf_rank = EXCLUDED.pf_rank, 
                    pfd_rank = EXCLUDED.pfd_rank, pts_rank = EXCLUDED.pts_rank, plus_minus_rank = EXCLUDED.plus_minus_rank, 
                    nba_fantasy_points_rank = EXCLUDED.nba_fantasy_points_rank, dd2_rank = EXCLUDED.dd2_rank, 
                    td3_rank = EXCLUDED.td3_rank, cfid = EXCLUDED.cfid, cfparams = EXCLUDED.cfparams;
                """,
                kwargs
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
            return cur.fetchall()
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
        """Fetch all game logs for a player with opponent & home team names, date, and result."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT t1.abbreviation AS home_team_name, t2.abbreviation AS opponent_team_name, 
                    gs.game_date, gs.result, 
                    CONCAT(t1.abbreviation, ' ', gs.score, ' ', t2.abbreviation) AS formatted_score, 
                    gs.home_or_away, g.points, g.assists, g.rebounds, g.steals, 
                    g.blocks, g.turnovers, g.minutes_played, g.season
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                JOIN teams t1 ON gs.team_id = t1.team_id  
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id  
                WHERE g.player_id = %s
                ORDER BY gs.game_date DESC;
            """, (player_id,))
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)
            
    @staticmethod
    def get_game_logs_by_player_and_season(player_id, season):
        """Fetch game logs for a player in a specific season with team names."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT t1.abbreviation AS home_team_name, t2.abbreviation AS opponent_team_name, 
                    gs.game_date, gs.result, 
                    CONCAT(t1.abbreviation, ' ', gs.score, ' ', t2.abbreviation) AS formatted_score, 
                    gs.home_or_away, g.points, g.assists, g.rebounds, g.steals, 
                    g.blocks, g.turnovers, g.minutes_played, g.season
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                JOIN teams t1 ON gs.team_id = t1.team_id  
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id  
                WHERE g.player_id = %s AND g.season = %s
                ORDER BY gs.game_date DESC;
            """, (player_id, season))
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_game_logs_by_team(team_id):
        """Fetch all game logs for a specific team with formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT t1.abbreviation AS home_team_name, t2.abbreviation AS opponent_team_name, 
                    gs.game_date, gs.result, 
                    CONCAT(t1.abbreviation, ' ', gs.score, ' ', t2.abbreviation) AS formatted_score, 
                    gs.home_or_away, g.points, g.assists, g.rebounds, g.steals, 
                    g.blocks, g.turnovers, g.minutes_played, g.season
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                JOIN teams t1 ON gs.team_id = t1.team_id  
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id  
                WHERE g.team_id = %s
                ORDER BY gs.game_date DESC;
            """, (team_id,))
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)


    @staticmethod
    def get_best_game_by_points(player_id):
        """Fetch the highest-scoring game for a player with team names."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT t1.abbreviation AS home_team_name, t2.abbreviation AS opponent_team_name, 
                    gs.game_date, gs.result, 
                    CONCAT(t1.abbreviation, ' ', gs.score, ' ', t2.abbreviation) AS formatted_score, 
                    gs.home_or_away, g.points, g.assists, g.rebounds, g.steals, 
                    g.blocks, g.turnovers, g.minutes_played, g.season
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                JOIN teams t1 ON gs.team_id = t1.team_id  
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id  
                WHERE g.player_id = %s
                ORDER BY g.points DESC
                LIMIT 1;
            """, (player_id,))
            return cur.fetchone()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_last_n_games_by_player(player_id, n=10):
        """Fetch last N games for a player, including formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT t1.abbreviation AS home_team_name, t2.abbreviation AS opponent_team_name, 
                    gs.game_date, gs.result, 
                    CONCAT(t1.abbreviation, ' ', gs.score, ' ', t2.abbreviation) AS formatted_score, 
                    gs.home_or_away, g.points, g.assists, g.rebounds, g.steals, 
                    g.blocks, g.turnovers, g.minutes_played, g.season
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                JOIN teams t1 ON gs.team_id = t1.team_id  
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id  
                WHERE g.player_id = %s
                ORDER BY gs.game_date DESC
                LIMIT %s;
            """, (player_id, n))
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_game_logs_by_date_range(player_id, start_date, end_date):
        """Fetch game logs for a player within a date range with formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT t1.abbreviation AS home_team_name, t2.abbreviation AS opponent_team_name, 
                    gs.game_date, gs.result, 
                    CONCAT(t1.abbreviation, ' ', gs.score, ' ', t2.abbreviation) AS formatted_score, 
                    gs.home_or_away, g.points, g.assists, g.rebounds, g.steals, 
                    g.blocks, g.turnovers, g.minutes_played, g.season
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                JOIN teams t1 ON gs.team_id = t1.team_id  
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id  
                WHERE g.player_id = %s AND gs.game_date BETWEEN %s AND %s
                ORDER BY gs.game_date DESC;
            """, (player_id, start_date, end_date))
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)


    @staticmethod
    def get_game_logs_vs_opponent(player_id, opponent_team_id):
        """Fetch game logs for a player against a specific opponent with formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT t1.abbreviation AS home_team_name, t2.abbreviation AS opponent_team_name, 
                    gs.game_date, gs.result, 
                    CONCAT(t1.abbreviation, ' ', gs.score, ' ', t2.abbreviation) AS formatted_score, 
                    gs.home_or_away, g.points, g.assists, g.rebounds, g.steals, 
                    g.blocks, g.turnovers, g.minutes_played, g.season
                FROM gamelogs g
                JOIN game_schedule gs ON g.game_id = gs.game_id
                JOIN teams t1 ON gs.team_id = t1.team_id  
                JOIN teams t2 ON gs.opponent_team_id = t2.team_id  
                WHERE g.player_id = %s AND gs.opponent_team_id = %s
                ORDER BY gs.game_date DESC;
            """, (player_id, opponent_team_id))
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
    league_stats = LeagueDashPlayerStats.get_league_stats_by_player(player_id) or []

    # Fetch last 10 game logs
    raw_game_logs = PlayerGameLog.get_last_n_games_by_player(player_id, 10) or []

    # Define headers based on query output
    game_logs_headers = [
        "home_team_name", "opponent_abbreviation", "game_date", "result", 
        "formatted_score", "home_or_away", "points", "assists", "rebounds", 
        "steals", "blocks", "turnovers", "minutes_played", "season"
    ]

    # Convert tuples into dictionaries
    game_logs = [dict(zip(game_logs_headers, row)) for row in raw_game_logs]

    # Format game_date, minutes_played, and formatted_score
    for log in game_logs:
        if isinstance(log["game_date"], datetime):
            log["game_date"] = log["game_date"].strftime("%a %m/%d")  # Example: 'Wed 1/29'

        # Format minutes to 1 decimal place
        log["minutes_played"] = f"{float(log['minutes_played']):.1f}"

        # Format score: Remove unnecessary decimals
        if "formatted_score" in log:
            match = re.search(r"(\D+)\s(\d+\.?\d*)\s-\s(\d+\.?\d*)\s(\D+)", log["formatted_score"])
            if match:
                team1, score1, score2, team2 = match.groups()
                score1 = int(float(score1)) if float(score1).is_integer() else score1
                score2 = int(float(score2)) if float(score2).is_integer() else score2
                log["formatted_score"] = f"{team1} {score1} - {score2} {team2}"

    # Normalize league stats headers
    league_stats_headers = [
        "player_id", "Name", "Season", "Team ID", "Team ABV", "Age", "GP", "W", "L", "W %",
        "Min", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "FTM", "FTA", "FT%", "O-Reb", "D-Reb",
        "Reb", "Ast", "Tov", "Stl", "Blk", "BlkA", "PF", "PFD", "PTS", "+/-", "Fantasy Pts",
        "DD", "TD3", "GP Rank", "W Rank", "L Rank", "W% Rank", "Min Rank", "FGM Rank", "FGA Rank", 
        "FG% Rank", "3PM Rank", "3PA Rank", "3P% Rank", "FTM Rank", "FTA Rank", "FT% Rank",
        "O-Reb Rank", "D-Reb Rank", "Reb Rank", "Ast Rank", "Tov Rank", "Stl Rank", "Blk Rank", "Blka Rank",
        "PF Rank", "PFD Rank", "PTS Rank", "+/- Rank", "Fantasy Pts Rank", "DD Rank", 
        "TD3 Rank", "Conference", "College"
    ]

    return {
        "statistics": [stat.to_dict() for stat in statistics], 
        "roster": dict(zip(["team_id", "player_id", "player_name", "jersey", "position", "note", "season"], roster)) if roster else {},
        "league_stats": [normalize_row(row, league_stats_headers) for row in league_stats],  # Return all league stats
        "game_logs": game_logs,  # Now includes formatted date, minutes, and score
    }

