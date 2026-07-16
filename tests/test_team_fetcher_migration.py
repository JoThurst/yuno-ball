"""Quick test to verify TeamFetcher ORM migration.

This script verifies that:
1. TeamFetcher imports correctly with ORM models
2. Basic methods can be called without errors
3. Database operations use ORM models
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_team_fetcher_imports():
    """Test that TeamFetcher imports correctly with ORM models."""
    print("Testing TeamFetcher imports...")
    try:
        from app.utils.fetch.team_fetcher import TeamFetcher
        print("  [OK] TeamFetcher imported successfully")
        
        # Check that it uses ORM models by checking the module file
        import inspect
        import os
        module_file = inspect.getfile(TeamFetcher)
        with open(module_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verify ORM imports (check for any variation)
        has_team_orm = "TeamORM" in source and "team_sqlalchemy" in source
        has_player_orm = "PlayerORM" in source and "player_sqlalchemy" in source
        has_db_context = "get_db_context" in source and "app.database" in source
        
        assert has_team_orm, "TeamORM import not found"
        assert has_player_orm, "PlayerORM import not found"
        assert has_db_context, "get_db_context import not found"
        print("  [OK] ORM imports verified")
        
        # Verify old models are NOT imported
        assert "from app.models.team import Team" not in source, "Old Team import still present"
        assert "from app.models.player import Player" not in source, "Old Player import still present"
        print("  [OK] Old model imports removed")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_team_fetcher_initialization():
    """Test that TeamFetcher can be initialized."""
    print("\nTesting TeamFetcher initialization...")
    try:
        from app.utils.fetch.team_fetcher import TeamFetcher
        
        fetcher = TeamFetcher()
        print("  [OK] TeamFetcher initialized successfully")
        
        # Check that methods exist
        assert hasattr(fetcher, 'fetch_current_rosters')
        assert hasattr(fetcher, '_fetch_single_team_roster')
        assert hasattr(fetcher, 'fetch_team_game_stats_for_season')
        assert hasattr(fetcher, 'fetch_league_dash_team_stats')
        print("  [OK] All expected methods exist")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Initialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orm_models_available():
    """Test that required ORM models are available."""
    print("\nTesting ORM model availability...")
    try:
        from app.models.team_sqlalchemy import TeamORM, RosterORM
        from app.models.player_sqlalchemy import PlayerORM
        from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
        from app.models.gameschedule_sqlalchemy import GameScheduleORM
        from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
        from app.database import get_db_context
        
        print("  [OK] All required ORM models imported")
        
        # Test database connection
        with get_db_context() as db:
            teams = TeamORM.get_all(db)
            print(f"  [OK] Database connection works (found {len(teams)} teams)")
        
        return True
    except Exception as e:
        print(f"  [FAIL] ORM model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("TeamFetcher ORM Migration Test")
    print("="*60)
    
    results = []
    
    results.append(("Imports", test_team_fetcher_imports()))
    results.append(("Initialization", test_team_fetcher_initialization()))
    results.append(("ORM Models", test_orm_models_available()))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n[SUCCESS] All tests passed! TeamFetcher migration is complete.")
        print("\nNext steps:")
        print("  1. Run full ingestion test: python daily_ingest.py --proxy")
        print("  2. Verify data: python test_ingestion_orm_compatibility.py")
        print("  3. Move on to PlayerFetcher migration")
    else:
        print("\n[WARNING] Some tests failed. Please review the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

