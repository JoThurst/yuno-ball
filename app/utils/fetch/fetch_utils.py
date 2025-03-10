import logging
import os, json
import time
from datetime import datetime, timedelta
from pprint import pprint
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import Timeout
import requests

from nba_api.stats.endpoints import (
    playercareerstats,
    LeagueGameFinder,
    PlayerGameLogs,
    commonplayerinfo,
    commonteamroster,
    PlayerGameLogs,
    LeagueGameFinder,
    leaguedashplayerstats,
    leaguedashteamstats,
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
from app.models.leaguedashteamstats import LeagueDashTeamStats
from app.models.team_game_stats import TeamGameStats
from app.models.playergamelog import PlayerGameLog
from app.models.gameschedule import GameSchedule
from app.utils.config_utils import logger, API_RATE_LIMIT, RateLimiter, MAX_WORKERS
from app.utils.cache_utils import set_cache, get_cache
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
from tqdm import tqdm

rate_limiter = RateLimiter(max_requests=30, interval=25)  # Adjust for actual limits

def fetch_and_store_player(player_id):
    """Fetch and store an NBA player, with rate-limited API calls."""
    valid_seasons = [f"{year}-{(year + 1) % 100:02d}" for year in range(2015, 2025)]

    if Player.player_exists(player_id):
        logger.info(f"Skipping player {player_id} - Already in database.")
        return

    retries = 3
    for attempt in range(retries):
        try:
            rate_limiter.wait_if_needed()  # ⏳ Ensures we don't exceed API limits
            api_config = get_api_config()
            cplayerinfo_obj = commonplayerinfo.CommonPlayerInfo(
                player_id=player_id, 
                timeout=api_config['timeout'],
                proxy=api_config['proxy'],
                headers=api_config['headers']
            )
            cplayerinfo_data = cplayerinfo_obj.get_data_frames()[0].iloc[0]
            break  # API call successful, exit retry loop

        except Timeout:
            logger.warning(f"Timeout for player {player_id}, retrying ({attempt+1}/{retries})...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error processing player {player_id}: {e}")
            return  # Don't retry if it's not a timeout

    try:
        from_year = int(cplayerinfo_data["FROM_YEAR"])
        to_year = int(cplayerinfo_data["TO_YEAR"])
        name = cplayerinfo_data.get("DISPLAY_FIRST_LAST", "Unknown")
        position = cplayerinfo_data.get("POSITION", "Unknown")
        weight = int(cplayerinfo_data.get("WEIGHT", 0)) if cplayerinfo_data.get("WEIGHT") else None
        born_date = cplayerinfo_data.get("BIRTHDATE", None)
        exp = int(cplayerinfo_data.get("SEASON_EXP", 0)) if cplayerinfo_data.get("SEASON_EXP") else None
        school = cplayerinfo_data.get("SCHOOL", None)

        age = None
        if born_date:
            born_date_obj = datetime.strptime(born_date.split("T")[0], "%Y-%m-%d")
            age = datetime.now().year - born_date_obj.year

        available_seasons = [season for season in valid_seasons if from_year <= int(season[:4]) <= to_year]

        if available_seasons:
            Player.add_player(
                player_id=int(player_id),
                name=name,
                position=position,
                weight=weight,
                born_date=born_date,
                age=age,
                exp=exp,
                school=school,
                available_seasons=",".join(available_seasons),
            )
            logger.info(f"✅ Player {name} (ID: {player_id}) added with seasons: {available_seasons}.")
        else:
            logger.warning(f"Player {name} (ID: {player_id}) has no valid seasons in range.")

    except Exception as e:
        logger.error(f"❌ Error processing player {player_id} after successful API call: {e}")
       

def fetch_and_store_players():
    """Fetch all NBA players and store them in the players table using parallel processing."""
    valid_seasons = [f"{year}-{(year + 1) % 100:02d}" for year in range(2015, 2025)]
    Player.create_table()

    all_players = players.get_players()
    logger.info(f"Fetched {len(all_players)} players from NBA API.")

    def process_player(player):
        """Helper function to fetch and store a single player."""
        player_id = player["id"]
        if not Player.player_exists(player_id):  # Avoid redundant fetches
            fetch_and_store_player(player_id)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:  # Adjust max_workers as needed
        executor.map(process_player, all_players)

    logger.info("All players have been successfully stored.")


def fetch_and_store_all_players_stats():
    """Fetch and store career stats for all players in parallel using multi-threading."""
    players = Player.get_all_players()
    logger.info(f"Found {len(players)} players in the database.")
    Statistics.create_table()
    def fetch_stats(player):
        """Fetch and store stats for a single player with retries."""
        player_id = player.player_id
        rate_limiter.wait_if_needed()  # ⏳ Prevent API overloading

        retries = 3
        for attempt in range(retries):
            try:
                logger.info(f"Fetching stats for player {player_id} ({player.name})...")
                career_stats = playercareerstats.PlayerCareerStats(player_id=player_id, timeout=10)
                stats_df = career_stats.get_data_frames()[0]

                # Insert stats into the database
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

                logger.info(f"Stats for player {player_id} stored successfully.")
                break  # Exit retry loop if request succeeds

            except Timeout:
                logger.warning(f"Timeout for player {player_id}, retrying ({attempt+1}/{retries})...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error fetching stats for player {player_id}: {e}")
                return  # Don't retry if it's not a timeout

    # Use ThreadPoolExecutor to process players in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(fetch_stats, players)

    logger.info("Successfully stored all player stats.")


def fetch_and_store_current_rosters():
    """Fetch and store current team rosters in parallel while respecting rate limits."""
    teams_list = Team.list_all_teams()  # Use the lightweight version that doesn't fetch standings
    logger.info(f"Fetched {len(teams_list)} teams from the database.")

    def fetch_team_roster(team):
        """Fetch and store the roster for a single team."""
        team_id = team["team_id"]
        team_name = team["name"]
        rate_limiter.wait_if_needed()  # ⏳ Prevent API overloading

        try:
            logger.info(f"Fetching roster for {team_name} (ID: {team_id})...")

            # Fetch team roster from API
            team_roster_data = commonteamroster.CommonTeamRoster(team_id=team_id, timeout=10).get_normalized_dict()
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

                # Ensure player exists in the database before adding to roster
                if not Player.player_exists(player_id=player_id):
                    logger.warning(f"Skipping {player_name} (ID: {player_id}): Not in database.")
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

            logger.info(f"Updated roster for {team_name}.")

        except Exception as e:
            logger.error(f"Error fetching roster for {team_name} (ID: {team_id}): {e}")

    # Use ThreadPoolExecutor to parallelize roster fetching
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        list(tqdm(executor.map(fetch_team_roster, teams_list), total=len(teams_list), desc="Fetching Rosters"))

    logger.info("✅ Successfully updated all NBA team rosters.")


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
                season=season_string, timeout=10
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
            season=current_season, timeout=10
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
    Fetch and store the season game schedule for all teams, including upcoming games.

    Args:
        season (str): Season string in "YYYY-YY" format (e.g., "2023-24").
        team_ids (list): List of team IDs to fetch schedules for.
    """
    print(f"📅 Fetching full schedule for season {season}...")
    all_games = []

    for team_id in team_ids:
        try:
            time.sleep(API_RATE_LIMIT)
            response = LeagueGameFinder(
                season_nullable=season, 
                team_id_nullable=team_id
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
                opponent_team_id = Team.get_team_id_by_abbreviation(opponent_abbreviation)

                if opponent_team_id is None:
                    print(f"⚠️ Warning: Could not find team_id for {opponent_abbreviation}. Skipping game.")
                    continue

                # Parse game date
                game_date = datetime.strptime(game["GAME_DATE"], "%Y-%m-%d").date()
                today = datetime.today().date()

                # Check if game is in the future
                is_future_game = game_date > today

                # Handle past games (completed with result)
                if not is_future_game:
                    team_score = game.get("PTS")
                    plus_minus = game.get("PLUS_MINUS")
                    if team_score is not None and plus_minus is not None:
                        opponent_score = (
                            team_score - plus_minus if game.get("WL") == "W" else team_score + plus_minus
                        )
                    else:
                        opponent_score = None

                    result = game.get("WL")
                    score = f"{team_score} - {opponent_score}" if team_score and opponent_score else None

                else:
                    # Future games have no result, score, or plus/minus
                    result = None
                    score = None

                # Append formatted game data
                all_games.append({
                    "game_id": game["GAME_ID"],
                    "season": season,
                    "team_id": game["TEAM_ID"],
                    "opponent_team_id": opponent_team_id,
                    "game_date": game["GAME_DATE"],
                    "home_or_away": "H" if "vs." in game["MATCHUP"] else "A",
                    "result": result,  # NULL for future games
                    "score": score  # NULL for future games
                })

        except Exception as e:
            print(f"❌ Error fetching games for team {team_id}: {e}")

    # ✅ Insert games into the database
    GameSchedule.insert_game_schedule(all_games)
    print(f"✅ Inserted {len(all_games)} games into the database (past + future).")

NBA_SCHEDULE_CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"

def fetch_and_store_future_games(season):
    """
    Fetch and store upcoming games for the current NBA season.

    Args:
        season (str): Season in "YYYY-YY" format (e.g., "2024-25").
    """
    print(f"📅 Fetching full NBA schedule for {season}...")

    try:
        response = requests.get(NBA_SCHEDULE_CDN_URL)
        response.raise_for_status()  
        data = response.json()

        games_list = data.get("leagueSchedule", {}).get("gameDates", [])
        today = datetime.today().date()
        all_games = []

        for game_date_info in games_list:
            try:
                # ✅ Fix: Correct format conversion
                game_date = datetime.strptime(game_date_info["gameDate"], "%m/%d/%Y %H:%M:%S").date()
            except ValueError as e:
                print(f"❌ Error parsing date {game_date_info['gameDate']}: {e}")
                continue

            if game_date <= today:
                continue

            for game in game_date_info.get("games", []):
                game_id = game["gameId"]
                home_team_id = game["homeTeam"]["teamId"]
                away_team_id = game["awayTeam"]["teamId"]

                # ✅ Store game with correct date format
                all_games.append({
                    "game_id": game_id,
                    "season": season,
                    "team_id": home_team_id,
                    "opponent_team_id": away_team_id,
                    "game_date": game_date.strftime("%Y-%m-%d"),
                    "home_or_away": "H",
                    "result": None,
                    "score": None
                })

                all_games.append({
                    "game_id": game_id,
                    "season": season,
                    "team_id": away_team_id,
                    "opponent_team_id": home_team_id,
                    "game_date": game_date.strftime("%Y-%m-%d"),
                    "home_or_away": "A",
                    "result": None,
                    "score": None
                })

        if all_games:
            GameSchedule.insert_game_schedule(all_games)
            print(f"✅ Inserted {len(all_games)} future games into the database.")
        else:
            print("⚠️ No new future games to insert.")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching NBA schedule: {e}")

   

#Should Proobably Move this to a different file
def fetch_todays_games():
    """
    Fetch today's games, conference standings, and other data from the NBA API.

    - Uses Redis caching for 24 hours to optimize performance.
    - Handles cases when no games are scheduled (e.g., All-Star Break).
    - Supports special event games like Rising Stars & All-Star Games.
    - If a team is missing from the database, it uses the API team name.

    Returns:
        dict: A dictionary containing today's games, standings, and game details.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"nba_games_{today}"
    
    # ✅ Check Redis Cache First
    cached_data = get_cache(cache_key)
    if cached_data:
        print(f"✅ Cache HIT: Returning cached data for {today}")
        return cached_data

    print(f"🔄 Cache MISS: Fetching new data for {today}")

    try:
        # Fetch scoreboard data with proxy and headers
        time.sleep(API_RATE_LIMIT)
        api_config = get_api_config()
        scoreboard = ScoreboardV2(
            game_date=today,
            proxy=api_config['proxy'],
            headers=api_config['headers'],
            timeout=api_config['timeout']
        )
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
            response = {"standings": standings, "games": []}
            set_cache(cache_key, response, ex=86400)  # ✅ Cache empty result for 24 hours
            return response

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

        # ✅ Store in Redis for 24 hours
        response = {"standings": standings, "games": games}
        set_cache(cache_key, response, ex=86400)
        print(f"✅ Cached today's games and standings for 24 hours")

        return response

    except Exception as e:
        print(f"⚠️ Error fetching today's games and standings: {e}")
        return {
            "standings": {},
            "games": []  # Return empty list to prevent crashes
        }

def fetch_team_rosters(team_ids):
    """Fetch and return rosters for specific teams as a list of dictionaries."""
    players = []
    for team_id in team_ids:
        roster = Team.get_roster_by_team_id(team_id)  
        for player in roster:
            players.append({
                "player_id": player[1],  # Assuming first value in tuple is player_id
                "team_id": team_id,  # Add team_id for filtering in UI
                "player_name": player[2]  # Assuming second value in tuple is player_name
            })
    return players


def debug_standings(scoreboard):
    """
    Debug and print standings data from the scoreboard.
    """
    print("East Conference Standings Data:")
    #pprint(scoreboard.east_conf_standings_by_day.get_dict())
    print("\nWest Conference Standings Data:")
    #pprint(scoreboard.west_conf_standings_by_day.get_dict())

def fetch_and_store_team_game_stats(game_id, team_id, season):
    """
    Fetch and store game-level team statistics for a specific team in a game using `TeamGameLog`.

    Args:
        game_id (str): The game ID to fetch stats for.
        team_id (int): The team ID to fetch stats for.
        season (str): The season (e.g., "2015-16").
    """
    logging.info(f"Fetching team game stats for team {team_id} in game {game_id}...")

    retries = 3
    for attempt in range(retries):
        try:
            time.sleep(API_RATE_LIMIT)  # Avoid rate-limiting issues

            # ✅ Fetch opponent team ID from `game_schedule`
            opponent_team_id = GameSchedule.get_opponent_team_id(game_id, team_id)
            if opponent_team_id is None:
                logging.warning(f"Opponent team ID not found in `game_schedule` for game {game_id}, team {team_id}. Skipping.")
                return  # 🚨 Skip games without valid opponents (e.g., international preseason)

            # ✅ Fetch stats from `TeamGameLog`
            response = teamgamelog.TeamGameLog(season=season, team_id=team_id, timeout=10).get_dict()

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

            logging.info(f" Successfully stored stats for team {team_id} in game {game_id}.")
            break  # ✅ Exit retry loop if successful

        except Timeout:
            logging.warning(f" Timeout for team {team_id}, game {game_id}, retrying ({attempt+1}/{retries})...")
            time.sleep(5)
        except Exception as e:
            logging.error(f" Error fetching team game stats for game {game_id}, team {team_id}: {e}")
            return  # 🚨 Don't retry if it's not a timeout



def fetch_and_store_team_game_stats_for_season(season):
    """
    Fetch and store team game statistics for all teams in a given season using multi-threading.

    Args:
        season (str): The season to fetch stats for (e.g., "2015-16").
    """
    logging.info(f" Fetching team game stats for season {season}...")

    teams = Team.get_all_teams()  # Get all NBA teams

    def fetch_team_stats(team):
        """Fetch and store stats for a single team with retries."""
        team_id = team["team_id"]
        retries = 3

        for attempt in range(retries):
            try:
                rate_limiter.wait_if_needed()  # Prevent API overloading

                time.sleep(API_RATE_LIMIT)  # Avoid rate-limiting issues
                logging.info(f"Fetching game logs for team {team_id} in {season}...")
                response = teamgamelog.TeamGameLog(season=season, team_id=team_id, timeout=120).get_dict()

                if "resultSets" not in response or not response["resultSets"]:
                    logging.warning(f" No game log data found for team {team_id} in season {season}.")
                    return

                headers = response["resultSets"][0]["headers"]
                rows = response["resultSets"][0]["rowSet"]

                for row in rows:
                    game_data = dict(zip(headers, row))
                    game_id = game_data["Game_ID"]

                    fetch_and_store_team_game_stats(game_id, team_id, season)  # Fetch detailed stats for each game

                logging.info(f" Successfully stored game stats for team {team_id} in season {season}.")
                break  # ✅ Exit retry loop if successful

            except Timeout:
                logging.warning(f"⚠️ Timeout for team {team_id}, retrying ({attempt+1}/{retries})...")
                time.sleep(5)
            except Exception as e:
                logging.error(f"❌ Error fetching game stats for team {team_id} in season {season}: {e}")
                return  # 🚨 Don't retry if it's not a timeout

    # Use ThreadPoolExecutor to process teams in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(fetch_team_stats, teams)

    logging.info(f" Completed fetching and storing team game stats for season {season}.")


def fetch_and_store_league_dash_team_stats(season="2023-24"):
    """
    Fetch and insert LeagueDashTeamStats for all measure types and per modes.
    Regular Season and Playoffs are stored separately to avoid overwrites.
    """
    print(f"\n🚀 Ingesting LeagueDashTeamStats for {season}...")

    # ✅ Ensure Table Exists Before Insert
    LeagueDashTeamStats.create_table()

    measure_types = ["Base", "Advanced", "Misc", "Four Factors", "Scoring", "Opponent", "Defense"]
    per_modes = ["Totals", "Per48", "Per100Possessions"]
    season_types = ["Regular Season", "Playoffs"]

    # Separate data for Regular Season and Playoffs
    regular_season_stats = {}
    playoffs_stats = {}

    def fetch_stats(measure_type, per_mode, season_type):
        clean_measure_type = measure_type.replace(" ", "")  # ✅ Remove spaces (Four Factors → FourFactors)
        retries = 3

        for attempt in range(retries):
            try:
                print(f"\n📊 Fetching: MeasureType={clean_measure_type}, PerMode={per_mode}, SeasonType={season_type}")

                # ✅ API Call
                time.sleep(API_RATE_LIMIT)  # 🔥 Avoid API rate limits
                response = leaguedashteamstats.LeagueDashTeamStats(
                    league_id_nullable="00",
                    season=season,
                    season_type_all_star=season_type,
                    measure_type_detailed_defense=measure_type,
                    per_mode_detailed=per_mode,
                    timeout=60,
                    rank="Y"
                ).get_dict()

                # ✅ Validate response
                if "resultSets" not in response:
                    logging.error(f"\n❌ API response missing 'resultSets' for {measure_type}, {per_mode}, {season_type}. Full response:\n{json.dumps(response, indent=4)}")
                    continue

                data_set = response["resultSets"][0]  # The first result set contains team stats
                headers = data_set["headers"]
                rows = data_set["rowSet"]

                if rows:
                    for row in rows:
                        team_id = row[headers.index("TEAM_ID")]
                        team_name = row[headers.index("TEAM_NAME")]

                        # Choose correct storage
                        storage = regular_season_stats if season_type == "Regular Season" else playoffs_stats

                        # Initialize team entry if not present
                        if team_id not in storage:
                            storage[team_id] = {
                                "team_id": team_id,
                                "team_name": team_name,
                                "season": season,
                                "season_type": season_type
                            }

                        # Add prefixed stats (Ensure no spaces in column names)
                        for i, stat in enumerate(headers):
                            if stat not in ["TEAM_ID", "TEAM_NAME"]:
                                col_name = f"{clean_measure_type}_{per_mode}_{stat}".lower()  # ✅ Ensure lowercase and remove spaces
                                storage[team_id][col_name] = row[i]

                    print(f"✅ Fetched {len(rows)} records for {clean_measure_type} {per_mode}.")
                break  # Exit retry loop if successful

            except KeyError as e:
                logging.error(f"\n❌ KeyError while fetching {clean_measure_type}, {per_mode}, {season_type}: {e}")
                logging.error(f"Full API Response:\n{json.dumps(response, indent=4)}")
                print(f"\n❌ KeyError: {e}. Check logs for full response.")
                continue

            except Exception as e:
                logging.error(f"❌ Error fetching data for {clean_measure_type}, {per_mode}, {season_type}: {e}")
                print(f"\n❌ Error fetching data: {e}")
                time.sleep(1)  # 🔥 Avoid API rate limits

    # Use ThreadPoolExecutor to process fetches in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(fetch_stats, measure_type, per_mode, season_type)
            for measure_type in measure_types
            for per_mode in per_modes
            for season_type in season_types
        ]
        for _ in tqdm(as_completed(futures), total=len(futures), desc="Fetching LeagueDashTeamStats"):
            pass

    # ✅ Insert Regular Season Data
    for team_id, team_data in regular_season_stats.items():
        try:
            LeagueDashTeamStats.add_team_season_stat(team_data)
            print(f"✅ Inserted Regular Season stats for Team ID {team_id}")
        except Exception as e:
            logging.error(f"❌ Error inserting Regular Season data for Team ID {team_id}: {e}")

    # ✅ Insert Playoff Data
    for team_id, team_data in playoffs_stats.items():
        try:
            LeagueDashTeamStats.add_team_season_stat(team_data)
            print(f"✅ Inserted Playoff stats for Team ID {team_id}")
        except Exception as e:
            logging.error(f"❌ Error inserting Playoff data for Team ID {team_id}: {e}")

    print(f"\n✅ Ingestion completed for {season}.")