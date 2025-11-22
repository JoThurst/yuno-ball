from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.player_service import PlayerService
from app.models.team_sqlalchemy import TeamORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.database import get_db_context
from app.utils.config_utils import logger
import traceback

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
    # Get season from query params or use current season
    from app.utils.fetch.fetch_utils import get_current_season_str
    season = request.args.get("season") or get_current_season_str()
    current_season = get_current_season_str()
    
    # Get player details using the service
    player_data = PlayerService.get_player_details(player_id)
    
    if not player_data:
        return render_template("error.html", message="Player not found"), 404
    
    # Get team information if available
    team_info = None
    if player_data.get('roster') and player_data['roster'].get('team_id'):
        team_id = player_data['roster']['team_id']
        with get_db_context() as db:
            team_orm = TeamORM.get_by_id(team_id, db)
            team_info = team_orm.to_dict() if team_orm else None
    
    # Add season info to template context
    player_data['season'] = season
    player_data['current_season'] = current_season
    
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
        
        # Determine current season
        now = datetime.now()
        if now.month >= 10:  # October-December
            current_season = f"{now.year}-{str(now.year + 1)[-2:]}"
        else:  # January-September
            current_season = f"{now.year - 1}-{str(now.year)[-2:]}"
        
        # Get today's games using ORM
        today = datetime.now().date()
        with get_db_context() as db:
            todays_games = GameScheduleORM.get_by_date(today, db=db)
        
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
            
            # Get team details using ORM
            with get_db_context() as db:
                home_team_orm = TeamORM.get_by_id(home_team_id, db)
                away_team_orm = TeamORM.get_by_id(away_team_id, db)
                
                if not home_team_orm or not away_team_orm:
                    continue
                
                # Get rosters
                home_roster = home_team_orm.get_roster(db=db)
                away_roster = away_team_orm.get_roster(db=db)
                
                # Get player IDs from both rosters
                home_player_ids = [r.player_id for r in home_roster]
                away_player_ids = [r.player_id for r in away_roster]
                
                # Get streaks for both teams using ORM
                home_streaks_data = []
                away_streaks_data = []
                
                if home_player_ids:
                    for player_id in home_player_ids:
                        streaks = PlayerStreaksORM.get_by_player(player_id, season=current_season, db=db)
                        home_streaks_data.extend([s.to_dict() if hasattr(s, 'to_dict') else s for s in streaks])
                
                if away_player_ids:
                    for player_id in away_player_ids:
                        streaks = PlayerStreaksORM.get_by_player(player_id, season=current_season, db=db)
                        away_streaks_data.extend([s.to_dict() if hasattr(s, 'to_dict') else s for s in streaks])
                
                home_team = home_team_orm.to_dict()
                away_team = away_team_orm.to_dict()
                home_team['roster'] = [r.to_dict() for r in home_roster]
                away_team['roster'] = [r.to_dict() for r in away_roster]
            
            # Format streaks with team info
            # Convert streak data to proper format
            def format_streaks(streaks_data, team_abbr):
                formatted = []
                for streak in streaks_data:
                    if isinstance(streak, dict):
                        formatted.append({
                            'player_name': streak.get('player_name', ''),
                            'stat': streak.get('stat', ''),
                            'stat_display': PlayerStreaksORM.STAT_DISPLAY_NAMES.get(streak.get('stat', ''), streak.get('stat', '')),
                            'threshold': streak.get('threshold', 0),
                            'streak_games': streak.get('streak_games', 0),
                            'team_abbreviation': team_abbr
                        })
                return formatted
            
            game_date_obj = game.get('game_date')
            if isinstance(game_date_obj, str):
                try:
                    game_date_obj = datetime.strptime(game_date_obj, '%Y-%m-%d')
                except ValueError:
                    game_date_obj = None
            
            game_streak = {
                'game_id': game.get('game_id', ''),
                'game_time': game_date_obj.strftime('%I:%M %p') if game_date_obj and hasattr(game_date_obj, 'strftime') else '',
                'home_team': {
                    'name': home_team.get('name', ''),
                    'abbreviation': home_team.get('abbreviation', ''),
                    'streaks': format_streaks(home_streaks_data, home_team.get('abbreviation', ''))
                },
                'away_team': {
                    'name': away_team.get('name', ''),
                    'abbreviation': away_team.get('abbreviation', ''),
                    'streaks': format_streaks(away_streaks_data, away_team.get('abbreviation', ''))
                }
            }
            game_streaks.append(game_streak)
        
        # Get all streaks for the main table using service
        player_service = PlayerService()
        with get_db_context() as db:
            grouped_streaks = player_service.get_player_streaks(min_streak_games=7, season=current_season, db=db)
        
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
