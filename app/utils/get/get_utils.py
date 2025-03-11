import logging
import os
import time
import re
from datetime import datetime, timedelta
from pprint import pprint
from concurrent.futures import ThreadPoolExecutor, as_completed

from nba_api.stats.endpoints import (
    leaguedashlineups,
)
from nba_api.stats.static import players, teams
from flask import current_app as app
from app.models.player import Player
from app.models.statistics import Statistics
from app.models.team import Team
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.models.playergamelog import PlayerGameLog
from app.models.gameschedule import GameSchedule
from app.utils.process.process_utils import normalize_row, calculate_averages
from app.utils.fetch.fetch_utils import (
    fetch_and_store_schedule,
    fetch_player_game_logs,
    fetch_todays_games
)

from app.utils.config_utils import logger, API_RATE_LIMIT, MAX_WORKERS, RateLimiter
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
from tqdm import tqdm

rate_limiter = RateLimiter(max_requests=30, interval=25)  # Adjust as needed

def populate_schedule(season="2024-25"):
    """
    Populate the game schedule for the specified season using multi-threading.
    """
    GameSchedule.create_table()
    teams = Team.list_all_teams()  # Fetch all teams
    team_ids = [team["team_id"] for team in teams]

    def fetch_schedule(team_id):
        """Fetch and store schedule for a single team."""
        rate_limiter.wait_if_needed()  # ⏳ Prevent API overloading

        try:
            logger.info(f" Fetching schedule for team ID {team_id} in {season}...")
            fetch_and_store_schedule(season, [team_id])
            logger.info(f" Successfully stored schedule for team {team_id}.")

        except Exception as e:
            logger.error(f" Error fetching schedule for team {team_id}: {e}")

    # Use ThreadPoolExecutor to process teams in parallel with tqdm progress bar
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        list(tqdm(executor.map(fetch_schedule, team_ids), total=len(team_ids)))

    logger.info(f" Successfully populated the schedule for {season}.")


def get_enhanced_teams_data():
    """
    Fetch all teams and merge them with their standings and today's game details.

    Returns:
        dict: Dictionary containing teams split by conference with standings and game details.
    """
    # Fetch teams from the database
    teams = Team.get_all_teams()

    # Fetch current standings and today's games
    fresh_data = fetch_todays_games()
    standings_data = fresh_data.get("standings", {})
    games_today_data = fresh_data.get("games", [])

    # Organize teams by conference
    enhanced_teams = {"East": [], "West": []}

    for team in teams:
        team_id = team["team_id"]
        team_entry = {
            "team_id": team_id,
            "name": team["name"],
            "abbreviation": team["abbreviation"],
            "record": "N/A",
            "conference": "Unknown",
            "home_record": "N/A",
            "road_record": "N/A",
            "win_pct": "N/A",
            "plays_today": False,
            "game_info": None,
        }

        # Add standings info
        for conf in ["East", "West"]:
            for standing in standings_data.get(conf, []):
                if standing["TEAM_ID"] == team_id:
                    team_entry.update(
                        {
                            "record": f"{standing['W']} - {standing['L']}",
                            "conference": standing["CONFERENCE"],
                            "home_record": standing["HOME_RECORD"],
                            "road_record": standing["ROAD_RECORD"],
                            "win_pct": standing["W_PCT"],
                        }
                    )
                    enhanced_teams[conf].append(team_entry)
                    break

        # Check if team plays today
        for game in games_today_data:
            if team["name"] in [game["home_team"], game["away_team"]]:
                team_entry["plays_today"] = True
                team_entry["game_info"] = {
                    "opponent": (
                        game["away_team"]
                        if team["name"] == game["home_team"]
                        else game["home_team"]
                    ),
                    "game_time": game["game_time"],
                }
                break

    return enhanced_teams


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
                logging.info(
                    f"Inserting {len(player_game_logs)} logs for {player_id} in {season_str}."
                )
                PlayerGameLog.insert_game_logs(player_game_logs)
            else:
                logging.info(f"No logs found for {player_id} in {season_str}.")

    logging.info(f"Finished fetching game logs from {season_from} to {season_to}.")


