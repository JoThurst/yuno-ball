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
from datetime import datetime, timedelta
from nba_api.stats.static import players, teams
from pprint import pprint 
from nba_api.stats.endpoints import (
    playercareerstats,
    commonteamroster,
    leaguedashplayerstats,
    commonplayerinfo,
    defensehub,
    commonallplayers,
    PlayerGameLogs,
    LeagueGameFinder,
    ScoreboardV2
)
from app.models import (
    Player, 
    Statistics, 
    Team, 
    LeagueDashPlayerStats, 
    PlayerGameLog, 
    GameSchedule
    )
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
    logger.info(f'Fetched {len(all_players)} players from NBA API.')

    for player in all_players:
        player_id = player["id"]
        time.sleep(2)  # Avoid rate-limiting issues

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
                    f"""Player {name} (ID: {player_id}) added with seasons:
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
                "Error processing player %s (ID: %s) (Pos: %s) (Weight: %s) (Age: %s) (EXP: %s) (School: %s) (Born %s):Error %s",
                player["full_name"],
                player_id,
                position,
                weight,
                age,
                exp,
                school,
                born_date,
                e,
            )

    logger.info("All players have been successfully stored.")


def fetch_and_store_player_stats(player_id):
    """
    Fetch and store career stats for a player. Updates records if they exist.
    
    Args:
        player_id (int): The unique identifier of the player.
    """
    logging.info(f"Fetching stats for player {player_id}.")

    # Ensure the statistics table exists
    Statistics.create_table()

    try:
        # Fetch player stats from NBA API
        time.sleep(1)
        career_stats = playercareerstats.PlayerCareerStats(player_id=player_id, timeout=300)
        stats_df = career_stats.get_data_frames()[0]

        # Store stats in the database
        for _, row in stats_df.iterrows():
            Statistics.add_stat(
                player_id=player_id,
                season_year=row["SEASON_ID"],
                points=row["PTS"],
                rebounds=row["REB"],
                assists=row["AST"],
                steals=row["STL"],
                blocks=row["BLK"],
            )

        logging.info(f"Stats for player {player_id} updated successfully.")

    except Exception as e:
        logging.error(f"Error fetching stats for player {player_id}: {e}")


def fetch_and_store_all_players_stats():
    """Fetch stats for all active players."""
    #all_players = players.get_active_players()
    players = Player.get_all_players()
    print(f"Found {len(players)} players in the database.")

    # Process each player
    for player in players:
        player_id = player.player_id
        print(f"Fetching Career Total Stats for player {player_id} ({player.name})...")
        fetch_and_store_player_stats(player_id=player_id)
    logger.info(f"Fetched {len(players)} active players from NBA API.")

def fetch_and_store_current_rosters():
    """Fetch and store current rosters, clearing old entries before updating."""
    teams_list = Team.get_all_teams()
    logging.info(f"Fetched {len(teams_list)} teams from NBA API.")

    for team in teams_list:
        team_id = team.team_id
        team_name = team.name
        team_abbreviation = team.abbreviation
        time.sleep(1)
        try:
            logging.info(f"Fetching roster for {team_name} (ID: {team_id})...")

            # Fetch roster for the current team
            team_roster_data = commonteamroster.CommonTeamRoster(
                team_id=team_id, timeout=600
            ).get_normalized_dict()
            team_roster = team_roster_data["CommonTeamRoster"]

            # **Step 1: Clear old roster entries for this team**
            Team.clear_roster(team_id)

            # **Step 2: Insert updated roster**
            for player in team_roster:
                player_id = player["PLAYER_ID"]
                player_name = player["PLAYER"]
                player_number = player["NUM"]  # Jersey number
                position = player["POSITION"]
                how_acquired = player["HOW_ACQUIRED"]
                season = player["SEASON"]

                # Ensure player exists in the database
                if not Player.player_exists(player_id=player_id):
                    logging.warning(f"Skipping {player_name} (ID: {player_id}): Not in database.")
                    continue

                team.add_to_roster(
                    player_id=player_id,
                    player_name=player_name,
                    player_number=player_number,
                    position=position,
                    how_acquired=how_acquired,
                    season=season,
                )

            logging.info(f"Updated roster for {team_name}.")

        except Exception as e:
            logging.error(f"Error fetching roster for {team_name} (ID: {team_id}): {e}")

    logging.info("Successfully updated all NBA rosters.")


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



def fetch_and_store_leaguedashplayer_stats(season_from, season_to):
    """Fetch and store player statistics for multiple seasons."""
    logging.info(f"Fetching league-wide player stats from {season_from} to {season_to}.")

    for season in range(int(season_from[:4]), int(season_to[:4]) + 1):
        season_string = f"{season}-{str(season + 1)[-2:]}"
        logging.info(f"Fetching stats for {season_string}...")
        time.sleep(1)
        try:
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season_string, timeout=300
            ).get_normalized_dict()["LeagueDashPlayerStats"]

            logging.info(f"Fetched {len(stats)} player stats for season {season_string}.")

            for player_stat in stats:
                LeagueDashPlayerStats.add_stat(**player_stat)

        except Exception as e:
            logging.error(f"Error fetching stats for season {season_string}: {e}")
    
    logging.info(f"Finished fetching league-wide player stats from {season_from} to {season_to}.")

def fetch_and_store_leaguedashplayer_stats_for_current_season():
    """Fetch and store player statistics for the current season."""
    current_year = datetime.now().year
    current_month = datetime.now().month
    print(current_month)
    if(current_month > 9):
        #Add a year to season string
        current_season = f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        current_season = f"{str(current_year - 1)}-{str(current_year)[-2:]}"
    
    logging.info(f"Fetching daily league-wide player stats for {current_season}.")

    try:
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season=current_season, timeout=300
        ).get_normalized_dict()["LeagueDashPlayerStats"]

        logging.info(f"Fetched {len(stats)} player stats for {current_season}.")

        for player_stat in stats:
            LeagueDashPlayerStats.add_stat(**player_stat)

    except Exception as e:
        logging.error(f"Error fetching stats for season {current_season}: {e}")

    logging.info(f"Finished updating daily league-wide player stats for {current_season}.")


def fetch_player_game_logs(player_ids, season):
    """
    Fetch game logs for players using the nba_api.

    Args:
        player_ids (list): List of player IDs.
        season (str): Season string in the format "YYYY-YY" (e.g., "2023-24").
    
    Returns:
        list: List of game log data for the players.
    """
    all_logs = []
    
    for player_id in player_ids:
        try:
            time.sleep(1)
            response = PlayerGameLogs(player_id_nullable=player_id, season_nullable=season)
            response_data = response.get_dict()

            # Access the 'resultSets' key
            result_sets = response_data.get('resultSets', [])
            if not result_sets:
                print(f"Warning: No resultSets in response for player {player_id}. Full response: {response_data}")
                continue

            # Extract rows and headers from the first result set
            rows = result_sets[0].get('rowSet', [])
            headers = result_sets[0].get('headers', [])
            if not rows:
                print(f"No rows found in response for player {player_id} in season {season}.")
                continue

            # Convert rows into dictionaries using headers
            logs = [dict(zip(headers, row)) for row in rows]
            print(f"Fetched {len(logs)} logs for player {player_id} in season {season}.")
            all_logs.extend(logs)

        except Exception as e:
            print(f"Error fetching game logs for player {player_id}: {e}")
    
    return all_logs

def fetch_and_store_schedule(season, team_ids):
    """
    Fetch and store the season game schedule for all teams.

    Args:
        season (str): Season string in "YYYY-YY" format (e.g., "2023-24").
        team_ids (list): List of team IDs to fetch schedules for.
    """
    print(f"Fetching schedule for season {season}...")
    all_games = []

    # Fetch data using LeagueGameFinder
    for team_id in team_ids:
        try:
            time.sleep(1)
            response = LeagueGameFinder(season_nullable=season, team_id_nullable=team_id)
            response_data = response.get_dict()

            if not response_data["resultSets"]:
                continue

            games = response_data["resultSets"][0]
            headers = games["headers"]
            rows = games["rowSet"]

            for row in rows:
                game = dict(zip(headers, row))
                opponent_abbreviation = game["MATCHUP"].split()[-1]
                opponent_team_id = Team.get_team_id_by_abbreviation(opponent_abbreviation)

                if opponent_team_id is None:
                    print(f"Warning: Could not find team_id for abbreviation {opponent_abbreviation}. Skipping game.")
                    continue

                # Calculate opponent score
                team_score = game.get("PTS")
                plus_minus = game.get("PLUS_MINUS")
                if team_score is not None and plus_minus is not None:
                    opponent_score = team_score - plus_minus if game.get("WL") == "W" else team_score + plus_minus
                else:
                    opponent_score = None

                all_games.append({
                    "game_id": game["GAME_ID"],
                    "season": season,
                    "team_id": game["TEAM_ID"],
                    "opponent_team_id": opponent_team_id,
                    "game_date": game["GAME_DATE"],
                    "home_or_away": "H" if "vs." in game["MATCHUP"] else "A",
                    "result": game.get("WL"),
                    "score": f"{team_score} - {opponent_score}" if team_score and opponent_score else None
                })
        except Exception as e:
            print(f"Error fetching games for team {team_id}: {e}")

    # Insert games into the database
    GameSchedule.insert_game_schedule(all_games)
    print(f"Inserted {len(all_games)} games into the database.")



def populate_schedule(season="2024-25"):
    """
    Populate the game schedule for the specified season.
    """
    GameSchedule.create_table()
    teams = Team.get_all_teams()  # Add a method to fetch all teams
    team_ids = [team.team_id for team in teams]

    fetch_and_store_schedule(season, team_ids)

    
def get_todays_games_and_standings():
    """
    Fetch today's games, conference standings, and other data from the NBA API.

    Returns:
        dict: A dictionary containing today's games, standings, and game details.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        # Fetch scoreboard data
        scoreboard = ScoreboardV2(game_date=today)
        debug_standings(scoreboard)
        # Process conference standings
        standings = {}
        for conf, data_obj in [("East", scoreboard.east_conf_standings_by_day), ("West", scoreboard.west_conf_standings_by_day)]:
            standings_data = data_obj.get_dict()
            standings_headers = standings_data["headers"]
            standings_rows = standings_data["data"]
            standings[conf] = [dict(zip(standings_headers, row)) for row in standings_rows]

        # Process games
        games_data = scoreboard.game_header.get_dict()
        game_headers = games_data["headers"]
        game_rows = games_data["data"]
        games = []

        # Fetch LineScore and LastMeeting data
        line_score_data = scoreboard.line_score.get_dict()
        line_headers = line_score_data["headers"]
        line_rows = line_score_data["data"]
        line_scores = [dict(zip(line_headers, row)) for row in line_rows]

        last_meeting_data = scoreboard.last_meeting.get_dict()
        last_headers = last_meeting_data["headers"]
        last_rows = last_meeting_data["data"]
        last_meetings = {row[0]: dict(zip(last_headers, row)) for row in last_rows}  # Map by GAME_ID

        for row in game_rows:
            game = dict(zip(game_headers, row))
            home_team = Team.get_team(game["HOME_TEAM_ID"])
            away_team = Team.get_team(game["VISITOR_TEAM_ID"])

            # Format game details
            games.append({
                "game_id": game["GAME_ID"],
                "home_team": home_team.name or "Unknown",
                "away_team": away_team.name or "Unknown",
                "game_time": game["GAME_STATUS_TEXT"],  # e.g., "7:30 pm ET"
                "arena": game.get("ARENA_NAME", "Unknown Arena"),  # Arena name
                "line_score": [
                    {
                        "team_name": ls["TEAM_NAME"],
                        "pts": ls["PTS"],
                        "fg_pct": ls["FG_PCT"],
                        "ft_pct": ls["FT_PCT"],
                        "fg3_pct": ls["FG3_PCT"],
                        "ast": ls["AST"],
                        "reb": ls["REB"],
                        "tov": ls["TOV"]
                    }
                    for ls in line_scores if ls["GAME_ID"] == game["GAME_ID"]
                ],
                "last_meeting": {
                    "date": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_DATE_EST"),
                    "home_team": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_HOME_TEAM_NAME"),
                    "home_points": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_HOME_TEAM_POINTS"),
                    "visitor_team": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_VISITOR_TEAM_NAME"),
                    "visitor_points": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_VISITOR_TEAM_POINTS")
                }
            })

        return {
            "standings": standings,
            "games": games
        }

    except Exception as e:
        print(f"Error fetching today's games and standings: {e}")
        return {"standings": {}, "games": []}


