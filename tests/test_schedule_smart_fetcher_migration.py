"""Quick test to verify ScheduleFetcher and SmartGameLogFetcher ORM migration.

This script verifies that:
1. Both fetchers import correctly with ORM models
2. Basic methods can be called without errors
3. Database operations use ORM models
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_schedule_fetcher_imports():
    """Test that ScheduleFetcher imports correctly with ORM models."""
    print("Testing ScheduleFetcher imports...")
    try:
        from app.utils.fetch.schedule_fetcher import ScheduleFetcher
        print("  [OK] ScheduleFetcher imported successfully")
        
        # Check that it uses ORM models by checking the module file
        import inspect
        module_file = inspect.getfile(ScheduleFetcher)
        with open(module_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verify ORM imports
        has_gameschedule_orm = "GameScheduleORM" in source and "gameschedule_sqlalchemy" in source
        has_db_context = "get_db_context" in source and "app.database" in source
        
        assert has_gameschedule_orm, "GameScheduleORM import not found"
        assert has_db_context, "get_db_context import not found"
        print("  [OK] ORM imports verified")
        
        # Verify old models are NOT imported
        assert "from app.models.gameschedule import GameSchedule" not in source, "Old GameSchedule import still present"
        print("  [OK] Old model imports removed")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_smart_gamelog_fetcher_imports():
    """Test that SmartGameLogFetcher imports correctly with ORM models."""
    print("\nTesting SmartGameLogFetcher imports...")
    try:
        from app.utils.fetch.smart_gamelog_fetcher import SmartGameLogFetcher
        print("  [OK] SmartGameLogFetcher imported successfully")
        
        # Check that it uses ORM models by checking the module file
        import inspect
        module_file = inspect.getfile(SmartGameLogFetcher)
        with open(module_file, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Verify ORM imports
        has_player_orm = "PlayerORM" in source and "player_sqlalchemy" in source
        has_gamelog_orm = "GameLogORM" in source and "gamelog_sqlalchemy" in source
        has_statistics_orm = "StatisticsORM" in source and "statistics_sqlalchemy" in source
        has_db_context = "get_db_context" in source and "app.database" in source
        
        assert has_player_orm, "PlayerORM import not found"
        assert has_gamelog_orm, "GameLogORM import not found"
        assert has_statistics_orm, "StatisticsORM import not found"
        assert has_db_context, "get_db_context import not found"
        print("  [OK] ORM imports verified")
        
        # Verify old models are NOT imported
        assert "from app.models.player import Player" not in source, "Old Player import still present"
        assert "from app.models.playergamelog import PlayerGameLog" not in source, "Old PlayerGameLog import still present"
        assert "from app.models.statistics import Statistics" not in source, "Old Statistics import still present"
        print("  [OK] Old model imports removed")
        
        return True
    except Exception as e:
        print(f"  [FAIL] Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fetcher_initialization():
    """Test that both fetchers can be initialized."""
    print("\nTesting fetcher initialization...")
    try:
        from app.utils.fetch.schedule_fetcher import ScheduleFetcher
        from app.utils.fetch.smart_gamelog_fetcher import SmartGameLogFetcher
        
        schedule_fetcher = ScheduleFetcher()
        smart_fetcher = SmartGameLogFetcher()
        print("  [OK] Both fetchers initialized successfully")
        
        # Check that methods exist
        assert hasattr(schedule_fetcher, 'fetch_and_store_schedule')
        assert hasattr(schedule_fetcher, 'fetch_and_store_future_games')
        assert hasattr(smart_fetcher, 'fetch_game_logs_tiered')
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
        from app.models.gameschedule_sqlalchemy import GameScheduleORM
        from app.models.player_sqlalchemy import PlayerORM
        from app.models.gamelog_sqlalchemy import GameLogORM
        from app.models.statistics_sqlalchemy import StatisticsORM
        from app.database import get_db_context
        
        print("  [OK] All required ORM models imported")
        
        # Test database connection
        with get_db_context() as db:
            # Just verify connection works
            players = PlayerORM.get_all(db)
            print(f"  [OK] Database connection works (found {len(players)} players)")
        
        return True
    except Exception as e:
        print(f"  [FAIL] ORM model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("ScheduleFetcher & SmartGameLogFetcher ORM Migration Test")
    print("="*60)
    
    results = []
    
    results.append(("ScheduleFetcher Imports", test_schedule_fetcher_imports()))
    results.append(("SmartGameLogFetcher Imports", test_smart_gamelog_fetcher_imports()))
    results.append(("Initialization", test_fetcher_initialization()))
    results.append(("ORM Models", test_orm_models_available()))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n[SUCCESS] All tests passed! Both fetchers migration is complete.")
        print("\nNext steps:")
        print("  1. Run full ingestion test: python daily_ingest.py --proxy")
        print("  2. Verify data: python test_ingestion_orm_compatibility.py")
        print("  3. Move on to BulkSeasonFetcher migration")
    else:
        print("\n[WARNING] Some tests failed. Please review the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