def get_game_logs_for_current_season():
    """
    Fetch and insert game logs for all players in the current season using multi-threading.
    Designed to be run daily to update recent game logs.
    """
    current_year = datetime.now().year
    current_month = datetime.now().month

    if current_month > 9:
        current_season = f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        current_season = f"{str(current_year - 1)}-{str(current_year)[-2:]}"

    logging.info(f"Fetching daily game logs for {current_season}.")

    # Fetch active players from the database
    active_players = players.get_active_players()

    # Set up start and end dates (fetch logs for the last 3 days)
    start_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    def fetch_logs(player):
        """Fetch and store game logs for a single player."""
        player_id = player["id"]
        rate_limiter.wait_if_needed()  # ⏳ Rate-limit API calls

        try:
            logging.info(f"Fetching logs for {player_id} ({player['full_name']}) in {current_season}...")
            player_game_logs = fetch_player_game_logs([player_id], current_season)

            if player_game_logs:
                logging.info(f" Inserting {len(player_game_logs)} logs for {player_id} in {current_season}.")
                PlayerGameLog.insert_game_logs(player_game_logs)
            else:
                logging.info(f" No logs found for {player_id} in {current_season}.")

        except Exception as e:
            logging.error(f" Error fetching game logs for {player_id}: {e}")

    # Use ThreadPoolExecutor to process players in parallel with tqdm progress bar
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        list(tqdm(executor.map(fetch_logs, active_players), total=len(active_players)))

    logging.info(f" Finished updating game logs for {current_season}.")


def get_team_lineup_stats(team_id, season="2024-25"):
    """
    Fetch the most recent and most used starting lineups for a given team.
    
    - Most Recent Lineup: Based on the most recent game played.
    - Most Used Lineup: The lineup with the most games played (`GP`).
    - Resolves player IDs for both lineups using the Roster class.

    Args:
        team_id (int): The ID of the team.
        season (str): The NBA season (e.g., "2024-25").
    
    Returns:
        dict: Contains both the most recent lineup, most used lineup, and resolved player IDs.
    """
    # Use the create_api_endpoint function to handle proxy configuration
    response = create_api_endpoint(
        leaguedashlineups.LeagueDashLineups,
        team_id_nullable=team_id,
        season=season,
        season_type_all_star="Regular Season",
        group_quantity=5,  # Get full starting lineups
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Base",
        rank="N"
    ).get_data_frames()[0]

    if response.empty:
        return None

    # Sort by most games played (`GP`)
    sorted_by_gp = response.sort_values(by="GP", ascending=False)
    # Sort by most recent game (`MIN` as a proxy for latest game data)
    sorted_by_recent = response.sort_values(by="MIN", ascending=False)

    # Select most used & most recent lineups
    most_used_lineup = sorted_by_gp.iloc[0]
    most_recent_lineup = sorted_by_recent.iloc[0]

    # Extract player names from "GROUP_NAME"
    most_used_players = most_used_lineup["GROUP_NAME"].split(" - ")
    most_recent_players = most_recent_lineup["GROUP_NAME"].split(" - ")
    
    # Fetch the team's full roster
    team_roster = Team.get_team_with_details(team_id)["roster"]

    # Function to match player names to IDs using the Roster class
    def match_players_to_ids(player_names):
        matched_player_ids = []
        for player in team_roster:
            full_name = player["player_name"]  # Get full player name
            first_initial = full_name.split(" ")[0][0]  # First initial
            last_name = " ".join(full_name.split(" ")[1:])  # Full last name (Handles Jr., III cases)

            # Match exact name using full name comparison
            if any(f"{first_initial}. {last_name}" in name for name in player_names):
                matched_player_ids.append(player["player_id"])

        return matched_player_ids

    return {
        "most_used_lineup": {
            "team_id": most_used_lineup["TEAM_ID"],
            "team_abbreviation": most_used_lineup["TEAM_ABBREVIATION"],
            "lineup": most_used_lineup["GROUP_NAME"],
            "gp": most_used_lineup["GP"],
            "w_pct": most_used_lineup["W_PCT"],
            "pts_rank": most_used_lineup["PTS_RANK"], 
            "plus_minus_rank": most_used_lineup["PLUS_MINUS_RANK"],  
            "reb_rank": most_used_lineup["REB_RANK"],
            "ast_rank": most_used_lineup["AST_RANK"],
            "player_ids": match_players_to_ids(most_used_players),  # Attach player IDs
        },
        "most_recent_lineup": {
            "team_id": most_recent_lineup["TEAM_ID"],
            "team_abbreviation": most_recent_lineup["TEAM_ABBREVIATION"],
            "lineup": most_recent_lineup["GROUP_NAME"],
            "gp": most_recent_lineup["GP"],
            "w_pct": most_recent_lineup["W_PCT"],
            "pts_rank": most_recent_lineup["PTS_RANK"],
            "reb_rank": most_recent_lineup["REB_RANK"],
            "ast_rank": most_recent_lineup["AST_RANK"],
            "plus_minus_rank": most_recent_lineup["PLUS_MINUS_RANK"], 
            "player_ids": match_players_to_ids(most_recent_players),  # Attach player IDs
        },
    }


