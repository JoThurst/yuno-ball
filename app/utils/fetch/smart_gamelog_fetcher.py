import logging
import os
import time
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Set

from requests.exceptions import Timeout, RequestException
from tqdm import tqdm
from nba_api.stats.endpoints import playergamelogs

from app.models.player_sqlalchemy import PlayerORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.utils.id_utils import normalize_nba_game_id
from app.models.statistics_sqlalchemy import StatisticsORM
from app.models.team_sqlalchemy import TeamORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.ingestion_run_sqlalchemy import IngestionTaskRunORM
from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.database import get_db_context
from app.utils.config_utils import MAX_WORKERS
from app.utils.season_utils import get_current_season

from .base_fetcher import BaseFetcher, rate_limiter

logger = logging.getLogger(__name__)

# Re-fetch players whose latest completed team game is newer than their latest stored log
RECENT_GAME_REFRESH_DAYS = 3


class PlayerGameLogConflictError(ValueError):
    """The league-wide source disagrees with canonical game/player identity."""

    def __init__(self, conflicts: dict[str, list[str]]):
        self.conflicts = conflicts
        details = "; ".join(
            f"{game_id}: {', '.join(reasons)}"
            for game_id, reasons in sorted(conflicts.items())
        )
        super().__init__(f"PlayerGameLogs conflicts: {details}")


def _source_row_summary(row: dict) -> str:
    return (
        f"player={row.get('PLAYER_ID')} team={row.get('TEAM_ID')} "
        f"pts={row.get('PTS')} min={row.get('MIN')}"
    )


def normalize_completed_gamelogs(
    response: dict,
    allowed: set,
    season: str,
    *,
    canonical_fallbacks: dict[str, list[dict]] | None = None,
) -> list:
    sets = response.get("resultSets") or []
    if not sets or not sets[0].get("rowSet"):
        raise ValueError("PlayerGameLogs returned no rows for completed games")
    headers = sets[0].get("headers") or []
    required = {"PLAYER_ID", "GAME_ID", "TEAM_ID", "PTS", "MIN", "AST", "REB", "STL", "BLK", "TOV"}
    if not required.issubset(headers):
        raise ValueError("PlayerGameLogs is missing required columns")
    games = {g for g, _ in allowed}
    seen = {}
    conflicts: dict[str, list[str]] = {}
    payload = []
    fields = {"points": "PTS", "assists": "AST", "rebounds": "REB",
              "steals": "STL", "blocks": "BLK", "turnovers": "TOV", "minutes_played": "MIN"}
    for values in sets[0]["rowSet"]:
        if len(values) != len(headers):
            raise ValueError("Malformed PlayerGameLogs row")
        row = dict(zip(headers, values))
        game_id = normalize_nba_game_id(row["GAME_ID"])
        if game_id not in games:
            continue
        if any(row[field] is None for field in required):
            raise ValueError("PlayerGameLogs is missing a required value for a completed game")
        team_id, player_id = int(row["TEAM_ID"]), int(row["PLAYER_ID"])
        if (game_id, team_id) not in allowed:
            conflicts.setdefault(game_id, []).append(
                f"unexpected team ({_source_row_summary(row)})"
            )
        prior = seen.get((player_id, game_id))
        if prior is not None:
            conflicts.setdefault(game_id, []).append(
                "duplicate player-game "
                f"({_source_row_summary(prior)}; {_source_row_summary(row)})"
            )
        seen[(player_id, game_id)] = row
        payload.append({"player_id": player_id, "game_id": game_id,
                        "team_id": team_id, "season": season,
                        **{key: row.get(source) for key, source in fields.items()}})
    if conflicts:
        fallbacks = canonical_fallbacks or {}
        unresolved = {game_id: reasons for game_id, reasons in conflicts.items()
                      if game_id not in fallbacks}
        if unresolved:
            raise PlayerGameLogConflictError(unresolved)
        conflict_games = set(conflicts)
        payload = [row for row in payload if row["game_id"] not in conflict_games]
        for game_id in sorted(conflict_games):
            payload.extend(fallbacks[game_id])
    if {(r["game_id"], r["team_id"]) for r in payload} != allowed:
        raise ValueError("PlayerGameLogs omits completed scheduled game/team rows")
    keys = [(r["player_id"], r["game_id"]) for r in payload]
    if len(keys) != len(set(keys)):
        raise ValueError("Resolved PlayerGameLogs still contains duplicate player-game keys")
    return payload


