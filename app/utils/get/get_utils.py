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
from app.models.team_sqlalchemy import TeamORM
from app.database import get_db_context
from app.utils.process.process_utils import normalize_row, calculate_averages
from app.utils.fetch.fetch_utils import (
    fetch_todays_games
)


from app.utils.config_utils import logger, API_RATE_LIMIT, MAX_WORKERS, RateLimiter
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
from tqdm import tqdm

rate_limiter = RateLimiter(max_requests=30, interval=25)  # Adjust as needed


def get_enhanced_teams_data():
    """
    Fetch all teams and merge them with their standings and today's game details.

    Returns:
        dict: Dictionary containing teams split by conference with standings and game details.
    """
    # Helper utilities local to this function
    def normalize_conference(label):
        if not label:
            return None
        value = str(label).strip().lower()
        if value.startswith("east"):
            return "East"
        if value.startswith("west"):
            return "West"
        return label

    def format_record(wins, losses):
        try:
            return f"{int(wins)} - {int(losses)}"
        except (TypeError, ValueError):
            return "N/A"

    def format_win_pct(value):
        if value in (None, ""):
            return "N/A"
        try:
            pct = float(value)
            return f"{pct:.3f}".lstrip("0")
        except (TypeError, ValueError):
            return value

    # Fetch teams from the database for supplemental metadata using ORM
    with get_db_context() as db:
        teams_orm = TeamORM.get_all(db)
        # Convert to dict format for compatibility
        team_lookup = {}
        for team in teams_orm:
            team_dict = {
                'team_id': team.team_id,
                'name': team.name,
                'abbreviation': team.abbreviation
            }
            team_lookup[str(team.team_id)] = team_dict

    # Fetch current standings and today's games
    fresh_data = fetch_todays_games()
    standings_data = fresh_data.get("standings") or {}
    games_today_data = fresh_data.get("games") or []

    # Quick lookup for today's games by team_id
    games_by_team_id = {}
    for game in games_today_data:
        for key in ("home_team_id", "away_team_id"):
            team_id = game.get(key)
            if team_id is not None:
                games_by_team_id.setdefault(str(team_id), []).append(game)

    enhanced_teams = {"East": [], "West": []}
    processed_team_ids = set()

    for raw_conf, standings_list in standings_data.items():
        normalized_conf = normalize_conference(raw_conf) or "Unknown"
        if normalized_conf not in enhanced_teams:
            enhanced_teams[normalized_conf] = []

        for standing in standings_list or []:
            team_id = standing.get("TEAM_ID")
            if team_id is None:
                continue

            team_key = str(team_id)
            processed_team_ids.add(team_key)
            team_meta = team_lookup.get(team_key, {})

            wins = standing.get("W")
            losses = standing.get("L")
            win_pct_value = standing.get("W_PCT")
            home_record = standing.get("HOME_RECORD", "N/A")
            road_record = standing.get("ROAD_RECORD", "N/A")

            team_entry = {
                "team_id": team_meta.get("team_id", team_id),
                "name": team_meta.get("name", standing.get("TEAM", "Unknown Team")),
                "abbreviation": team_meta.get("abbreviation", team_meta.get("name", "UNK")),
                "record": format_record(wins, losses),
                "conference": normalize_conference(standing.get("CONFERENCE")) or normalized_conf,
                "home_record": home_record if home_record else "N/A",
                "road_record": road_record if road_record else "N/A",
                "win_pct": format_win_pct(win_pct_value),
                "plays_today": False,
                "game_info": None,
            }

            if "stats" in team_meta:
                team_entry["stats"] = team_meta["stats"]

            games_for_team = games_by_team_id.get(team_key, [])
            if games_for_team:
                game_today = games_for_team[0]
                is_home = str(game_today.get("home_team_id")) == team_key
                opponent_name = (
                    game_today.get("away_team") if is_home else game_today.get("home_team")
                )
                team_entry["plays_today"] = True
                team_entry["game_info"] = {
                    "opponent": opponent_name,
                    "game_time": game_today.get("game_time", "TBD"),
                }

            enhanced_teams.setdefault(normalized_conf, []).append(team_entry)

    # Handle teams missing from standings data (should be rare)
    if len(processed_team_ids) < len(team_lookup):
        missing_team_ids = [
            team_id for team_id in team_lookup.keys() if team_id not in processed_team_ids
        ]
        if missing_team_ids:
            logger.debug(
                "get_enhanced_teams_data: %d teams missing in standings response, assigning fallback conference buckets",
                len(missing_team_ids),
            )
        for team_key in missing_team_ids:
            team_meta = team_lookup[team_key]
            fallback_conf = (
                "East"
                if len(enhanced_teams.get("East", []))
                <= len(enhanced_teams.get("West", []))
                else "West"
            )
            fallback_entry = {
                "team_id": team_meta["team_id"],
                "name": team_meta["name"],
                "abbreviation": team_meta["abbreviation"],
                "record": "N/A",
                "conference": fallback_conf,
                "home_record": "N/A",
                "road_record": "N/A",
                "win_pct": "N/A",
                "plays_today": False,
                "game_info": None,
            }

            games_for_team = games_by_team_id.get(team_key, [])
            if games_for_team:
                game_today = games_for_team[0]
                is_home = str(game_today.get("home_team_id")) == team_key
                opponent_name = (
                    game_today.get("away_team") if is_home else game_today.get("home_team")
                )
                fallback_entry["plays_today"] = True
                fallback_entry["game_info"] = {
                    "opponent": opponent_name,
                    "game_time": game_today.get("game_time", "TBD"),
                }

            enhanced_teams.setdefault(fallback_conf, []).append(fallback_entry)

    # Ensure both conference keys are present for template consumption
    enhanced_teams.setdefault("East", [])
    enhanced_teams.setdefault("West", [])

    return {"East": enhanced_teams["East"], "West": enhanced_teams["West"]}

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
    
    # Fetch the team's full roster using ORM
    with get_db_context() as db:
        team = TeamORM.get_by_id(team_id, db)
        if team:
            roster_entries = team.get_roster(season=season, db=db)
            team_roster = [entry.to_dict() for entry in roster_entries]
        else:
            team_roster = []

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

