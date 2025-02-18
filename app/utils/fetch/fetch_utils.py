import logging
import os, json
import time
from datetime import datetime, timedelta
from pprint import pprint

from nba_api.stats.endpoints import (
    playercareerstats,
    LeagueGameFinder,
    PlayerGameLogs,
    commonplayerinfo,
    commonteamroster,
    PlayerGameLogs,
    LeagueGameFinder,
    leaguedashplayerstats,
    ScoreboardV2,
    cumestatsteam,
    teamgamelog
)
from nba_api.stats.static import players
from flask import current_app as app
from app.models.player import Player
from app.models.statistics import Statistics
from app.models.team import Team
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.models.team_game_stats import TeamGameStats
from app.models.playergamelog import PlayerGameLog
from app.models.gameschedule import GameSchedule
from app.utils.config_utils import logger, API_RATE_LIMIT

def fetch_and_store_player(player_id):
    """Fetch single NBA player and store in the players table if available seasons in range."""
    # Define the range of seasons we are storing
    valid_seasons = [f"{year}-{(year + 1) % 100:02d}" for year in range(2015, 2025)]
    player = players.find_player_by_id(player_id)
    Player.create_table()
    print(player)
         #Hot fix to load players and skip existing
    if not Player.player_exists(player_id):
        time.sleep(API_RATE_LIMIT)  # Avoid rate-limiting issues
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
            
            print(available_seasons)

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
       

def fetch_and_store_players():
    """Fetch all NBA players and store them in the players table."""
    # Define the range of seasons we are storing
    valid_seasons = [f"{year}-{(year + 1) % 100:02d}" for year in range(2015, 2025)]
    Player.create_table()
    # Fetch all players
    all_players = players.get_players()
    logger.info(f"Fetched {len(all_players)} players from NBA API.")

    for player in all_players:
        player_id = player["id"]
        
        #Hot fix to load players and skip existing
        if not Player.player_exists(player_id):
            time.sleep(API_RATE_LIMIT)  # Avoid rate-limiting issues
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
        time.sleep(API_RATE_LIMIT)
        career_stats = playercareerstats.PlayerCareerStats(
            player_id=player_id, timeout=300
        )
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
        team_id = team["team_id"]
        team_name = team["name"]
        time.sleep(API_RATE_LIMIT)
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
                    logging.warning(
                        f"Skipping {player_name} (ID: {player_id}): Not in database."
                    )
                    continue

                Team.add_to_roster(
                    self=team,
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


def fetch_and_store_leaguedashplayer_stats(season_from, season_to):
    """Fetch and store player statistics for multiple seasons."""
    logging.info(
        f"Fetching league-wide player stats from {season_from} to {season_to}."
    )

    # ✅ Ensure table is created before inserting data
    LeagueDashPlayerStats.create_table()

    season_from = str(season_from)
    season_to = str(season_to)

    expected_fields = [
        "player_id",
        "player_name",
        "team_id",
        "team_abbreviation",
        "age",
        "gp",
        "w",
        "l",
        "w_pct",
        "min",
        "fgm",
        "fga",
        "fg_pct",
        "fg3m",
        "fg3a",
        "fg3_pct",
        "ftm",
        "fta",
        "ft_pct",
        "oreb",
        "dreb",
        "reb",
        "ast",
        "tov",
        "stl",
        "blk",
        "blka",
        "pf",
        "pfd",
        "pts",
        "plus_minus",
        "nba_fantasy_pts",
        "dd2",
        "td3",
        "wnba_fantasy_pts"
        "gp_rank",
        "w_rank",
        "l_rank",
        "w_pct_rank",
        "min_rank",
        "fgm_rank",
        "fga_rank",
        "fg_pct_rank",
        "fg3m_rank",
        "fg3a_rank",
        "fg3_pct_rank",
        "ftm_rank",
        "fta_rank",
        "ft_pct_rank",
        "oreb_rank",
        "dreb_rank",
        "reb_rank",
        "ast_rank",
        "tov_rank",
        "stl_rank",
        "blk_rank",
        "blka_rank",
        "pf_rank",
        "pfd_rank",
        "pts_rank",
        "plus_minus_rank",
        "nba_fantasy_pts_rank",
        "dd2_rank",
        "td3_rank",
        "wnba_fantasy_pts_rank",
    ]

    for season in range(int(season_from[:4]), int(season_to[:4]) + 1):
        season_string = f"{season}-{str(season + 1)[-2:]}"
        logging.info(f"Fetching stats for {season_string}...")
        time.sleep(API_RATE_LIMIT)

        try:
            api_response = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season_string, timeout=300
            ).get_normalized_dict()

            if "LeagueDashPlayerStats" not in api_response:
                logging.error(
                    f"Unexpected API response structure for {season_string}: {api_response}"
                )
                continue

            stats = api_response["LeagueDashPlayerStats"]

            if not isinstance(stats, list):
                logging.error(
                    f"Expected list but got {type(stats)} for {season_string}"
                )
                continue

            logging.info(
                f"Fetched {len(stats)} player stats for season {season_string}."
            )

            for player_stat in stats:
                if not isinstance(player_stat, dict):
                    logging.error(
                        f"Unexpected data format in season {season_string}: {player_stat}"
                    )
                    continue

                # ✅ Convert all keys to lowercase
                player_stat_lower = {k.lower(): v for k, v in player_stat.items()}

                # ✅ Manually add 'season'
                player_stat_lower["season"] = season_string

                # ✅ Ensure all expected fields exist (fill missing fields with `None` or `0`)
                for field in expected_fields:
                    if field not in player_stat_lower:
                        player_stat_lower[field] = (
                            0 if "rank" in field or "pts" in field else None
                        )

                if "player_id" not in player_stat_lower:
                    logging.error(
                        f"Missing 'player_id' key after conversion in season {season_string}: {player_stat_lower}"
                    )
                    continue

                # ✅ Insert using lowercase keys with season added
                LeagueDashPlayerStats.add_stat(**player_stat_lower)

        except Exception as e:
            logging.error(f"Error fetching stats for season {season_string}: {e}")


