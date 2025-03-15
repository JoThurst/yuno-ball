from app.models.player import Player
from app.models.statistics import Statistics
from app.models.team import Team
from app.models.playergamelog import PlayerGameLog
from app.models.leaguedashplayerstats import LeagueDashPlayerStats
from app.utils.cache_utils import get_cache, set_cache
from app.utils.get.get_utils import get_player_data
from app.utils.config_utils import logger
import re
from datetime import datetime
from app.models.player_streaks import PlayerStreaks

class PlayerService:
    @staticmethod
    def get_all_players():
        """Get all players with caching."""
        cache_key = "players"
        players = get_cache(cache_key)
        
        if not players:
            print("❌ Cache MISS on Players - Fetching fresh data.")
            players = Player.get_all_players()
            players = [player.__dict__ for player in players]
            set_cache(cache_key, players, ex=3600)  # Cache for 1 hour
        else:
            print("✅ Cache HIT on Players")
        
        return players
    
    @staticmethod
    def get_player_details(player_id):
        """Get detailed player information."""
        # Get player data
        player = Player.get_player(player_id)
        
        if not player:
            return None
        
        player_data = get_player_data(player_id)

        if not player_data:
            return None
        
        
        return player_data
    
    @staticmethod
    def get_formatted_game_logs(player_id, num_games=10):
        """Get formatted game logs for a player."""
        # Get game logs
        raw_game_logs = PlayerGameLog.get_last_n_games_by_player(player_id, num_games) or []
        
        # Define headers based on query output
        game_logs_headers = [
            "home_team_name", "opponent_abbreviation", "game_date", "result",
            "formatted_score", "home_or_away", "points", "assists", "rebounds",
            "steals", "blocks", "turnovers", "minutes_played", "season"
        ]
        
        # Convert tuples into dictionaries
        game_logs = [dict(zip(game_logs_headers, row)) for row in raw_game_logs]
        
        # Format game_date, minutes_played, and formatted_score
        for log in game_logs:
            if isinstance(log["game_date"], datetime):
                log["game_date"] = log["game_date"].strftime("%a %m/%d")
            
            # Format minutes to 1 decimal place
            log["minutes_played"] = f"{float(log['minutes_played']):.1f}" if log["minutes_played"] else "0.0"
            
            # Format score: Remove unnecessary decimals
            if "formatted_score" in log:
                match = re.search(r"(\D+)\s(\d+\.?\d*)\s-\s(\d+\.?\d*)\s(\D+)", log["formatted_score"])
                if match:
                    team1, score1, score2, team2 = match.groups()
                    score1 = int(float(score1)) if float(score1).is_integer() else score1
                    score2 = int(float(score2)) if float(score2).is_integer() else score2
                    log["formatted_score"] = f"{team1} {score1} - {score2} {team2}"
        
        return game_logs
    
    @staticmethod
    def calculate_averages(game_logs):
        """Calculate player averages from game logs."""
        total_games = len(game_logs)
        averages = {}
        
        if total_games > 0:
            averages = {
                "points_avg": sum(log['points'] for log in game_logs) / total_games,
                "rebounds_avg": sum(log['rebounds'] for log in game_logs) / total_games,
                "assists_avg": sum(log['assists'] for log in game_logs) / total_games,
                "steals_avg": sum(log['steals'] for log in game_logs) / total_games,
                "blocks_avg": sum(log['blocks'] for log in game_logs) / total_games,
                "turnovers_avg": sum(log['turnovers'] for log in game_logs) / total_games,
            }
        
        return averages
    
    @staticmethod
    def get_player_streaks():
        """Get players on hot streaks with caching."""
        cache_key = "player_streaks"
        streaks = get_cache(cache_key)
        
        if not streaks:
            logger.info("❌ Cache MISS on Player Streaks - Fetching fresh data.")
            streaks = PlayerStreaks.get_all_player_streaks(min_streak_games=3) or {}
            logger.debug(f"Retrieved {len(streaks.keys() if streaks else [])} streak types from database")
            
            # Convert database rows to proper format
            formatted_streaks = {}
            for stat_type, stat_streaks in streaks.items():
                formatted_streaks[stat_type] = []
                for streak in stat_streaks:
                    formatted_streak = {
                        'player_name': streak.get('player_name', 'Unknown'),
                        'team': streak.get('team', 'N/A'),
                        'streak_type': stat_type,
                        'streak_value': 10,  # Default threshold
                        'streak_games': streak.get('streak_games', 0)
                    }
                    formatted_streaks[stat_type].append(formatted_streak)
            
            if not formatted_streaks:
                logger.warning("No streaks found in database")
            else:
                logger.debug(f"First streak example: {next(iter(formatted_streaks.values()))[0] if formatted_streaks else None}")
            
            streaks = formatted_streaks
            set_cache(cache_key, streaks, ex=3600)  # Cache for 1 hour
        else:
            logger.info("✅ Cache HIT on Player Streaks")
            logger.debug(f"Retrieved {len(streaks.keys() if streaks else [])} streak types from cache")
        
        return streaks
    
    @staticmethod
    def get_grouped_player_streaks():
        """Get player streaks grouped by type."""
        streaks = PlayerService.get_player_streaks()
        logger.debug(f"Grouping {len(streaks.keys() if streaks else [])} streaks by type")
        
        # Group streaks by type (they're already grouped, just return as is)
        logger.debug(f"Found {len(streaks.keys() if streaks else [])} different streak types: {list(streaks.keys()) if streaks else []}")
        return streaks
    
    @staticmethod
    def get_comparison_stats(player_id):
        """Get properly formatted player stats for comparison."""
        # Initialize with default values
        default_stats = {
            "pts": 0,
            "reb": 0,
            "ast": 0,
            "stl": 0,
            "blk": 0,
            "fg_pct": 0
        }
        
        # Try to get player stats from LeagueDashPlayerStats
        player_stats = LeagueDashPlayerStats.get_all_stats({"player_id": player_id})
        
        if player_stats and len(player_stats) > 0:
            # Get the most recent season's stats (first entry)
            stats = player_stats[0]
            
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
                
                print(f"Calculated stats for player {player_id}: {default_stats}")
            except (ValueError, TypeError) as e:
                print(f"Error converting stats for player {player_id}: {e}")
        
        return default_stats
    
    @staticmethod
    def compare_players(player1_id, player2_id):
        """Compare two players' statistics."""
        # Get player details
        player1 = Player.get_player(player1_id)
        player2 = Player.get_player(player2_id)
        
        if not player1 or not player2:
            return None
        
        # Get player stats
        player1_stats = PlayerService.get_comparison_stats(player1_id)
        player2_stats = PlayerService.get_comparison_stats(player2_id)
        
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
