"""
Module: playergamelog
Defines the PlayerGameLog class which is responsible for handling the storage and retrieval of player game log data.
Includes functions to create the necessary table, insert logs in batches, and perform various queries such as retrieving logs by player, season, team, opponent, as well as fetching the best game and recent games for a given player.
Key functionalities:
- Creation of the "gamelogs" table if it does not already exist.
- Insertion of multiple game log records into the database using batch processing.
- Retrieval of game logs by player (with options to filter by season, date range, or opponent).
- Querying for a player's highest-scoring game and their last N games.
- Integration with related tables to provide enriched game log information.
Dependencies:
- Relies on the db_config module for managing database connections.
- Assumes the existence of related tables with appropriate schema for joins.
"""

from db_config import get_connection, release_connection


class PlayerGameLog:
    """Handles inserting and retrieving player game logs."""

    @staticmethod
    def create_table() -> None:
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
            release_connection(conn=conn)

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
                batch = player_game_logs[i : i + batch_size]
                values = [
                    (
                        log["PLAYER_ID"],
                        log["GAME_ID"],
                        log["TEAM_ID"],
                        log.get("PTS", 0),
                        log.get("AST", 0),
                        log.get("REB", 0),
                        log.get("STL", 0),
                        log.get("BLK", 0),
                        log.get("TO", 0),
                        log.get("MIN", "00:00"),
                        log["SEASON_YEAR"],
                    )
                    for log in batch
                ]
                cur.executemany(sql, values)
                conn.commit()
        finally:
            cur.close()
            release_connection(conn=conn)

    @staticmethod
    def get_game_logs_by_player(player_id):
        """Fetch all game logs for a player with opponent & home team names, date, and result."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
            """,
                (player_id,),
            )
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
            cur.execute(
                """
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
            """,
                (player_id, season),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn=conn)

    @staticmethod
    def get_game_logs_by_team(team_id):
        """Fetch all game logs for a specific team with formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
            """,
                (team_id,),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn=conn)

    @staticmethod
    def get_best_game_by_points(player_id):
        """Fetch the highest-scoring game for a player with team names."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
            """,
                (player_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()
            release_connection(conn=conn)

    @staticmethod
    def get_last_n_games_by_player(player_id, n=10):
        """Fetch last N games for a player, including formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
            """,
                (player_id, n),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn=conn)

    @staticmethod
    def get_game_logs_by_date_range(player_id, start_date, end_date):
        """Fetch game logs for a player within a date range with formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
            """,
                (player_id, start_date, end_date),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn=conn)

    @staticmethod
    def get_game_logs_vs_opponent(player_id, opponent_team_id):
        """Fetch game logs for a player against a specific opponent with formatted score."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
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
            """,
                (player_id, opponent_team_id),
            )
            return cur.fetchall()
        finally:
            cur.close()
            release_connection(conn=conn)
