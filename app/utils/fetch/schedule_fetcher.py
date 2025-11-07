import logging
from datetime import datetime
import requests
from app.models.gameschedule import GameSchedule
from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

NBA_SCHEDULE_CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"

class ScheduleFetcher(BaseFetcher):
    """Fetcher for NBA game schedules."""

    def __init__(self):
        super().__init__()
        self._cached_schedule_payload = None

    def _load_schedule_payload(self):
        """Fetch the master schedule payload from the NBA CDN (with simple caching)."""
        if self._cached_schedule_payload is not None:
            return self._cached_schedule_payload

        try:
            response = requests.get(NBA_SCHEDULE_CDN_URL, timeout=30)
            response.raise_for_status()
            payload = response.json().get("leagueSchedule", {})
            if not payload:
                logger.warning("Schedule payload missing 'leagueSchedule' key.")
            self._cached_schedule_payload = payload
            return payload
        except requests.RequestException as exc:
            logger.error(f"Failed to download schedule payload: {exc}")
            raise

    @staticmethod
    def _parse_score(value):
        if value in (None, "", "-"):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _build_schedule_entries(self, season, mode="all"):
        """
        Build schedule entries for the requested season.

        Args:
            season (str): Season string in format 'YYYY-YY'
            mode (str): 'all', 'past', or 'future'
        """
        payload = self._load_schedule_payload()
        season_year = payload.get("seasonYear")
        if season_year and season_year != season:
            logger.info(f"Schedule payload seasonYear {season_year} does not match requested {season}. Proceeding anyway.")

        entries = []

        for game_date in payload.get("gameDates", []):
            for game in game_date.get("games", []):
                game_status = game.get("gameStatus")
                is_final = game_status == 3
                is_upcoming = game_status in (1, 2)

                # Determine whether to include the game based on requested mode
                if mode == "future" and not is_upcoming:
                    continue
                if mode == "past" and is_upcoming:
                    continue

                game_datetime_raw = game.get("gameDateTimeUTC")
                if not game_datetime_raw:
                    logger.debug(f"Skipping game {game.get('gameId')} with missing gameDateTimeUTC.")
                    continue

                try:
                    game_datetime = datetime.fromisoformat(game_datetime_raw.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Unable to parse gameDateTimeUTC '{game_datetime_raw}' for game {game.get('gameId')}.")
                    continue

                home_team = game.get("homeTeam", {})
                away_team = game.get("awayTeam", {})
                home_id = home_team.get("teamId")
                away_id = away_team.get("teamId")

                # Skip TBD matchups (teamId == 0)
                if not home_id or not away_id:
                    logger.debug(f"Skipping TBD game {game.get('gameId')} with unresolved team IDs.")
                    continue

                home_score = self._parse_score(home_team.get("score"))
                away_score = self._parse_score(away_team.get("score"))
                score_str = None
                home_result = None
                away_result = None

                if home_score is not None and away_score is not None:
                    score_str = f"{home_score}-{away_score}"
                    if is_final:
                        if home_score > away_score:
                            home_result, away_result = "W", "L"
                        elif home_score < away_score:
                            home_result, away_result = "L", "W"
                        else:
                            home_result = away_result = None

                entries.append({
                    "game_id": game.get("gameId"),
                    "season": season,
                    "team_id": home_id,
                    "opponent_team_id": away_id,
                    "game_date": game_datetime,
                    "home_or_away": "H",
                    "result": home_result,
                    "score": score_str
                })
                entries.append({
                    "game_id": game.get("gameId"),
                    "season": season,
                    "team_id": away_id,
                    "opponent_team_id": home_id,
                    "game_date": game_datetime,
                    "home_or_away": "A",
                    "result": away_result,
                    "score": score_str
                })

        return entries

    def fetch_and_store_schedule(self, season):
        """
        Fetch and store the season game schedule for all teams using the NBA CDN.
        
        Args:
            season (str): Season string in "YYYY-YY" format (e.g., "2023-24")
        """
        logger.info(f"Fetching full schedule for season {season}")

        # Ensure the schedule table exists
        GameSchedule.create_table()

        try:
            schedule_entries = self._build_schedule_entries(season, mode="all")
        except Exception as exc:
            logger.error(f"Unable to build schedule entries: {exc}")
            return

        # Store all games in the database
        if schedule_entries:
            inserted = GameSchedule.insert_game_schedule(schedule_entries)
            logger.info(f"Successfully stored/updated {inserted} schedule rows for {season}")
        else:
            logger.warning(f"No games found for {season}")

    def fetch_and_store_future_games(self, season):
        """
        Fetch and store upcoming games for the current NBA season from the NBA CDN.
        
        Args:
            season (str): Season in "YYYY-YY" format (e.g., "2024-25")
        """
        logger.info(f"Fetching future games for season {season}")

        try:
            future_entries = self._build_schedule_entries(season, mode="future")
        except Exception as exc:
            logger.error(f"Unable to build future schedule entries: {exc}")
            raise

        if future_entries:
            inserted = GameSchedule.insert_game_schedule(future_entries)
            logger.info(f"Successfully stored/updated {inserted} future games for {season}")
        else:
            logger.info("No upcoming games found to insert")