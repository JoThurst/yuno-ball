"""
BulkSeasonFetcher - Efficient season stats fetching using bulk endpoints.

This fetcher uses LeagueDashPlayerStats and LeagueDashTeamStats to fetch
ALL players/teams in a single API call per season, instead of making
individual calls for each player.

Efficiency: 1 call per season vs 1483 calls per season = 99.93% reduction
"""

import logging
import time
from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats
from app.models.player_sqlalchemy import PlayerORM
from app.models.statistics_sqlalchemy import StatisticsORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.database import get_db_context
from .base_fetcher import BaseFetcher, rate_limiter

logger = logging.getLogger(__name__)


class BulkSeasonFetcher(BaseFetcher):
    """
    Fetches season data for ALL players and teams using bulk endpoints.
    
    This is the most efficient way to populate historical data.
    """
    
    def _generate_season_list(self, start_year, end_year):
        """Generate list of season strings."""
        return [f"{year}-{str(year + 1)[-2:]}" for year in range(start_year, end_year)]
    
    def fetch_all_seasons_player_stats(self, seasons=None, start_year=2015, end_year=2026):
        """
        Fetch season stats for ALL players using bulk endpoint.
        
        This replaces 1483+ individual PlayerCareerStats calls with just
        1 call per season!
        
        Args:
            seasons: List of season strings (e.g., ["2023-24", "2024-25"])
                    If None, generates from start_year to end_year
            start_year: Start year if seasons not provided
            end_year: End year if seasons not provided
        
        Returns:
            dict: Summary of results {season: player_count}
        """
        if seasons is None:
            seasons = self._generate_season_list(start_year, end_year)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"BULK SEASON STATS FETCH: {len(seasons)} seasons")
        logger.info(f"Seasons: {', '.join(seasons)}")
        logger.info(f"{'='*70}\n")
        
        results = {}
        total_players_processed = 0
        
        for idx, season in enumerate(seasons, 1):
            logger.info(f"\n[{idx}/{len(seasons)}] Fetching {season}...")
            
            try:
                rate_limiter.wait_if_needed()
                
                # ONE API call gets ALL players for this season
                endpoint = self.create_endpoint(
                    leaguedashplayerstats.LeagueDashPlayerStats,
                    season=season,
                    season_type_all_star="Regular Season",
                    measure_type_detailed_defense="Base",
                    per_mode_detailed="Totals",
                    last_n_games=0,
                    month=0,
                    opponent_team_id=0,
                    pace_adjust="N",
                    period=0,
                    plus_minus="N",
                    rank="N"
                )
                
                response = endpoint.get_normalized_dict()
                
                if "LeagueDashPlayerStats" not in response:
                    logger.error(f"❌ {season}: Invalid API response")
                    results[season] = 0
                    continue
                
                player_data = response["LeagueDashPlayerStats"]
                logger.info(f"✓ Received {len(player_data)} players for {season}")
                
                # Process each player
                players_added = 0
                stats_added = 0
                
                # Process all players in a single database session for efficiency
                with get_db_context() as db:
                    for player_stat in player_data:
                        player_id = player_stat.get('PLAYER_ID')
                        if not player_id:
                            continue
                        
                        # Add player to players table if new using ORM
                        if not PlayerORM.exists(player_id, db):
                            try:
                                PlayerORM.create(
                                    player_id=player_id,
                                    name=player_stat.get('PLAYER_NAME', 'Unknown'),
                                    position=None,  # Not provided by this endpoint
                                    weight=None,
                                    born_date=None,
                                    age=player_stat.get('AGE'),
                                    exp=None,
                                    school=None,
                                    available_seasons=[season]  # ORM expects list, will be appended on subsequent seasons
                                )
                                players_added += 1
                            except Exception as e:
                                logger.debug(f"Player {player_id} already exists or error: {e}")
                        
                        # Add/update season stats using ORM (upserts automatically)
                        try:
                            StatisticsORM.create(
                                player_id=player_id,
                                season_year=season,
                                points=player_stat.get('PTS', 0),
                                rebounds=player_stat.get('REB', 0),
                                assists=player_stat.get('AST', 0),
                                steals=player_stat.get('STL', 0),
                                blocks=player_stat.get('BLK', 0),
                                db=db
                            )
                            stats_added += 1
                        except Exception as e:
                            logger.error(f"Error adding stats for player {player_id}: {e}")
                    
                    # Commit all changes for this season
                    db.commit()
                
                results[season] = len(player_data)
                total_players_processed += len(player_data)
                
                logger.info(f"✓ {season} complete:")
                logger.info(f"  - {players_added} new players added to database")
                logger.info(f"  - {stats_added} season stat records stored")
                
                # Conservative delay between seasons
                if idx < len(seasons):
                    time.sleep(2.0)
                
            except Exception as e:
                logger.error(f"❌ Error fetching {season}: {e}")
                results[season] = 0
                continue
        
        # Summary
        logger.info(f"\n{'='*70}")
        logger.info(f"✓ BULK SEASON STATS COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Total seasons processed: {len(seasons)}")
        logger.info(f"Total player-season records: {total_players_processed}")
        logger.info(f"API calls used: {len(seasons)} (vs {total_players_processed} old method)")
        logger.info(f"Efficiency gain: {(1 - len(seasons)/max(total_players_processed, 1)) * 100:.1f}%")
        logger.info(f"{'='*70}\n")
        
        return results
    
    def fetch_all_seasons_team_stats(self, seasons=None, start_year=2015, end_year=2026):
        """
        NOTE: For team stats, use TeamFetcher.fetch_league_dash_team_stats() instead.
        
        The league_dash_team_stats table has a complex schema with hundreds of 
        prefixed columns (Base_Totals_GP, Advanced_Per48_*, etc.). The existing
        fetch_and_store_league_dash_team_stats() in fetch_utils.py properly handles
        all the measure types and column prefixing.
        
        This method is kept for API compatibility but redirects to the proper implementation.
        """
        logger.warning("="*70)
        logger.warning("Team stats should use TeamFetcher.fetch_league_dash_team_stats()")
        logger.warning("That method properly handles the complex column schema.")
        logger.warning("Skipping bulk team stats - use TeamFetcher instead.")
        logger.warning("="*70)
        
        return {}

