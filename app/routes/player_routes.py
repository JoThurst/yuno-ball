from flask import Blueprint, render_template, request, jsonify
from app.models.player import Player
from app.models.player_streaks import PlayerStreaks
from app.services.player_service import PlayerService
from app.utils.config_utils import logger
import traceback
from app.models.team import Team
from app.models.gameschedule import GameSchedule

player_bp = Blueprint("player", __name__, url_prefix="/players")

@player_bp.route("/")
def player_list():
    """Display a list of all players."""
    players = PlayerService.get_all_players()
    return render_template("player_list.html", players=players)

# Player detail route - displays comprehensive player dashboard
@player_bp.route("/<int:player_id>")
def player_detail(player_id):
    """Display detailed information for a specific player."""
    # Get player details using the service
    player_data = PlayerService.get_player_details(player_id)
    
    if not player_data:
        return render_template("error.html", message="Player not found"), 404
    
    # Get team information if available
    team_info = None
    if player_data.get('roster') and player_data['roster'].get('team_id'):
        team_id = player_data['roster']['team_id']
        team_info = Team.get_team(team_id)
    
    return render_template(
        "player_detail.html",
        player_data=player_data,
        player_id=player_id,
        team_info=team_info
    )

@player_bp.route("/streaks")
def player_streaks():
    """Display players on hot streaks."""
    try:
        logger.info("Fetching player streaks for display")
        
        # Get today's games
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        todays_games = GameSchedule.get_games_by_date(today)
        
        # Initialize container for today's game streaks
        game_streaks = []
        processed_game_ids = set()  # Track which games we've already processed
        
        # Process each game to get team-specific streaks
        for game in todays_games:
            # Skip if we've already processed this game
            if game['game_id'] in processed_game_ids:
                continue
            processed_game_ids.add(game['game_id'])
            
            # Determine home and away teams based on home_or_away flag
            if game['home_or_away'] == 'H':
                home_team_id = game['team_id']
                away_team_id = game['opponent_team_id']
            else:
                home_team_id = game['opponent_team_id']
                away_team_id = game['team_id']
            
            # Get team details
            home_team = Team.get_team_with_details(home_team_id)
            away_team = Team.get_team_with_details(away_team_id)
            
            if not home_team or not away_team:
                continue
                
            # Get player IDs from both rosters
            home_player_ids = [player['player_id'] for player in home_team['roster']]
            away_player_ids = [player['player_id'] for player in away_team['roster']]
            
            # Get streaks for both teams
            home_streaks = PlayerStreaks.get_streaks_by_player_ids(home_player_ids) if home_player_ids else []
            away_streaks = PlayerStreaks.get_streaks_by_player_ids(away_player_ids) if away_player_ids else []
            
            # Format streaks with team info
            game_streak = {
                'game_id': game['game_id'],
                'game_time': game.get('game_date', '').strftime('%I:%M %p') if game.get('game_date') else '',
                'home_team': {
                    'name': home_team['name'],
                    'abbreviation': home_team['abbreviation'],
                    'streaks': [{
                        'player_name': streak[2],  # player_name is the 3rd column
                        'stat': streak[3],         # stat is the 4th column
                        'stat_display': PlayerStreaks.STAT_DISPLAY_NAMES.get(streak[3], streak[3]),
                        'threshold': streak[4],    # threshold is the 5th column
                        'streak_games': streak[5], # streak_games is the 6th column
                        'team_abbreviation': home_team['abbreviation']
                    } for streak in home_streaks] if home_streaks else []
                },
                'away_team': {
                    'name': away_team['name'],
                    'abbreviation': away_team['abbreviation'],
                    'streaks': [{
                        'player_name': streak[2],  # player_name is the 3rd column
                        'stat': streak[3],         # stat is the 4th column
                        'stat_display': PlayerStreaks.STAT_DISPLAY_NAMES.get(streak[3], streak[3]),
                        'threshold': streak[4],    # threshold is the 5th column
                        'streak_games': streak[5], # streak_games is the 6th column
                        'team_abbreviation': away_team['abbreviation']
                    } for streak in away_streaks] if away_streaks else []
                }
            }
            game_streaks.append(game_streak)
        
        # Get all streaks for the main table
        grouped_streaks = PlayerStreaks.get_all_player_streaks(min_streak_games=7)
        
        if not grouped_streaks:
            logger.warning("No streaks found to display")
            return render_template("player_streaks.html", streaks=[], message="No active streaks found")
        
        # Flatten the grouped streaks for the main table
        streaks = []
        for stat_streaks in grouped_streaks.values():
            streaks.extend(stat_streaks)
        
        # Sort streaks by streak length (descending)
        streaks = sorted(streaks, key=lambda x: x['streak_games'], reverse=True)
        
        logger.info(f"Successfully retrieved {len(streaks)} streaks for display")
        return render_template("player_streaks.html", 
                             streaks=streaks,
                             game_streaks=game_streaks,
                             has_games_today=bool(game_streaks))
        
    except Exception as e:
        logger.error(f"Error displaying player streaks: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return render_template("error.html", message="Error loading player streaks"), 500

# This function is kept here for backward compatibility with other modules
# that might be importing it directly from routes
def get_player_comparison_stats(player_id):
    """Helper function to get properly formatted player stats for comparison."""
    return PlayerService.get_comparison_stats(player_id)
