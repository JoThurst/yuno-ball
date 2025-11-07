import logging
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional

from requests.exceptions import Timeout, RequestException
from tqdm import tqdm
from nba_api.stats.endpoints import playergamelogs

from app.models.player import Player
from app.models.playergamelog import PlayerGameLog
from app.models.statistics import Statistics
from app.utils.config_utils import MAX_WORKERS

from .base_fetcher import BaseFetcher, rate_limiter

logger = logging.getLogger(__name__)


class SmartGameLogFetcher(BaseFetcher):
    """
    Fetches player game logs efficiently with batching, resume capability,
    and adaptive throttling to avoid API rate limits and timeouts.
    """

    def _fetch_single_player_season_gamelogs(self, player_id: int, season: str) -> Optional[List[Dict]]:
        """
        Helper to fetch game logs for a single player for a single season.
        Returns a list of game log dictionaries, [] if already cached, or None on failure.
        """
        player_name = Player.get_player_name(player_id)

        if PlayerGameLog.has_logs_for_season(player_id, season):
            logger.debug(f"Skipping game logs for {player_name} ({player_id}) in {season} - already exists.")
            return []

        try:
            rate_limiter.wait_if_needed()
            endpoint = self.create_endpoint(
                playergamelogs.PlayerGameLogs,
                player_id_nullable=player_id,
                season_nullable=season,
                timeout=45
            )
            response_data = endpoint.get_dict()

            result_sets = response_data.get("resultSets", [])
            if not result_sets or not result_sets[0].get("rowSet"):
                logger.debug(f"No game logs found for {player_name} ({player_id}) in {season}.")
                return []

            rows = result_sets[0].get("rowSet", [])
            headers = result_sets[0].get("headers", [])

            logs: List[Dict] = []
            for row in rows:
                log_dict = dict(zip(headers, row))
                log_dict["SEASON"] = season  # Ensure season column for DB insert
                logs.append(log_dict)

            logger.debug(f"Fetched {len(logs)} game logs for {player_name} ({player_id}) in {season}.")
            return logs

        except (Timeout, RequestException) as exc:
            logger.warning(f"Timeout/RequestError fetching logs for {player_name} ({player_id}) in {season}: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Unexpected error fetching logs for {player_name} ({player_id}) in {season}: {exc}")
            return None

    def _determine_current_season(self) -> str:
        """Return the current NBA season string."""
        now = datetime.now()
        if now.month >= 9:
            return f"{now.year}-{str(now.year + 1)[-2:]}"
        return f"{now.year - 1}-{str(now.year)[-2:]}"

    def _resolve_seasons_and_players(
        self,
        tier: str,
        start_year: int,
        end_year: int
    ) -> Tuple[List[str], List[int]]:
        """
        Determine which seasons and players should be processed for a given tier.
        """
        current_season = self._determine_current_season()
        seasons_to_fetch: List[str] = []
        player_ids: set[int] = set()

        if tier == "current":
            seasons_to_fetch = [current_season]
            active_players = Player.get_all_players()
            player_ids.update([p.player_id for p in active_players])
            logger.info(f"Tier 'current': {len(player_ids)} players -> {current_season}")

        elif tier == "recent":
            current_year = int(current_season[:4])
            seasons_to_fetch = [
                current_season,
                f"{current_year - 1}-{str(current_year)[-2:]}",
                f"{current_year - 2}-{str(current_year - 1)[-2:]}"
            ]
            active_players = Player.get_all_players()
            player_ids.update([p.player_id for p in active_players])
            logger.info(f"Tier 'recent': {len(player_ids)} players -> {', '.join(seasons_to_fetch)}")

        elif tier == "all":
            seasons_to_fetch = [
                f"{year}-{str(year + 1)[-2:]}"
                for year in range(start_year, end_year + 1)
            ]
            for season in seasons_to_fetch:
                player_ids.update(Statistics.get_player_ids_for_season(season))
            logger.info(f"Tier 'all': {len(player_ids)} players across {len(seasons_to_fetch)} seasons.")

        else:
            raise ValueError("Tier must be one of: 'current', 'recent', 'all'")

        return seasons_to_fetch, sorted(list(player_ids))

    def fetch_game_logs_tiered(
        self,
        tier: str = "current",
        start_year: int = 2015,
        end_year: int = 2026,
        batch_size: int = 100
    ) -> None:
        """
        Fetches game logs based on a tiered approach:
        - "current": Only current season for active players.
        - "recent": Current season and last 2 seasons for active players.
        - "all": All seasons from start_year to end_year for all players with stats.
        """
        PlayerGameLog.create_table()

        seasons_to_fetch, player_ids_to_fetch = self._resolve_seasons_and_players(
            tier, start_year, end_year
        )

        tasks: List[Tuple[int, str]] = []
        for player_id in player_ids_to_fetch:
            for season in seasons_to_fetch:
                tasks.append((player_id, season))

        random.shuffle(tasks)
        total_tasks = len(tasks)
        logger.info(f"Total player-season combinations to process: {total_tasks}")

        successful_fetches = 0
        failed_fetches: List[Tuple[int, str]] = []
        processed_count = 0
        consecutive_failures = 0

        for idx in tqdm(range(0, total_tasks, batch_size), desc="Processing Game Log Batches"):
            batch_tasks = tasks[idx: idx + batch_size]

            if consecutive_failures >= 3:
                logger.warning("Hit 3+ consecutive failing batches. Sleeping 5 minutes...")
                time.sleep(300)
                consecutive_failures = 0
            elif consecutive_failures > 0:
                adaptive_delay = 2.0 + consecutive_failures
                logger.info(f"Adaptive delay: {adaptive_delay}s (consecutive failing batches: {consecutive_failures})")
                time.sleep(adaptive_delay)
            else:
                time.sleep(2.0)

            batch_results: List[Dict] = []

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(self._fetch_single_player_season_gamelogs, pid, season): (pid, season)
                    for pid, season in batch_tasks
                }

                for future in as_completed(futures):
                    player_id, season = futures[future]
                    try:
                        logs = future.result(timeout=60)
                        if logs:
                            batch_results.extend(logs)
                            successful_fetches += 1
                        elif logs is None:
                            failed_fetches.append((player_id, season))
                    except Timeout:
                        logger.warning(f"Future timed out for player {player_id} ({season}).")
                        failed_fetches.append((player_id, season))
                    except Exception as exc:  # noqa: BLE001
                        logger.error(f"Error processing player {player_id}, season {season}: {exc}")
                        failed_fetches.append((player_id, season))

            if batch_results:
                PlayerGameLog.insert_game_logs(batch_results)
                logger.info(f"Inserted/updated {len(batch_results)} game logs this batch.")
                consecutive_failures = 0
            else:
                logger.warning(f"No logs inserted this batch. Tasks failed or skipped: {len(batch_tasks)}")
                consecutive_failures += 1

            processed_count += len(batch_tasks)
            logger.info(
                f"Batch progress: {processed_count}/{total_tasks} processed | "
                f"Successful player-seasons: {successful_fetches} | "
                f"Failures: {len(failed_fetches)}"
            )

        logger.info("\n" + "=" * 70)
        logger.info(f"Game Log Fetching Summary (Tier: {tier.upper()})")
        logger.info(f"Total tasks attempted: {total_tasks}")
        logger.info(f"Successful player-season fetches: {successful_fetches}")
        logger.info(f"Failed player-season fetches: {len(failed_fetches)}")
        if failed_fetches:
            logger.warning(f"Failed player-season combinations (first 20): {failed_fetches[:20]}")
        logger.info("=" * 70 + "\n")

