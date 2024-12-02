"""
NBA Data Fetching and Storage Module.

This module provides functions to fetch NBA player information, player
statistics, team rosters, and league-wide player statistics from the NBA API
and store them into a PostgreSQL database using the application's models.

Functions:
    fetch_and_store_players()
    fetch_and_store_player_stats(player_id)
    fetch_and_store_current_rosters()
    fetch_and_store_all_players_stats()
    update_player_teams()
    fetch_and_store_leaguedashplayer_stats()
"""

import os
import time
import logging
from datetime import datetime
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playercareerstats,
    commonteamroster,
    leaguedashplayerstats,
    commonplayerinfo,
)
from app.models import Player, Statistics, Team, LeagueDashPlayerStats
from db_config import get_connection

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "nba_data_module.log")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)],
)

logger = logging.getLogger(__name__)

# Establish connection to PostgreSQL database
conn = get_connection(schema=os.getenv("DB_SCHEMA", "public"))
# Create a cursor for executing SQL commands
cur = conn.cursor()


def fetch_and_store_players():
    """Fetch all NBA players and store them in the players table."""
    # Define the range of seasons we are storing
    valid_seasons = [f"{year}-{(year + 1) % 100:02d}" for year in range(2015, 2025)]

    # Fetch all players
    all_players = players.get_players()
    logger.info("Fetched {len(all_players)} players from NBA API.")

    for player in all_players:
        player_id = player["id"]
        time.sleep(5)  # Avoid rate-limiting issues

        try:
            # Fetch player info using the API
            cplayerinfo_obj = commonplayerinfo.CommonPlayerInfo(
                player_id=player_id, timeout=300
            )
            # First DataFrame is CommonPlayerInfo
            cplayerinfo_data = cplayerinfo_obj.get_data_frames()[0].iloc[0]

            # Extract and calculate data
            from_year = int(cplayerinfo_data["FROM_YEAR"])
            to_year = int(cplayerinfo_data["TO_YEAR"])
            name = player["full_name"]
            position = cplayerinfo_data.get("POSITION", "Unknown")
            weight = (
                int(cplayerinfo_data.get("WEIGHT", 0))
                if cplayerinfo_data.get("WEIGHT")
                else None
            )
            born_date = cplayerinfo_data.get("BIRTHDATE", None)
            exp = (
                int(cplayerinfo_data.get("SEASON_EXP", 0))
                if cplayerinfo_data.get("SEASON_EXP")
                else None
            )
            school = cplayerinfo_data.get("SCHOOL", None)

            # Calculate age
            age = None
            if born_date:
                born_date_obj = datetime.strptime(born_date.split("T")[0], "%Y-%m-%d")
                age = datetime.now().year - born_date_obj.year

            # Calculate available seasons within the valid range
            available_seasons = [
                season
                for season in valid_seasons
                if from_year <= int(season[:4]) <= to_year
            ]

            if available_seasons:
                # Add player to the database
                Player.add_player(
                    player_id=int(player_id),  # Ensure player_id is Python int
                    name=name,
                    position=position,
                    weight=weight,
                    born_date=born_date,
                    age=age,
                    exp=exp,
                    school=school,
                    available_seasons=",".join(available_seasons),
                    # Store as comma-separated string
                )
                logger.info(
                    """Player {name} (ID: {player_id}) added with seasons:
                    {available_seasons}."""
                )
            else:
                logger.warning(
                    "Player %s (ID: %s) has no valid seasons in the range.",
                    name,
                    player_id,
                )
        except Exception as e:
            logger.error(
                "Error processing player %s (ID: %s): %s",
                player["full_name"],
                player_id,
                e,
            )

    logger.info("All players have been successfully stored.")


