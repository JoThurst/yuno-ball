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
from app.utils.get.get_utils import get_player_data
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
        """Get detailed player information.
        
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
            
            # Use existing utility function for now (will migrate later)
            # This function still uses old models, but it works
            player_data = get_player_data(player_id)
            return player_data
        
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
        db: Optional[Session] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get players on hot streaks with caching.
        
        Args:
            min_streak_games: Minimum number of games for a streak
            db: Optional database session for transaction control
        
        Returns:
            Dictionary grouped by stat type, each containing list of streaks
        """
        cache_key = f"player_streaks_{min_streak_games}"
        
        def fetch_streaks(session: Session) -> Dict[str, List[Dict[str, Any]]]:
            # Get all streaks grouped by stat type
            streaks_by_stat = PlayerStreaksORM.get_all_streaks_by_stat(
                min_streak=min_streak_games,
                db=session
            )
            
            if not streaks_by_stat:
                logger.warning("No streaks found in database")
                return {}
            
            # Convert to formatted dictionary
            formatted_streaks = {}
            for stat_type, streaks_list in streaks_by_stat.items():
                formatted_streaks[stat_type] = []
                for streak in streaks_list:
                    formatted_streak = {
                        'player_name': streak.get('player_name', 'Unknown'),
                        'team': streak.get('team_abbreviation', 'N/A'),  # Use team_abbreviation from ORM
                        'streak_type': stat_type,
                        'streak_value': streak.get('threshold', 10),  # Use actual threshold from database
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
        db: Optional[Session] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get player streaks grouped by type.
        
        Args:
            min_streak_games: Minimum number of games for a streak
            db: Optional database session for transaction control
        
        Returns:
            Dictionary grouped by stat type (same as get_player_streaks)
        """
        streaks = self.get_player_streaks(min_streak_games, db)
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
