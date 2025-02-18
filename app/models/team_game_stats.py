from db_config import get_connection, release_connection

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
        """Create the `team_game_stats` table with game_date."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS team_game_stats (
                    game_id VARCHAR NOT NULL,
                    team_id BIGINT NOT NULL,
                    opponent_team_id BIGINT NOT NULL REFERENCES teams(team_id),
                    season VARCHAR(10) NOT NULL,
                    game_date DATE NOT NULL,  -- 🔥 Added game_date
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
                    FOREIGN KEY (game_id, team_id) REFERENCES game_schedule (game_id, team_id) ON DELETE CASCADE
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)


    @classmethod
    def add_team_game_stat(cls, game_stats):
        """
        Insert or update team game statistics in the database.

        Parameters:
            game_stats (dict): Dictionary containing team game statistics.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            sql = """
                INSERT INTO team_game_stats (
                    game_id, team_id, opponent_team_id, season, game_date, fg, fga, fg_pct, fg3, fg3a, fg3_pct, 
                    ft, fta, ft_pct, reb, ast, stl, blk, tov, pts, plus_minus
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id, team_id) DO UPDATE SET
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
                    plus_minus = EXCLUDED.plus_minus,
                    game_date = EXCLUDED.game_date;  -- 🔥 Ensure `game_date` updates
            """
            values = (
                game_stats["game_id"],
                game_stats["team_id"],
                game_stats["opponent_team_id"],
                game_stats["season"],
                game_stats["game_date"],  # 🔥 Include game_date
                game_stats["fg"],
                game_stats["fga"],
                game_stats["fg_pct"],
                game_stats["fg3"],
                game_stats["fg3a"],
                game_stats["fg3_pct"],
                game_stats["ft"],
                game_stats["fta"],
                game_stats["ft_pct"],
                game_stats["reb"],
                game_stats["ast"],
                game_stats["stl"],
                game_stats["blk"],
                game_stats["tov"],
                game_stats["pts"],
                game_stats["plus_minus"]
            )
            cur.execute(sql, values)
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)


    @classmethod
    def get_team_game_stats(cls, game_id, team_id):
        """
        Retrieve team game statistics by game ID and team ID.

        Parameters:
            game_id (str): The game identifier.
            team_id (int): The team identifier.

        Returns:
            dict: Team game statistics or None if not found.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT * FROM team_game_stats
                WHERE game_id = %s AND team_id = %s;
                """,
                (game_id, team_id),
            )
            row = cur.fetchone()
            if row:
                return {
                    "game_id": row[0],
                    "team_id": row[1],
                    "opponent_team_id": row[2],
                    "season": row[3],
                    "fg": row[4],
                    "fga": row[5],
                    "fg_pct": row[6],
                    "fg3": row[7],
                    "fg3a": row[8],
                    "fg3_pct": row[9],
                    "ft": row[10],
                    "fta": row[11],
                    "ft_pct": row[12],
                    "reb": row[13],
                    "ast": row[14],
                    "stl": row[15],
                    "blk": row[16],
                    "tov": row[17],
                    "pts": row[18],
                    "plus_minus": row[19],
                }
            return None
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_team_stats_for_season(cls, team_id, season):
        """
        Retrieve all game stats for a team in a specific season.

        Parameters:
            team_id (int): The team identifier.
            season (str): The season (e.g., "2023-24").

        Returns:
            list: A list of dictionaries with game stats.
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT * FROM team_game_stats
                WHERE team_id = %s AND season = %s;
                """,
                (team_id, season),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)