def fetch_and_store_player_stats(player_id):
    """
    Fetch and store career stats for a player if not already in the database.

    Args:
        player_id (int): The unique identifier of the player.
    """
    # Ensure the statistics table exists
    Statistics.create_table()

    if Statistics.stats_exist_for_player(player_id):
        logger.info("Stats for player %s already exist. Skipping API call.", player_id)
        return

    retries = 3  # Number of retries
    delay = 2  # Initial delay between retries in seconds

    for attempt in range(retries):
        try:
            # Fetch player stats from NBA API
            time.sleep(10)
            career_stats = playercareerstats.PlayerCareerStats(
                player_id=player_id, timeout=300
            )

            stats_df = career_stats.get_data_frames()[0]

            # Store stats in database
            for _, row in stats_df.iterrows():
                Statistics.add_stat(
                    player_id=player_id,
                    game_date=row["SEASON_ID"],
                    points=row["PTS"],
                    rebounds=row["REB"],
                    assists=row["AST"],
                    steals=row["STL"],
                    blocks=row["BLK"],
                )

            logger.info("Stats for player {player_id} stored successfully.")
            break  # Exit loop if successful

        except Exception as e:
            logger.error("Error fetching stats for player %s: %s", player_id, e)
            if attempt < retries - 1:
                # Only retry if attempts are left
                logger.info("Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(
                    "Failed to fetch stats for player %s after %s attempts.",
                    player_id,
                    retries,
                )


def fetch_and_store_current_rosters():
    """Fetch and store roster information for current NBA teams."""
    teams_list = teams.get_teams()
    logger.info("Fetched {len(teams_list)} teams from NBA API.")

    for team in teams_list:
        team_id = team["id"]
        team_name = team["full_name"]
        team_abbreviation = team["abbreviation"]

        # Create or retrieve the team in the database
        team_obj = Team.add_team(name=team_name, abbreviation=team_abbreviation)
        logger.info(
            "Added %s with ID: %s. Sleeping for 15 seconds.", team_name, team_id
        )
        time.sleep(15)

        try:
            # Fetch the roster for this team
            team_roster_data = commonteamroster.CommonTeamRoster(
                team_id=team_id, timeout=600
            ).get_normalized_dict()
            team_roster = team_roster_data["CommonTeamRoster"]

            logger.info(
                "Fetched roster for team %s with %s players.",
                team_name,
                len(team_roster),
            )

            # Add each player in the roster to the team
            for player in team_roster:
                time.sleep(1)
                player_id = player["PLAYER_ID"]
                player_name = player["PLAYER"]
                player_number = player["NUM"]  # Jersey number
                position = player["POSITION"]
                how_acquired = player["HOW_ACQUIRED"]
                season = player["SEASON"]

                # Player Data
                weight = player.get("WEIGHT", 0)
                born_date = player.get("BIRTH_DATE", "Unknown")
                age = player.get("AGE", 0)
                exp = player.get("EXP", "0")
                if exp == "R":
                    exp = 0
                elif exp.isdigit():
                    exp = int(exp)
                else:
                    exp = 0

                school = player.get("SCHOOL", "Unknown")

                logger.info("Processing player %s (ID: %s).", player_name, player_id)
                parsed_age = age_parser(age)
                if not Player.player_exists(player_id=player_id):
                    Player.add_player(
                        player_id=int(player_id),
                        name=player_name,
                        position=position,
                        weight=weight,
                        born_date=born_date,
                        age=parsed_age,
                        exp=exp,
                        school=school,
                        available_seasons="Unknown",
                    )

                    # Add player to the team's roster in the database
                    team_obj.add_to_roster(
                        player_id=player_id,
                        player_name=player_name,
                        player_number=player_number,
                        position=position,
                        how_acquired=how_acquired,
                        season=season,
                    )

        except Exception as e:
            logger.error(
                "Error fetching roster for team %s (ID: %s): %s", team_name, team_id, e
            )

    logger.info(
        """All current NBA teams and their rosters have been
                successfully stored."""
    )


def age_parser(age):
    """
    Parses the given age value and returns it as an integer if valid.

    This function checks if the input `age` is a string containing
    only digits. If so, it converts the string to an integer and
    returns it. Otherwise, it returns `None`.

    Args:
        age (str | int): The age value to parse. Typically expected to be
            a string representing a number.

    Returns:
        int | None: The parsed age as an integer if valid, or `None` if
            the input is not a valid age string.
    """
    parsed_age = int(age) if isinstance(age, str) and age.isdigit() else None
    return parsed_age


def fetch_and_store_all_players_stats():
    """Fetch stats for all active players."""
    all_players = players.get_active_players()
    logger.info("Fetched {len(all_players)} active players from NBA API.")

    for player in all_players:
        fetch_and_store_player_stats(player["id"])
    logger.info("All active player statistics have been successfully stored.")