def get_player_data(player_id):
    """
    Consolidate player data from multiple tables for the player dashboard.
    """
    statistics = Statistics.get_stats_by_player(player_id) or []
    roster = Team.get_roster_by_player(player_id) or {}
    league_stats = LeagueDashPlayerStats.get_league_stats_by_player(player_id) or []

    # Fetch last 10 game logs
    raw_game_logs = PlayerGameLog.get_last_n_games_by_player(player_id, 10) or []

    # Define headers based on query output
    game_logs_headers = [
        "home_team_name",
        "opponent_abbreviation",
        "game_date",
        "result",
        "formatted_score",
        "home_or_away",
        "points",
        "assists",
        "rebounds",
        "steals",
        "blocks",
        "turnovers",
        "minutes_played",
        "season",
    ]

    # Convert tuples into dictionaries
    game_logs = [dict(zip(game_logs_headers, row)) for row in raw_game_logs]

    # Calculate averages
    total_games = len(game_logs)
    averages = {}
    if total_games > 0:
        averages = {
            'points_avg': sum(log['points'] for log in game_logs) / total_games,
            'rebounds_avg': sum(log['rebounds'] for log in game_logs) / total_games,
            'assists_avg': sum(log['assists'] for log in game_logs) / total_games,
            'steals_avg': sum(log['steals'] for log in game_logs) / total_games,
            'blocks_avg': sum(log['blocks'] for log in game_logs) / total_games,
            'turnovers_avg': sum(log['turnovers'] for log in game_logs) / total_games,
        }

    # Format game_date, minutes_played, and formatted_score
    for log in game_logs:
        if isinstance(log["game_date"], datetime):
            log["game_date"] = log["game_date"].strftime(
                "%a %m/%d"
            )  # Example: 'Wed 1/29'

        # Format minutes to 1 decimal place
        log["minutes_played"] = f"{float(log['minutes_played']):.1f}"

        # Format score: Remove unnecessary decimals
        if "formatted_score" in log:
            match = re.search(
                r"(\D+)\s(\d+\.?\d*)\s-\s(\d+\.?\d*)\s(\D+)", log["formatted_score"]
            )
            if match:
                team1, score1, score2, team2 = match.groups()
                score1 = int(float(score1)) if float(score1).is_integer() else score1
                score2 = int(float(score2)) if float(score2).is_integer() else score2
                log["formatted_score"] = f"{team1} {score1} - {score2} {team2}"

    # Normalize league stats headers
    league_stats_headers = [
        "player_id",
        "Name",
        "Season",
        "Team ID",
        "Team ABV",
        "Age",
        "GP",
        "W",
        "L",
        "W %",
        "Min",
        "FGM",
        "FGA",
        "FG%",
        "3PM",
        "3PA",
        "3P%",
        "FTM",
        "FTA",
        "FT%",
        "O-Reb",
        "D-Reb",
        "Reb",
        "Ast",
        "Tov",
        "Stl",
        "Blk",
        "BlkA",
        "PF",
        "PFD",
        "PTS",
        "+/-",
        "Fantasy Pts",
        "DD",
        "TD3",
        "WNBA F Pts Rank",
        "GP Rank",
        "W Rank",
        "L Rank",
        "W% Rank",
        "Min Rank",
        "FGM Rank",
        "FGA Rank",
        "FG% Rank",
        "3PM Rank",
        "3PA Rank",
        "3P% Rank",
        "FTM Rank",
        "FTA Rank",
        "FT% Rank",
        "O-Reb Rank",
        "D-Reb Rank",
        "Reb Rank",
        "Ast Rank",
        "Tov Rank",
        "Stl Rank",
        "Blk Rank",
        "Blka Rank",
        "PF Rank",
        "PFD Rank",
        "PTS Rank",
        "+/- Rank",
        "Fantasy Pts Rank",
        "DD Rank",
        "TD3 Rank",
        "WNBA F Pts Rank",
    ]

    return {
        "statistics": [stat.to_dict() for stat in statistics],
        "roster": (
            dict(
                zip(
                    [
                        "team_id",
                        "player_id",
                        "player_name",
                        "jersey",
                        "position",
                        "note",
                        "season",
                    ],
                    roster,
                )
            )
            if roster
            else {}
        ),
        "league_stats": [
            normalize_row(row, league_stats_headers) for row in league_stats
        ],  # Return all league stats
        "game_logs": game_logs, 
        "averages": averages,
    }
