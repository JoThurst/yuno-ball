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
    leaguestandingsv3,
    cumestatsteam,
    teamgamelog
)
from nba_api.stats.endpoints._base import Endpoint
from nba_api.stats.static import players
from flask import current_app as app
from app.models.player_sqlalchemy import PlayerORM
from app.models.statistics_sqlalchemy import StatisticsORM
from app.models.team_sqlalchemy import TeamORM, RosterORM
from app.database import get_db_context
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.utils.config_utils import logger, API_RATE_LIMIT, RateLimiter, MAX_WORKERS
from app.utils.cache_utils import set_cache, get_cache
from app.utils.fetch.api_utils import (
    get_api_config,
    create_api_endpoint,
)
from tqdm import tqdm

rate_limiter = RateLimiter(max_requests=30, interval=25)  # Adjust for actual limits


class SafeScoreboardV2(ScoreboardV2):
    """
    Wrapper around `ScoreboardV2` that tolerates missing datasets, such as `WinProbability`.
    """

    def load_response(self):
        data_sets = self.nba_response.get_data_sets()

        self.data_sets = [
            Endpoint.DataSet(data=data_set)
            for _, data_set in data_sets.items()
        ]

        def safe_dataset(name):
            return Endpoint.DataSet(
                data=data_sets.get(name, {"headers": [], "data": []})
            )

        self.available = safe_dataset("Available")
        self.east_conf_standings_by_day = safe_dataset("EastConfStandingsByDay")
        self.game_header = safe_dataset("GameHeader")
        self.last_meeting = safe_dataset("LastMeeting")
        self.line_score = safe_dataset("LineScore")
        self.series_standings = safe_dataset("SeriesStandings")
        self.team_leaders = safe_dataset("TeamLeaders")
        self.ticket_links = safe_dataset("TicketLinks")
        self.west_conf_standings_by_day = safe_dataset("WestConfStandingsByDay")
        self.win_probability = safe_dataset("WinProbability")


def get_current_season_str():
    """
    Determine the current NBA season string (e.g., '2024-25').
    """
    now = datetime.now()
    if now.month >= 10:
        start_year = now.year
    else:
        start_year = now.year - 1
    end_year = str(start_year + 1)[-2:]
    return f"{start_year}-{end_year}"


def normalize_conference_label(label):
    if not label:
        return None
    value = str(label).strip().lower()
    if value.startswith("east"):
        return "East"
    if value.startswith("west"):
        return "West"
    return label


def fetch_league_standings_fallback(season=None, season_type="Regular Season"):
    """
    Use LeagueStandingsV3 to fetch conference standings with up-to-date records.
    Returns a dict formatted similarly to ScoreboardV2 standings.
    """
    season = season or get_current_season_str()
    try:
        endpoint = create_api_endpoint(
            leaguestandingsv3.LeagueStandingsV3,
            league_id="00",
            season=season,
            season_type=season_type,
        )
        dataset = endpoint.standings.get_dict()
        headers = dataset.get("headers", [])
        rows = dataset.get("data", [])

        if not rows:
            return None

        standings = {"East": [], "West": []}
        for row in rows:
            entry = dict(zip(headers, row))
            conference = normalize_conference_label(entry.get("Conference"))
            mapped = {
                "TEAM_ID": entry.get("TeamID"),
                "TEAM": entry.get("TeamName"),
                "CONFERENCE": conference,
                "W": entry.get("WINS"),
                "L": entry.get("LOSSES"),
                "W_PCT": entry.get("WinPCT"),
                "HOME_RECORD": entry.get("HOME"),
                "ROAD_RECORD": entry.get("ROAD"),
            }
            bucket = "East" if conference == "East" else "West" if conference == "West" else "Unknown"
            standings.setdefault(bucket, []).append(mapped)

        # Ensure keys exist even if empty
        standings.setdefault("East", [])
        standings.setdefault("West", [])
        return standings
    except Exception as exc:
        logger.error(f"Error fetching fallback league standings: {exc}")
        return None


def standings_have_real_records(standings_list):
    if not standings_list:
        return False
    for entry in standings_list:
        for key in ("W", "L"):
            value = entry.get(key)
            try:
                if value is not None and float(value) > 0:
                    return True
            except (TypeError, ValueError):
                continue
        win_pct = entry.get("W_PCT")
        try:
            if win_pct is not None and float(win_pct) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False

# DEPRECATED: All player/team fetch functions have been replaced by fetcher classes:
# - fetch_and_store_player() -> PlayerFetcher._fetch_single_player()
# - fetch_and_store_players() -> PlayerFetcher.fetch_all_players()
# - fetch_and_store_all_players_stats() -> PlayerFetcher.fetch_all_players_stats()
# - fetch_and_store_current_rosters() -> TeamFetcher.fetch_current_rosters()
# - fetch_and_store_leaguedashplayer_stats() -> PlayerFetcher.fetch_league_dash_player_stats()
# - fetch_and_store_leaguedashplayer_stats_for_current_season() -> PlayerFetcher.fetch_league_dash_player_stats()