def canonical_game_fallback(
    facts: list,
    team_stats: list,
    *,
    game_id: str,
    schedule_teams: set[int],
    season: str,
    successful_run_ids: set[str],
) -> tuple[list[dict], dict]:
    """Build one legacy game projection from fully reconciled canonical facts."""
    if len(schedule_teams) != 2:
        raise ValueError(f"Canonical fallback requires two scheduled teams for {game_id}")
    if not facts:
        raise ValueError(f"Canonical fallback has no player facts for {game_id}")
    source_run_ids = {str(row.source_run_id) for row in facts}
    if len(source_run_ids) != 1 or not source_run_ids.issubset(successful_run_ids):
        raise ValueError(
            f"Canonical fallback source task is not successful for {game_id}: "
            f"runs={sorted(source_run_ids)}"
        )
    if any(
        row.canonical_game_id != game_id
        or int(row.canonical_team_id) not in schedule_teams
        or row.season != season
        or row.season_type != "Regular Season"
        or row.completeness_status != "complete"
        or row.source_name != "nba_boxscore_traditional_v3"
        for row in facts
    ):
        raise ValueError(f"Canonical fallback facts are incomplete or out of scope for {game_id}")
    stats_by_team = {int(row.team_id): row for row in team_stats}
    if set(stats_by_team) != schedule_teams or len(team_stats) != 2:
        raise ValueError(f"Canonical fallback lacks the reciprocal team-stat pair for {game_id}")
    required = {
        "points": "points", "assists": "assists", "rebounds": "rebounds_total",
        "steals": "steals", "blocks": "blocks", "turnovers": "turnovers",
        "minutes_played": "minutes",
    }
    payload = []
    totals = {team_id: {key: 0 for key in required if key != "minutes_played"}
              for team_id in schedule_teams}
    seen = set()
    for row in facts:
        if row.participation_status != "played":
            continue
        key = (int(row.canonical_player_id), game_id)
        if key in seen:
            raise ValueError(f"Canonical fallback has duplicate player-game identity for {game_id}")
        seen.add(key)
        values = {target: getattr(row, source) for target, source in required.items()}
        if any(value is None for value in values.values()) or not str(values["minutes_played"]).strip():
            raise ValueError(f"Canonical fallback has missing played-player fields for {game_id}")
        team_id = int(row.canonical_team_id)
        for field in totals[team_id]:
            totals[team_id][field] += int(values[field])
        payload.append({
            "player_id": int(row.canonical_player_id), "game_id": game_id,
            "team_id": team_id, "season": season, **values,
        })
    if {row["team_id"] for row in payload} != schedule_teams:
        raise ValueError(f"Canonical fallback omits played rows for a scheduled team in {game_id}")
    team_fields = {
        "points": "pts", "assists": "ast", "rebounds": "reb",
        "steals": "stl", "blocks": "blk", "turnovers": "tov",
    }
    for team_id, expected in totals.items():
        team_row = stats_by_team[team_id]
        if team_row.season != season or int(team_row.opponent_team_id) not in schedule_teams - {team_id}:
            raise ValueError(f"Canonical fallback team-stat identity mismatch for {game_id}")
        mismatches = {
            field: (value, getattr(team_row, team_fields[field]))
            for field, value in expected.items()
            if getattr(team_row, team_fields[field]) is None
            or value != int(getattr(team_row, team_fields[field]))
        }
        if mismatches:
            raise ValueError(
                f"Canonical fallback does not reconcile to team totals for "
                f"{game_id}/{team_id}: {mismatches}"
            )
    evidence = {
        "game_id": game_id,
        "source_run_id": next(iter(source_run_ids)),
        "player_rows": len(payload),
        "team_ids": sorted(schedule_teams),
        "data_available_at": max(row.data_available_at for row in facts).isoformat(),
        "canonical_source": "nba_boxscore_traditional_v3",
        "reconciled_fields": sorted(team_fields),
    }
    return payload, evidence