def fetch_and_store_leaguedashplayer_stats():
    """Fetch and store player statistics for the last 10 seasons."""
    for season in range(2015, 2025):  # Last 10 seasons
        season_string = f"{season}-{(season + 1) % 100:02d}"
        logger.info("Fetching stats for season {season_string}...")

        time.sleep(10)  # Pause to avoid rate limits
        try:
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season_string, timeout=300
            ).get_normalized_dict()["LeagueDashPlayerStats"]

            logger.info(
                """Fetched %s player stats for season
                        %s.""",
                len(stats),
                season_string,
            )

            for player_stat in stats:
                player_id = player_stat["PLAYER_ID"]
                if not Player.player_exists(player_id):
                    logger.info(
                        "Player %s is not in database. Adding.",
                        player_stat["PLAYER_NAME"],
                    )
                    Player.add_player(
                        player_id=int(player_id),
                        name=player_stat["PLAYER_NAME"],
                        position="Unknown",
                        weight=0,
                        born_date="Unknown",
                        age=(
                            int(player_stat["AGE"])
                            if player_stat["AGE"].isdigit()
                            else None
                        ),
                        exp=0,
                        school="Unknown",
                        available_seasons="Unknown",
                    )

                LeagueDashPlayerStats.add_stat(
                    player_id=player_id,
                    player_name=player_stat["PLAYER_NAME"],
                    season=season_string,
                    team_id=player_stat["TEAM_ID"],
                    age=player_stat["AGE"],
                    gp=player_stat["GP"],
                    w=player_stat["W"],
                    l=player_stat["L"],
                    w_pct=player_stat["W_PCT"],
                    min=player_stat["MIN"],
                    fgm=player_stat["FGM"],
                    fga=player_stat["FGA"],
                    fg_pct=player_stat["FG_PCT"],
                    fg3m=player_stat["FG3M"],
                    fg3a=player_stat["FG3A"],
                    fg3_pct=player_stat["FG3_PCT"],
                    fta=player_stat["FTA"],
                    ft_pct=player_stat["FT_PCT"],
                    oreb=player_stat["OREB"],
                    dreb=player_stat["DREB"],
                    reb=player_stat["REB"],
                    ast=player_stat["AST"],
                    tov=player_stat["TOV"],
                    stl=player_stat["STL"],
                    blk=player_stat["BLK"],
                    blka=player_stat["BLKA"],
                    pf=player_stat["PF"],
                    pfd=player_stat["PFD"],
                    pts=player_stat["PTS"],
                    plus_minus=player_stat["PLUS_MINUS"],
                    nba_fantasy_points=player_stat["NBA_FANTASY_PTS"],
                    dd=player_stat["DD2"],
                    td3=player_stat["TD3"],
                    gp_rank=player_stat["GP_RANK"],
                    w_rank=player_stat["W_RANK"],
                    l_rank=player_stat["L_RANK"],
                    w_pct_rank=player_stat["W_PCT_RANK"],
                    min_rank=player_stat["MIN_RANK"],
                    fgm_rank=player_stat["FGM_RANK"],
                    fg_pct_rank=player_stat["FG_PCT_RANK"],
                    fg3m_rank=player_stat["FG3M_RANK"],
                    fg3a_rank=player_stat["FG3A_RANK"],
                    fg3_pct_rank=player_stat["FG3_PCT_RANK"],
                    ftm_rank=player_stat["FTM_RANK"],
                    fta_rank=player_stat["FTA_RANK"],
                    ft_pct_rank=player_stat["FT_PCT_RANK"],
                    oreb_rank=player_stat["OREB_RANK"],
                    dreb_rank=player_stat["DREB_RANK"],
                    reb_rank=player_stat["REB_RANK"],
                    ast_rank=player_stat["AST_RANK"],
                    tov_rank=player_stat["TOV_RANK"],
                    stl_rank=player_stat["STL_RANK"],
                    blk_rank=player_stat["BLK_RANK"],
                    blka_rank=player_stat["BLKA_RANK"],
                    pf_rank=player_stat["PF_RANK"],
                    pfd_rank=player_stat["PFD_RANK"],
                    pts_rank=player_stat["PTS_RANK"],
                    plus_minus_rank=player_stat["PLUS_MINUS_RANK"],
                    nba_fantasy_points_rank=(player_stat["NBA_FANTASY_PTS_RANK"]),
                    dd2_rank=player_stat["DD2_RANK"],
                    td3_rank=player_stat["TD3_RANK"],
                )
            logger.info("Stats for season %s stored successfully.", season_string)
        except Exception as e:
            logger.error("Error fetching stats for season %s: %s", season_string, e)
