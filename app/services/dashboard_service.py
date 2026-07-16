from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Tuple, Optional

from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_sqlalchemy import TeamORM
from app.models.player_sqlalchemy import PlayerORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.utils.config_utils import logger
from app.utils.get.get_utils import fetch_todays_games
from app.utils.fetch.fetch_utils import fetch_team_rosters
from app.services.team_service import TeamService

class DashboardService(BaseService):
    """Service for dashboard-related operations.
    
    Can be used as instance methods or static methods for backward compatibility.
    """
    
    def get_calendar_days(self, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Get games for the next 7 days starting from tomorrow.
        
        Args:
            db: Optional database session for transaction control
        
        Returns:
            List of calendar day dictionaries with games
        """
        def fetch_calendar_days(session: Session) -> List[Dict[str, Any]]:
            calendar_days = []
            tomorrow = datetime.now().date() + timedelta(days=1)
            
            # Get games for next 7 days starting from tomorrow
            for i in range(7):
                current_date = tomorrow + timedelta(days=i)
                weekday = current_date.strftime('%a')  # Get abbreviated weekday name (Sun, Mon, etc.)
                
                # Get games for this date using ORM (takes date object, not string)
                games = GameScheduleORM.get_by_date(current_date, db=session)
                
                # Format games for the calendar
                formatted_games = []
                seen_game_ids = set()  # To prevent duplicate games
                
                for game in games:
                    game_id = game.get('game_id')
                    if game_id not in seen_game_ids:
                        # Handle game_date which is already a datetime object
                        game_date = game.get('game_date')
                        if isinstance(game_date, str):
                            try:
                                game_date = datetime.strptime(game_date, '%Y-%m-%d')
                            except ValueError:
                                game_date = None
                        
                        game_time = game_date.strftime('%I:%M %p') if game_date and hasattr(game_date, 'strftime') else ''
                        formatted_games.append({
                            'home_abbr': game.get('team_abbreviation') if game.get('home_or_away') == 'H' else game.get('opponent_abbreviation'),
                            'away_abbr': game.get('opponent_abbreviation') if game.get('home_or_away') == 'H' else game.get('team_abbreviation'),
                            'time': game_time
                        })
                        seen_game_ids.add(game_id)
                
                # Add day to calendar with formatted date
                calendar_days.append({
                    'date': current_date.strftime('%d'),  # Day number
                    'weekday': weekday,  # Abbreviated weekday
                    'full_date': current_date.strftime('%b %d'),  # Month and day (e.g., "Jan 15")
                    'games': formatted_games
                })
            
            return calendar_days
        
        return self.with_db_session(fetch_calendar_days, db)

    def get_home_dashboard_data(self, season: str = "2024-25", db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Get comprehensive data for the home dashboard.
        
        Args:
            season: The NBA season (e.g., "2024-25")
            db: Optional database session for transaction control
        
        Returns:
            Dictionary containing all data needed for the home dashboard
        """
        cache_key = f"home_dashboard_{season}_{datetime.now().strftime('%Y-%m-%d')}"
        
        def fetch_dashboard_data(session: Session) -> Dict[str, Any]:
            logger.info("[INFO] Cache MISS for home dashboard data - Fetching fresh data")
            
            # Get calendar days for upcoming games
            calendar_days = self.get_calendar_days(session)
            logger.debug(f"Calendar days: {calendar_days}")
    
            # 1. Get today's games for the featured section -- Correct
            today_games_data = fetch_todays_games()
            all_games = today_games_data.get("games", [])
            featured_games = all_games[:3] if all_games else []  # Limit to 3 games for the featured widget
            
            # Add additional data to each game
            for game in all_games:
                # Get team objects using ORM
                home_team_orm = TeamORM.get_by_id(game["home_team_id"], session)
                away_team_orm = TeamORM.get_by_id(game["away_team_id"], session)
                
                # Handle home team data
                if home_team_orm:
                    home_team = home_team_orm.to_dict()
                    home_record = game.get("home_record", "0-0")  # Use record from game data if available
                    game["home_team_abbreviation"] = home_team.get('abbreviation', '')
                else:
                    game["home_record"] = "0-0"
                    game["home_team_abbreviation"] = ""
                
                # Handle away team data
                if away_team_orm:
                    away_team = away_team_orm.to_dict()
                    away_record = game.get("away_record", "0-0")  # Use record from game data if available
                    game["away_team_abbreviation"] = away_team.get('abbreviation', '')
                else:
                    game["away_record"] = "0-0"
                    game["away_team_abbreviation"] = ""
                
                # Check if game is live (placeholder for now)
                game["is_live"] = False
                game["home_score"] = game.get("home_score", 0)
                game["away_score"] = game.get("away_score", 0)
                game["game_clock"] = game.get("game_clock", "")
                
                # Add team stats for comparison
                game["home_team_stats"] = {
                    "ppg": 0,
                    "rpg": 0,
                    "apg": 0,
                    "fg_pct": 0
                }
                
                game["away_team_stats"] = {
                    "ppg": 0,
                    "rpg": 0,
                    "apg": 0,
                    "fg_pct": 0
                }
                
                # Try to get actual stats if available using ORM
                team_rankings = LeagueDashTeamStatsORM.get_team_rankings(season=season, per_mode="Totals", db=session)
                if team_rankings:
                    for stat in team_rankings:
                        if stat.get("team_id") == game["home_team_id"]:
                            game["home_team_stats"] = {
                                "ppg": stat.get("pts_rank", 0),
                                "rpg": stat.get("reb_rank", 0),
                                "apg": stat.get("ast_rank", 0),
                                "fg_pct": stat.get("fgm_rank", 0)
                            }
                        
                        if stat.get("team_id") == game["away_team_id"]:
                            game["away_team_stats"] = {
                                "ppg": stat.get("pts_rank", 0),
                                "rpg": stat.get("reb_rank", 0),
                                "apg": stat.get("ast_rank", 0),
                                "fg_pct": stat.get("fgm_rank", 0)
                            }
    
            # Fix player streaks processing using ORM
            from app.services.player_service import PlayerService
            player_service = PlayerService()
            player_streaks_by_stat = player_service.get_player_streaks(min_streak_games=3, db=session)
            logger.debug(f"Retrieved streaks for {len(player_streaks_by_stat.keys()) if player_streaks_by_stat else 0} stat categories")
            
            # Convert the stat-grouped dictionary into a flat list of streaks
            processed_streaks = []
            if player_streaks_by_stat:
                for stat_type, streaks in player_streaks_by_stat.items():
                    processed_streaks.extend(streaks)
            
            # Sort by streak length and limit to top 5 for featured streaks
            try:
                featured_streaks = sorted(processed_streaks, 
                                        key=lambda x: x.get('streak_games', 0), 
                                        reverse=True)[:5]
            except (AttributeError, TypeError) as e:
                logger.error(f"Error sorting player_streaks: {str(e)}")
                featured_streaks = []
            
            # Store both the featured and all streaks
            player_streaks = processed_streaks
            
            # 3. Get standings data
            standings = today_games_data.get("standings", {"East": [], "West": []})
            
            # 4. Get team data for the performance chart
            teams_orm = TeamORM.get_all(session)
            teams = [team.to_dict() for team in teams_orm]
            
            # Get team stats for visualization
            team_service = TeamService()
            team_data = team_service.get_team_visuals_data(season, session)
            
            # 5. Get player data for the players section
            # Get top scorers and assisters from LeagueDashPlayerStatsORM
            player_stats_orm = LeagueDashPlayerStatsORM.get_all_by_season(season, db=session)
            player_stats = [stat.to_dict() if hasattr(stat, 'to_dict') else stat for stat in player_stats_orm]
            
            top_scorers = []
            top_assisters = []
            
            # Create a mapping of team_id to abbreviation
            team_abbr_map = {team.get("team_id"): team.get("abbreviation", "") for team in teams}

            # Get all team rosters to map players to teams
            all_team_ids = [team.get("team_id") for team in teams]
            all_rosters = fetch_team_rosters(all_team_ids)
            
            # Create player_id to team_id mapping
            player_team_map = {str(player["player_id"]): player["team_id"] for player in all_rosters}
            
            if player_stats:
                # Sort by points and assists
                sorted_by_pts = sorted(player_stats, key=lambda x: float(x.get("pts", 0)) if x.get("pts") else 0, reverse=True)
                sorted_by_ast = sorted(player_stats, key=lambda x: float(x.get("ast", 0)) if x.get("ast") else 0, reverse=True)
                
                # Get top 5 scorers
                for player in sorted_by_pts[:5]:
                    player_id = player.get("player_id")
                    if player_id:
                        player_orm = PlayerORM.get_by_id(player_id, session)
                        player_name = player_orm.name if player_orm else "Unknown Player"
                        team_id = player.get("team_id")
                        team_abbr = team_abbr_map.get(team_id, "N/A") if team_id else "N/A"
                        
                        top_scorers.append({
                            "player_id": player_id,
                            "player_name": player_name,
                            "team_abbreviation": team_abbr,
                            "pts": round(float(player.get("pts", 0)) if player.get("pts") else 0, 1)
                        })
                
                # Get top 5 assisters
                for player in sorted_by_ast[:5]:
                    player_id = player.get("player_id")
                    if player_id:
                        player_orm = PlayerORM.get_by_id(player_id, session)
                        player_name = player_orm.name if player_orm else "Unknown Player"
                        team_id = player.get("team_id")
                        team_abbr = team_abbr_map.get(team_id, "N/A") if team_id else "N/A"
                        
                        top_assisters.append({
                            "player_id": player_id,
                            "player_name": player_name,
                            "team_abbreviation": team_abbr,
                            "ast": round(float(player.get("ast", 0)) if player.get("ast") else 0, 1)
                        })
            
            # 6. Get all players for the comparison tool
            all_players = []
            players_orm = PlayerORM.get_all(session)
            
            for player_orm in players_orm:
                player = player_orm.to_dict()
                # Only include players with current season data
                if player.get("available_seasons") and season in player.get("available_seasons", []):
                    team_id = player_team_map.get(str(player.get("player_id")))
                    team_abbr = team_abbr_map.get(team_id, "N/A") if team_id else "N/A"
                
                    all_players.append({
                        "player_id": player.get("player_id"),
                        "name": player.get("name"),
                        "team_abbreviation": team_abbr
                    })
            
            # Prepare the final data structure
            dashboard_data = {
                "featured_games": featured_games,
                "games": all_games,
                "standings": standings,
                "featured_streaks": featured_streaks,
                "player_streaks": player_streaks,
                "top_scorers": top_scorers,
                "top_assisters": top_assisters,
                "all_players": all_players,
                "team_names": team_data["team_names"],
                "team_ppg": team_data["team_ppg"],
                "team_rpg": team_data["team_rpg"],
                "team_apg": team_data["team_apg"],
                "team_fg_pct": team_data["team_fg_pct"],
                "teams": teams,
                "calendar_days": calendar_days
            }
            
            return dashboard_data
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_dashboard_data, db),
            ttl=3600  # 1 hour
        )

    def get_today_matchups(self, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Get today's matchups for the navbar dropdown.
        
        Args:
            db: Optional database session for transaction control
        
        Returns:
            List of today's games
        """
        cache_key = f"today_matchups_{datetime.now().strftime('%Y-%m-%d')}"
        
        def fetch_matchups(session: Session) -> List[Dict[str, Any]]:
            logger.debug("[CACHE] Miss for today's matchups - Fetching fresh data")
            
            # Get today's games
            today_games_data = fetch_todays_games()
            games = today_games_data.get("games", [])
            
            return games
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_matchups, db),
            ttl=3600  # 1 hour
        )

    def process_games_data(
        self,
        today_games: List[Tuple],
        team_stats: List[Any],
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Process games data to create a list of game objects.
        
        Args:
            today_games: List of game tuples from GameSchedule
            team_stats: List of team stats from LeagueDashTeamStats
            db: Optional database session for transaction control
        
        Returns:
            List of processed game objects
        """
        def process_games(session: Session) -> List[Dict[str, Any]]:
            games = []
            
            for game_tuple in today_games:
                # game_tuple is (game_id, team_id, opponent_team_id, game_date, home_or_away, result, score)
                logger.debug(f"Processing game: {game_tuple}")
                game_id, team_id, opponent_team_id, game_date, home_or_away, result, score = game_tuple
                
                # Determine which team is home and which is away
                if home_or_away == 'H':
                    home_team_id = team_id
                    away_team_id = opponent_team_id
                else:
                    home_team_id = opponent_team_id
                    away_team_id = team_id
                
                # Get team details using ORM
                home_team_orm = TeamORM.get_by_id(home_team_id, session)
                away_team_orm = TeamORM.get_by_id(away_team_id, session)
                home_team = home_team_orm.to_dict() if home_team_orm else None
                away_team = away_team_orm.to_dict() if away_team_orm else None
                
                # Set default values
                home_record = ""
                away_record = ""
                home_team_abbreviation = ""
                away_team_abbreviation = ""
                home_team_name = ""
                away_team_name = ""
                home_team_score = 0
                away_team_score = 0
                
                # Get team records and abbreviations if teams exist
                if home_team:
                    home_record = home_team.get("record", "")
                    home_team_abbreviation = home_team.get("abbreviation", "")
                    home_team_name = home_team.get("name", "")
                else:
                    home_record = ""
                    home_team_abbreviation = ""
                    home_team_name = ""
                
                if away_team:
                    away_record = away_team.get("record", "")
                    away_team_abbreviation = away_team.get("abbreviation", "")
                    away_team_name = away_team.get("name", "")
                else:
                    away_record = ""
                    away_team_abbreviation = ""
                    away_team_name = ""
        
                # Parse score if available
                home_team_score = 0
                away_team_score = 0
                if score:
                    score_parts = score.split(" - ")
                    if len(score_parts) == 2:
                        try:
                            if home_or_away == 'H':
                                home_team_score = int(score_parts[0])
                                away_team_score = int(score_parts[1])
                            else:
                                away_team_score = int(score_parts[0])
                                home_team_score = int(score_parts[1])
                        except (ValueError, TypeError):
                            pass
                
                # Determine game status
                game_status = "Scheduled"
                if result:
                    game_status = "Final"
                elif isinstance(game_date, datetime) and datetime.now().date() == game_date.date():
                    game_status = "Today"
                
                # Format game time
                game_time = game_date.strftime("%I:%M %p") if hasattr(game_date, 'strftime') else ""
                
                # Add team stats
                home_team_stats = {"ppg": 0, "rpg": 0, "apg": 0, "fg_pct": 0}
                away_team_stats = {"ppg": 0, "rpg": 0, "apg": 0, "fg_pct": 0}
                
                # Find team stats in the team_stats data
                for stat in team_stats:
                    if stat and isinstance(stat, dict):
                        stat_team_id = stat.get('team_id')
                        if stat_team_id == home_team_id:
                            home_team_stats = {
                                "ppg": stat.get('pts_rank', 0),
                                "rpg": stat.get('reb_rank', 0),
                                "apg": stat.get('ast_rank', 0),
                                "fg_pct": stat.get('fgm_rank', 0)
                            }
                        
                        if stat_team_id == away_team_id:
                            away_team_stats = {
                                "ppg": stat.get('pts_rank', 0),
                                "rpg": stat.get('reb_rank', 0),
                                "apg": stat.get('ast_rank', 0),
                                "fg_pct": stat.get('fgm_rank', 0)
                            }
                
                # Create game object
                game_obj = {
                    "game_id": game_id,
                    "home_team_id": home_team_id,
                    "home_team_name": home_team_name,
                    "home_team_score": home_team_score,
                    "away_team_id": away_team_id,
                    "away_team_name": away_team_name,
                    "away_team_score": away_team_score,
                    "game_status": game_status,
                    "game_date": game_date.strftime("%Y-%m-%d") if hasattr(game_date, 'strftime') else "",
                    "game_time": game_time,
                    "home_record": home_record,
                    "away_record": away_record,
                    "home_team_abbreviation": home_team_abbreviation,
                    "away_team_abbreviation": away_team_abbreviation,
                    "home_team_stats": home_team_stats,
                    "away_team_stats": away_team_stats,
                    "is_live": game_status == "Live"
                }
                
                games.append(game_obj)
            
            return games
        
        return self.with_db_session(process_games, db)

    @staticmethod
    def get_featured_games(games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get featured games for the dashboard.
        
        Args:
            games: List of processed game objects
        
        Returns:
            List of featured game objects (max 3)
        """
        featured_games = []
        
        # Add to featured games if it's not a final game
        for game in games:
            if len(featured_games) < 3 and game.get("game_status") != "Final":
                featured_games.append(game)
        
        # If we don't have enough featured games, add some from the regular games
        if len(featured_games) < 3:
            remaining_games = [g for g in games if g not in featured_games]
            featured_games.extend(remaining_games[:3 - len(featured_games)])
        
        return featured_games

    @staticmethod
    def get_standings_data(teams: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Process teams data to create standings.
        
        Args:
            teams: List of team objects
        
        Returns:
            Dict with East and West conference standings
        """
        try:
            standings_data = {
                "East": [],
                "West": []
            }
            
            for team in teams:
                team_data = {
                    "TEAM": team.get('name', ''),
                    "W": team.get('wins', 0),
                    "L": team.get('losses', 0),
                    "W_PCT": team.get('win_pct', 0.0)
                }
                if team.get('conference') == 'East':
                    standings_data["East"].append(team_data)
                else:
                    standings_data["West"].append(team_data)
            
            # Sort standings by win percentage
            standings_data["East"] = sorted(standings_data["East"], key=lambda x: x["W_PCT"], reverse=True)
            standings_data["West"] = sorted(standings_data["West"], key=lambda x: x["W_PCT"], reverse=True)
            logger.debug("Standings data processed successfully")
            
            return standings_data
        except Exception as e:
            logger.error(f"Error processing standings data: {str(e)}")
            return {"East": [], "West": []}

    def get_hot_players_data(self, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """
        Get players on streaks data.
        
        Args:
            db: Optional database session for transaction control
        
        Returns:
            List of players on streaks
        """
        def fetch_hot_players(session: Session) -> List[Dict[str, Any]]:
            try:
                hot_players_data = PlayerStreaksORM.get_hot_streaks(
                    min_streak=10,
                    season="2024-25",
                    limit=5,
                    db=session
                )
                logger.debug(f"Retrieved {len(hot_players_data)} players on hot streaks")
                
                hot_players = []
                for player_dict in hot_players_data:
                    player_obj = {
                        "player_id": player_dict.get("player_id"),
                        "player_name": player_dict.get("player_name", ""),
                        "team_abbreviation": player_dict.get("team", "N/A"),
                        "streak_type": player_dict.get("stat", ""),
                        "streak_value": 10,  # Default threshold
                        "streak_count": player_dict.get("streak_games", 0)
                    }
                    hot_players.append(player_obj)
                
                return hot_players
            except Exception as e:
                logger.warning(f"Error fetching player streaks: {str(e)}")
                return []
        
        return self.with_db_session(fetch_hot_players, db)


# Create singleton instance for backward compatibility with static method calls
_dashboard_service_instance = DashboardService()

# Add class-level methods for backward compatibility
DashboardService.get_calendar_days = staticmethod(_dashboard_service_instance.get_calendar_days)
DashboardService.get_home_dashboard_data = staticmethod(_dashboard_service_instance.get_home_dashboard_data)
DashboardService.get_today_matchups = staticmethod(_dashboard_service_instance.get_today_matchups)
DashboardService.process_games_data = staticmethod(_dashboard_service_instance.process_games_data)
DashboardService.get_hot_players_data = staticmethod(_dashboard_service_instance.get_hot_players_data)

# Also create module-level functions for backward compatibility
get_calendar_days = _dashboard_service_instance.get_calendar_days
get_home_dashboard_data = _dashboard_service_instance.get_home_dashboard_data
get_today_matchups = _dashboard_service_instance.get_today_matchups
process_games_data = _dashboard_service_instance.process_games_data
get_featured_games = DashboardService.get_featured_games
get_standings_data = DashboardService.get_standings_data
get_hot_players_data = _dashboard_service_instance.get_hot_players_data


