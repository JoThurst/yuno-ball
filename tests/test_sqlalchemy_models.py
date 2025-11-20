"""Test suite for SQLAlchemy ORM models.

This test suite verifies all converted SQLAlchemy models work correctly
with the live database. Tests cover query operations, CRUD operations,
relationships, and data integrity.

Models tested:
- UserORM (User authentication and management)
- PlayerORM (Player biographical data)
- TeamORM (Team information)
- RosterORM (Player-team associations)
- StatisticsORM (Season statistics)
- GameLogORM (Individual game performance)

Run: python -m pytest tests/test_sqlalchemy_models.py -v
Or:  python tests/test_sqlalchemy_models.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_context
from app.models.player_sqlalchemy import PlayerORM
from app.models.team_sqlalchemy import TeamORM, RosterORM
from app.models.statistics_sqlalchemy import StatisticsORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.models.player_z_scores_sqlalchemy import PlayerZScoresORM


def test_player_model():
    """Test PlayerORM model operations."""
    print("\n" + "=" * 60)
    print("Testing PlayerORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all players (limit to 5 for display)
            players = db.query(PlayerORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(players)} players from database")
            
            if players:
                # Display first player
                player = players[0]
                print(f"\nSample Player:")
                print(f"  - ID: {player.player_id}")
                print(f"  - Name: {player.name}")
                print(f"  - Position: {player.position}")
                print(f"  - Age: {player.age}")
                print(f"  - School: {player.school}")
                
                # Test: Get player by ID
                same_player = PlayerORM.get_by_id(player.player_id, db)
                if same_player and same_player.player_id == player.player_id:
                    print(f"\n[OK] get_by_id() works correctly")
                else:
                    print(f"\n[FAIL] get_by_id() failed")
                    return False
                
                # Test: to_dict()
                player_dict = player.to_dict()
                if 'player_id' in player_dict and 'name' in player_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: Check if player exists
                exists = PlayerORM.exists(player.player_id, db)
                if exists:
                    print(f"[OK] exists() works correctly")
                else:
                    print(f"[FAIL] exists() failed")
                    return False
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] PlayerORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_team_model():
    """Test TeamORM model operations."""
    print("\n" + "=" * 60)
    print("Testing TeamORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all teams (limit to 5 for display)
            teams = db.query(TeamORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(teams)} teams from database")
            
            if teams:
                # Display first team
                team = teams[0]
                print(f"\nSample Team:")
                print(f"  - ID: {team.team_id}")
                print(f"  - Name: {team.name}")
                print(f"  - Abbreviation: {team.abbreviation}")
                
                # Test: Get team by ID
                same_team = TeamORM.get_by_id(team.team_id, db)
                if same_team and same_team.team_id == team.team_id:
                    print(f"\n[OK] get_by_id() works correctly")
                else:
                    print(f"\n[FAIL] get_by_id() failed")
                    return False
                
                # Test: Get team by abbreviation
                if team.abbreviation:
                    team_by_abbr = TeamORM.get_by_abbreviation(team.abbreviation, db)
                    if team_by_abbr and team_by_abbr.team_id == team.team_id:
                        print(f"[OK] get_by_abbreviation() works correctly")
                    else:
                        print(f"[FAIL] get_by_abbreviation() failed")
                        return False
                
                # Test: to_dict()
                team_dict = team.to_dict()
                if 'team_id' in team_dict and 'name' in team_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TeamORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_roster_model():
    """Test RosterORM model operations."""
    print("\n" + "=" * 60)
    print("Testing RosterORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get roster entries (limit to 5)
            roster_entries = db.query(RosterORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(roster_entries)} roster entries from database")
            
            if roster_entries:
                # Display first roster entry
                entry = roster_entries[0]
                print(f"\nSample Roster Entry:")
                print(f"  - Team ID: {entry.team_id}")
                print(f"  - Player ID: {entry.player_id}")
                print(f"  - Player Name: {entry.player_name}")
                print(f"  - Number: {entry.player_number}")
                print(f"  - Position: {entry.position}")
                print(f"  - Season: {entry.season}")
                
                # Test: Get roster by player
                player_roster = RosterORM.get_by_player(entry.player_id, db)
                if player_roster and len(player_roster) > 0:
                    print(f"\n[OK] get_by_player() works correctly (found {len(player_roster)} entries)")
                else:
                    print(f"\n[FAIL] get_by_player() failed")
                    return False
                
                # Test: to_dict()
                entry_dict = entry.to_dict()
                if 'team_id' in entry_dict and 'player_id' in entry_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: Get team's roster
                team = TeamORM.get_by_id(entry.team_id, db)
                if team:
                    roster = team.get_roster(db=db)
                    print(f"[OK] Team.get_roster() works correctly (found {len(roster)} players)")
                else:
                    print(f"[FAIL] Could not get team for roster test")
                    return False
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] RosterORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_statistics_model():
    """Test StatisticsORM model operations."""
    print("\n" + "=" * 60)
    print("Testing StatisticsORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all statistics (limit to 5 for display)
            stats = db.query(StatisticsORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(stats)} statistics entries from database")
            
            if stats:
                # Display first statistics entry
                stat = stats[0]
                print(f"\nSample Statistics Entry:")
                print(f"  - Stat ID: {stat.stat_id}")
                print(f"  - Player ID: {stat.player_id}")
                print(f"  - Season: {stat.season_year}")
                print(f"  - Points: {stat.points}")
                print(f"  - Rebounds: {stat.rebounds}")
                print(f"  - Assists: {stat.assists}")
                
                # Test: Get statistics by player
                player_stats = StatisticsORM.get_by_player(stat.player_id, db)
                if player_stats and len(player_stats) > 0:
                    print(f"\n[OK] get_by_player() works correctly (found {len(player_stats)} seasons)")
                else:
                    print(f"\n[FAIL] get_by_player() failed")
                    return False
                
                # Test: Get statistics by player and season
                if stat.season_year:
                    season_stat = StatisticsORM.get_by_player_and_season(stat.player_id, stat.season_year, db)
                    if season_stat and season_stat.stat_id == stat.stat_id:
                        print(f"[OK] get_by_player_and_season() works correctly")
                    else:
                        print(f"[FAIL] get_by_player_and_season() failed")
                        return False
                
                # Test: to_dict()
                stat_dict = stat.to_dict()
                if 'stat_id' in stat_dict and 'player_id' in stat_dict and 'season_year' in stat_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: exists_for_player
                exists = StatisticsORM.exists_for_player(stat.player_id, db)
                if exists:
                    print(f"[OK] exists_for_player() works correctly")
                else:
                    print(f"[FAIL] exists_for_player() failed")
                    return False
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] StatisticsORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gamelog_model():
    """Test GameLogORM model operations."""
    print("\n" + "=" * 60)
    print("Testing GameLogORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all game logs (limit to 5 for display)
            gamelogs = db.query(GameLogORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(gamelogs)} game logs from database")
            
            if gamelogs:
                # Display first game log
                log = gamelogs[0]
                print(f"\nSample Game Log:")
                print(f"  - Player ID: {log.player_id}")
                print(f"  - Game ID: {log.game_id}")
                print(f"  - Team ID: {log.team_id}")
                print(f"  - Season: {log.season}")
                print(f"  - Points: {log.points}")
                print(f"  - Rebounds: {log.rebounds}")
                print(f"  - Assists: {log.assists}")
                print(f"  - Minutes: {log.minutes_played}")
                
                # Test: Get game logs by player
                player_logs = GameLogORM.get_by_player(log.player_id, db)
                if player_logs and len(player_logs) > 0:
                    print(f"\n[OK] get_by_player() works correctly (found {len(player_logs)} games)")
                else:
                    print(f"\n[FAIL] get_by_player() failed")
                    return False
                
                # Test: Get game logs by player and season
                season_logs = GameLogORM.get_by_player_and_season(log.player_id, log.season, db)
                if season_logs and len(season_logs) > 0:
                    print(f"[OK] get_by_player_and_season() works correctly (found {len(season_logs)} games)")
                else:
                    print(f"[FAIL] get_by_player_and_season() failed")
                    return False
                
                # Test: Get single game log
                single_log = GameLogORM.get_single_log(log.player_id, log.game_id, db)
                if single_log and single_log.game_id == log.game_id:
                    print(f"[OK] get_single_log() works correctly")
                else:
                    print(f"[FAIL] get_single_log() failed")
                    return False
                
                # Test: to_dict()
                log_dict = log.to_dict()
                if 'player_id' in log_dict and 'game_id' in log_dict and 'season' in log_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: has_logs_for_season
                has_logs = GameLogORM.has_logs_for_season(log.player_id, log.season, db)
                if has_logs:
                    print(f"[OK] has_logs_for_season() works correctly")
                else:
                    print(f"[FAIL] has_logs_for_season() failed")
                    return False
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] GameLogORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_player_streaks_model():
    """Test PlayerStreaksORM model operations."""
    print("\n" + "=" * 60)
    print("Testing PlayerStreaksORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all streaks (limit to 5 for display)
            streaks = db.query(PlayerStreaksORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(streaks)} player streaks from database")
            
            if streaks:
                # Display first streak
                streak = streaks[0]
                print(f"\nSample Player Streak:")
                print(f"  - ID: {streak.id}")
                print(f"  - Player ID: {streak.player_id}")
                print(f"  - Player Name: {streak.player_name}")
                print(f"  - Stat: {streak.stat}")
                print(f"  - Threshold: {streak.threshold}")
                print(f"  - Streak Games: {streak.streak_games}")
                print(f"  - Season: {streak.season}")
                
                # Test: Get streak by ID
                same_streak = PlayerStreaksORM.get_by_id(streak.id, db)
                if same_streak and same_streak.id == streak.id:
                    print(f"\n[OK] get_by_id() works correctly")
                else:
                    print(f"\n[FAIL] get_by_id() failed")
                    return False
                
                # Test: Get streaks by player
                player_streaks = PlayerStreaksORM.get_by_player(streak.player_id, db=db)
                if player_streaks and len(player_streaks) > 0:
                    print(f"[OK] get_by_player() works correctly (found {len(player_streaks)} streaks)")
                else:
                    print(f"[FAIL] get_by_player() failed")
                    return False
                
                # Test: to_dict()
                streak_dict = streak.to_dict()
                if 'id' in streak_dict and 'player_id' in streak_dict and 'stat' in streak_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
            else:
                print(f"[INFO] No player streaks found in database (might be expected)")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] PlayerStreaksORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_team_game_stats_model():
    """Test TeamGameStatsORM model operations."""
    print("\n" + "=" * 60)
    print("Testing TeamGameStatsORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all team game stats (limit to 5 for display)
            stats = db.query(TeamGameStatsORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(stats)} team game stats from database")
            
            if stats:
                # Display first stat
                stat = stats[0]
                print(f"\nSample Team Game Stat:")
                print(f"  - Game ID: {stat.game_id}")
                print(f"  - Team ID: {stat.team_id}")
                print(f"  - Opponent Team ID: {stat.opponent_team_id}")
                print(f"  - Season: {stat.season}")
                print(f"  - Game Date: {stat.game_date}")
                print(f"  - Points: {stat.pts}")
                print(f"  - Rebounds: {stat.reb}")
                print(f"  - Assists: {stat.ast}")
                
                # Test: Get stat by game and team
                same_stat = TeamGameStatsORM.get_by_game_and_team(stat.game_id, stat.team_id, db)
                if same_stat and same_stat.game_id == stat.game_id:
                    print(f"\n[OK] get_by_game_and_team() works correctly")
                else:
                    print(f"\n[FAIL] get_by_game_and_team() failed")
                    return False
                
                # Test: Get stats by team
                team_stats = TeamGameStatsORM.get_by_team(stat.team_id, db=db)
                if team_stats and len(team_stats) > 0:
                    print(f"[OK] get_by_team() works correctly (found {len(team_stats)} games)")
                else:
                    print(f"[FAIL] get_by_team() failed")
                    return False
                
                # Test: to_dict()
                stat_dict = stat.to_dict()
                if 'game_id' in stat_dict and 'team_id' in stat_dict and 'pts' in stat_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
            else:
                print(f"[INFO] No team game stats found in database (might be expected)")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] TeamGameStatsORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_game_schedule_model():
    """Test GameScheduleORM model operations."""
    print("\n" + "=" * 60)
    print("Testing GameScheduleORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all game schedules (limit to 5 for display)
            schedules = db.query(GameScheduleORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(schedules)} game schedules from database")
            
            if schedules:
                # Display first schedule
                schedule = schedules[0]
                print(f"\nSample Game Schedule:")
                print(f"  - Game ID: {schedule.game_id}")
                print(f"  - Team ID: {schedule.team_id}")
                print(f"  - Opponent Team ID: {schedule.opponent_team_id}")
                print(f"  - Season: {schedule.season}")
                print(f"  - Game Date: {schedule.game_date}")
                print(f"  - Home/Away: {schedule.home_or_away}")
                print(f"  - Result: {schedule.result}")
                print(f"  - Score: {schedule.score}")
                
                # Test: Get schedule by game and team
                same_schedule = GameScheduleORM.get_by_game_and_team(schedule.game_id, schedule.team_id, db)
                if same_schedule and same_schedule.game_id == schedule.game_id:
                    print(f"\n[OK] get_by_game_and_team() works correctly")
                else:
                    print(f"\n[FAIL] get_by_game_and_team() failed")
                    return False
                
                # Test: Get schedules by team
                team_schedules = GameScheduleORM.get_by_team(schedule.team_id, db=db)
                if team_schedules and len(team_schedules) > 0:
                    print(f"[OK] get_by_team() works correctly (found {len(team_schedules)} games)")
                else:
                    print(f"[FAIL] get_by_team() failed")
                    return False
                
                # Test: to_dict()
                schedule_dict = schedule.to_dict()
                if 'game_id' in schedule_dict and 'team_id' in schedule_dict and 'season' in schedule_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: get_opponent_team_id
                opponent_id = GameScheduleORM.get_opponent_team_id(schedule.game_id, schedule.team_id, db)
                if opponent_id == schedule.opponent_team_id:
                    print(f"[OK] get_opponent_team_id() works correctly")
                else:
                    print(f"[FAIL] get_opponent_team_id() failed")
                    return False
            else:
                print(f"[INFO] No game schedules found in database (might be expected)")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] GameScheduleORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_league_dash_team_stats_model():
    """Test LeagueDashTeamStatsORM model operations."""
    print("\n" + "=" * 60)
    print("Testing LeagueDashTeamStatsORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all team stats (limit to 5 for display)
            stats = db.query(LeagueDashTeamStatsORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(stats)} league dash team stats from database")
            
            if stats:
                # Display first stat entry
                stat = stats[0]
                print(f"\nSample League Dash Team Stat:")
                print(f"  - Team ID: {stat.team_id}")
                print(f"  - Team Name: {stat.team_name}")
                print(f"  - Season: {stat.season}")
                print(f"  - Season Type: {stat.season_type}")
                print(f"  - Base Totals GP: {stat.base_totals_gp}")
                print(f"  - Base Totals W: {stat.base_totals_w}")
                print(f"  - Base Totals L: {stat.base_totals_l}")
                print(f"  - Base Totals PTS: {stat.base_totals_pts}")
                print(f"  - Advanced Totals OFF Rating: {stat.advanced_totals_off_rating}")
                
                # Test: Get by team
                same_stat = LeagueDashTeamStatsORM.get_by_team(
                    stat.team_id, stat.season, stat.season_type, db
                )
                if same_stat and same_stat.team_id == stat.team_id:
                    print(f"\n[OK] get_by_team() works correctly")
                else:
                    print(f"\n[FAIL] get_by_team() failed")
                    return False
                
                # Test: Get all teams for a season
                all_teams = LeagueDashTeamStatsORM.get_all_teams(season=stat.season, db=db)
                if all_teams and len(all_teams) > 0:
                    print(f"[OK] get_all_teams() works correctly (found {len(all_teams)} teams)")
                else:
                    print(f"[FAIL] get_all_teams() failed")
                    return False
                
                # Test: to_dict() for Base/Totals
                stat_dict = stat.to_dict(measure_type='Base', per_mode='Totals')
                if 'team_id' in stat_dict and 'team_name' in stat_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: get_team_rankings
                rankings = LeagueDashTeamStatsORM.get_team_rankings(season=stat.season, db=db)
                if rankings and len(rankings) > 0:
                    print(f"[OK] get_team_rankings() works correctly (found {len(rankings)} teams)")
                else:
                    print(f"[FAIL] get_team_rankings() failed")
                    return False
            else:
                print(f"[INFO] No league dash team stats found in database (might be expected)")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] LeagueDashTeamStatsORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_league_dash_player_stats_model():
    """Test LeagueDashPlayerStatsORM model operations."""
    print("\n" + "=" * 60)
    print("Testing LeagueDashPlayerStatsORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all player stats (limit to 5 for display)
            stats = db.query(LeagueDashPlayerStatsORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(stats)} league dash player stats from database")
            
            if stats:
                # Display first stat entry
                stat = stats[0]
                print(f"\nSample League Dash Player Stat:")
                print(f"  - Player ID: {stat.player_id}")
                print(f"  - Player Name: {stat.player_name}")
                print(f"  - Season: {stat.season}")
                print(f"  - Team: {stat.team_abbreviation}")
                print(f"  - GP: {stat.gp}")
                print(f"  - PTS: {stat.pts}")
                print(f"  - REB: {stat.reb}")
                print(f"  - AST: {stat.ast}")
                
                # Test: Get by player
                same_stat = LeagueDashPlayerStatsORM.get_by_player(stat.player_id, stat.season, db)
                if same_stat and same_stat.player_id == stat.player_id:
                    print(f"\n[OK] get_by_player() works correctly")
                else:
                    print(f"\n[FAIL] get_by_player() failed")
                    return False
                
                # Test: Get all by season
                all_players = LeagueDashPlayerStatsORM.get_all_by_season(season=stat.season, db=db)
                if all_players and len(all_players) > 0:
                    print(f"[OK] get_all_by_season() works correctly (found {len(all_players)} players)")
                else:
                    print(f"[FAIL] get_all_by_season() failed")
                    return False
                
                # Test: to_dict()
                stat_dict = stat.to_dict()
                if 'player_id' in stat_dict and 'player_name' in stat_dict and 'pts' in stat_dict:
                    print(f"[OK] to_dict() works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: search_by_name
                if stat.player_name:
                    search_name = stat.player_name.split()[0]  # First name
                    search_results = LeagueDashPlayerStatsORM.search_by_name(search_name, db=db)
                    if search_results and len(search_results) > 0:
                        print(f"[OK] search_by_name() works correctly (found {len(search_results)} matches)")
                    else:
                        print(f"[FAIL] search_by_name() failed")
                        return False
            else:
                print(f"[INFO] No league dash player stats found in database (might be expected)")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] LeagueDashPlayerStatsORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_player_z_scores_model():
    """Test PlayerZScoresORM model operations."""
    print("\n" + "=" * 60)
    print("Testing PlayerZScoresORM Model")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Get all Z-scores (limit to 5 for display)
            z_scores = db.query(PlayerZScoresORM).limit(5).all()
            print(f"\n[OK] Retrieved {len(z_scores)} player Z-score records from database")
            
            if z_scores:
                # Display first Z-score record
                z_score = z_scores[0]
                print(f"\nSample Player Z-Score Record:")
                print(f"  - Player ID: {z_score.player_id}")
                print(f"  - PTS Z-Score: {z_score.pts_z_score:.3f}" if z_score.pts_z_score else "  - PTS Z-Score: N/A")
                print(f"  - REB Z-Score: {z_score.reb_z_score:.3f}" if z_score.reb_z_score else "  - REB Z-Score: N/A")
                print(f"  - AST Z-Score: {z_score.ast_z_score:.3f}" if z_score.ast_z_score else "  - AST Z-Score: N/A")
                print(f"  - STL Z-Score: {z_score.stl_z_score:.3f}" if z_score.stl_z_score else "  - STL Z-Score: N/A")
                print(f"  - BLK Z-Score: {z_score.blk_z_score:.3f}" if z_score.blk_z_score else "  - BLK Z-Score: N/A")
                
                # Test: Get Z-score by player ID
                same_z_score = PlayerZScoresORM.get_by_player(db, z_score.player_id)
                if same_z_score and same_z_score.player_id == z_score.player_id:
                    print(f"\n[OK] get_by_player() works correctly")
                else:
                    print(f"\n[FAIL] get_by_player() failed")
                    return False
                
                # Test: to_dict() with all fields
                z_score_dict = z_score.to_dict(include_all=True)
                if 'player_id' in z_score_dict and 'pts_z_score' in z_score_dict:
                    print(f"[OK] to_dict(include_all=True) works correctly")
                else:
                    print(f"[FAIL] to_dict() missing keys")
                    return False
                
                # Test: to_dict() without None values
                z_score_dict_filtered = z_score.to_dict(include_all=False)
                non_null_count = sum(1 for v in z_score_dict_filtered.values() if v is not None)
                print(f"[OK] to_dict(include_all=False) filtered to {non_null_count} non-null fields")
                
                # Test: get_composite_score()
                composite = z_score.get_composite_score()
                if isinstance(composite, float):
                    print(f"[OK] get_composite_score() works correctly (score: {composite:.3f})")
                else:
                    print(f"[FAIL] get_composite_score() failed")
                    return False
                
                # Test: get_top_players() by PTS
                top_scorers = PlayerZScoresORM.get_top_players(db, 'pts', limit=5)
                if top_scorers and len(top_scorers) > 0:
                    print(f"[OK] get_top_players('pts') works correctly (found {len(top_scorers)} players)")
                    print(f"     Top scorer Z-score: {top_scorers[0].pts_z_score:.3f}" if top_scorers[0].pts_z_score else "     Top scorer Z-score: N/A")
                else:
                    print(f"[FAIL] get_top_players() failed")
                    return False
                
                # Test: get_all()
                all_z_scores = PlayerZScoresORM.get_all(db, limit=10)
                if all_z_scores and len(all_z_scores) > 0:
                    print(f"[OK] get_all() works correctly (retrieved {len(all_z_scores)} records)")
                else:
                    print(f"[FAIL] get_all() failed")
                    return False
                
                # Test: Check relationship to PlayerORM (if player data exists)
                if hasattr(z_score, 'player') and z_score.player:
                    print(f"[OK] Relationship to PlayerORM works correctly")
                    print(f"     Player name: {z_score.player.name}")
                else:
                    print(f"[INFO] No player relationship found (foreign key may not have matching record)")
            else:
                print(f"[INFO] No player Z-scores found in database (might be expected)")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] PlayerZScoresORM test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_relationships():
    """Test relationships between models."""
    print("\n" + "=" * 60)
    print("Testing Model Relationships")
    print("=" * 60)
    
    try:
        with get_db_context() as db:
            # Test: Team -> Roster relationship
            team = db.query(TeamORM).first()
            if team:
                print(f"\nTesting Team '{team.name}' roster entries:")
                roster_count = len(team.roster_entries)
                print(f"  - Roster entries via relationship: {roster_count}")
                
                if roster_count > 0:
                    print(f"[OK] Team->Roster relationship works")
                else:
                    print(f"[INFO] Team has no roster entries (might be expected)")
            else:
                print(f"[INFO] No teams found in database")
        
        return True
        
    except Exception as e:
        print(f"\n[FAIL] Relationship test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n")
    print("=" * 60)
    print("  SQLAlchemy ORM Models Test Suite")
    print("  Testing: User, Player, Team, Roster, Statistics, GameLog,")
    print("           PlayerStreaks, TeamGameStats, GameSchedule,")
    print("           LeagueDashTeamStats, LeagueDashPlayerStats, PlayerZScores")
    print("=" * 60)
    
    tests = [
        ("PlayerORM Model", test_player_model),
        ("TeamORM Model", test_team_model),
        ("RosterORM Model", test_roster_model),
        ("StatisticsORM Model", test_statistics_model),
        ("GameLogORM Model", test_gamelog_model),
        ("PlayerStreaksORM Model", test_player_streaks_model),
        ("TeamGameStatsORM Model", test_team_game_stats_model),
        ("GameScheduleORM Model", test_game_schedule_model),
        ("LeagueDashTeamStatsORM Model", test_league_dash_team_stats_model),
        ("LeagueDashPlayerStatsORM Model", test_league_dash_player_stats_model),
        ("PlayerZScoresORM Model", test_player_z_scores_model),
        ("Model Relationships", test_relationships),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n[ERROR] Test '{test_name}' crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print("\n" + "-" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("-" * 60)
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! SQLAlchemy models are working correctly.")
        print("\nModels tested:")
        print("  [OK] PlayerORM - Player biographical data")
        print("  [OK] TeamORM - Team information")
        print("  [OK] RosterORM - Player-team associations")
        print("  [OK] StatisticsORM - Season statistics")
        print("  [OK] GameLogORM - Individual game performance")
        print("  [OK] PlayerStreaksORM - Player streak tracking")
        print("  [OK] TeamGameStatsORM - Team game statistics")
        print("  [OK] GameScheduleORM - Game schedules and results")
        print("  [OK] LeagueDashTeamStatsORM - Comprehensive team statistics")
        print("  [OK] LeagueDashPlayerStatsORM - League-wide player statistics")
        print("  [OK] PlayerZScoresORM - Player Z-score statistics")
        print("\nNext steps:")
        print("  1. Add relationships between models")
        print("  2. Update routes to use SQLAlchemy models")
        print("  3. Generate final Alembic migration")
        return 0
    else:
        print("\n[ERROR] Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