#Should Proobably Move this to a different file
# This does a lot more than just fetch todays games. And its called a lot. We can determine todays games from the database and return very fast.
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
    
    # Check Redis Cache First
    cached_data = get_cache(cache_key)
    if cached_data:
        print(f"[CACHE HIT] Returning cached data for {today}")
        return cached_data

    print(f"[CACHE MISS] Fetching new data for {today}")

    try:
        time.sleep(API_RATE_LIMIT)

        api_config = get_api_config()
        retries = max(api_config.get("retries", 1), 1)

        scoreboard = None
        last_error = None

        for attempt in range(retries):
            try:
                rate_limiter.wait_if_needed()
                scoreboard = create_api_endpoint(
                    SafeScoreboardV2,
                    game_date=today,
                    day_offset=0,
                    league_id="00",
                )
                break
            except Exception as err:
                last_error = err
                backoff = api_config.get("backoff_factor", 1.5)
                time.sleep(backoff * (attempt + 1))
                api_config = get_api_config()

        if scoreboard is None:
            raise last_error or Exception("Failed to fetch scoreboard data")

        def dataset_to_dicts(data_set):
            dataset_dict = data_set.get_dict() if data_set else {"headers": [], "data": []}
            headers = dataset_dict.get("headers", [])
            data_rows = dataset_dict.get("data", [])
            return [dict(zip(headers, row)) for row in data_rows]

        standings = {
            "East": dataset_to_dicts(scoreboard.east_conf_standings_by_day),
            "West": dataset_to_dicts(scoreboard.west_conf_standings_by_day),
        }

        # If scoreboard standings are empty/zeroed (common early in season), fallback to LeagueStandingsV3
        needs_east_fallback = not standings_have_real_records(standings.get("East"))
        needs_west_fallback = not standings_have_real_records(standings.get("West"))
        if needs_east_fallback or needs_west_fallback:
            fallback_standings = fetch_league_standings_fallback()
            if fallback_standings:
                if needs_east_fallback:
                    standings["East"] = fallback_standings.get("East", standings.get("East", []))
                if needs_west_fallback:
                    standings["West"] = fallback_standings.get("West", standings.get("West", []))

        game_dataset = scoreboard.game_header.get_dict()
        game_headers = game_dataset.get("headers", [])
        game_rows = game_dataset.get("data", [])

        if not game_rows:
            print("[WARNING] No games scheduled today.")
            response = {"standings": standings, "games": []}
            set_cache(cache_key, response, ex=86400)
            return response

        line_score_entries = dataset_to_dicts(scoreboard.line_score)
        line_scores_by_game = {}
        for entry in line_score_entries:
            game_id = entry.get("GAME_ID")
            if not game_id:
                continue
            line_scores_by_game.setdefault(game_id, []).append(
                {
                    "team_name": entry.get("TEAM_NAME", "Unknown"),
                    "pts": entry.get("PTS", 0),
                    "fg_pct": entry.get("FG_PCT", 0),
                    "ft_pct": entry.get("FT_PCT", 0),
                    "fg3_pct": entry.get("FG3_PCT", 0),
                    "ast": entry.get("AST", 0),
                    "reb": entry.get("REB", 0),
                    "tov": entry.get("TOV", 0),
                }
            )

        last_meeting_entries = dataset_to_dicts(scoreboard.last_meeting)
        last_meetings_by_game = {
            entry.get("GAME_ID"): entry for entry in last_meeting_entries if entry.get("GAME_ID")
        }

        games = []
        for row in game_rows:
            game = dict(zip(game_headers, row))

            # Get teams using ORM
            with get_db_context() as db:
                home_team = TeamORM.get_by_id(game.get("HOME_TEAM_ID"), db)
                away_team = TeamORM.get_by_id(game.get("VISITOR_TEAM_ID"), db)

            home_team_name = home_team.name if home_team else game.get("HOME_TEAM_NAME", "Special Event Team")
            away_team_name = away_team.name if away_team else game.get("VISITOR_TEAM_NAME", "Special Event Team")

            home_team_id = home_team.team_id if home_team else game.get("HOME_TEAM_ID")
            away_team_id = away_team.team_id if away_team else game.get("VISITOR_TEAM_ID")

            last_meeting = last_meetings_by_game.get(game.get("GAME_ID"), {})

            games.append(
                {
                    "game_id": game.get("GAME_ID"),
                    "home_team": home_team_name,
                    "home_team_id": home_team_id,
                    "away_team": away_team_name,
                    "away_team_id": away_team_id,
                    "game_time": game.get("GAME_STATUS_TEXT", "TBD"),
                    "arena": game.get("ARENA_NAME", "Unknown Arena"),
                    "line_score": line_scores_by_game.get(game.get("GAME_ID"), []),
                    "last_meeting": {
                        "date": last_meeting.get("LAST_GAME_DATE_EST", "N/A"),
                        "home_team": last_meeting.get("LAST_GAME_HOME_TEAM_NAME", "Unknown"),
                        "home_points": last_meeting.get("LAST_GAME_HOME_TEAM_POINTS", "N/A"),
                        "visitor_team": last_meeting.get("LAST_GAME_VISITOR_TEAM_NAME", "Unknown"),
                        "visitor_points": last_meeting.get("LAST_GAME_VISITOR_TEAM_POINTS", "N/A"),
                    },
                }
            )

        response = {"standings": standings, "games": games}
        set_cache(cache_key, response, ex=86400)
        print(f"[SUCCESS] Cached today's games and standings for 24 hours")

        return response

    except Exception as e:
        print(f"[ERROR] Error fetching today's games and standings: {e}")
        return {
            "standings": {},
            "games": []
        }

def fetch_team_rosters(team_ids):
    """Fetch and return rosters for specific teams as a list of dictionaries using ORM."""
    players = []
    with get_db_context() as db:
        for team_id in team_ids:
            team = TeamORM.get_by_id(team_id, db)
            if team:
                roster_entries = team.get_roster(db=db)
                for entry in roster_entries:
                    players.append({
                        "player_id": entry.player_id,
                        "team_id": team_id,
                        "player_name": entry.player_name
                    })
    return players