def debug_standings(scoreboard):
    """
    Debug and print standings data from the scoreboard.
    """
    print("East Conference Standings Data:")
    pprint(scoreboard.east_conf_standings_by_day.get_dict())
    print("\nWest Conference Standings Data:")
    pprint(scoreboard.west_conf_standings_by_day.get_dict())

def get_recent_seasons():
    """
    Determine the range of recent seasons to fetch data for.
    
    Returns:
        list: List of season start years (e.g., [2018, 2019, 2020, 2021, 2022]).
    """
    current_year = datetime.now().year
    return [current_year - i for i in range(5)]


def get_game_logs_for_player(player_id, season):
    """
    Fetch and insert game logs for a specific player and season.
    
    Args:
        player_id (str): The player's ID.
        season (str): Season string in the format "YYYY-YY" (e.g., "2023-24").
    """
    print(f"Fetching game logs for player: {player_id} and season: {season}")

    # Fetch game logs for the player
    player_game_logs = fetch_player_game_logs([player_id], season)

    # Debug statement to inspect returned data
    if player_game_logs:
        print(f"Retrieved {len(player_game_logs)} game logs for player {player_id}.")
    else:
        print(f"No game logs retrieved for player {player_id} in season {season}.")
        return

    # Insert logs into the database
    print(f"Inserting game logs for player {player_id}...")
    PlayerGameLog.insert_game_logs(player_game_logs)
    print(f"Successfully inserted logs for player {player_id}.")