def fetch_and_store_leaguedashplayer_stats_for_current_season():
    """Fetch and store player statistics for the current season."""
    current_year = datetime.now().year
    current_month = datetime.now().month

    if current_month > 9:
        current_season = f"{current_year}-{str(current_year + 1)[-2:]}"
    else:
        current_season = f"{str(current_year - 1)}-{str(current_year)[-2:]}"

    logging.info(f"Fetching daily league-wide player stats for {current_season}.")

    # ✅ Ensure the table is created before inserting data
    LeagueDashPlayerStats.create_table()

    expected_fields = [
        "player_id",
        "player_name",
        "team_id",
        "team_abbreviation",
        "age",
        "gp",
        "w",
        "l",
        "w_pct",
        "min",
        "fgm",
        "fga",
        "fg_pct",
        "fg3m",
        "fg3a",
        "fg3_pct",
        "ftm",
        "fta",
        "ft_pct",
        "oreb",
        "dreb",
        "reb",
        "ast",
        "tov",
        "stl",
        "blk",
        "blka",
        "pf",
        "pfd",
        "pts",
        "plus_minus",
        "nba_fantasy_pts",
        "dd2",
        "td3",
        "wnba_fantasy_pts"
        "gp_rank",
        "w_rank",
        "l_rank",
        "w_pct_rank",
        "min_rank",
        "fgm_rank",
        "fga_rank",
        "fg_pct_rank",
        "fg3m_rank",
        "fg3a_rank",
        "fg3_pct_rank",
        "ftm_rank",
        "fta_rank",
        "ft_pct_rank",
        "oreb_rank",
        "dreb_rank",
        "reb_rank",
        "ast_rank",
        "tov_rank",
        "stl_rank",
        "blk_rank",
        "blka_rank",
        "pf_rank",
        "pfd_rank",
        "pts_rank",
        "plus_minus_rank",
        "nba_fantasy_pts_rank",
        "dd2_rank",
        "td3_rank",
        "wnba_fantasy_pts_rank",
    ]

    try:
        api_response = leaguedashplayerstats.LeagueDashPlayerStats(
            season=current_season, timeout=300
        ).get_normalized_dict()

        if "LeagueDashPlayerStats" not in api_response:
            logging.error(
                f"Unexpected API response structure for {current_season}: {api_response}"
            )
            return

        stats = api_response["LeagueDashPlayerStats"]

        if not isinstance(stats, list):
            logging.error(f"Expected list but got {type(stats)} for {current_season}")
            return

        logging.info(f"Fetched {len(stats)} player stats for {current_season}.")

        for player_stat in stats:
            if not isinstance(player_stat, dict):
                logging.error(
                    f"Unexpected data format in {current_season}: {player_stat}"
                )
                continue

            # ✅ Convert all keys to lowercase
            player_stat_lower = {k.lower(): v for k, v in player_stat.items()}

            # ✅ Manually add 'season'
            player_stat_lower["season"] = current_season

            # ✅ Ensure all expected fields exist (fill missing fields with `None` or `0`)
            for field in expected_fields:
                if field not in player_stat_lower:
                    player_stat_lower[field] = (
                        0 if "rank" in field or "pts" in field else None
                    )

            if "player_id" not in player_stat_lower:
                logging.error(
                    f"Missing 'player_id' key after conversion in {current_season}: {player_stat_lower}"
                )
                continue

            if Player.player_exists(player_stat_lower['player_id']):
                # ✅ Insert using lowercase keys with season added
                LeagueDashPlayerStats.add_stat(**player_stat_lower)

    except Exception as e:
        logging.error(f"Error fetching stats for season {current_season}: {e}")

    logging.info(
        f"Finished updating daily league-wide player stats for {current_season}."
    )


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
            time.sleep(API_RATE_LIMIT)
            response = PlayerGameLogs(
                player_id_nullable=player_id, season_nullable=season
            )
            response_data = response.get_dict()

            # Access the 'resultSets' key
            result_sets = response_data.get("resultSets", [])
            if not result_sets:
                print(
                    f"Warning: No resultSets in response for player {player_id}. Full response: {response_data}"
                )
                continue

            # Extract rows and headers from the first result set
            rows = result_sets[0].get("rowSet", [])
            headers = result_sets[0].get("headers", [])
            if not rows:
                print(
                    f"No rows found in response for player {player_id} in season {season}."
                )
                continue

            # Convert rows into dictionaries using headers
            logs = [dict(zip(headers, row)) for row in rows]
            print(
                f"Fetched {len(logs)} logs for player {player_id} in season {season}."
            )
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
            time.sleep(API_RATE_LIMIT)
            response = LeagueGameFinder(
                season_nullable=season, team_id_nullable=team_id
            )
            response_data = response.get_dict()

            if not response_data["resultSets"]:
                continue

            games = response_data["resultSets"][0]
            headers = games["headers"]
            rows = games["rowSet"]

            for row in rows:
                game = dict(zip(headers, row))
                opponent_abbreviation = game["MATCHUP"].split()[-1]
                opponent_team_id = Team.get_team_id_by_abbreviation(
                    opponent_abbreviation
                )

                if opponent_team_id is None:
                    print(
                        f"Warning: Could not find team_id for abbreviation {opponent_abbreviation}. Skipping game."
                    )
                    continue

                # Calculate opponent score
                team_score = game.get("PTS")
                plus_minus = game.get("PLUS_MINUS")
                if team_score is not None and plus_minus is not None:
                    opponent_score = (
                        team_score - plus_minus
                        if game.get("WL") == "W"
                        else team_score + plus_minus
                    )
                else:
                    opponent_score = None

                all_games.append(
                    {
                        "game_id": game["GAME_ID"],
                        "season": season,
                        "team_id": game["TEAM_ID"],
                        "opponent_team_id": opponent_team_id,
                        "game_date": game["GAME_DATE"],
                        "home_or_away": "H" if "vs." in game["MATCHUP"] else "A",
                        "result": game.get("WL"),
                        "score": (
                            f"{team_score} - {opponent_score}"
                            if team_score and opponent_score
                            else None
                        ),
                    }
                )
        except Exception as e:
            print(f"Error fetching games for team {team_id}: {e}")

    # Insert games into the database
    GameSchedule.insert_game_schedule(all_games)
    print(f"Inserted {len(all_games)} games into the database.")

