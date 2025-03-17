from db_config import get_db_connection
from app.models.leaguedashteamstats import LeagueDashTeamStats

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

    def to_dict(self):
        """Convert team object to dictionary."""
        return {
            'team_id': self.team_id,
            'name': self.name,
            'abbreviation': self.abbreviation,
            'roster': self.roster
        }

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
                SELECT t.team_id, t.name, t.abbreviation
                FROM teams t
                WHERE t.team_id = %s;
                """,
                (team_id,),
            )
            
            team_info = cur.fetchone()
            if not team_info:
                return None
                
            # Create team dictionary
            team = {
                'team_id': team_info[0],
                'name': team_info[1],
                'abbreviation': team_info[2],
                'roster': []
            }
            
            # Get roster with DISTINCT to avoid duplicates
            cur.execute(
                """
                SELECT DISTINCT ON (r.player_id) 
                       r.player_id, r.player_name, r.player_number,
                       r.position, r.how_acquired, r.season,
                       s.points, s.rebounds, s.assists
                FROM roster r
                LEFT JOIN statistics s ON r.player_id = s.player_id
                WHERE r.team_id = %s
                ORDER BY r.player_id, r.season DESC;
                """,
                (team_id,),
            )
            
            # Process roster and statistics
            for row in cur.fetchall():
                if row[0]:  # if player_id exists
                    player = {
                        'player_id': row[0],
                        'player_name': row[1],
                        'number': row[2],
                        'position': row[3],
                        'how_acquired': row[4],
                        'season': row[5],
                        'stats': {
                            'points': row[6],
                            'rebounds': row[7],
                            'assists': row[8]
                        }
                    }
                    team['roster'].append(player)
            
            print(f"Team {team_id} roster has {len(team['roster'])} players after deduplication")
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
                SELECT r.team_id, r.season, r.position, r.player_number as jersey, r.how_acquired as note,
                       r.player_name, r.player_id
                FROM roster r
                WHERE r.player_id = %s
                ORDER BY r.season DESC
                LIMIT 1;
                """,
                (player_id,),
            )
            result = cur.fetchone()
            if result:
                return {
                    'team_id': result[0],
                    'season': result[1],
                    'position': result[2],
                    'jersey': result[3],
                    'note': result[4],
                    'player_name': result[5],
                    'player_id': result[6]
                }
            return None

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
            # Return list of dictionaries instead of Team objects
            return [{'team_id': row[0], 'name': row[1], 'abbreviation': row[2]} for row in cur.fetchall()]

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
        from app.models.leaguedashteamstats import LeagueDashTeamStats
        
        # Get team stats from LeagueDashTeamStats
        stats = LeagueDashTeamStats.get_team_stats_by_id(team_id, season)
        if not stats:
            return None
            
        return {
            'pts': stats['pts'],
            'reb': stats['reb'],
            'ast': stats['ast'],
            'stl': stats['stl'],
            'blk': stats['blk'],
            'tov': stats['tov'],
            'fg_pct': stats['fg_pct'],
            'fg3_pct': stats['fg3_pct'],
            'ft_pct': stats['ft_pct'],
            'games_played': stats['gp'],
            'off_rtg': stats['off_rtg'],
            'def_rtg': stats['def_rtg'],
            'net_rtg': stats['net_rtg'],
            'pace': stats['pace'],
            'ts_pct': stats['ts_pct']
        }

    @classmethod
    def get_team_recent_games(cls, team_id, limit=5):
        """Get recent games for a team."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from app.models.gameschedule import GameSchedule
            logger.info(f"Fetching last {limit} games for team {team_id}")
            games = GameSchedule.get_last_n_games_by_team(team_id, limit)
            logger.info(f"Found {len(games)} recent games")
            
            if not games:
                logger.warning(f"No recent games found for team {team_id}")
                return []
                
            # Get all unique team IDs from the games
            team_ids = set()
            for game in games:
                team_ids.add(game['home_team_id'])
                team_ids.add(game['away_team_id'])
            
            # Get team info for all teams
            teams = {team['team_id']: team for team in cls.get_teams_by_ids(list(team_ids))}
            
            formatted_games = []
            for game in games:
                try:
                    # For each game, we already have the team names from the JOIN in GameSchedule
                    is_home = int(game['home_team_id']) == int(team_id)
                    
                    # Get opponent info based on whether team was home or away
                    if is_home:
                        opponent_id = int(game['away_team_id'])
                        opponent = teams.get(opponent_id, {})
                        opponent_name = opponent.get('name', 'Unknown Team')
                    else:
                        opponent_id = int(game['home_team_id'])
                        opponent = teams.get(opponent_id, {})
                        opponent_name = opponent.get('name', 'Unknown Team')
                    
                    # Parse score if available
                    team_score = None
                    opponent_score = None
                    if game.get('score'):
                        scores = game['score'].split('-')
                        if len(scores) == 2:
                            team_score = scores[0].strip()
                            opponent_score = scores[1].strip()
                    
                    formatted_games.append({
                        'game_id': game['game_id'],
                        'date': game['game_date'].strftime('%Y-%m-%d'),
                        'opponent_name': opponent_name,
                        'opponent_team_id': opponent_id,
                        'is_home': is_home,
                        'result': game.get('result'),
                        'team_score': team_score,
                        'opponent_score': opponent_score
                    })
                except Exception as e:
                    logger.error(f"Error formatting game: {str(e)}")
                    logger.error(f"Game data causing error: {game}")
                    continue
                
            return formatted_games
        except Exception as e:
            logger.error(f"Error fetching recent games for team {team_id}: {str(e)}")
            logger.error(f"Full error details:", exc_info=True)
            return []

    @classmethod
    def get_team_upcoming_games(cls, team_id, limit=5):
        """Get upcoming games for a team."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from app.models.gameschedule import GameSchedule
            logger.info(f"Fetching next {limit} games for team {team_id}")
            games = GameSchedule.get_upcoming_n_games_by_team(team_id, limit)
            logger.info(f"Found {len(games)} upcoming games")
            
            if not games:
                logger.warning(f"No upcoming games found for team {team_id}")
                return []
                
            # Get all unique team IDs from the games
            team_ids = set()
            for game in games:
                team_ids.add(game['home_team_id'])
                team_ids.add(game['away_team_id'])
            
            # Get team info for all teams
            teams = {team['team_id']: team for team in cls.get_teams_by_ids(list(team_ids))}
            
            formatted_games = []
            for game in games:
                try:
                    # For each game, we already have the team names from the JOIN in GameSchedule
                    is_home = int(game['home_team_id']) == int(team_id)
                    
                    # Get opponent info based on whether team was home or away
                    if is_home:
                        opponent_id = int(game['away_team_id'])
                        opponent = teams.get(opponent_id, {})
                        opponent_name = opponent.get('name', 'Unknown Team')
                    else:
                        opponent_id = int(game['home_team_id'])
                        opponent = teams.get(opponent_id, {})
                        opponent_name = opponent.get('name', 'Unknown Team')
                    
                    formatted_games.append({
                        'game_id': game['game_id'],
                        'game_date': game['game_date'],
                        'opponent_name': opponent_name,
                        'opponent_team_id': opponent_id,
                        'is_home': is_home
                    })
                except Exception as e:
                    logger.error(f"Error formatting game: {str(e)}")
                    logger.error(f"Game data causing error: {game}")
                    continue
                
            return formatted_games
        except Exception as e:
            logger.error(f"Error fetching upcoming games for team {team_id}: {str(e)}")
            logger.error(f"Full error details:", exc_info=True)
            return []

    @classmethod
    def get_team_standings_rank(cls, team_id, season="2024-25"):
        """Get team's current rank in standings."""
        from app.models.leaguedashteamstats import LeagueDashTeamStats
        from app.utils.fetch.fetch_utils import fetch_todays_games
        
        # Get team stats from LeagueDashTeamStats
        stats = LeagueDashTeamStats.get_team_stats_by_id(team_id, season)
        if not stats:
            return None
            
        # Get conference standings from today's games data
        today_data = fetch_todays_games()
        standings = today_data.get("standings", {})
        
        # Find team in conference standings
        team_name = stats['team_name']
        conference = None
        conference_rank = None
        conference_total = None
        
        # Check East conference
        for i, team in enumerate(standings.get("East", []), 1):
            if str(team.get("TEAM_ID")) == str(team_id):
                conference = "Eastern"
                conference_rank = i
                conference_total = len(standings.get("East", []))
                break
                
        # Check West conference if not found in East
        if not conference:
            for i, team in enumerate(standings.get("West", []), 1):
                if str(team.get("TEAM_ID")) == str(team_id):
                    conference = "Western"
                    conference_rank = i
                    conference_total = len(standings.get("West", []))
                    break
        
        # Get home/away record from game schedule
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN home_or_away = 'H' AND result = 'W' THEN 1 END) as home_wins,
                    COUNT(CASE WHEN home_or_away = 'H' AND result = 'L' THEN 1 END) as home_losses,
                    COUNT(CASE WHEN home_or_away = 'A' AND result = 'W' THEN 1 END) as away_wins,
                    COUNT(CASE WHEN home_or_away = 'A' AND result = 'L' THEN 1 END) as away_losses
                FROM game_schedule
                WHERE team_id = %s AND season = %s AND result IS NOT NULL;
            """, (team_id, season))
            record = cur.fetchone()
            
        return {
            'conference': conference,
            'conference_rank': conference_rank,
            'conference_total': conference_total,
            'wins': stats['w'],
            'losses': stats['l'],
            'games_played': stats['gp'],
            'win_pct': stats['w_pct'],
            'record': f"{stats['w']}-{stats['l']}",
            'home_record': f"{record[0]}-{record[1]}" if record else None,
            'road_record': f"{record[2]}-{record[3]}" if record else None
        }
            