def get_game_logs_for_all_players(season_from, season_to):
    """
    Fetch and insert game logs for all players within a specified season range.

    Args:
        season_from (str): Start season in format "YYYY-YY" (e.g., "2018-19").
        season_to (str): End season in format "YYYY-YY" (e.g., "2023-24").
    """
    logging.info(f"Fetching game logs from {season_from} to {season_to}.")
    
    # Ensure the gamelogs table exists
    PlayerGameLog.create_table()
    
    players = Player.get_all_players()
    logging.info(f"Found {len(players)} players in the database.")

    for player in players:
        player_id = player.player_id
        logging.info(f"Fetching logs for player {player_id} ({player.name})...")

        for season in range(int(season_from[:4]), int(season_to[:4]) + 1):
            season_str = f"{season}-{str(season + 1)[-2:]}"
            logging.info(f"Fetching logs for {season_str}...")
            
            player_game_logs = fetch_player_game_logs([player_id], season_str)

            if player_game_logs:
                logging.info(f"Inserting {len(player_game_logs)} logs for {player_id} in {season_str}.")
                PlayerGameLog.insert_game_logs(player_game_logs)
            else:
                logging.info(f"No logs found for {player_id} in {season_str}.")
    
    logging.info(f"Finished fetching game logs from {season_from} to {season_to}.")

def get_game_logs_for_current_season():
    """
    Fetch and insert game logs for all players in the current season.
    This is designed to be run daily to update recent game logs.
    """
    current_year = datetime.now().year
    current_month = datetime.now().month
    print(current_month)
    if(current_month > 9):
        #Add a year to season string
        current_season = f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        current_season = f"{str(current_year - 1)}-{str(current_year)[-2:]}"

    logging.info(f"Fetching daily game logs for {current_season}.")

    # Fetch players from the database
    active_players = players.get_active_players()

    for player in active_players:
        player_id = player['id']
        logging.info(f"Fetching logs for {player_id} ({player['full_name']}) in {current_season}...")

        # Fetch logs only for recent games (e.g., last 3 days)
        start_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        player_game_logs = fetch_player_game_logs([player_id], current_season)

        if player_game_logs:
            logging.info(f"Inserting {len(player_game_logs)} logs for {player_id} in {current_season}.")
            PlayerGameLog.insert_game_logs(player_game_logs)
        else:
            logging.info(f"No logs found for {player_id} in {current_season}.")
        
    logging.info(f"Finished updating game logs for {current_season}.")