class SmartGameLogFetcher(BaseFetcher):
    """
    Fetches player game logs efficiently with batching, resume capability,
    and adaptive throttling to avoid API rate limits and timeouts.
    """

    def fetch_current_season_gamelogs_bulk(self, *, current_season: str) -> dict:
        """Refresh completed Regular Season logs in one source request.

        Validate the whole source batch before publishing. Out-of-scope source
        games are excluded; wrong team identities, duplicate keys, empty completed
        games, and storage failures fail the task rather than disappearing.
        """
        with get_db_context() as db:
            schedule = db.query(GameScheduleORM.game_id, GameScheduleORM.team_id).filter(
                GameScheduleORM.season == current_season,
                GameScheduleORM.season_type == "Regular Season",
                GameScheduleORM.result.isnot(None),
            ).all()
        allowed = {(normalize_nba_game_id(g), int(t)) for g, t in schedule}
        if not allowed:
            return {"rows_read": 0, "rows_written": 0, "games": 0}
        response = self.create_endpoint(
            playergamelogs.PlayerGameLogs,
            season_nullable=current_season,
            season_type_nullable="Regular Season",
            timeout=45,
        ).get_dict()
        recovery = []
        with get_db_context() as db:
            try:
                payload = normalize_completed_gamelogs(response, allowed, current_season)
            except PlayerGameLogConflictError as exc:
                fallback_by_game = {}
                conflict_games = sorted(exc.conflicts)
                facts = db.query(PlayerGameFactORM).filter(
                    PlayerGameFactORM.canonical_game_id.in_(conflict_games),
                ).all()
                stats = db.query(TeamGameStatsORM).filter(
                    TeamGameStatsORM.game_id.in_(conflict_games),
                ).all()
                run_ids = {str(row.source_run_id) for row in facts}
                successful_run_ids = {
                    str(run_id) for (run_id,) in db.query(IngestionTaskRunORM.run_id).filter(
                        IngestionTaskRunORM.run_id.in_(run_ids),
                        IngestionTaskRunORM.task_name == "fetch.player_facts",
                        IngestionTaskRunORM.status == "success",
                    ).all()
                }
                for game_id in conflict_games:
                    fallback, evidence = canonical_game_fallback(
                        [row for row in facts if row.canonical_game_id == game_id],
                        [row for row in stats if str(row.game_id) == game_id],
                        game_id=game_id,
                        schedule_teams={team for candidate, team in allowed if candidate == game_id},
                        season=current_season,
                        successful_run_ids=successful_run_ids,
                    )
                    fallback_by_game[game_id] = fallback
                    recovery.append({**evidence, "conflicts": exc.conflicts[game_id]})
                logger.warning(
                    "Resolved PlayerGameLogs conflicts from canonical facts: %s",
                    recovery,
                )
                payload = normalize_completed_gamelogs(
                    response, allowed, current_season,
                    canonical_fallbacks=fallback_by_game,
                )
            GameLogORM.bulk_upsert(payload, db=db)
            db.commit()
        return {"rows_read": len(response["resultSets"][0]["rowSet"]),
                "rows_written": len(payload), "games": len({r["game_id"] for r in payload}),
                "canonical_fallback_count": len(recovery),
                "canonical_fallbacks": recovery}

    def _player_needs_gamelog_refresh(
        self,
        player_id: int,
        season: str,
        completed_game_ids: Set[str],
        force_refresh: bool,
        db,
    ) -> bool:
        """Return True if we should hit the API for this player-season."""
        if force_refresh:
            return True

        existing_count = db.query(GameLogORM).filter(
            GameLogORM.player_id == player_id,
            GameLogORM.season == season,
        ).count()

        if existing_count == 0:
            return True

        # Player has logs — refresh if any completed schedule games are missing
        stored_game_ids = {
            normalize_nba_game_id(gid) for (gid,) in db.query(GameLogORM.game_id).filter(
                GameLogORM.player_id == player_id,
                GameLogORM.season == season,
            ).all()
        }
        missing = completed_game_ids - stored_game_ids
        # Only care about missing games if the player might have played;
        # if they have recent logs covering all recent completed games, skip.
        if not missing:
            return False

        # If missing games are all older than RECENT_GAME_REFRESH_DAYS and player
        # already has substantial logs, skip (likely DNP / inactive for those).
        # Always refresh when there are recently completed games not in storage.
        recent_cutoff = datetime.now() - timedelta(days=RECENT_GAME_REFRESH_DAYS)
        recent_missing = db.query(GameScheduleORM.game_id).filter(
            GameScheduleORM.season == season,
            GameScheduleORM.result.isnot(None),
            GameScheduleORM.game_date >= recent_cutoff,
            GameScheduleORM.game_id.in_(list(missing)[:500] if len(missing) > 500 else list(missing)),
        ).limit(1).first()

        return recent_missing is not None or existing_count < 5

    def _fetch_single_player_season_gamelogs(self, player_id: int, season: str) -> Optional[List[Dict]]:
        """
        Helper to fetch game logs for a single player for a single season.
        Returns a list of game log dictionaries, [] if already cached, or None on failure.
        """
        # Get player name using ORM
        with get_db_context() as db:
            player = PlayerORM.get_by_id(player_id, db)
            player_name = player.name if player else f"Player {player_id}"

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
        """Return the current NBA season string (October+ rule)."""
        return get_current_season()

    def _resolve_seasons_and_players(
        self,
        tier: str,
        start_year: int,
        end_year: int,
        current_season: Optional[str] = None,
    ) -> Tuple[List[str], List[int]]:
        """
        Determine which seasons and players should be processed for a given tier.
        """
        current_season = current_season or self._determine_current_season()
        seasons_to_fetch: List[str] = []
        player_ids: set[int] = set()

        if tier == "current":
            seasons_to_fetch = [current_season]
            with get_db_context() as db:
                active_players = PlayerORM.get_active_for_season(current_season, db)
                player_ids.update([p.player_id for p in active_players])
            logger.info(f"Tier 'current': {len(player_ids)} players -> {current_season}")

        elif tier == "recent":
            current_year = int(current_season[:4])
            seasons_to_fetch = [
                current_season,
                f"{current_year - 1}-{str(current_year)[-2:]}",
                f"{current_year - 2}-{str(current_year - 1)[-2:]}"
            ]
            with get_db_context() as db:
                active_players = PlayerORM.get_all(db)
                player_ids.update([p.player_id for p in active_players])
            logger.info(f"Tier 'recent': {len(player_ids)} players -> {', '.join(seasons_to_fetch)}")

        elif tier == "all":
            seasons_to_fetch = [
                f"{year}-{str(year + 1)[-2:]}"
                for year in range(start_year, end_year + 1)
            ]
            with get_db_context() as db:
                for season in seasons_to_fetch:
                    # StatisticsORM uses season_year parameter
                    player_ids.update(StatisticsORM.get_player_ids_for_season(season, db))
            logger.info(f"Tier 'all': {len(player_ids)} players across {len(seasons_to_fetch)} seasons.")

        else:
            raise ValueError("Tier must be one of: 'current', 'recent', 'all'")

        return seasons_to_fetch, sorted(list(player_ids))

    def fetch_game_logs_tiered(
        self,
        tier: str = "current",
        start_year: int = 2015,
        end_year: int = 2026,
        batch_size: int = 100,
        current_season: Optional[str] = None,
        force_refresh: Optional[bool] = None,
    ) -> None:
        """
        Fetches game logs based on a tiered approach:
        - "current": Only current season for active players.
        - "recent": Current season and last 2 seasons for active players.
        - "all": All seasons from start_year to end_year for all players with stats.

        Skips player-seasons that already have logs covering recent completed games
        unless force_refresh is True (or FORCE_GAMELOG_REFRESH=true).
        """
        if force_refresh is None:
            force_refresh = os.getenv("FORCE_GAMELOG_REFRESH", "").lower() in ("1", "true", "yes")

        # Load valid team IDs from database to filter out non-NBA teams (preseason games, etc.)
        with get_db_context() as db:
            valid_teams = TeamORM.get_all(db)
            valid_team_ids = {team.team_id for team in valid_teams}
            # Load valid game IDs from game_schedule to filter out summer league and other invalid games
            # Convert to strings to ensure type consistency with API responses
            valid_game_ids = {
                normalize_nba_game_id(result[0])
                for result in db.query(GameScheduleORM.game_id).distinct().all()
            }
        logger.info(f"Loaded {len(valid_team_ids)} valid team IDs from database")
        logger.info(f"Loaded {len(valid_game_ids)} valid game IDs from game_schedule")

        seasons_to_fetch, player_ids_to_fetch = self._resolve_seasons_and_players(
            tier, start_year, end_year, current_season=current_season
        )

        tasks: List[Tuple[int, str]] = []
        skipped_cached = 0

        with get_db_context() as db:
            for season in seasons_to_fetch:
                completed_game_ids = {
                    normalize_nba_game_id(gid)
                    for (gid,) in db.query(GameScheduleORM.game_id).filter(
                        GameScheduleORM.season == season,
                        GameScheduleORM.result.isnot(None),
                    ).distinct().all()
                }
                for player_id in player_ids_to_fetch:
                    if self._player_needs_gamelog_refresh(
                        player_id, season, completed_game_ids, force_refresh, db
                    ):
                        tasks.append((player_id, season))
                    else:
                        skipped_cached += 1

        if force_refresh:
            logger.info("FORCE_GAMELOG_REFRESH enabled — skipping cache optimization")
        logger.info(f"Skipped {skipped_cached} player-seasons already up to date")

        random.shuffle(tasks)
        total_tasks = len(tasks)
        logger.info(f"Total player-season combinations to process: {total_tasks}")

        if total_tasks == 0:
            logger.info("No player-seasons need gamelog refresh — done.")
            return

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
                # Convert API format to ORM format and filter out gamelogs with invalid team IDs
                # and games that don't exist in game_schedule (e.g., summer league games)
                game_logs_orm = []
                skipped_invalid_teams = 0
                skipped_invalid_games = 0
                for log in batch_results:
                    team_id = log.get("TEAM_ID")
                    game_id = normalize_nba_game_id(log.get("GAME_ID"))
                    
                    # Skip gamelogs with team IDs that don't exist in the teams table
                    # (e.g., preseason games vs non-NBA teams)
                    if team_id not in valid_team_ids:
                        skipped_invalid_teams += 1
                        logger.debug(f"Skipping gamelog with invalid team_id {team_id} (player {log.get('PLAYER_ID')}, game {game_id})")
                        continue
                    
                    # Skip gamelogs for games that don't exist in game_schedule
                    # (e.g., summer league games, exhibition games, etc.)
                    # Convert game_id to string for consistent comparison
                    if game_id not in valid_game_ids:
                        skipped_invalid_games += 1
                        logger.debug(f"Skipping gamelog with game not in schedule {game_id} (player {log.get('PLAYER_ID')}, team {team_id})")
                        continue
                    
                    game_logs_orm.append({
                        'player_id': log.get("PLAYER_ID"),
                        'game_id': game_id,
                        'team_id': team_id,
                        'season': log.get("SEASON"),
                        'points': log.get("PTS"),
                        'assists': log.get("AST"),
                        'rebounds': log.get("REB"),
                        'steals': log.get("STL"),
                        'blocks': log.get("BLK"),
                        'turnovers': log.get("TOV"),
                        'minutes_played': log.get("MIN")
                    })
                
                if skipped_invalid_teams > 0:
                    logger.info(f"Skipped {skipped_invalid_teams} gamelogs with invalid team IDs (non-NBA teams)")
                if skipped_invalid_games > 0:
                    logger.info(f"Skipped {skipped_invalid_games} gamelogs with games not in schedule (summer league, exhibition, etc.)")
                
                if game_logs_orm:
                    try:
                        with get_db_context() as db:
                            GameLogORM.bulk_upsert(game_logs_orm, db=db)
                            db.commit()
                        logger.info(f"Inserted/updated {len(game_logs_orm)} game logs this batch (skipped {skipped_invalid_teams} with invalid teams, {skipped_invalid_games} with games not in schedule).")
                        consecutive_failures = 0
                    except Exception as e:
                        logger.error(f"Error inserting game logs batch: {e}")
                        consecutive_failures += 1
                else:
                    logger.warning(f"No valid game logs to insert after filtering (skipped {skipped_invalid_teams} with invalid team IDs, {skipped_invalid_games} with games not in schedule).")
                    consecutive_failures += 1
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
