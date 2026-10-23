import logging
import os
from datetime import date, datetime
import pytz
import requests
from zoneinfo import ZoneInfo
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_sqlalchemy import TeamORM
from app.database import get_db_context
from app.utils.season_utils import normalize_season, season_type_from_game_id
from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

NBA_SCHEDULE_CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
EASTERN = ZoneInfo("America/New_York")
SCHEDULE_SOURCES = {"auto", "stats_api", "cdn"}


class ScheduleSourceError(RuntimeError):
    """Raised when a schedule source cannot satisfy the requested season."""

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

    @staticmethod
    def _validate_payload_season(payload, season):
        payload_season = payload.get("seasonYear")
        if payload_season and payload_season != season:
            raise ScheduleSourceError(
                f"Schedule CDN returned season {payload_season!r}; requested {season!r}"
            )
        if not payload.get("gameDates"):
            raise ScheduleSourceError(
                f"Schedule CDN returned no game dates for requested season {season!r}"
            )

    def _load_schedule_payload(self, season):
        """Fetch the master schedule payload from the NBA CDN (with simple caching)."""
        if self._cached_schedule_payload is not None:
            self._validate_payload_season(self._cached_schedule_payload, season)
            return self._cached_schedule_payload

        try:
            response = requests.get(NBA_SCHEDULE_CDN_URL, **self._cdn_request_kwargs())
            response.raise_for_status()
            payload = response.json().get("leagueSchedule", {})
            if not payload:
                raise ScheduleSourceError(
                    "Schedule CDN response missing 'leagueSchedule' payload"
                )
            self._validate_payload_season(payload, season)
            self._cached_schedule_payload = payload
            return payload
        except ScheduleSourceError:
            raise
        except requests.RequestException as exc:
            logger.error(f"Failed to download schedule payload: {exc}")
            raise

    @staticmethod
    def _record_value(record, *keys):
        for key in keys:
            if key in record:
                return record[key]
        return None

    @staticmethod
    def _parse_game_datetime(value, *, game_id):
        if not value:
            raise ScheduleSourceError(
                f"Schedule game {game_id!r} is missing gameDateTimeUTC"
            )
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ScheduleSourceError(
                f"Schedule game {game_id!r} has invalid gameDateTimeUTC {value!r}"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = pytz.UTC.localize(parsed)
        return parsed.astimezone(pytz.UTC).replace(tzinfo=None)

    @staticmethod
    def _parse_score(value):
        if value in (None, "", "-"):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _entries_from_records(
        cls,
        records,
        *,
        season,
        source_name,
        source_parser_version,
        mode="all",
        start_date=None,
        end_date=None,
        season_types=None,
    ):
        season = normalize_season(season)
        allowed_types = set(season_types or ())
        entries = []
        for record in records:
            game_id = str(cls._record_value(record, "gameId", "GAME_ID") or "").strip()
            if not game_id:
                raise ScheduleSourceError("Schedule source returned a game without gameId")
            game_season = str(
                cls._record_value(record, "seasonYear", "SEASON_YEAR") or season
            )
            if game_season != season:
                raise ScheduleSourceError(
                    f"Schedule source returned game {game_id!r} for season {game_season!r}; "
                    f"requested {season!r}"
                )
            season_type = season_type_from_game_id(game_id)
            if season_type == "Unknown":
                raise ScheduleSourceError(
                    f"Schedule source returned unsupported game ID {game_id!r}"
                )
            if allowed_types and season_type not in allowed_types:
                continue

            status = cls._record_value(record, "gameStatus", "GAME_STATUS")
            try:
                status_code = int(status)
            except (TypeError, ValueError):
                status_code = None
            is_upcoming = status_code in (1, 2)
            if mode == "future" and not is_upcoming:
                continue
            if mode == "past" and is_upcoming:
                continue

            game_datetime = cls._parse_game_datetime(
                cls._record_value(record, "gameDateTimeUTC", "GAME_DATE_TIME_UTC"),
                game_id=game_id,
            )
            eastern_date = game_datetime.replace(tzinfo=pytz.UTC).astimezone(EASTERN).date()
            if start_date is not None and eastern_date < start_date:
                continue
            if end_date is not None and eastern_date > end_date:
                continue

            home_id = cls._record_value(record, "homeTeam_teamId", "HOME_TEAM_ID")
            away_id = cls._record_value(record, "awayTeam_teamId", "AWAY_TEAM_ID")
            if not home_id or not away_id:
                # The released schedule can contain NBA Cup games whose
                # eventual matchup is still TBD.  This is an expected,
                # non-canonical state: retain the rest of the season payload
                # and let a later schedule refresh materialize the reciprocal
                # rows once both teams are known.
                logger.info(
                    "Skipping unresolved TBD schedule game %s from %s",
                    game_id,
                    source_name,
                )
                continue
            home_id, away_id = int(home_id), int(away_id)
            is_final = status_code == 3
            home_score = cls._parse_score(
                cls._record_value(record, "homeTeam_score", "HOME_TEAM_SCORE")
            )
            away_score = cls._parse_score(
                cls._record_value(record, "awayTeam_score", "AWAY_TEAM_SCORE")
            )
            if is_final and (
                home_score is None
                or away_score is None
                or (home_score == 0 and away_score == 0)
                or home_score == away_score
            ):
                raise ScheduleSourceError(
                    f"Final schedule game {game_id!r} has unresolved scores "
                    f"({home_score!r}-{away_score!r})"
                )
            # ScheduleLeagueV2 uses zero scores as a placeholder for games
            # that have not started.  The canonical schedule contract only
            # stores scores for completed games; otherwise the database's
            # result/score checks correctly reject the row.
            if not is_final:
                home_score = away_score = None
            score = None
            home_result = away_result = None
            if home_score is not None and away_score is not None:
                score = f"{home_score}-{away_score}"
                if is_final and home_score != away_score:
                    home_result = "W" if home_score > away_score else "L"
                    away_result = "L" if home_result == "W" else "W"

            common = {
                "game_id": game_id,
                "season": season,
                "season_type": season_type,
                "game_date": game_datetime,
                "game_date_precision": "exact",
                "source_name": source_name,
                "source_parser_version": source_parser_version,
                "team_score": home_score,
                "opponent_score": away_score,
            }
            entries.extend([
                {
                    **common,
                    "team_id": home_id,
                    "opponent_team_id": away_id,
                    "home_or_away": "H",
                    "result": home_result,
                    "score": score,
                },
                {
                    **common,
                    "team_id": away_id,
                    "opponent_team_id": home_id,
                    "home_or_away": "A",
                    "result": away_result,
                    "score": score,
                    "team_score": away_score,
                    "opponent_score": home_score,
                },
            ])
        return entries

    def _build_stats_api_entries(
        self,
        season,
        *,
        mode="all",
        start_date=None,
        end_date=None,
        season_types=None,
    ):
        from nba_api.stats.endpoints import ScheduleLeagueV2

        endpoint = self.create_endpoint(
            ScheduleLeagueV2,
            league_id="00",
            season=normalize_season(season),
            validate=True,
        )
        records = endpoint.season_games.get_data_frame().to_dict("records")
        if not records:
            raise ScheduleSourceError(
                f"NBA Stats ScheduleLeagueV2 returned no games for {season!r}"
            )
        return self._entries_from_records(
            records,
            season=season,
            source_name="nba-stats-scheduleleaguev2",
            source_parser_version="scheduleleaguev2-v1",
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            season_types=season_types,
        )

    def _build_schedule_entries(
        self,
        season,
        mode="all",
        *,
        source="auto",
        start_date=None,
        end_date=None,
        season_types=None,
    ):
        """
        Build schedule entries for the requested season.

        Args:
            season (str): Season string in format 'YYYY-YY'
            mode (str): 'all', 'past', or 'future'
        """
        if source not in SCHEDULE_SOURCES:
            raise ValueError(f"source must be one of {sorted(SCHEDULE_SOURCES)}")
        season = normalize_season(season)
        if start_date is not None and end_date is not None and end_date < start_date:
            raise ValueError("end_date cannot precede start_date")

        if source in {"auto", "stats_api"}:
            try:
                api_entries = self._build_stats_api_entries(
                    season,
                    mode=mode,
                    start_date=start_date,
                    end_date=end_date,
                    season_types=season_types,
                )
                if api_entries:
                    return api_entries
                if source == "stats_api":
                    raise ScheduleSourceError(
                        f"NBA Stats ScheduleLeagueV2 returned no matching games for {season!r}"
                    )
            except (ScheduleSourceError, requests.RequestException, ImportError) as exc:
                if source == "stats_api":
                    raise
                logger.warning(
                    "NBA Stats ScheduleLeagueV2 unavailable for %s; trying validated CDN fallback: %s",
                    season,
                    exc,
                )

        payload = self._load_schedule_payload(season)

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
                    game_datetime = self._parse_game_datetime(
                        game_datetime_raw,
                        game_id=game.get("gameId"),
                    )
                except ScheduleSourceError as exc:
                    logger.warning(str(exc))
                    continue
                eastern_date = game_datetime.replace(tzinfo=pytz.UTC).astimezone(EASTERN).date()
                if start_date is not None and eastern_date < start_date:
                    continue
                if end_date is not None and eastern_date > end_date:
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
                if not is_final or (home_score == 0 and away_score == 0):
                    home_score = away_score = None
                season_type = season_type_from_game_id(game.get("gameId"))
                if season_type == "Unknown":
                    logger.warning("Skipping schedule game with unsupported ID: %s", game.get("gameId"))
                    continue
                if season_types and season_type not in set(season_types):
                    continue
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
                    "season_type": season_type,
                    "team_id": home_id,
                    "opponent_team_id": away_id,
                    "game_date": game_datetime,
                    "game_date_precision": "exact",
                    "home_or_away": "H",
                    "result": home_result,
                    "score": score_str,
                    "team_score": home_score,
                    "opponent_score": away_score,
                    "source_name": "nba-cdn-schedule",
                    "source_parser_version": "scheduleleaguev2-cdn-v1",
                })
                entries.append({
                    "game_id": game.get("gameId"),
                    "season": season,
                    "season_type": season_type,
                    "team_id": away_id,
                    "opponent_team_id": home_id,
                    "game_date": game_datetime,
                    "game_date_precision": "exact",
                    "home_or_away": "A",
                    "result": away_result,
                    "score": score_str,
                    "team_score": away_score,
                    "opponent_score": home_score,
                    "source_name": "nba-cdn-schedule",
                    "source_parser_version": "scheduleleaguev2-cdn-v1",
                })

        return entries

    def fetch_schedule_entries(
        self,
        season,
        *,
        source="auto",
        mode="all",
        start_date=None,
        end_date=None,
        season_types=None,
    ):
        """Fetch validated schedule rows without writing to PostgreSQL."""
        return self._build_schedule_entries(
            season,
            mode=mode,
            source=source,
            start_date=start_date,
            end_date=end_date,
            season_types=season_types,
        )

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
            raise

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
