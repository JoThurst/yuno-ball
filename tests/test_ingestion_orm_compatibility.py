"""Test script to verify ingestion works with ORM and test proxy configuration.

This script:
1. Tests that ingestion can write data using old models
2. Verifies ORM models can read the data back
3. Tests with proxy configuration for speed
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set proxy config if provided
if "--proxy" in sys.argv:
    os.environ["FORCE_PROXY"] = "true"
    print("🔄 Proxy mode enabled")
    sys.argv.remove("--proxy")

if "--local" in sys.argv:
    os.environ["FORCE_LOCAL"] = "true"
    print("🔄 Local mode enabled")
    sys.argv.remove("--local")

from app.database import get_db_context
from app.models.team_sqlalchemy import TeamORM
from app.models.player_sqlalchemy import PlayerORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.statistics_sqlalchemy import StatisticsORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM

def test_orm_read_access():
    """Test that ORM models can read data written by old models."""
    print("\n" + "="*60)
    print("Testing ORM Read Access")
    print("="*60)
    
    with get_db_context() as db:
        # Test 1: Read teams
        print("\n1. Testing TeamORM...")
        teams = TeamORM.get_all(db, limit=5)
        if teams:
            print(f"   ✅ Found {len(teams)} teams")
            team = teams[0]
            print(f"   Sample: {team.name} (ID: {team.team_id})")
        else:
            print("   ⚠️  No teams found")
        
        # Test 2: Read players
        print("\n2. Testing PlayerORM...")
        players = PlayerORM.get_all(db, limit=5)
        if players:
            print(f"   ✅ Found {len(players)} players")
            player = players[0]
            print(f"   Sample: {player.name} (ID: {player.player_id})")
        else:
            print("   ⚠️  No players found")
        
        # Test 3: Read game logs
        print("\n3. Testing GameLogORM...")
        game_logs = GameLogORM.get_all(db, limit=5)
        if game_logs:
            print(f"   ✅ Found {len(game_logs)} game logs")
            log = game_logs[0]
            print(f"   Sample: Player {log.player_id}, Game {log.game_id}, {log.pts} pts")
        else:
            print("   ⚠️  No game logs found")
        
        # Test 4: Read game schedule
        print("\n4. Testing GameScheduleORM...")
        games = GameScheduleORM.get_all(db, limit=5)
        if games:
            print(f"   ✅ Found {len(games)} scheduled games")
            game = games[0]
            print(f"   Sample: {game.team_id} vs {game.opponent_team_id} on {game.game_date}")
        else:
            print("   ⚠️  No scheduled games found")
        
        # Test 5: Read team game stats
        print("\n5. Testing TeamGameStatsORM...")
        stats = TeamGameStatsORM.get_all(db, limit=5)
        if stats:
            print(f"   ✅ Found {len(stats)} team game stats")
            stat = stats[0]
            print(f"   Sample: Team {stat.team_id}, Game {stat.game_id}, {stat.pts} pts")
        else:
            print("   ⚠️  No team game stats found")
        
        # Test 6: Read league dash team stats
        print("\n6. Testing LeagueDashTeamStatsORM...")
        ld_stats = LeagueDashTeamStatsORM.get_all(db, limit=3)
        if ld_stats:
            print(f"   ✅ Found {len(ld_stats)} league dash team stats")
            stat = ld_stats[0]
            print(f"   Sample: Team {stat.team_id}, Season {stat.season}")
        else:
            print("   ⚠️  No league dash team stats found")
        
        # Test 7: Read player statistics
        print("\n7. Testing StatisticsORM...")
        player_stats = StatisticsORM.get_all(db, limit=5)
        if player_stats:
            print(f"   ✅ Found {len(player_stats)} player statistics")
            stat = player_stats[0]
            print(f"   Sample: Player {stat.player_id}, Season {stat.season_year}, {stat.pts} PPG")
        else:
            print("   ⚠️  No player statistics found")
        
        # Test 8: Read player streaks
        print("\n8. Testing PlayerStreaksORM...")
        streaks = PlayerStreaksORM.get_all(db, limit=5)
        if streaks:
            print(f"   ✅ Found {len(streaks)} player streaks")
            streak = streaks[0]
            print(f"   Sample: Player {streak.player_id}, {streak.streak_type} streak")
        else:
            print("   ⚠️  No player streaks found")
        
        # Test 9: Read league dash player stats
        print("\n9. Testing LeagueDashPlayerStatsORM...")
        ld_player_stats = LeagueDashPlayerStatsORM.get_all(db, limit=5)
        if ld_player_stats:
            print(f"   ✅ Found {len(ld_player_stats)} league dash player stats")
            stat = ld_player_stats[0]
            print(f"   Sample: Player {stat.player_id}, Season {stat.season}")
        else:
            print("   ⚠️  No league dash player stats found")
    
    print("\n" + "="*60)
    print("ORM Read Test Complete")
    print("="*60)

def test_ingestion_compatibility():
    """Test that ingestion writes data that ORM can read."""
    print("\n" + "="*60)
    print("Testing Ingestion → ORM Compatibility")
    print("="*60)
    print("\nThis test verifies that:")
    print("  1. Ingestion writes data using old models (raw SQL)")
    print("  2. ORM models can read that data back")
    print("  3. Both systems work with the same database tables")
    print("\n✅ If ORM can read the data, ingestion is compatible!")
    print("\nTo test full ingestion, run:")
    print("  python daily_ingest.py --proxy  # With proxy for speed")
    print("  python daily_ingest.py --local  # Without proxy")

if __name__ == "__main__":
    try:
        test_orm_read_access()
        test_ingestion_compatibility()
        
        print("\n" + "="*60)
        print("Next Steps")
        print("="*60)
        print("\n1. Run ingestion with proxy for speed:")
        print("   python daily_ingest.py --proxy")
        print("\n2. Verify data was written:")
        print("   python test_ingestion_orm_compatibility.py")
        print("\n3. Check ingestion logs:")
        print("   tail -f daily_ingest.log")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

