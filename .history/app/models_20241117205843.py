from db_config import get_connection

# Establish connection to PostgreSQL database
conn = get_connection(schema="public")

# Create a cursor for executing SQL commands
cur = conn.cursor()


# Define the Player model
class Player:

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

    @classmethod
    def add_player(
        cls,
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
        """Add a new player to the database."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO players (player_id, name, position, weight, born_date, age, exp, school, available_seasons)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id) DO NOTHING;
            """,
            (
                player_id,
                name,
                position,
                weight,
                born_date,
                age,
                exp,
                school,
                available_seasons,
            ),
        )
        conn.commit()
        return cls(player_id, name, available_seasons, position)

    @classmethod
    def get_all_players(cls):
        """Retrieve all players from the database."""
        cur.execute(
            "SELECT player_id, name, position, weight, born_date, age, exp, school, available_seasons FROM players;"
        )
        rows = cur.fetchall()
        return [cls(*row) for row in rows]

    @classmethod
    def get_player(cls, player_id):
        """Retrieve a player by ID."""
        cur.execute(
            """
            SELECT player_id, name, position
            FROM players
            WHERE player_id = %s;
            """,
            (player_id,),
)

        row = cur.fetchone()
        if row:
            return cls(*row)
        return None

    # outdated
    @classmethod
    def update_player(
        cls, player_id, name, team, position, weight, born_date, age, exp, school
    ):
        """Update player information if it differs."""
        # Check current player data
        cur.execute(
            """
            SELECT name, team, position, weight, born_date, age, exp, school
            FROM players
            WHERE player_id = %s;
            """,
            (player_id,),
        )
        row = cur.fetchone()

        # If the player exists, compare fields and update as necessary
        if row:
            updates = []
            params = []
            fields = [
                "name",
                "team",
                "position",
                "weight",
                "born_date",
                "age",
                "exp",
                "school",
            ]
            new_data = [name, team, position, weight, born_date, age, exp, school]

            for field, current_value, new_value in zip(fields, row, new_data):
                if current_value != new_value:
                    updates.append(f"{field} = %s")
                    params.append(new_value)

            if updates:
                params.append(player_id)
                cur.execute(
                    f"""
                    UPDATE players
                    SET {", ".join(updates)}
                    WHERE player_id = %s;
                    """,
                    tuple(params),
                )
                conn.commit()
                print(f"Player {name} (ID: {player_id}) updated.")
        else:
            print(f"Player ID {player_id} not found for update.")

    @classmethod
    def player_exists(cls, player_id):
        """Check if a player exists in the database by player_id."""
        cur.execute("SELECT 1 FROM players WHERE player_id = %s;", (player_id))
        return cur.fetchone() is not None


