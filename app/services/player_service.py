from typing import Optional, List, Dict, Any
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.models.player_sqlalchemy import PlayerORM
from app.models.statistics_sqlalchemy import StatisticsORM
from app.models.team_sqlalchemy import TeamORM, RosterORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
# Removed get_player_data import - now implemented directly in PlayerService using ORM
from app.utils.config_utils import logger


class PlayerService(BaseService):
    """Service for player-related operations.
    
    Can be used as instance methods or static methods for backward compatibility.
    """
    
    def get_all_players(self, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        """Get all players with caching.
        
        Args:
            db: Optional database session for transaction control
        
        Returns:
            List of player dictionaries
        """
        cache_key = "players"
        
        def fetch_players(session: Session) -> List[Dict[str, Any]]:
            players = PlayerORM.get_all(session)
            return self.to_dict_list(players)
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_players, db),
            ttl=3600
        )
    
    def get_player_details(self, player_id: int, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """Get detailed player information using ORM.
        
        Consolidates player data from multiple tables for the player dashboard.
        
        Args:
            player_id: Player ID
            db: Optional database session for transaction control
        
        Returns:
            Dictionary with player details or None if not found
        """
        def fetch_player_details(session: Session) -> Optional[Dict[str, Any]]:
            player = PlayerORM.get_by_id(player_id, session)
            if not player:
                return None
            
            # Get statistics using ORM
            statistics_orm = StatisticsORM.get_by_player(player_id, session)
            statistics = [stat.to_dict() for stat in statistics_orm]
            
            # Get roster info using ORM (most recent roster entry)
            roster_entries = RosterORM.get_by_player(player_id, session)
            roster = {}
            if roster_entries:
                most_recent = roster_entries[0]  # Already sorted by season desc
                roster = {
                    'team_id': most_recent.team_id,
                    'player_id': most_recent.player_id,
                    'player_name': most_recent.player_name,
                    'player_number': most_recent.player_number,
                    'position': most_recent.position,
                    'season': most_recent.season
                }
            
            # Get team info if we have a team_id from roster
            team_info = None
            if roster and 'team_id' in roster:
                team_info = TeamORM.get_by_id(roster['team_id'], session)
            
            # Get league stats for all seasons using ORM
            league_stats_orm = session.query(LeagueDashPlayerStatsORM).filter(
                LeagueDashPlayerStatsORM.player_id == player_id
            ).order_by(LeagueDashPlayerStatsORM.season.desc()).all()
            league_stats = [stat.to_dict() for stat in league_stats_orm]
            
            # Get last 10 game logs with schedule info using ORM
            game_logs_orm = GameLogORM.get_last_n_games(player_id, 10, session)
            
            # Enrich game logs with schedule information
            game_logs = []
            for log_orm in game_logs_orm:
                # Get schedule info for this game
                schedule = GameScheduleORM.get_by_game_and_team(log_orm.game_id, log_orm.team_id, session)
                
                # Get team abbreviations
                team = TeamORM.get_by_id(log_orm.team_id, session)
                opponent_team = None
                if schedule:
                    opponent_team = TeamORM.get_by_id(schedule.opponent_team_id, session)
                
                # Format game log
                formatted_log = {
                    'points': int(log_orm.points or 0),
                    'assists': int(log_orm.assists or 0),
                    'rebounds': int(log_orm.rebounds or 0),
                    'steals': int(log_orm.steals or 0),
                    'blocks': int(log_orm.blocks or 0),
                    'turnovers': int(log_orm.turnovers or 0),
                    'minutes_played': str(log_orm.minutes_played or '0.0'),
                    'game_date': schedule.game_date if schedule else None,
                    'home_or_away': schedule.home_or_away if schedule else None,
                    'result': schedule.result if schedule else None,
                    'formatted_score': schedule.score if schedule else None,
                    'team_abbreviation': team.abbreviation if team else None,
                    'opponent_abbreviation': opponent_team.abbreviation if opponent_team else None,
                    'team_score': None,  # Parse from score if needed
                    'opponent_score': None,  # Parse from score if needed
                    'season': log_orm.season
                }
                
                # Parse score if available
                if schedule and schedule.score:
                    try:
                        scores = schedule.score.split('-')
                        if len(scores) == 2:
                            if schedule.home_or_away == 'H':
                                formatted_log['team_score'] = int(scores[0].strip())
                                formatted_log['opponent_score'] = int(scores[1].strip())
                            else:
                                formatted_log['team_score'] = int(scores[1].strip())
                                formatted_log['opponent_score'] = int(scores[0].strip())
                    except (ValueError, AttributeError):
                        pass
                
                game_logs.append(formatted_log)
            
            # Calculate averages from the formatted logs
            total_games = len(game_logs)
            averages = {}
            if total_games > 0:
                averages = {
                    'points_avg': sum(log['points'] for log in game_logs) / total_games,
                    'rebounds_avg': sum(log['rebounds'] for log in game_logs) / total_games,
                    'assists_avg': sum(log['assists'] for log in game_logs) / total_games,
                    'steals_avg': sum(log['steals'] for log in game_logs) / total_games,
                    'blocks_avg': sum(log['blocks'] for log in game_logs) / total_games,
                    'turnovers_avg': sum(log['turnovers'] for log in game_logs) / total_games,
                }
            
            # Format game_date and minutes_played for display
            for log in game_logs:
                if isinstance(log.get("game_date"), datetime):
                    log["game_date"] = log["game_date"].strftime("%a %m/%d")
                
                # Format minutes to 1 decimal place
                try:
                    minutes = float(log["minutes_played"])
                    log["minutes_played"] = f"{minutes:.1f}"
                except (ValueError, TypeError):
                    log["minutes_played"] = "0.0"
            
            # Process league stats with mapping for template
            key_mapping = {
                'Name': 'player_name',
                'Season': 'season',
                'Team ABV': 'team_abbreviation',
                'GP': 'gp',
                'W': 'w',
                'L': 'l',
                'W %': 'w_pct',
                'Min': 'min',
                'FG%': 'fg_pct',
                '3P%': 'fg3_pct',
                'FT%': 'ft_pct',
                'PTS': 'pts',
                'Reb': 'reb',
                'Ast': 'ast'
            }
            
            processed_league_stats = []
            for stat in league_stats:
                if isinstance(stat, dict):
                    template_stat = {}
                    for template_key, db_key in key_mapping.items():
                        value = stat.get(db_key)
                        if value is not None:
                            # Format percentages as strings with 3 decimal places
                            if '_pct' in db_key:
                                template_stat[template_key] = f"{float(value):.3f}"
                            else:
                                template_stat[template_key] = value
                        else:
                            template_stat[template_key] = 0
                    processed_league_stats.append(template_stat)
            
            # Sort processed stats by season in descending order
            processed_league_stats.sort(key=lambda x: x.get('Season', ''), reverse=True)
            
            return {
                "statistics": statistics,
                "roster": roster,
                "league_stats": processed_league_stats,
                "game_logs": game_logs,
                "averages": averages,
                "team_info": team_info.to_dict() if team_info else None
            }
        
        return self.with_db_session(fetch_player_details, db)
    
    def get_formatted_game_logs(
        self, 
        player_id: int, 
        num_games: int = 10,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get formatted game logs for a player.
        
        Args:
            player_id: Player ID
            num_games: Number of recent games to retrieve
            db: Optional database session for transaction control
        
        Returns:
            List of formatted game log dictionaries
        """
        def fetch_game_logs(session: Session) -> List[Dict[str, Any]]:
            game_logs_orm = GameLogORM.get_last_n_games(player_id, num_games, session)
            return self._format_game_logs(game_logs_orm)
        
        return self.with_db_session(fetch_game_logs, db)
    
    def _format_game_logs(self, game_logs_orm: List[GameLogORM]) -> List[Dict[str, Any]]:
        """Format game logs from ORM objects to dictionaries.
        
        Args:
            game_logs_orm: List of GameLogORM objects
        
        Returns:
            List of formatted game log dictionaries
        """
        game_logs = []
        for log_orm in game_logs_orm:
            log_dict = log_orm.to_dict()
            
            # Format game_date
            if log_dict.get("game_date"):
                if isinstance(log_dict["game_date"], datetime):
                    log_dict["game_date"] = log_dict["game_date"].strftime("%a %m/%d")
            
            # Format minutes_played to 1 decimal place
            minutes = log_dict.get("minutes_played", 0)
            log_dict["minutes_played"] = f"{float(minutes):.1f}" if minutes else "0.0"
            
            # Format score: Remove unnecessary decimals
            formatted_score = log_dict.get("formatted_score", "")
            if formatted_score:
                match = re.search(r"(\D+)\s(\d+\.?\d*)\s-\s(\d+\.?\d*)\s(\D+)", formatted_score)
                if match:
                    team1, score1, score2, team2 = match.groups()
                    score1 = int(float(score1)) if float(score1).is_integer() else score1
                    score2 = int(float(score2)) if float(score2).is_integer() else score2
                    log_dict["formatted_score"] = f"{team1} {score1} - {score2} {team2}"
            
            game_logs.append(log_dict)
        
        return game_logs
    
    @staticmethod
    def calculate_averages(game_logs: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate player averages from game logs.
        
        Args:
            game_logs: List of game log dictionaries
        
        Returns:
            Dictionary with average statistics
        """
        total_games = len(game_logs)
        averages = {}
        
        if total_games > 0:
            averages = {
                "points_avg": sum(log.get('points', 0) for log in game_logs) / total_games,
                "rebounds_avg": sum(log.get('rebounds', 0) for log in game_logs) / total_games,
                "assists_avg": sum(log.get('assists', 0) for log in game_logs) / total_games,
                "steals_avg": sum(log.get('steals', 0) for log in game_logs) / total_games,
                "blocks_avg": sum(log.get('blocks', 0) for log in game_logs) / total_games,
                "turnovers_avg": sum(log.get('turnovers', 0) for log in game_logs) / total_games,
            }
        
        return averages
    
    def get_player_streaks(
        self, 
        min_streak_games: int = 3,
        season: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get players on hot streaks with caching.
        
        Args:
            min_streak_games: Minimum number of games for a streak
            season: Optional season to filter by (e.g., "2025-26"). 
                   If None, determines current season automatically.
            db: Optional database session for transaction control
        
        Returns:
            Dictionary grouped by stat type, each containing list of streaks
        """
        # Determine current season if not provided
        if season is None:
            now = datetime.now()
            if now.month >= 10:  # October-December
                season = f"{now.year}-{str(now.year + 1)[-2:]}"
            else:  # January-September
                season = f"{now.year - 1}-{str(now.year)[-2:]}"
        
        cache_key = f"player_streaks_{min_streak_games}_{season}"
        
        def fetch_streaks(session: Session) -> Dict[str, List[Dict[str, Any]]]:
            # Get all streaks grouped by stat type for the specified season
            streaks_by_stat = PlayerStreaksORM.get_all_streaks_by_stat(
                min_streak=min_streak_games,
                season=season,
                db=session
            )
            
            if not streaks_by_stat:
                logger.warning("No streaks found in database")
                return {}
            
            # Convert to formatted dictionary - use field names that match template expectations
            formatted_streaks = {}
            for stat_type, streaks_list in streaks_by_stat.items():
                formatted_streaks[stat_type] = []
                for streak in streaks_list:
                    formatted_streak = {
                        'player_name': streak.get('player_name', 'Unknown'),
                        'team_abbreviation': streak.get('team_abbreviation', 'N/A'),  # Template expects team_abbreviation
                        'stat': streak.get('stat', stat_type),  # Template expects stat (not streak_type)
                        'stat_display': streak.get('stat_display', PlayerStreaksORM.STAT_DISPLAY_NAMES.get(stat_type, stat_type)),  # Template expects stat_display
                        'threshold': streak.get('threshold', 10),  # Template expects threshold (not streak_value)
                        'streak_games': streak.get('streak_games', 0)
                    }
                    formatted_streaks[stat_type].append(formatted_streak)
            
            logger.debug(f"Retrieved {len(formatted_streaks.keys())} streak types from database")
            return formatted_streaks
        
        return self.get_or_set_cache(
            cache_key,
            lambda: self.with_db_session(fetch_streaks, db),
            ttl=3600
        )
    
    def get_grouped_player_streaks(
        self,
        min_streak_games: int = 3,
        season: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get player streaks grouped by type.
        
        Args:
            min_streak_games: Minimum number of games for a streak
            season: Optional season to filter by (e.g., "2025-26"). 
                   If None, determines current season automatically.
            db: Optional database session for transaction control
        
        Returns:
            Dictionary grouped by stat type (same as get_player_streaks)
        """
        streaks = self.get_player_streaks(min_streak_games, season=season, db=db)
        logger.debug(f"Grouping {len(streaks.keys() if streaks else [])} streaks by type")
        logger.debug(f"Found {len(streaks.keys() if streaks else [])} different streak types: {list(streaks.keys()) if streaks else []}")
        return streaks
    
    def get_comparison_stats(
        self,
        player_id: int,
        season: str = "2024-25",
        db: Optional[Session] = None
    ) -> Dict[str, float]:
        """Get properly formatted player stats for comparison.
        
        Args:
            player_id: Player ID
            season: Season identifier (e.g., "2024-25")
            db: Optional database session for transaction control
        
        Returns:
            Dictionary with normalized stats for comparison
        """
        # Initialize with default values
        default_stats = {
            "pts": 0,
            "reb": 0,
            "ast": 0,
            "stl": 0,
            "blk": 0,
            "fg_pct": 0
        }
        
        def fetch_stats(session: Session) -> Dict[str, float]:
            # Try to get player stats from LeagueDashPlayerStats
            player_stats_orm = LeagueDashPlayerStatsORM.get_by_player(
                player_id, 
                season,
                db=session
            )
            
            if not player_stats_orm:
                return default_stats
            
            # Convert to dict if it's an ORM object
            if hasattr(player_stats_orm, 'to_dict'):
                stats = player_stats_orm.to_dict()
            else:
                stats = player_stats_orm
            
            # Extract the stats we need
            try:
                # Convert per-game stats from total stats
                games_played = float(stats.get("gp", 1)) if stats.get("gp") and float(stats.get("gp")) > 0 else 1
                
                # Calculate per-game averages
                default_stats["pts"] = float(stats.get("pts", 0)) / games_played if stats.get("pts") else 0
                default_stats["reb"] = float(stats.get("reb", 0)) / games_played if stats.get("reb") else 0
                default_stats["ast"] = float(stats.get("ast", 0)) / games_played if stats.get("ast") else 0
                default_stats["stl"] = float(stats.get("stl", 0)) / games_played if stats.get("stl") else 0
                default_stats["blk"] = float(stats.get("blk", 0)) / games_played if stats.get("blk") else 0
                default_stats["fg_pct"] = float(stats.get("fg_pct", 0)) * 100 if stats.get("fg_pct") else 0
                
                # Apply reasonable caps for better visualization
                # These caps match the normalization scales in the frontend
                if default_stats["pts"] > 40: default_stats["pts"] = 40
                if default_stats["reb"] > 15: default_stats["reb"] = 15
                if default_stats["ast"] > 15: default_stats["ast"] = 15
                if default_stats["stl"] > 5: default_stats["stl"] = 5
                if default_stats["blk"] > 5: default_stats["blk"] = 5
                
                # Round to 1 decimal place for better display
                default_stats["pts"] = round(default_stats["pts"], 1)
                default_stats["reb"] = round(default_stats["reb"], 1)
                default_stats["ast"] = round(default_stats["ast"], 1)
                default_stats["stl"] = round(default_stats["stl"], 1)
                default_stats["blk"] = round(default_stats["blk"], 1)
                default_stats["fg_pct"] = round(default_stats["fg_pct"], 1)
                
                logger.debug(f"Calculated stats for player {player_id}: {default_stats}")
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting stats for player {player_id}: {e}")
            
            return default_stats
        
        return self.with_db_session(fetch_stats, db)
    
    def compare_players(
        self,
        player1_id: int,
        player2_id: int,
        season: str = "2024-25",
        db: Optional[Session] = None
    ) -> Optional[Dict[str, Any]]:
        """Compare two players' statistics.
        
        Args:
            player1_id: First player ID
            player2_id: Second player ID
            season: Season identifier (e.g., "2024-25")
            db: Optional database session for transaction control
        
        Returns:
            Dictionary with comparison data or None if players not found
        """
        def fetch_comparison(session: Session) -> Optional[Dict[str, Any]]:
            # Get player details
            player1 = PlayerORM.get_by_id(player1_id, session)
            player2 = PlayerORM.get_by_id(player2_id, session)
            
            if not player1 or not player2:
                return None
            
            # Get player stats (reuse session)
            player1_stats = self.get_comparison_stats(player1_id, season, session)
            player2_stats = self.get_comparison_stats(player2_id, season, session)
            
            # Calculate max values for normalization
            max_values = {
                "pts": 40,  # Max points per game
                "reb": 15,  # Max rebounds per game
                "ast": 15,  # Max assists per game
                "stl": 5,   # Max steals per game
                "blk": 5,   # Max blocks per game
                "fg_pct": 100  # Field goal percentage (already 0-100)
            }
            
            # Normalize stats to 0-100 scale
            player1_normalized = {}
            player2_normalized = {}
            
            for stat, max_val in max_values.items():
                player1_normalized[stat] = (player1_stats[stat] / max_val) * 100
                player2_normalized[stat] = (player2_stats[stat] / max_val) * 100
            
            return {
                "player1": {
                    "name": player1.name,
                    "stats": player1_stats,
                    "normalized": player1_normalized
                },
                "player2": {
                    "name": player2.name,
                    "stats": player2_stats,
                    "normalized": player2_normalized
                },
                "max_values": max_values
            }
        
        return self.with_db_session(fetch_comparison, db)


# Create singleton instance for backward compatibility with static method calls
_player_service_instance = PlayerService()

# Add class-level methods for backward compatibility
# Routes can still call PlayerService.get_all_players() as before
def _make_static_wrapper(instance_method):
    """Create a static method wrapper that delegates to instance."""
    @staticmethod
    def wrapper(*args, **kwargs):
        return instance_method(*args, **kwargs)
    return wrapper

# Bind static methods to class for backward compatibility
PlayerService.get_all_players = staticmethod(_player_service_instance.get_all_players)
PlayerService.get_player_details = staticmethod(_player_service_instance.get_player_details)
PlayerService.get_formatted_game_logs = staticmethod(_player_service_instance.get_formatted_game_logs)
PlayerService.get_player_streaks = staticmethod(_player_service_instance.get_player_streaks)
PlayerService.get_grouped_player_streaks = staticmethod(_player_service_instance.get_grouped_player_streaks)
PlayerService.get_comparison_stats = staticmethod(_player_service_instance.get_comparison_stats)
PlayerService.compare_players = staticmethod(_player_service_instance.compare_players)
