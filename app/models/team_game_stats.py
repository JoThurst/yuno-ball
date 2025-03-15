from db_config import get_db_connection

class TeamGameStats:
    """
    Represents a team's game-specific statistics.

    Attributes:
        game_id (str): Unique identifier for the game.
        team_id (int): Unique identifier for the team.
        opponent_team_id (int): Unique identifier for the opponent team.
        season (str): The season year (e.g., "2023-24").
        fg (int): Field Goals Made.
        fga (int): Field Goals Attempted.
        fg_pct (float): Field Goal Percentage.
        fg3 (int): Three-Point Field Goals Made.
        fg3a (int): Three-Point Attempts.
        fg3_pct (float): Three-Point Percentage.
        ft (int): Free Throws Made.
        fta (int): Free Throws Attempted.
        ft_pct (float): Free Throw Percentage.
        reb (int): Total Rebounds.
        ast (int): Assists.
        stl (int): Steals.
        blk (int): Blocks.
        tov (int): Turnovers.
        pts (int): Points Scored.
        plus_minus (float): Plus-Minus Rating.
    """

    def __init__(self, game_id, team_id, opponent_team_id, season, fg, fga, fg_pct, fg3, fg3a, fg3_pct,
                 ft, fta, ft_pct, reb, ast, stl, blk, tov, pts, plus_minus):
        self.game_id = game_id
        self.team_id = team_id
        self.opponent_team_id = opponent_team_id
        self.season = season
        self.fg = fg
        self.fga = fga
        self.fg_pct = fg_pct
        self.fg3 = fg3
        self.fg3a = fg3a
        self.fg3_pct = fg3_pct
        self.ft = ft
        self.fta = fta
        self.ft_pct = ft_pct
        self.reb = reb
        self.ast = ast
        self.stl = stl
        self.blk = blk
        self.tov = tov
        self.pts = pts
        self.plus_minus = plus_minus

    @classmethod
    def create_table(cls):
        """Create the team_game_stats table if it doesn't exist."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS team_game_stats (
                    game_id VARCHAR(20),
                    team_id INT,
                    opponent_team_id INT,
                    season VARCHAR(10),
                    fg INT,
                    fga INT,
                    fg_pct FLOAT,
                    fg3 INT,
                    fg3a INT,
                    fg3_pct FLOAT,
                    ft INT,
                    fta INT,
                    ft_pct FLOAT,
                    reb INT,
                    ast INT,
                    stl INT,
                    blk INT,
                    tov INT,
                    pts INT,
                    plus_minus FLOAT,
                    PRIMARY KEY (game_id, team_id),
                    FOREIGN KEY (team_id) REFERENCES teams(team_id),
                    FOREIGN KEY (opponent_team_id) REFERENCES teams(team_id)
                );
                
                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_team_game_stats_team_id ON team_game_stats(team_id);
                CREATE INDEX IF NOT EXISTS idx_team_game_stats_season ON team_game_stats(season);
            """)

    @classmethod
    def add_team_game_stat(cls, game_stats):
        """
        Add or update team game statistics.
        
        Args:
            game_stats (dict): Dictionary containing game statistics
            
        Returns:
            TeamGameStats: The created or updated team game statistics object
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO team_game_stats (
                    game_id, team_id, opponent_team_id, season,
                    fg, fga, fg_pct, fg3, fg3a, fg3_pct,
                    ft, fta, ft_pct, reb, ast, stl,
                    blk, tov, pts, plus_minus
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (game_id, team_id) DO UPDATE SET
                    opponent_team_id = EXCLUDED.opponent_team_id,
                    season = EXCLUDED.season,
                    fg = EXCLUDED.fg,
                    fga = EXCLUDED.fga,
                    fg_pct = EXCLUDED.fg_pct,
                    fg3 = EXCLUDED.fg3,
                    fg3a = EXCLUDED.fg3a,
                    fg3_pct = EXCLUDED.fg3_pct,
                    ft = EXCLUDED.ft,
                    fta = EXCLUDED.fta,
                    ft_pct = EXCLUDED.ft_pct,
                    reb = EXCLUDED.reb,
                    ast = EXCLUDED.ast,
                    stl = EXCLUDED.stl,
                    blk = EXCLUDED.blk,
                    tov = EXCLUDED.tov,
                    pts = EXCLUDED.pts,
                    plus_minus = EXCLUDED.plus_minus
                RETURNING *;
            """, (
                game_stats['game_id'], game_stats['team_id'],
                game_stats['opponent_team_id'], game_stats['season'],
                game_stats['fg'], game_stats['fga'], game_stats['fg_pct'],
                game_stats['fg3'], game_stats['fg3a'], game_stats['fg3_pct'],
                game_stats['ft'], game_stats['fta'], game_stats['ft_pct'],
                game_stats['reb'], game_stats['ast'], game_stats['stl'],
                game_stats['blk'], game_stats['tov'], game_stats['pts'],
                game_stats['plus_minus']
            ))
            return cls(*cur.fetchone())

    @classmethod
    def get_team_game_stats(cls, game_id, team_id):
        """
        Get team game statistics for a specific game.
        
        Args:
            game_id (str): The game ID
            team_id (int): The team ID
            
        Returns:
            TeamGameStats: The team game statistics object if found, None otherwise
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM team_game_stats
                WHERE game_id = %s AND team_id = %s;
            """, (game_id, team_id))
            result = cur.fetchone()
            return cls(*result) if result else None

    @classmethod
    def get_team_stats_for_season(cls, team_id, season):
        """
        Get all game statistics for a team in a specific season.
        
        Args:
            team_id (int): The team ID
            season (str): The season year (e.g., "2023-24")
            
        Returns:
            list: List of TeamGameStats objects for the team's games in the season
        """
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT *
                FROM team_game_stats
                WHERE team_id = %s AND season = %s
                ORDER BY game_id;
            """, (team_id, season))
            return [cls(*row) for row in cur.fetchall()]
