import logging
import os
from datetime import datetime
import pytz
import requests
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_sqlalchemy import TeamORM
from app.database import get_db_context
from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

NBA_SCHEDULE_CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"

class ScheduleFetcher(BaseFetcher):
    """Fetcher for NBA game schedules."""

    def __init__(self):
        super().__init__()
        self._cached_schedule_payload = None

    def _cdn_request_kwargs(self):
        """Build requests kwargs; use proxy when FORCE_PROXY is set (CDN often 403s direct)."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com",
        }
        kwargs = {"headers": headers, "timeout": 45}
        force_proxy = os.getenv("FORCE_PROXY", "").lower() == "true"
        force_local = os.getenv("FORCE_LOCAL", "").lower() == "true"
        if force_proxy and not force_local:
            try:
                from app.utils.fetch.api_utils import get_proxy_manager
                proxy = get_proxy_manager().get_healthy_proxy()
                if proxy:
                    kwargs["proxies"] = {"http": proxy, "https": proxy}
                    display = proxy.split("@")[-1] if "@" in proxy else proxy
                    logger.info(f"Fetching schedule CDN via proxy {display}")
            except Exception as exc:
                logger.warning(f"Could not attach proxy for schedule CDN: {exc}")
        return kwargs

    def _load_schedule_payload(self):
        """Fetch the master schedule payload from the NBA CDN (with simple caching)."""
        if self._cached_schedule_payload is not None:
            return self._cached_schedule_payload

        try:
            response = requests.get(NBA_SCHEDULE_CDN_URL, **self._cdn_request_kwargs())
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
                    # Parse UTC datetime from API (format: "2024-10-25T19:30:00Z")
                    # Ensure it's timezone-aware and in UTC
                    if game_datetime_raw.endswith('Z'):
                        # ISO format with Z suffix
                        game_datetime = datetime.fromisoformat(game_datetime_raw.replace("Z", "+00:00"))
                    else:
                        # Already has timezone info
                        game_datetime = datetime.fromisoformat(game_datetime_raw)
                    
                    # Ensure datetime is timezone-aware and in UTC
                    if game_datetime.tzinfo is None:
                        # If naive, assume UTC
                        game_datetime = pytz.UTC.localize(game_datetime)
                    else:
                        # Convert to UTC if not already
                        game_datetime = game_datetime.astimezone(pytz.UTC)
                    
                    # Store as naive UTC datetime in TIMESTAMP column
                    # PostgreSQL TIMESTAMP (without timezone) stores naive datetimes
                    # We store UTC time and always query with AT TIME ZONE 'UTC' assumption
                    # This ensures consistent date handling regardless of server timezone
                    game_datetime = game_datetime.replace(tzinfo=None)
                    
                except ValueError as e:
                    logger.warning(f"Unable to parse gameDateTimeUTC '{game_datetime_raw}' for game {game.get('gameId')}: {e}")
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

        # Load valid team IDs from database to filter out non-NBA teams
        with get_db_context() as db:
            valid_teams = TeamORM.get_all(db)
            valid_team_ids = {team.team_id for team in valid_teams}
        logger.info(f"Loaded {len(valid_team_ids)} valid team IDs from database")

        try:
            schedule_entries = self._build_schedule_entries(season, mode="all")
        except Exception as exc:
            logger.error(f"Unable to build schedule entries: {exc}")
            return

        # Filter out schedule entries with invalid team IDs (non-NBA teams)
        filtered_entries = []
        skipped_count = 0
        for entry in schedule_entries:
            team_id = entry.get("team_id")
            opponent_team_id = entry.get("opponent_team_id")
            if team_id not in valid_team_ids or opponent_team_id not in valid_team_ids:
                skipped_count += 1
                logger.debug(f"Skipping schedule entry with invalid team IDs: "
                           f"team_id={team_id}, opponent_team_id={opponent_team_id}, game_id={entry.get('game_id')}")
                continue
            filtered_entries.append(entry)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} schedule entries with invalid team IDs (non-NBA teams)")

        # Store all games in the database using ORM
        if filtered_entries:
            try:
                with get_db_context() as db:
                    inserted = GameScheduleORM.bulk_create(filtered_entries, db=db)
                    db.commit()
                logger.info(f"Successfully stored/updated {inserted} schedule rows for {season}")
            except Exception as e:
                logger.error(f"Error storing schedule entries: {e}")
                raise
        else:
            logger.warning(f"No valid games found for {season} after filtering")

    def fetch_and_store_future_games(self, season):
        """
        Fetch and store upcoming games for the current NBA season from the NBA CDN.
        
        Args:
            season (str): Season in "YYYY-YY" format (e.g., "2024-25")
        """
        logger.info(f"Fetching future games for season {season}")

        # Load valid team IDs from database to filter out non-NBA teams
        with get_db_context() as db:
            valid_teams = TeamORM.get_all(db)
            valid_team_ids = {team.team_id for team in valid_teams}
        logger.info(f"Loaded {len(valid_team_ids)} valid team IDs from database")

        try:
            future_entries = self._build_schedule_entries(season, mode="future")
        except Exception as exc:
            # Soft-fail: CDN 403 / empty offseason payload should not block calculate
            logger.warning(
                f"Unable to build future schedule entries (soft-fail): {exc}. "
                f"Keeping existing upcoming games in DB."
            )
            return

        # Filter out schedule entries with invalid team IDs (non-NBA teams)
        filtered_entries = []
        skipped_count = 0
        for entry in future_entries:
            team_id = entry.get("team_id")
            opponent_team_id = entry.get("opponent_team_id")
            if team_id not in valid_team_ids or opponent_team_id not in valid_team_ids:
                skipped_count += 1
                logger.debug(f"Skipping future game with invalid team IDs: "
                           f"team_id={team_id}, opponent_team_id={opponent_team_id}, game_id={entry.get('game_id')}")
                continue
            filtered_entries.append(entry)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} future games with invalid team IDs (non-NBA teams)")

        if filtered_entries:
            try:
                with get_db_context() as db:
                    inserted = GameScheduleORM.bulk_create(filtered_entries, db=db)
                    db.commit()
                logger.info(f"Successfully stored/updated {inserted} future games for {season}")
            except Exception as e:
                logger.error(f"Error storing future games: {e}")
                raise
        else:
            logger.info(
                "No upcoming games found (normal in offseason) — future task OK"
            )