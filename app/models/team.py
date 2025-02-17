"""
Module for handling Team related operations and data modeling in the NBA sports analytics application.
Defines the Team class that encapsulates operations for creating, retrieving, and updating.
Team information and their corresponding rosters in a PostgreSQL database. It provides an interface to:
    - Create necessary database tables (teams and roster).
    - Add new teams and fetch existing teams by their ID or abbreviation.
    - Manage and update team rosters including adding players and clearing existing rosters.
    - Retrieve full team details such as roster information and standings data.
Team class interacts with the database through helper functions (get_connection and release_connection)
from the db_config module. Additionally, the module makes use of a lazy import to handle dependencies
(e.g., importing a utility function to fetch today’s games and standings) to prevent circular imports.
Usage:
    Import the Team class from this module and call its class methods or create instances to perform
    operations related to teams and their rosters within the application.
Note:
    It is required that the players table exists for proper foreign key reference in the roster table.
"""

from db_config import get_connection, release_connection


class Team:
    """
    Represents a sports team with its roster.

    Attributes:
        team_id (int): The unique identifier for the team.
        name (str): The name of the team.
        abbreviation (str): The team's abbreviation.
        roster (list): The list of players in the team.
    """

    def __init__(self, team_id, name, abbreviation) -> None:
        self.team_id = team_id
        self.name = name
        self.abbreviation = abbreviation
        self.roster = self.get_roster()

    @classmethod
    def create_table(cls) -> None:
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
            release_connection(conn=conn)

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
                (team_id,),
            )
            row = cur.fetchone()
            return cls(*row) if row else None
        finally:
            cur.close()
            release_connection(conn=conn)

    @classmethod
    def clear_roster(cls, team_id) -> None:
        """Remove all players from a team's roster before updating."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                DELETE FROM roster WHERE team_id = %s;
                """,
                (team_id,),
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn=conn)

    def add_to_roster(
        self, player_id, player_name, player_number, position, how_acquired, season
    ):
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
        finally:
            cur.close()
            release_connection(conn=conn)

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
                (self.team_id,),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn=conn)

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
            return [
                {"team_id": row[0], "name": row[1], "abbreviation": row[2]}
                for row in rows
            ]
        finally:
            cur.close()
            release_connection(conn=conn)

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
                (team_id,),
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
                "standings_date": None,
            }

            # Fetch Roster
            cur.execute(
                """
                SELECT player_id, player_name, position
                FROM roster
                WHERE team_id = %s;
                """,
                (team_id,),
            )
            team_data["roster"] = [
                {"player_id": row[0], "player_name": row[1], "position": row[2]}
                for row in cur.fetchall()
            ]

            # **Lazy Import to Prevent Circular Import**
            from app.utils.get.get_utils import get_todays_games_and_standings

            # Fetch Standings
            standings = get_todays_games_and_standings()

            for conf in standings.get("standings", {}):
                for team_standing in standings["standings"][conf]:
                    if team_standing["TEAM_ID"] == team_id:
                        # ✅ Extract and Store Full Standings Data
                        team_data.update(
                            {
                                "record": f"{team_standing['W']} - {team_standing['L']}",
                                "games_played": team_standing["G"],
                                "win_pct": team_standing["W_PCT"],
                                "conference": team_standing["CONFERENCE"],
                                "home_record": team_standing["HOME_RECORD"],
                                "road_record": team_standing["ROAD_RECORD"],
                                "season": team_standing["SEASON_ID"],
                                "standings_date": team_standing["STANDINGSDATE"],
                            }
                        )
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
                (abbreviation,),
            )
            result = cur.fetchone()
            return result[0] if result else None
        finally:
            cur.close()
            release_connection(conn=conn)

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
                (player_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()
            release_connection(conn=conn)