# Define the Statistics model
class Statistics:
    def __init__(
        self, stat_id, player_id, game_date, points, rebounds, assists, steals, 
        blocks
    ):
        self.stat_id = stat_id
        self.player_id = player_id
        self.game_date = game_date
        self.points = points
        self.rebounds = rebounds
        self.assists = assists
        self.steals = steals
        self.blocks = blocks

    @classmethod
    def create_table(cls):
        """Create the statistics table if it doesn't exist."""
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS statistics (
                stat_id SERIAL PRIMARY KEY,
                player_id INT REFERENCES players(player_id),
                game_date VARCHAR(7),
                points INT,
                rebounds INT,
                assists INT,
                steals INT,
                blocks INT
            );
        """
        )
        conn.commit()

    @classmethod
    def add_stat(cls, player_id, game_date, points, rebounds, assists, steals,
                 blocks):
        """Add a new game statistic entry."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO statistics (player_id, game_date, points, rebounds, assists, steals, blocks)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING stat_id;
            """,
            (player_id, game_date, points, rebounds, assists, steals, blocks),
        )
        stat_id = cur.fetchone()[0]
        conn.commit()
        return cls(
            stat_id, player_id, game_date, points, rebounds, assists, steals, blocks
        )

    @classmethod
    def get_stats_by_player(cls, player_id):
        """Retrieve all stats for a given player."""
        cur.execute(
            "SELECT stat_id, player_id, game_date, points, rebounds, assists, steals, blocks FROM statistics WHERE player_id = %s;",
            (player_id,),
        )
        rows = cur.fetchall()
        return [cls(*row) for row in rows]

    @classmethod
    def stats_exist_for_player(cls, player_id):
        """Check if statistics for a player exist in the database."""
        cur.execute(
            "SELECT 1 FROM statistics WHERE player_id = %s LIMIT 1;", (player_id,)
        )
        return cur.fetchone() is not None

# Define the Team model
class Team:

    def __init__(self, team_id, name, abbreviation):
        self.team_id = team_id
        self.name = name
        self.abbreviation = abbreviation
        self.roster = self.get_roster()

    @classmethod
    def create_table(cls):
        """Create the teams and roster tables if they don't exist."""
        # Create teams table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                team_id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                abbreviation VARCHAR(10)
            );
        """
        )

        # Create roster table with a foreign key reference to teams and players
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

    @classmethod
    def add_team(cls, name, abbreviation):
        """Add a new team to the database."""
        cls.create_table()
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

    @classmethod
    def get_team(cls, team_id):
        """Retrieve a team by ID."""
        cur.execute(
            "SELECT team_id, name, abbreviation FROM teams WHERE team_id = %s;",
            (team_id,),
        )
        row = cur.fetchone()
        if row:
            return cls(*row)
        return None

    def add_to_roster(
        self, player_id, player_name, player_number, position, how_acquired, season
    ):
        """Add a player to the team's roster."""
        cur.execute(
            """
            INSERT INTO roster (team_id, player_id, player_name, player_number, position, how_acquired, season)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
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

    def get_roster(self):
        """Retrieve the team's roster."""
        cur.execute(
            """
            SELECT player_id, player_name, player_number FROM roster
            WHERE team_id = %s;
            """,
            (self.team_id,),
        )
        return (
            cur.fetchall()
        )  # Returns a list of tuples (player_id, player_name, player_number)


class LeagueDashPlayerStats:
    @classmethod
    def create_table(cls):
        """Create the leaguedashplayerstats table."""
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
                gp_rank INT,
                w_rank INT,
                l_rank INT,
                w_pct_rank INT,
                min_rank INT,
                fgm_rank INT,
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
                td3_rank INT
            );
        """
        )
        conn.commit()

    @classmethod
    def add_stat(cls, **kwargs):
        """Add a record to the leaguedashplayerstats table."""
        cls.create_table()
        cur.execute(
            """
            INSERT INTO leaguedashplayerstats (
                player_id, player_name,season, team_id, age, gp, w, l, w_pct, min, fgm, fga, fg_pct,
                fg3m, fg3a, fg3_pct, fta, ft_pct, oreb, dreb, reb, ast, tov, stl, blk, blka,
                pf, pfd, pts, plus_minus, nba_fantasy_points, dd, td3, gp_rank, w_rank,
                l_rank, w_pct_rank, min_rank, fgm_rank, fg_pct_rank, fg3m_rank, fg3a_rank,
                fg3_pct_rank, ftm_rank, fta_rank, ft_pct_rank, oreb_rank, dreb_rank, reb_rank,
                ast_rank, tov_rank, stl_rank, blk_rank, blka_rank, pf_rank, pfd_rank, pts_rank,
                plus_minus_rank, nba_fantasy_points_rank, dd2_rank, td3_rank
            ) VALUES (
                %(player_id)s, %(player_name)s,%(season)s, %(team_id)s, %(age)s, %(gp)s, %(w)s, %(l)s,
                %(w_pct)s, %(min)s, %(fgm)s, %(fga)s, %(fg_pct)s, %(fg3m)s, %(fg3a)s,
                %(fg3_pct)s, %(fta)s, %(ft_pct)s, %(oreb)s, %(dreb)s, %(reb)s, %(ast)s,
                %(tov)s, %(stl)s, %(blk)s, %(blka)s, %(pf)s, %(pfd)s, %(pts)s, %(plus_minus)s,
                %(nba_fantasy_points)s, %(dd)s, %(td3)s, %(gp_rank)s, %(w_rank)s, %(l_rank)s,
                %(w_pct_rank)s, %(min_rank)s, %(fgm_rank)s, %(fg_pct_rank)s, %(fg3m_rank)s,
                %(fg3a_rank)s, %(fg3_pct_rank)s, %(ftm_rank)s, %(fta_rank)s, %(ft_pct_rank)s,
                %(oreb_rank)s, %(dreb_rank)s, %(reb_rank)s, %(ast_rank)s, %(tov_rank)s,
                %(stl_rank)s, %(blk_rank)s, %(blka_rank)s, %(pf_rank)s, %(pfd_rank)s,
                %(pts_rank)s, %(plus_minus_rank)s, %(nba_fantasy_points_rank)s,
                %(dd2_rank)s, %(td3_rank)s
            );
            """,
            kwargs,
        )
        conn.commit()

    @classmethod
    def get_all_stats(cls, filters=None):
        """Fetch all stats with optional filters."""
        base_query = """
            SELECT player_id, player_name,season, team_id, age, gp, w, l, w_pct, min, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, fta, ft_pct, pts,oreb,dreb, reb, ast, tov,stl,blk,blka,pf,pfd,plus_minus,nba_fantasy_points,dd,td3,gp_rank,w_rank,l_rank,w_pct_rank, min_rank, fgm_rank, fg_pct_rank, fg3m_rank, fg3a_rank, fg3_pct_rank, ftm_rank, fta_rank, oreb_rank, dreb_rank, reb_rank, ast_rank, tov_rank, stl_rank, blk_rank,blka_rank, pts_rank, pf_rank, pfd_rank, plus_minus_rank, nba_fantasy_points_rank, dd2_rank, td3_rank
            FROM leaguedashplayerstats
        """
        conditions = []
        params = []

        # Add filters dynamically
        if filters:
            for key, value in filters.items():
                conditions.append(f"{key} = %s")
                params.append(value)

        # Finalize query with conditions
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        print(base_query)

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in rows]
