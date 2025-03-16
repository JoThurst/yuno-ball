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
                (team_id,),
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
                (team_id,),
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)

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
                    self["team_id"],
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
                (self.team_id,),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_all_teams(cls):
        """Retrieve all teams from the database with standings data."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Get base team data
            cur.execute(
                """
                SELECT team_id, name, abbreviation
                FROM teams;
                """
            )
            rows = cur.fetchall()
            teams = []
            
            # **Lazy Import to Prevent Circular Import**
            from app.utils.get.get_utils import fetch_todays_games
            from app.utils.cache_utils import get_cache, set_cache
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Try to get standings from cache first
            cache_key = "standings_data"
            standings_data = get_cache(cache_key)
            
            if not standings_data:
                logger.debug("❌ Cache MISS on standings data - Fetching fresh data")
                # Fetch standings data
                standings = fetch_todays_games()
                standings_data = {}
                
                # Create a lookup of team standings
                for conf in standings.get("standings", {}):
                    for team in standings["standings"][conf]:
                        standings_data[team["TEAM_ID"]] = {
                            "wins": team["W"],
                            "losses": team["L"],
                            "win_pct": team["W_PCT"],
                            "conference": team["CONFERENCE"],
                            "record": f"{team['W']} - {team['L']}"
                        }
                
                # Cache the standings data for 6 hours
                set_cache(cache_key, standings_data, ex=21600)
                logger.debug("✅ Cached standings data for 6 hours")
            else:
                logger.debug("✅ Cache HIT on standings data")
            
            # Combine team data with standings
            for row in rows:
                team_id, name, abbreviation = row
                team_data = {
                    "team_id": team_id,
                    "name": name,
                    "abbreviation": abbreviation
                }
                
                # Add standings data if available
                if team_id in standings_data:
                    team_data.update(standings_data[team_id])
                else:
                    # Default values if no standings data
                    team_data.update({
                        "wins": 0,
                        "losses": 0,
                        "win_pct": 0.0,
                        "conference": "East",  # Default conference
                        "record": "0 - 0"
                    })
                
                teams.append(team_data)
            
            return teams
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
            from app.utils.get.get_utils import fetch_todays_games

            # Fetch Standings
            standings = fetch_todays_games()

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
                (player_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_roster_by_team_id(cls, team_id):
        """Retrieve the roster for a specific team."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT * FROM roster WHERE team_id = %s;
                """,
                (team_id,),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)
            


    @classmethod
    def get_teams_by_ids(cls, team_ids):
        """Retrieve teams by their IDs."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT team_id, name, abbreviation
                FROM teams
                WHERE team_id = ANY(%s);
                """,
                (team_ids,),
            )
            return [{"team_id": row[0], "name": row[1], "abbreviation": row[2]} for row in cur.fetchall()]
        finally:
            cur.close()
            release_connection(conn)    

    @classmethod
    def list_all_teams(cls):
        """
        Retrieve all teams from the database without fetching standings data.
        This is a lightweight version of get_all_teams() for use in data ingestion scripts.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Get base team data
            cur.execute(
                """
                SELECT team_id, name, abbreviation
                FROM teams;
                """
            )
            rows = cur.fetchall()
            teams = []
            
            # Just return the basic team data
            for row in rows:
                team_id, name, abbreviation = row
                team_data = {
                    "team_id": team_id,
                    "name": name,
                    "full_name": name,
                    "abbreviation": abbreviation,
                }
                teams.append(team_data)
            
            return teams
        finally:
            cur.close()
            release_connection(conn)
    #Fix this
    #USE LeagueDashTeamStats table
    @classmethod
    def get_team_statistics(cls, team_id, season="2024-25"):
        """Get team statistics for a specific season."""
        
        # Import league dash team stats table
        from app.models.leaguedashteamstats import LeagueDashTeamStats
        
        # Get the team stats from the LeagueDashTeamStats model using the new method
        # Use "Totals" instead of "PerGame" since "PerGame" doesn't exist in the database
        stats = LeagueDashTeamStats.get_team_stats_by_id(team_id, season, "Totals")
        
        # Return the stats directly from the LeagueDashTeamStats model
        return stats

    @classmethod
    def get_team_recent_games(cls, team_id, limit=5):
        """Get recent games for a team."""
        from app.models.gameschedule import GameSchedule
        
        # Use the GameSchedule class method
        return GameSchedule.get_last_n_games_by_team(team_id, limit)

    @classmethod
    def get_team_upcoming_games(cls, team_id, limit=5):
        """Get upcoming games for a team."""
        from app.models.gameschedule import GameSchedule
        
        # Use the GameSchedule class method
        return GameSchedule.get_upcoming_n_games_by_team(team_id, limit)

    @classmethod
    def get_team_standings_rank(cls, team_id, season="2024-25"):
        """Get team standings rank in conference and league."""
        # This would typically query a standings table
        # For now, we'll use the standings data from fetch_todays_games
        from app.utils.fetch.fetch_utils import fetch_todays_games
        
        standings = fetch_todays_games().get("standings", {})
        
        for conf in standings:
            for i, team in enumerate(standings[conf]):
                if team["TEAM_ID"] == team_id:
                    return {
                        "conference": conf,
                        "conference_rank": i + 1,
                        "conference_total": len(standings[conf]),
                        "win_pct": team["W_PCT"],
                        "games_behind": team.get("GB", "0"),
                    }
        
        return None
            
