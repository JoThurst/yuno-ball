from db_config import get_db_connection

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
        with get_db_connection() as conn:
            cur = conn.cursor()
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

    @classmethod
    def add_team(cls, name, abbreviation):
        """Add a new team to the database."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO teams (name, abbreviation)
                VALUES (%s, %s)
                RETURNING team_id;
                """,
                (name, abbreviation),
            )
            team_id = cur.fetchone()[0]
            return cls(team_id, name, abbreviation)

    @classmethod
    def get_team(cls, team_id):
        """Get a team by its ID."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT team_id, name, abbreviation
                FROM teams
                WHERE team_id = %s;
                """,
                (team_id,),
            )
            result = cur.fetchone()
            if result:
                return cls(*result)
            return None

    @classmethod
    def clear_roster(cls, team_id):
        """Clear all players from a team's roster."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM roster
                WHERE team_id = %s;
                """,
                (team_id,),
            )

    def add_to_roster(
        self, player_id, player_name, player_number, position, how_acquired, season
    ):
        """Add a player to the team's roster."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO roster (
                    team_id, player_id, player_name,
                    player_number, position, how_acquired, season
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (team_id, player_id, season)
                DO UPDATE SET
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

    def get_roster(self):
        """Get the team's current roster."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT player_id, player_name, player_number, position, how_acquired
                FROM roster
                WHERE team_id = %s;
                """,
                (self.team_id,),
            )
            return cur.fetchall()

    @classmethod
    def get_all_teams(cls):
        """Get all teams from the database."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT team_id, name, abbreviation FROM teams;")
            return [cls(*row) for row in cur.fetchall()]

    @classmethod
    def get_team_with_details(cls, team_id):
        """Get detailed team information including roster and statistics."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Get team info
            cur.execute(
                """
                SELECT t.team_id, t.name, t.abbreviation,
                       r.player_id, r.player_name, r.player_number,
                       r.position, r.how_acquired, r.season,
                       s.points, s.rebounds, s.assists
                FROM teams t
                LEFT JOIN roster r ON t.team_id = r.team_id
                LEFT JOIN statistics s ON r.player_id = s.player_id
                WHERE t.team_id = %s;
                """,
                (team_id,),
            )
            
            results = cur.fetchall()
            if not results:
                return None
                
            # First row contains team info
            team = cls(results[0][0], results[0][1], results[0][2])
            
            # Process roster and statistics
            roster = []
            for row in results:
                if row[3]:  # if player_id exists
                    player = {
                        'player_id': row[3],
                        'name': row[4],
                        'number': row[5],
                        'position': row[6],
                        'how_acquired': row[7],
                        'season': row[8],
                        'stats': {
                            'points': row[9],
                            'rebounds': row[10],
                            'assists': row[11]
                        }
                    }
                    roster.append(player)
            
            team.roster = roster
            return team

    @staticmethod
    def get_team_id_by_abbreviation(abbreviation):
        """Get team ID by team abbreviation."""
        with get_db_connection() as conn:
            cur = conn.cursor()
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

    @staticmethod
    def get_roster_by_player(player_id):
        """Get all roster entries for a player."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT team_id, season, position, player_number, how_acquired
                FROM roster
                WHERE player_id = %s;
                """,
                (player_id,),
            )
            return cur.fetchall()

    @classmethod
    def get_roster_by_team_id(cls, team_id):
        """Get current roster for a team."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT player_id, player_name, player_number, position, how_acquired, season
                FROM roster
                WHERE team_id = %s;
                """,
                (team_id,),
            )
            return cur.fetchall()

    @classmethod
    def get_teams_by_ids(cls, team_ids):
        """Get multiple teams by their IDs."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            placeholders = ','.join(['%s'] * len(team_ids))
            cur.execute(
                f"""
                SELECT team_id, name, abbreviation
                FROM teams
                WHERE team_id IN ({placeholders});
                """,
                tuple(team_ids),
            )
            return [cls(*row) for row in cur.fetchall()]

    @classmethod
    def list_all_teams(cls):
        """List all teams with their basic information."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT t.team_id, t.name, t.abbreviation,
                       COUNT(DISTINCT r.player_id) as roster_size,
                       AVG(s.points) as avg_points,
                       AVG(s.rebounds) as avg_rebounds,
                       AVG(s.assists) as avg_assists
                FROM teams t
                LEFT JOIN roster r ON t.team_id = r.team_id
                LEFT JOIN statistics s ON r.player_id = s.player_id
                GROUP BY t.team_id, t.name, t.abbreviation
                ORDER BY t.name;
                """
            )
            
            teams = []
            for row in cur.fetchall():
                team = {
                    'team_id': row[0],
                    'name': row[1],
                    'abbreviation': row[2],
                    'roster_size': row[3],
                    'stats': {
                        'avg_points': float(row[4]) if row[4] else 0,
                        'avg_rebounds': float(row[5]) if row[5] else 0,
                        'avg_assists': float(row[6]) if row[6] else 0
                    }
                }
                teams.append(team)
            
            return teams

    @classmethod
    def get_team_statistics(cls, team_id, season="2024-25"):
        """Get team statistics for a specific season."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT AVG(points), AVG(rebounds), AVG(assists)
                FROM statistics s
                JOIN roster r ON s.player_id = r.player_id
                WHERE r.team_id = %s AND r.season = %s;
                """,
                (team_id, season),
            )
            return cur.fetchone()

    @classmethod
    def get_team_recent_games(cls, team_id, limit=5):
        """Get recent games for a team."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT game_id, game_date, home_team_id, away_team_id, 
                       home_team_score, away_team_score
                FROM game_schedule
                WHERE (home_team_id = %s OR away_team_id = %s)
                AND game_date < CURRENT_DATE
                ORDER BY game_date DESC
                LIMIT %s;
                """,
                (team_id, team_id, limit),
            )
            return cur.fetchall()

    @classmethod
    def get_team_upcoming_games(cls, team_id, limit=5):
        """Get upcoming games for a team."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT game_id, game_date, home_team_id, away_team_id
                FROM game_schedule
                WHERE (home_team_id = %s OR away_team_id = %s)
                AND game_date >= CURRENT_DATE
                ORDER BY game_date ASC
                LIMIT %s;
                """,
                (team_id, team_id, limit),
            )
            return cur.fetchall()

    @classmethod
    def get_team_standings_rank(cls, team_id, season="2024-25"):
        """Get team's current rank in standings."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                WITH team_records AS (
                    SELECT 
                        t.team_id,
                        COUNT(CASE WHEN 
                            (gs.home_team_id = t.team_id AND gs.home_team_score > gs.away_team_score) OR
                            (gs.away_team_id = t.team_id AND gs.away_team_score > gs.home_team_score)
                        THEN 1 END) as wins,
                        COUNT(*) as games_played
                    FROM teams t
                    JOIN game_schedule gs ON t.team_id IN (gs.home_team_id, gs.away_team_id)
                    WHERE gs.season = %s AND gs.game_date < CURRENT_DATE
                    GROUP BY t.team_id
                ),
                ranked_teams AS (
                    SELECT 
                        team_id,
                        wins,
                        games_played,
                        RANK() OVER (ORDER BY CAST(wins AS FLOAT) / NULLIF(games_played, 0) DESC) as rank
                    FROM team_records
                )
                SELECT rank, wins, games_played
                FROM ranked_teams
                WHERE team_id = %s;
                """,
                (season, team_id),
            )
            return cur.fetchone()
            
