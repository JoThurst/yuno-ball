"""Team service for team-related operations.

This service handles team data retrieval, statistics, lineups, and game schedules.
Migrated to use SQLAlchemy ORM models.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import traceback

from sqlalchemy.orm import Session
from nba_api.stats.endpoints import leaguedashlineups

from app.services.base_service import BaseService
from app.models.team_sqlalchemy import TeamORM, RosterORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
from app.utils.config_utils import logger


class TeamService(BaseService):
    """Service for team-related operations.
    
    Can be used as instance methods or static methods for backward compatibility.
    """
    
    def get_team_lineup_stats(
        self,
        team_id: int,
        season: str = "2024-25",
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch the most recent and most used starting lineups for a given team.
        
        Args:
            team_id: The ID of the team
            season: The NBA season (e.g., "2024-25")
            db: Optional database session for transaction control
        
        Returns:
            Dictionary containing both the most recent lineup, most used lineup, and resolved player IDs
        """
        cache_key = f"team_lineup_stats_{team_id}_{season}"
        
        def fetch_lineup_stats(session: Session) -> Optional[Dict[str, Any]]:
            try:
                # Use create_api_endpoint to handle proxy configuration
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
                team = TeamORM.get_by_id(team_id, session)
                if not team:
                    return None
                
                roster = team.get_roster(season=season, db=session)
                team_roster = [r.to_dict() for r in roster]

                # Function to match player names to IDs using the Roster
                def match_players_to_ids(player_names):
                    matched_player_ids = []
                    for player in team_roster:
                        full_name = player.get("player_name", "")
                        if not full_name:
                            continue
                        name_parts = full_name.split(" ")
                        if len(name_parts) < 2:
                            continue
                        first_initial = name_parts[0][0]  # First initial
                        last_name = " ".join(name_parts[1:])  # Full last name (Handles Jr., III cases)

                        # Match exact name using full name comparison
                        if any(f"{first_initial}. {last_name}" in name for name in player_names):
                            matched_player_ids.append(player.get("player_id"))
                    return matched_player_ids

                result = {
                    "most_used_lineup": {
                        "team_id": int(most_used_lineup["TEAM_ID"]) if "TEAM_ID" in most_used_lineup else None,
                        "team_abbreviation": most_used_lineup["TEAM_ABBREVIATION"] if "TEAM_ABBREVIATION" in most_used_lineup else None,
                        "lineup": most_used_lineup["GROUP_NAME"] if "GROUP_NAME" in most_used_lineup else None,
                        "gp": int(most_used_lineup["GP"]) if "GP" in most_used_lineup else None,
                        "w_pct": float(most_used_lineup["W_PCT"]) if "W_PCT" in most_used_lineup else None,
                        "pts_rank": int(most_used_lineup["PTS_RANK"]) if "PTS_RANK" in most_used_lineup else None, 
                        "plus_minus_rank": int(most_used_lineup["PLUS_MINUS_RANK"]) if "PLUS_MINUS_RANK" in most_used_lineup else None,  
                        "reb_rank": int(most_used_lineup["REB_RANK"]) if "REB_RANK" in most_used_lineup else None,
                        "ast_rank": int(most_used_lineup["AST_RANK"]) if "AST_RANK" in most_used_lineup else None,
                        "player_ids": match_players_to_ids(most_used_players),
                    },
                    "most_recent_lineup": {
                        "team_id": int(most_recent_lineup["TEAM_ID"]) if "TEAM_ID" in most_recent_lineup else None,
                        "team_abbreviation": most_recent_lineup["TEAM_ABBREVIATION"] if "TEAM_ABBREVIATION" in most_recent_lineup else None,
                        "lineup": most_recent_lineup["GROUP_NAME"] if "GROUP_NAME" in most_recent_lineup else None,
                        "gp": int(most_recent_lineup["GP"]) if "GP" in most_recent_lineup else None,
                        "w_pct": float(most_recent_lineup["W_PCT"]) if "W_PCT" in most_recent_lineup else None,
                        "pts_rank": int(most_recent_lineup["PTS_RANK"]) if "PTS_RANK" in most_recent_lineup else None,
                        "reb_rank": int(most_recent_lineup["REB_RANK"]) if "REB_RANK" in most_recent_lineup else None,
                        "ast_rank": int(most_recent_lineup["AST_RANK"]) if "AST_RANK" in most_recent_lineup else None,
                        "plus_minus_rank": int(most_recent_lineup["PLUS_MINUS_RANK"]) if "PLUS_MINUS_RANK" in most_recent_lineup else None, 
                        "player_ids": match_players_to_ids(most_recent_players),
                    },
                }
                
                return result
            except Exception as e:
                logger.error(f"Error fetching team lineup stats: {e}")
                return None
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_lineup_stats, db),
            ttl=21600  # 6 hours
        )
    
    def get_team_stats(
        self,
        team_id: int,
        season: str = "2024-25",
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Fetch team statistics for the given season.
        
        Args:
            team_id: The ID of the team
            season: The NBA season (e.g., "2024-25")
            db: Optional database session for transaction control
        
        Returns:
            Dictionary with team statistics
        """
        cache_key = f"team_stats_{team_id}_{season}"
        
        def fetch_team_stats(session: Session) -> Dict[str, Any]:
            # Get stats from LeagueDashTeamStatsORM
            team_stats_orm = LeagueDashTeamStatsORM.get_by_team(team_id, season, "Regular Season", db=session)
            
            # Define default stats with None values
            default_stats = {
                "pts": None, "reb": None, "ast": None, "stl": None, "blk": None, 
                "tov": None, "fg_pct": None, "fg3_pct": None, "ft_pct": None,
                "off_rtg": None, "def_rtg": None, "net_rtg": None, "pace": None, "ts_pct": None
            }
            
            if team_stats_orm:
                # Get Base Totals stats
                base_stats = team_stats_orm.to_dict(measure_type='Base', per_mode='Totals')
                
                # Map Base stats
                default_stats["pts"] = base_stats.get("pts")
                default_stats["reb"] = base_stats.get("reb")
                default_stats["ast"] = base_stats.get("ast")
                default_stats["stl"] = base_stats.get("stl")
                default_stats["blk"] = base_stats.get("blk")
                default_stats["tov"] = base_stats.get("tov")
                default_stats["fg_pct"] = base_stats.get("fg_pct")
                default_stats["fg3_pct"] = base_stats.get("fg3_pct")
                default_stats["ft_pct"] = base_stats.get("ft_pct")
                
                # Get Advanced stats
                advanced_stats = team_stats_orm.to_dict(measure_type='Advanced', per_mode='Totals')
                default_stats["off_rtg"] = advanced_stats.get("off_rating")
                default_stats["def_rtg"] = advanced_stats.get("def_rating")
                default_stats["net_rtg"] = advanced_stats.get("net_rating")
                default_stats["pace"] = advanced_stats.get("pace")
                default_stats["ts_pct"] = advanced_stats.get("ts_pct")
            
            return default_stats
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_team_stats, db),
            ttl=21600  # 6 hours
        )
    
    def get_team_game_results(
        self,
        team_id: int,
        limit: int = 10,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent game results for a team.
        
        Args:
            team_id: The ID of the team
            limit: Maximum number of games to return
            db: Optional database session for transaction control
        
        Returns:
            List of recent game results
        """
        cache_key = f"team_game_results_{team_id}_{limit}"
        
        def fetch_game_results(session: Session) -> List[Dict[str, Any]]:
            # Get recent games from GameScheduleORM
            games = GameScheduleORM.get_last_n_games(team_id, limit, db=session)
            
            if not games:
                return []
            
            # Convert to dictionaries and format dates
            formatted_games = []
            for game in games:
                game_dict = game.to_dict() if hasattr(game, 'to_dict') else game
                
                # Convert game_date string to datetime if needed
                if isinstance(game_dict.get("date"), str):
                    try:
                        game_dict["game_date"] = datetime.strptime(game_dict["date"], "%Y-%m-%d")
                    except ValueError:
                        game_dict["game_date"] = game_dict.get("date")
                
                formatted_games.append(game_dict)
            
            return formatted_games
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_game_results, db),
            ttl=3600  # 1 hour
        )
    
    def get_team_upcoming_schedule(
        self,
        team_id: int,
        limit: int = 5,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming games for a team.
        
        Args:
            team_id: The ID of the team
            limit: Maximum number of games to return
            db: Optional database session for transaction control
        
        Returns:
            List of upcoming games
        """
        cache_key = f"team_upcoming_schedule_{team_id}_{limit}"
        
        def fetch_upcoming_games(session: Session) -> List[Dict[str, Any]]:
            # Get upcoming games from GameScheduleORM
            games = GameScheduleORM.get_upcoming_n_games(team_id, limit, db=session)
            
            if not games:
                return []
            
            # Convert to dictionaries and format dates
            formatted_games = []
            for game in games:
                game_dict = game.to_dict() if hasattr(game, 'to_dict') else game
                
                # Convert game_date string to datetime if needed
                if isinstance(game_dict.get("game_date"), str):
                    try:
                        game_dict["game_date"] = datetime.strptime(game_dict["game_date"], "%Y-%m-%d")
                    except ValueError:
                        pass
                
                formatted_games.append(game_dict)
            
            return formatted_games
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_upcoming_games, db),
            ttl=3600  # 1 hour
        )
    
    def get_complete_team_details(
        self,
        team_id: int,
        season: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive team details for the team detail page.
        
        Args:
            team_id: The ID of the team
            season: Optional season (e.g., "2024-25"). If None, uses current season.
            db: Optional database session for transaction control
        
        Returns:
            Dictionary with complete team details or None if not found
        """
        def fetch_team_details(session: Session) -> Optional[Dict[str, Any]]:
            try:
                # Get current season if not provided (do this first before using season)
                current_season = season
                if current_season is None:
                    current_year = datetime.now().year
                    current_month = datetime.now().month
                    if current_month >= 10:  # NBA season starts in October
                        current_season = f"{current_year}-{str(current_year + 1)[-2:]}"
                    else:
                        current_season = f"{current_year-1}-{str(current_year)[-2:]}"
                
                # Get base team data using ORM
                team = TeamORM.get_by_id(team_id, session)
                if not team:
                    logger.error(f"Team with ID {team_id} not found")
                    return None
                
                # Convert to dict
                team_data = team.to_dict()
                
                # Get roster (filter by season if provided)
                if current_season:
                    roster = team.get_roster(season=current_season, db=session)
                else:
                    roster = team.get_roster(db=session)
                team_data["roster"] = [r.to_dict() for r in roster]
                
                # Get team standings rank using ORM
                try:
                    from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
                    from app.utils.fetch.fetch_utils import fetch_todays_games
                    
                    # Get team stats from LeagueDashTeamStatsORM
                    team_stats_orm = LeagueDashTeamStatsORM.get_by_team(
                        team_id, current_season, "Regular Season", session
                    )
                    
                    if team_stats_orm:
                        # Get conference standings from today's games data
                        today_data = fetch_todays_games()
                        standings = today_data.get("standings", {})
                        
                        # Find team in conference standings
                        team_name = team_stats_orm.team_name
                        conference = None
                        conference_rank = None
                        conference_total = None
                        
                        # Check East conference
                        for i, team in enumerate(standings.get("East", []), 1):
                            if str(team.get("TEAM_ID")) == str(team_id):
                                conference = "Eastern"
                                conference_rank = i
                                conference_total = len(standings.get("East", []))
                                break
                        
                        # Check West conference if not found in East
                        if not conference:
                            for i, team in enumerate(standings.get("West", []), 1):
                                if str(team.get("TEAM_ID")) == str(team_id):
                                    conference = "Western"
                                    conference_rank = i
                                    conference_total = len(standings.get("West", []))
                                    break
                        
                        if conference:
                            team_data.update({
                                'conference': conference,
                                'conference_rank': conference_rank,
                                'conference_total': conference_total
                            })
                except Exception as e:
                    logger.error(f"Error getting team standings rank: {e}")
                
                # Get team statistics and win/loss record
                try:
                    from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
                    
                    # Get team stats from LeagueDashTeamStatsORM
                    team_stats_orm = LeagueDashTeamStatsORM.get_by_team(
                        team_id, current_season, "Regular Season", session
                    )
                    
                    if team_stats_orm:
                        # Get basic stats
                        team_stats = self.get_team_stats(team_id, current_season, session)
                        team_data["stats"] = team_stats
                        
                        # Add win/loss record data
                        team_data["w"] = team_stats_orm.base_totals_w
                        team_data["l"] = team_stats_orm.base_totals_l
                        team_data["win_pct"] = team_stats_orm.base_totals_w_pct
                        team_data["games_played"] = team_stats_orm.base_totals_gp
                        team_data["record"] = f"{team_stats_orm.base_totals_w}-{team_stats_orm.base_totals_l}"
                        
                        # Try to get home/away records (may not be available in LeagueDashTeamStats)
                        # For now, set to None - can be calculated from game schedule if needed
                        team_data["home_record"] = None
                        team_data["road_record"] = None
                    else:
                        # No stats found for this season
                        logger.warning(f"No team stats found for team {team_id} in season {current_season}")
                        team_data["stats"] = {
                            "pts": None, "reb": None, "ast": None, "stl": None, "blk": None, 
                            "tov": None, "fg_pct": None, "fg3_pct": None, "ft_pct": None,
                            "off_rtg": None, "def_rtg": None, "net_rtg": None, "pace": None, "ts_pct": None
                        }
                        team_data["w"] = None
                        team_data["l"] = None
                        team_data["win_pct"] = None
                        team_data["games_played"] = None
                        team_data["record"] = None
                        team_data["home_record"] = None
                        team_data["road_record"] = None
                except Exception as e:
                    logger.error(f"Error getting team stats: {e}")
                    traceback.print_exc()
                    # Ensure stats is always present even if empty
                    team_data["stats"] = {
                        "pts": None, "reb": None, "ast": None, "stl": None, "blk": None, 
                        "tov": None, "fg_pct": None, "fg3_pct": None, "ft_pct": None,
                        "off_rtg": None, "def_rtg": None, "net_rtg": None, "pace": None, "ts_pct": None
                    }
                    team_data["w"] = None
                    team_data["l"] = None
                    team_data["win_pct"] = None
                    team_data["games_played"] = None
                    team_data["record"] = None
                    team_data["home_record"] = None
                    team_data["road_record"] = None
                
                # Get team lineups
                try:
                    lineups = self.get_team_lineup_stats(team_id, current_season, session)
                    if lineups:
                        team_data["lineups"] = lineups
                except Exception as e:
                    logger.error(f"Error getting team lineups: {e}")
                
                # Get recent game results
                try:
                    recent_games = self.get_team_game_results(team_id, 5, session)
                    if recent_games:
                        team_data["recent_games"] = recent_games
                except Exception as e:
                    logger.error(f"Error getting recent games: {e}")
                
                # Get upcoming schedule
                try:
                    upcoming_games = self.get_team_upcoming_schedule(team_id, 5, session)
                    if upcoming_games:
                        team_data["upcoming_games"] = upcoming_games
                except Exception as e:
                    logger.error(f"Error getting upcoming games: {e}")
                
                return team_data
            except Exception as e:
                logger.error(f"Error in get_complete_team_details: {e}")
                return None
        
        return self.with_db_session(fetch_team_details, db)
    
    def get_enhanced_teams_data(
        self,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Get enhanced team data including records, standings, and game information.
        
        Args:
            db: Optional database session for transaction control
        
        Returns:
            List of team dictionaries with enhanced data
        """
        # TODO: Implementation needed
        return []
    
    def get_team_visuals_data(
        self,
        season: str = "2024-25",
        db: Optional[Session] = None
    ) -> Dict[str, List[Any]]:
        """
        Get team performance data for visualization.
        
        Args:
            season: Season identifier (e.g., "2024-25")
            db: Optional database session for transaction control
        
        Returns:
            Dictionary with team visualization data
        """
        def fetch_visuals_data(session: Session) -> Dict[str, List[Any]]:
            # Initialize empty result structure
            result = {
                "team_names": [],
                "team_ppg": [],
                "team_rpg": [],
                "team_apg": [],
                "team_fg_pct": []
            }
            
            # Get team rankings from LeagueDashTeamStatsORM
            team_rankings = LeagueDashTeamStatsORM.get_team_rankings(
                season=season,
                per_mode="Totals",
                db=session
            )
            
            logger.debug(f"Retrieved {len(team_rankings) if team_rankings else 0} team rankings")
            
            if team_rankings:
                # Convert to dicts if needed
                team_dicts = []
                for team in team_rankings:
                    if hasattr(team, 'to_dict'):
                        team_dicts.append(team.to_dict())
                    else:
                        team_dicts.append(team)
                
                # Sort by points rank for initial display
                sorted_teams = sorted(team_dicts, key=lambda x: x.get("base_totals_pts_rank", 30))
                
                for team in sorted_teams[:15]:  # Show top 15 teams for better visualization
                    team_name = team.get("team_name", "")
                    if team_name:
                        result["team_names"].append(team_name)
                        result["team_ppg"].append(team.get("pts_rank", 30))
                        result["team_rpg"].append(team.get("reb_rank", 30))
                        result["team_apg"].append(team.get("ast_rank", 30))
                        result["team_fg_pct"].append(team.get("fgm_rank", 30))
            
            logger.debug(f"Team names: {result['team_names']}")
            logger.debug(f"Points ranks: {result['team_ppg']}")
            logger.debug(f"Rebounds ranks: {result['team_rpg']}")
            logger.debug(f"Assists ranks: {result['team_apg']}")
            logger.debug(f"FG% ranks: {result['team_fg_pct']}")
            
            return result
        
        return self.with_db_session(fetch_visuals_data, db)


# Create singleton instance for backward compatibility with static method calls
_team_service_instance = TeamService()

# Add class-level methods for backward compatibility
# Routes can still call get_team_lineup_stats() as before
TeamService.get_team_lineup_stats = staticmethod(_team_service_instance.get_team_lineup_stats)
TeamService.get_team_stats = staticmethod(_team_service_instance.get_team_stats)
TeamService.get_team_game_results = staticmethod(_team_service_instance.get_team_game_results)
TeamService.get_team_upcoming_schedule = staticmethod(_team_service_instance.get_team_upcoming_schedule)
TeamService.get_complete_team_details = staticmethod(_team_service_instance.get_complete_team_details)
TeamService.get_enhanced_teams_data = staticmethod(_team_service_instance.get_enhanced_teams_data)
TeamService.get_team_visuals_data = staticmethod(_team_service_instance.get_team_visuals_data)

# Also create module-level functions for backward compatibility
get_team_lineup_stats = _team_service_instance.get_team_lineup_stats
get_team_stats = _team_service_instance.get_team_stats
get_team_game_results = _team_service_instance.get_team_game_results
get_team_upcoming_schedule = _team_service_instance.get_team_upcoming_schedule
get_complete_team_details = _team_service_instance.get_complete_team_details
get_enhanced_teams_data = _team_service_instance.get_enhanced_teams_data
get_team_visuals_data = _team_service_instance.get_team_visuals_data
