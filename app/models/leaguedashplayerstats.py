from db_config import get_connection, release_connection

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
                    nba_fantasy_pts FLOAT,
                    dd2 INT,
                    td3 INT,
                    wnba_fantasy_pts FLOAT,
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
                    nba_fantasy_pts_rank INT,
                    dd2_rank INT,
                    td3_rank INT,
                    wnba_fantasy_pts_rank INT,
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
                    ast, tov, stl, blk, blka, pf, pfd, pts, plus_minus, nba_fantasy_pts, dd2, td3, wnba_fantasy_pts,
                    gp_rank, w_rank, l_rank, w_pct_rank, min_rank, fgm_rank, fga_rank, fg_pct_rank,
                    fg3m_rank, fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank, ft_pct_rank, oreb_rank,
                    dreb_rank, reb_rank, ast_rank, tov_rank, stl_rank, blk_rank, blka_rank, pf_rank,
                    pfd_rank, pts_rank, plus_minus_rank, nba_fantasy_pts_rank, dd2_rank, td3_rank,
                    wnba_fantasy_pts_rank
                ) VALUES (
                    %(player_id)s, %(player_name)s, %(season)s, %(team_id)s, %(team_abbreviation)s, 
                    %(age)s, %(gp)s, %(w)s, %(l)s, %(w_pct)s, %(min)s, %(fgm)s, %(fga)s, %(fg_pct)s, 
                    %(fg3m)s, %(fg3a)s, %(fg3_pct)s, %(ftm)s, %(fta)s, %(ft_pct)s, %(oreb)s, %(dreb)s, 
                    %(reb)s, %(ast)s, %(tov)s, %(stl)s, %(blk)s, %(blka)s, %(pf)s, %(pfd)s, %(pts)s, 
                    %(plus_minus)s, %(nba_fantasy_pts)s, %(dd2)s, %(td3)s, %(wnba_fantasy_pts)s, %(gp_rank)s, %(w_rank)s, 
                    %(l_rank)s, %(w_pct_rank)s, %(min_rank)s, %(fgm_rank)s, %(fga_rank)s, %(fg_pct_rank)s, 
                    %(fg3m_rank)s, %(fg3a_rank)s, %(fg3_pct_rank)s, %(ftm_rank)s, %(fta_rank)s, %(ft_pct_rank)s, 
                    %(oreb_rank)s, %(dreb_rank)s, %(reb_rank)s, %(ast_rank)s, %(tov_rank)s, %(stl_rank)s, 
                    %(blk_rank)s, %(blka_rank)s, %(pf_rank)s, %(pfd_rank)s, %(pts_rank)s, %(plus_minus_rank)s, 
                    %(nba_fantasy_pts_rank)s, %(dd2_rank)s, %(td3_rank)s, %(wnba_fantasy_pts_rank)s
                )
                ON CONFLICT (player_id, season) DO UPDATE SET
                    team_id = EXCLUDED.team_id, team_abbreviation = EXCLUDED.team_abbreviation,
                    age = EXCLUDED.age, gp = EXCLUDED.gp, w = EXCLUDED.w, l = EXCLUDED.l, w_pct = EXCLUDED.w_pct,
                    min = EXCLUDED.min, fgm = EXCLUDED.fgm, fga = EXCLUDED.fga, fg_pct = EXCLUDED.fg_pct,
                    fg3m = EXCLUDED.fg3m, fg3a = EXCLUDED.fg3a, fg3_pct = EXCLUDED.fg3_pct, ftm = EXCLUDED.ftm,
                    fta = EXCLUDED.fta, ft_pct = EXCLUDED.ft_pct, oreb = EXCLUDED.oreb, dreb = EXCLUDED.dreb,
                    reb = EXCLUDED.reb, ast = EXCLUDED.ast, tov = EXCLUDED.tov, stl = EXCLUDED.stl, 
                    blk = EXCLUDED.blk, blka = EXCLUDED.blka, pf = EXCLUDED.pf, pfd = EXCLUDED.pfd, 
                    pts = EXCLUDED.pts, plus_minus = EXCLUDED.plus_minus, nba_fantasy_pts = EXCLUDED.nba_fantasy_pts,
                    dd2 = EXCLUDED.dd2, td3 = EXCLUDED.td3, wnba_fantasy_pts = EXCLUDED.wnba_fantasy_pts, gp_rank = EXCLUDED.gp_rank, w_rank = EXCLUDED.w_rank,
                    l_rank = EXCLUDED.l_rank, w_pct_rank = EXCLUDED.w_pct_rank, min_rank = EXCLUDED.min_rank, 
                    fgm_rank = EXCLUDED.fgm_rank, fga_rank = EXCLUDED.fga_rank, fg_pct_rank = EXCLUDED.fg_pct_rank, 
                    fg3m_rank = EXCLUDED.fg3m_rank, fg3a_rank = EXCLUDED.fg3a_rank, fg3_pct_rank = EXCLUDED.fg3_pct_rank, 
                    ftm_rank = EXCLUDED.ftm_rank, fta_rank = EXCLUDED.fta_rank, ft_pct_rank = EXCLUDED.ft_pct_rank, 
                    oreb_rank = EXCLUDED.oreb_rank, dreb_rank = EXCLUDED.dreb_rank, reb_rank = EXCLUDED.reb_rank, 
                    ast_rank = EXCLUDED.ast_rank, tov_rank = EXCLUDED.tov_rank, stl_rank = EXCLUDED.stl_rank, 
                    blk_rank = EXCLUDED.blk_rank, blka_rank = EXCLUDED.blka_rank, pf_rank = EXCLUDED.pf_rank, 
                    pfd_rank = EXCLUDED.pfd_rank, pts_rank = EXCLUDED.pts_rank, plus_minus_rank = EXCLUDED.plus_minus_rank, 
                    nba_fantasy_pts_rank = EXCLUDED.nba_fantasy_pts_rank, dd2_rank = EXCLUDED.dd2_rank, 
                    td3_rank = EXCLUDED.td3_rank, wnba_fantasy_pts_rank = EXCLUDED.wnba_fantasy_pts_rank;
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
            return [
                dict(zip([desc[0] for desc in cur.description], row)) for row in rows
            ]
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def get_league_stats_by_player(player_id):
        """Fetch league stats for a specific player."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM leaguedashplayerstats WHERE player_id = %s;",
                (player_id,),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn)
