from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import re
import traceback

from sqlalchemy.orm import Session

from app.services.dashboard_service import DashboardService
from app.services.team_service import TeamService
from app.services.player_service import PlayerService
from app.models.team_sqlalchemy import TeamORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.database import get_db_context
from app.utils.fetch.fetch_utils import fetch_todays_games, get_current_season_str
from app.utils.cache_utils import get_cache, set_cache
from app.utils.config_utils import logger


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@dashboard_bp.route("/")
def dashboard():
    """Main dashboard with various statistics and visualizations."""
    try:
        # Get season from query params or use current season
        season = request.args.get("season") or get_current_season_str()
        current_season = get_current_season_str()
        
        logger.info(f"Loading dashboard for season: {season}")
        
        with get_db_context() as db:
            # Get player stats using ORM
            from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
            player_stats_orm = LeagueDashPlayerStatsORM.get_all_by_season(season, db=db)
            
            if not player_stats_orm:
                logger.warning(f"No player stats found for season {season}")
                player_stats = []
            else:
                player_stats = [stat.to_dict() for stat in player_stats_orm]
                logger.info(f"Retrieved {len(player_stats)} player stats for season {season}")
            
            # Get teams using ORM
            teams_orm = TeamORM.get_all(db)
            teams = [team.to_dict() for team in teams_orm]
            
            if not teams:
                logger.warning("No teams found in database")
                teams = []
            else:
                logger.info(f"Retrieved {len(teams)} teams")
        
        return render_template(
            "dashboard.html", 
            player_stats=player_stats, 
            teams=teams, 
            season=season, 
            current_season=current_season
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        logger.error(traceback.format_exc())
        return render_template("error.html", message=f"Error loading dashboard: {str(e)}"), 500

@dashboard_bp.route('/games')
def games_dashboard():
    """Dashboard showing today's games and standings."""
    # Use fetch_todays_games to get both standings and games data
    data = fetch_todays_games()
    standings = data.get("standings", {"East": [], "West": []})
    games = data.get("games", [])
    
    print(f"Retrieved {len(games)} games and standings for East ({len(standings.get('East', []))}) and West ({len(standings.get('West', []))})")
    
    return render_template("games_dashboard.html", standings=standings, games=games)

#Todo Fix this route
#maybe, need to fix matchups populating 
@dashboard_bp.route("/matchup", methods=['GET', 'POST'])
def matchup():
    """Display matchup analysis between two teams."""
    # Get season from query params or use current season
    season = request.args.get("season") or get_current_season_str()
    current_season = get_current_season_str()
    
    # If it's a POST request, redirect to GET with the same parameters
    if request.method == 'POST':
        team1_id = request.form.get("team1_id")
        team2_id = request.form.get("team2_id")
        season_param = request.form.get("season", current_season)
        return redirect(url_for('dashboard.matchup', team1_id=team1_id, team2_id=team2_id, season=season_param))
    
    team1_id = request.args.get("team1_id")
    team2_id = request.args.get("team2_id")
    
    if not team1_id or not team2_id:
        with get_db_context() as db:
            teams_orm = TeamORM.get_all(db)
            teams = [team.to_dict() for team in teams_orm]
        return render_template("matchup.html", teams=teams, season=season, current_season=current_season)
    
    # Check cache first (include season in cache key)
    cache_key = f"matchup:{team1_id}:{team2_id}:{season}"
    cached_data = get_cache(cache_key)
    
    if cached_data:
        logger.info(f"Cache HIT for matchup: {team1_id} vs {team2_id} (season: {season})")
        cached_data['season'] = season
        cached_data['current_season'] = current_season
        return render_template("matchup.html", **cached_data)
    
    # Get matchup data
    matchup_data = get_matchup_data(team1_id, team2_id, season)
    
    if not matchup_data:
        return render_template("error.html", message="Could not retrieve matchup data for the selected teams"), 404
    
    # Convert player IDs to strings for JSON serialization
    matchup_data["team1_recent_logs"] = {
        str(k): v for k, v in matchup_data.get("team1_recent_logs", {}).items()
    }
    matchup_data["team2_recent_logs"] = {
        str(k): v for k, v in matchup_data.get("team2_recent_logs", {}).items()
    }
    matchup_data["team1_vs_team2_logs"] = {
        str(k): v for k, v in matchup_data.get("team1_vs_team2_logs", {}).items()
    }
    matchup_data["team2_vs_team1_logs"] = {
        str(k): v for k, v in matchup_data.get("team2_vs_team1_logs", {}).items()
    }
    
    # Add season info
    matchup_data['season'] = season
    matchup_data['current_season'] = current_season
    
    # Cache the data
    set_cache(cache_key, matchup_data, ex=86400)  # Cache for 24 hours
    logger.info(f"Cached matchup: {team1_id} vs {team2_id} (season: {season})")
    
    return render_template("matchup.html", **matchup_data)

def get_matchup_data(team1_id, team2_id, season=None):
    """Get matchup data for two teams."""
    try:
        if season is None:
            season = get_current_season_str()
            
        logger.info(f"Starting matchup data retrieval for teams {team1_id} vs {team2_id} (season: {season})")
        # Convert string IDs to integers if needed
        if isinstance(team1_id, str):
            team1_id = int(team1_id)
        if isinstance(team2_id, str):
            team2_id = int(team2_id)
            
        # Fetch team details using service
        logger.info(f"Fetching team details for {team1_id} and {team2_id}")
        team_service = TeamService()
        with get_db_context() as db:
            team1 = team_service.get_complete_team_details(team1_id, db)
            team2 = team_service.get_complete_team_details(team2_id, db)
        
        if not team1 or not team2:
            logger.error(f"Could not find team data for {team1_id} or {team2_id}")
            return None
        
        logger.info(f"Successfully retrieved team details. Team1 roster size: {len(team1['roster'])}, Team2 roster size: {len(team2['roster'])}")
        
        # Get lineup stats with season parameter
        try:
            logger.info(f"Fetching lineup stats for teams {team1_id} and {team2_id} (season: {season})")
            from app.utils.get.get_utils import get_team_lineup_stats
            team1_lineup_stats = get_team_lineup_stats(team1['team_id'], season=season)
            team2_lineup_stats = get_team_lineup_stats(team2['team_id'], season=season)
            logger.info(f"Successfully retrieved lineup stats")
        except Exception as e:
            logger.error(f"Error fetching team lineup stats: {str(e)}")
            traceback.print_exc()
            team1_lineup_stats = {"most_recent_lineup": {}, "most_used_lineup": {}}
            team2_lineup_stats = {"most_recent_lineup": {}, "most_used_lineup": {}}
        
        # Get player logs for both teams (limit to 10 players per team for performance)
        logger.info(f"Fetching recent logs for team {team1_id}")
        team1_recent_logs = fetch_logs(team1['roster'], max_players=10, season=season)
        logger.info(f"Fetching recent logs for team {team2_id}")
        team2_recent_logs = fetch_logs(team2['roster'], max_players=10, season=season)
        logger.info(f"Fetching team1 vs team2 logs")
        team1_vs_team2_logs = fetch_logs(team1['roster'], opponent_id=team2_id, max_players=10, season=season)
        logger.info(f"Fetching team2 vs team1 logs")
        team2_vs_team1_logs = fetch_logs(team2['roster'], opponent_id=team1_id, max_players=10, season=season)
        logger.info(f"Successfully retrieved all game logs")
        
        with get_db_context() as db:
            teams = [team.to_dict() for team in TeamORM.get_all(db)]
        
        return {
            "team1": team1,
            "team2": team2,
            "team1_lineup_stats": team1_lineup_stats,
            "team2_lineup_stats": team2_lineup_stats,
            "team1_recent_logs": team1_recent_logs,
            "team2_recent_logs": team2_recent_logs,
            "team1_vs_team2_logs": team1_vs_team2_logs,
            "team2_vs_team1_logs": team2_vs_team1_logs,
            "teams": teams
        }
    except Exception as e:
        logger.error(f"Error in get_matchup_data: {str(e)}")
        traceback.print_exc()
        return None

def normalize_logs(raw_logs):
    """Normalize player game logs."""
    if not raw_logs:
        return []
    
    # Convert minutes_played from "MM:SS" format to decimal minutes
    def convert_minutes(min_str):
        if not min_str or min_str == "00:00":
            return "0.0"
        try:
            if ':' in str(min_str):
                minutes, seconds = map(int, str(min_str).split(':'))
                return f"{minutes + seconds/60:.1f}"
            return f"{float(min_str):.1f}"
        except (ValueError, TypeError):
            return "0.0"
    
    def format_game_date(date_str):
        """Format game date converting from UTC to EST/EDT for display."""
        from app.utils.date_utils import format_game_date_for_display
        
        if isinstance(date_str, datetime):
            return format_game_date_for_display(date_str)
        try:
            # Try parsing as ISO format datetime string
            date_obj = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
            return format_game_date_for_display(date_obj)
        except (ValueError, TypeError):
            try:
                # Try parsing as date string
                date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")
                return format_game_date_for_display(date_obj)
            except (ValueError, TypeError):
                return str(date_str)
    
    normalized_logs = []
    for log in raw_logs:
        if isinstance(log, dict):
            # Format the score
            team_score = log.get('team_score', 0)
            opponent_score = log.get('opponent_score', 0)
            team_abbrev = log.get('team_abbreviation', 'TEAM')
            opp_abbrev = log.get('opponent_abbreviation', 'OPP')
            
            # Determine win/loss (use result from log if available)
            result = log.get('result', 'W' if team_score > opponent_score else 'L')
            if result not in ['W', 'L']:
                result = 'W' if team_score > opponent_score else 'L'
            formatted_score = f"{team_abbrev} {team_score} - {opponent_score} {opp_abbrev}"
            
            # Create normalized log with all fields
            normalized_log = {
                'game_date': format_game_date(log.get('game_date')),
                'points': log.get('points', 0),
                'assists': log.get('assists', 0),
                'rebounds': log.get('rebounds', 0),
                'steals': log.get('steals', 0),
                'blocks': log.get('blocks', 0),
                'turnovers': log.get('turnovers', 0),
                'minutes_played': convert_minutes(log.get('minutes_played', '00:00')),
                'season': log.get('season', '2024-25'),
                'home_or_away': log.get('home_or_away', 'H'),
                'opponent_abbreviation': opp_abbrev,
                'team_abbreviation': team_abbrev,
                'result': result,
                'formatted_score': formatted_score,
                'team_score': team_score,
                'opponent_score': opponent_score
            }
        else:
            # Fallback for tuple input (should be rare)
            normalized_log = {
                'game_date': format_game_date(datetime.now()),
                'points': 0,
                'assists': 0,
                'rebounds': 0,
                'steals': 0,
                'blocks': 0,
                'turnovers': 0,
                'minutes_played': '0.0',
                'season': '2024-25',
                'home_or_away': 'H',
                'opponent_abbreviation': 'OPP',
                'team_abbreviation': 'TEAM',
                'result': 'W',
                'formatted_score': 'TEAM 100 - 90 OPP',
                'team_score': 100,
                'opponent_score': 90
            }
            
            # Try to extract values if possible
            try:
                if len(log) > 3:
                    normalized_log['points'] = int(log[3] or 0)
                if len(log) > 4:
                    normalized_log['assists'] = int(log[4] or 0)
                if len(log) > 5:
                    normalized_log['rebounds'] = int(log[5] or 0)
                if len(log) > 6:
                    normalized_log['steals'] = int(log[6] or 0)
                if len(log) > 7:
                    normalized_log['blocks'] = int(log[7] or 0)
                if len(log) > 8:
                    normalized_log['turnovers'] = int(log[8] or 0)
                if len(log) > 9:
                    normalized_log['minutes_played'] = convert_minutes(log[9])
            except (ValueError, TypeError, IndexError):
                pass  # Keep default values if conversion fails
        
        normalized_logs.append(normalized_log)
    
    return normalized_logs

def fetch_logs(players, opponent_id=None, max_players=None, season=None):
    """Fetch game logs for players against a specific opponent."""
    if season is None:
        season = get_current_season_str()
    
    # Limit players for performance (only process starting lineup or first 10 players)
    if max_players:
        players = players[:max_players]
    elif len(players) > 10:
        # Only process first 10 players for performance
        players = players[:10]
        logger.info(f"Limiting to first 10 players for performance (from {len(players)} total)")
    
    logger.info(f"Starting fetch_logs for {len(players)} players, opponent_id: {opponent_id}, season: {season}")
    player_logs = {}
    
    # Deduplicate players by player_id
    unique_players = {}
    for player in players:
        player_id = player.get("player_id")
        if player_id and player_id not in unique_players:
            unique_players[player_id] = player
    
    # Convert back to list
    deduplicated_players = list(unique_players.values())
    logger.debug(f"Deduplicated roster from {len(players)} to {len(deduplicated_players)} players")
    
    # Use single DB session for all queries (performance optimization)
    with get_db_context() as db:
        from app.models.gameschedule_sqlalchemy import GameScheduleORM
        from app.models.team_sqlalchemy import TeamORM
        
        # Pre-fetch opponent game IDs if filtering by opponent (performance optimization)
        opponent_game_ids = set()
        if opponent_id:
            # Get games where opponent_id is either team_id or opponent_team_id
            opponent_schedules = db.query(GameScheduleORM).filter(
                (GameScheduleORM.team_id == opponent_id) | (GameScheduleORM.opponent_team_id == opponent_id)
            ).filter(GameScheduleORM.season == season).all()
            opponent_game_ids = {g.game_id for g in opponent_schedules}
            logger.debug(f"Found {len(opponent_game_ids)} games involving opponent {opponent_id}")
        
        for i, player in enumerate(deduplicated_players):
            player_id = player.get("player_id")
            player_name = player.get("player_name")
            
            if not player_id or not player_name:
                continue
            
            try:
                # Get game logs for player in this season
                game_logs_orm = GameLogORM.get_by_player_and_season(player_id, season, db=db)
                
                # Filter by opponent if needed
                if opponent_id:
                    logs_orm = [log for log in game_logs_orm if log.game_id in opponent_game_ids][:10]
                else:
                    logs_orm = game_logs_orm[:10]  # Limit to 10
                
                if not logs_orm:
                    continue
                
                # Enrich logs with schedule and team information
                enriched_logs = []
                for log_orm in logs_orm:
                    # Get schedule info for this game
                    schedule = GameScheduleORM.get_by_game_and_team(log_orm.game_id, log_orm.team_id, db=db)
                    
                    if not schedule:
                        continue
                    
                    # Get team abbreviations
                    team = TeamORM.get_by_id(log_orm.team_id, db)
                    opponent_team = TeamORM.get_by_id(schedule.opponent_team_id, db)
                    
                    # Parse score if available
                    team_score = 0
                    opponent_score = 0
                    if schedule.score:
                        try:
                            scores = schedule.score.split('-')
                            if len(scores) == 2:
                                # Determine which score is which based on home/away
                                if schedule.home_or_away == 'H':
                                    team_score = int(scores[0].strip())
                                    opponent_score = int(scores[1].strip())
                                else:
                                    team_score = int(scores[1].strip())
                                    opponent_score = int(scores[0].strip())
                        except (ValueError, AttributeError):
                            pass
                    
                    # Create enriched log dict
                    log_dict = log_orm.to_dict()
                    log_dict['game_date'] = schedule.game_date
                    log_dict['home_or_away'] = schedule.home_or_away
                    log_dict['team_abbreviation'] = team.abbreviation if team else 'N/A'
                    log_dict['opponent_abbreviation'] = opponent_team.abbreviation if opponent_team else 'N/A'
                    log_dict['team_score'] = team_score
                    log_dict['opponent_score'] = opponent_score
                    # Use schedule result if available, otherwise determine from score
                    if schedule.result:
                        log_dict['result'] = schedule.result
                    elif team_score > 0 or opponent_score > 0:
                        log_dict['result'] = 'W' if team_score > opponent_score else 'L'
                    else:
                        log_dict['result'] = 'N/A'
                    
                    enriched_logs.append(log_dict)
                
                # Normalize logs
                normalized_logs = normalize_logs(enriched_logs)
                
                if normalized_logs:
                    player_logs[player_id] = normalized_logs
                    logger.debug(f"Added {len(normalized_logs)} logs for player {player_name} (ID: {player_id})")
                    
            except Exception as e:
                logger.error(f"Error processing logs for player {player_id}: {str(e)}")
                traceback.print_exc()
    
    logger.info(f"Completed fetch_logs, retrieved logs for {len(player_logs)} players")
    return player_logs