def fetch_todays_games():
    """
    Fetch today's games, conference standings, and other data from the NBA API.

    - Handles cases when no games are scheduled (e.g., All-Star Break).
    - Supports special event games like Rising Stars & All-Star Games.
    - If a team is missing from the database, it uses the API team name.

    Returns:
        dict: A dictionary containing today's games, standings, and game details.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        # Fetch scoreboard data
        time.sleep(API_RATE_LIMIT)
        scoreboard = ScoreboardV2(game_date=today)
        debug_standings(scoreboard)

        # Process conference standings
        standings = {}
        for conf, data_obj in [
            ("East", scoreboard.east_conf_standings_by_day),
            ("West", scoreboard.west_conf_standings_by_day),
        ]:
            standings_data = data_obj.get_dict()
            standings_headers = standings_data["headers"]
            standings_rows = standings_data["data"]
            standings[conf] = [
                dict(zip(standings_headers, row)) for row in standings_rows
            ]

        # Process games (Handle case when no games are available)
        games_data = scoreboard.game_header.get_dict()
        if not games_data["data"]:  # No games today
            print("⚠️ No games scheduled today.")
            return {
                "standings": standings,
                "games": []  # Return empty game list
            }

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
        last_meetings = {
            row[0]: dict(zip(last_headers, row)) for row in last_rows
        }  # Map by GAME_ID

        for row in game_rows:
            game = dict(zip(game_headers, row))

            # Attempt to get real teams first
            home_team = Team.get_team(game["HOME_TEAM_ID"])
            away_team = Team.get_team(game["VISITOR_TEAM_ID"])

            # If the team is not found, use the API's team names
            home_team_name = home_team.name if home_team else game.get("HOME_TEAM_NAME", "Special Event Team")
            away_team_name = away_team.name if away_team else game.get("VISITOR_TEAM_NAME", "Special Event Team")

            home_team_id = home_team.team_id if home_team else None
            away_team_id = away_team.team_id if away_team else None

            # Format game details
            games.append({
                "game_id": game["GAME_ID"],
                "home_team": home_team_name,
                "home_team_id": home_team_id,
                "away_team": away_team_name,
                "away_team_id": away_team_id,
                "game_time": game.get("GAME_STATUS_TEXT", "TBD"),  # Default to TBD if missing
                "arena": game.get("ARENA_NAME", "Unknown Arena"),  # Default arena name
                "line_score": [
                    {
                        "team_name": ls.get("TEAM_NAME", "Unknown"),
                        "pts": ls.get("PTS", 0),
                        "fg_pct": ls.get("FG_PCT", 0),
                        "ft_pct": ls.get("FT_PCT", 0),
                        "fg3_pct": ls.get("FG3_PCT", 0),
                        "ast": ls.get("AST", 0),
                        "reb": ls.get("REB", 0),
                        "tov": ls.get("TOV", 0)
                    }
                    for ls in line_scores if ls.get("GAME_ID") == game["GAME_ID"]
                ],
                "last_meeting": {
                    "date": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_DATE_EST", "N/A"),
                    "home_team": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_HOME_TEAM_NAME", "Unknown"),
                    "home_points": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_HOME_TEAM_POINTS", "N/A"),
                    "visitor_team": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_VISITOR_TEAM_NAME", "Unknown"),
                    "visitor_points": last_meetings.get(game["GAME_ID"], {}).get("LAST_GAME_VISITOR_TEAM_POINTS", "N/A")
                },
            })

        return {
            "standings": standings,
            "games": games
        }

    except Exception as e:
        print(f"⚠️ Error fetching today's games and standings: {e}")
        return {
            "standings": {},
            "games": []  # Return empty list to prevent crashes
        }

def debug_standings(scoreboard):
    """
    Debug and print standings data from the scoreboard.
    """
    print("East Conference Standings Data:")
    #pprint(scoreboard.east_conf_standings_by_day.get_dict())
    print("\nWest Conference Standings Data:")
    #pprint(scoreboard.west_conf_standings_by_day.get_dict())

import json
from datetime import datetime

def fetch_and_store_team_game_stats(game_id, team_id, season):
    """
    Fetch and store game-level team statistics for a specific team in a game using `TeamGameLog`.

    Args:
        game_id (str): The game ID to fetch stats for.
        team_id (int): The team ID to fetch stats for.
        season (str): The season (e.g., "2015-16").
    """
    logging.info(f"Fetching team game stats for team {team_id} in game {game_id}...")

    try:
        time.sleep(API_RATE_LIMIT)  # Avoid rate-limiting issues

        # ✅ Fetch opponent team ID from `game_schedule`
        opponent_team_id = GameSchedule.get_opponent_team_id(game_id, team_id)
        if opponent_team_id is None:
            logging.warning(f"Opponent team ID not found in `game_schedule` for game {game_id}, team {team_id}. Skipping.")
            return  # 🚨 Skip games without valid opponents (e.g., international preseason)

        # ✅ Fetch stats from `TeamGameLog`
        response = teamgamelog.TeamGameLog(season=season, team_id=team_id, timeout=300).get_dict()

        if "resultSets" not in response or not response["resultSets"]:
            logging.warning(f"No game log data found for team {team_id} in game {game_id}.")
            return

        headers = response["resultSets"][0]["headers"]
        rows = response["resultSets"][0]["rowSet"]

        # ✅ Find the specific game entry in `TeamGameLog`
        game_stats = None
        for row in rows:
            row_data = dict(zip(headers, row))
            if row_data["Game_ID"] == game_id:
                game_stats = row_data
                break

        if not game_stats:
            logging.warning(f"No matching game log found for team {team_id}, game {game_id}.")
            return

        # ✅ Extract `GAME_DATE` and derive `SEASON_ID`
        game_date_str = game_stats["GAME_DATE"]  # Format: 'APR 01, 2016'
        game_date = datetime.strptime(game_date_str, "%b %d, %Y")
        season_start_year = game_date.year if game_date.month >= 10 else game_date.year - 1
        season_id = f"{season_start_year}-{str(season_start_year + 1)[-2:]}"

        # ✅ Insert or update stats in the database
        TeamGameStats.add_team_game_stat({
            "game_id": game_id,
            "team_id": team_id,
            "opponent_team_id": opponent_team_id,
            "season": season_id,  # 🔥 Use inferred season
            "game_date": game_date.strftime("%Y-%m-%d"),  # 🔥 Store actual game date
            "fg": game_stats.get("FGM", 0),
            "fga": game_stats.get("FGA", 0),
            "fg_pct": game_stats.get("FG_PCT", 0),
            "fg3": game_stats.get("FG3M", 0),
            "fg3a": game_stats.get("FG3A", 0),
            "fg3_pct": game_stats.get("FG3_PCT", 0),
            "ft": game_stats.get("FTM", 0),
            "fta": game_stats.get("FTA", 0),
            "ft_pct": game_stats.get("FT_PCT", 0),
            "reb": game_stats.get("REB", 0),
            "ast": game_stats.get("AST", 0),
            "stl": game_stats.get("STL", 0),
            "blk": game_stats.get("BLK", 0),
            "tov": game_stats.get("TOV", 0),
            "pts": game_stats.get("PTS", 0),
            "plus_minus": 0,  # 🔥 API does not return Plus-Minus, set to 0
        })

        logging.info(f"Successfully stored stats for team {team_id} in game {game_id}.")

    except Exception as e:
        logging.error(f"Error fetching team game stats for game {game_id}, team {team_id}: {e}")



def fetch_and_store_team_game_stats_for_season(season):
    """
    Fetch and store team game statistics for all teams in a given season.
    Optimized to reduce API calls by fetching `TeamGameLog` once per team.

    Args:
        season (str): The season to fetch stats for (e.g., "2015-16").
    """
    logging.info(f"Fetching team game stats for season {season}...")

    time.sleep(API_RATE_LIMIT)
    try:
        # ✅ Get all teams
        teams = Team.get_all_teams()

        for team in teams:
            team_id = team["team_id"]
            logging.info(f"Fetching game logs for team {team_id} in {season}...")

            # ✅ Fetch `TeamGameLog` ONCE per team for the entire season
            response = teamgamelog.TeamGameLog(season=season, team_id=team_id, timeout=300).get_dict()

            if "resultSets" not in response or not response["resultSets"]:
                logging.warning(f"No game log data found for team {team_id} in season {season}.")
                continue

            headers = response["resultSets"][0]["headers"]
            rows = response["resultSets"][0]["rowSet"]

            # ✅ Process each game from the fetched data
            for row in rows:
                game_data = dict(zip(headers, row))

                game_id = game_data["Game_ID"]

                # ✅ Fetch and store stats for this specific game (without making another API call)
                fetch_and_store_team_game_stats(game_id, team_id, season)

        logging.info(f"Completed fetching and storing team game stats for season {season}.")

    except Exception as e:
        logging.error(f"Error fetching team game stats for season {season}: {e}")
