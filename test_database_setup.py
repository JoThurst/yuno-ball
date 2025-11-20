"""Test script to verify SQLAlchemy and Alembic setup.

This script tests:
1. Database connection via SQLAlchemy
2. Alembic migration environment
3. Both psycopg2 and SQLAlchemy compatibility
4. Schema access (public, nba, mlb)

Run this script to verify Day 1 setup is complete.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment_variables():
    """Test that required environment variables are set."""
    print("=" * 60)
    print("Testing Environment Variables")
    print("=" * 60)
    
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Mask the password in output
        masked_url = database_url
        if '@' in masked_url:
            parts = masked_url.split('@')
            user_part = parts[0].split(':')
            if len(user_part) > 1:
                masked_url = f"{user_part[0]}:****@{parts[1]}"
        print(f"✓ DATABASE_URL is set: {masked_url}")
        return True
    else:
        print("✗ DATABASE_URL is not set")
        return False


def test_sqlalchemy_import():
    """Test SQLAlchemy and database module imports."""
    print("\n" + "=" * 60)
    print("Testing SQLAlchemy Imports")
    print("=" * 60)
    
    try:
        from app.database import engine, SessionLocal, Base, get_db_context, check_database_connection
        print("✓ SQLAlchemy imports successful")
        print(f"  - Engine: {type(engine).__name__}")
        print(f"  - SessionLocal: {type(SessionLocal).__name__}")
        print(f"  - Base: {type(Base).__name__}")
        return True
    except ImportError as e:
        print(f"✗ SQLAlchemy import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error during import: {e}")
        return False


def test_database_connection():
    """Test database connection via SQLAlchemy."""
    print("\n" + "=" * 60)
    print("Testing Database Connection (SQLAlchemy)")
    print("=" * 60)
    
    try:
        from app.database import check_database_connection, get_db_context
        
        if check_database_connection():
            print("✓ Database connection successful")
            
            # Test query
            with get_db_context() as db:
                result = db.execute("SELECT version()")
                version = result.fetchone()[0]
                print(f"  - PostgreSQL version: {version.split(',')[0]}")
            
            return True
        else:
            print("✗ Database connection failed")
            return False
    except Exception as e:
        print(f"✗ Database connection error: {e}")
        return False


def test_schema_access():
    """Test access to different PostgreSQL schemas."""
    print("\n" + "=" * 60)
    print("Testing Schema Access")
    print("=" * 60)
    
    try:
        from app.database import get_db_context, set_schema
        
        schemas_to_test = ['public', 'nba', 'mlb']
        results = {}
        
        for schema in schemas_to_test:
            try:
                with get_db_context() as db:
                    set_schema(db, schema)
                    result = db.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{schema}'")
                    count = result.fetchone()[0]
                    results[schema] = count
                    print(f"✓ Schema '{schema}' accessible - {count} tables found")
            except Exception as e:
                print(f"✗ Schema '{schema}' access failed: {e}")
                results[schema] = None
        
        return all(v is not None for v in results.values())
    except Exception as e:
        print(f"✗ Schema access test error: {e}")
        return False


def test_psycopg2_compatibility():
    """Test backward compatibility with psycopg2."""
    print("\n" + "=" * 60)
    print("Testing Psycopg2 Compatibility")
    print("=" * 60)
    
    try:
        from db_config import get_database_info, is_sqlalchemy_available
        
        info = get_database_info()
        print(f"✓ Database info retrieved:")
        print(f"  - Psycopg2 pool initialized: {info['psycopg2_pool_initialized']}")
        print(f"  - SQLAlchemy available: {info['sqlalchemy_available']}")
        print(f"  - Recommended for new code: {info['recommended_for_new_code']}")
        
        return True
    except Exception as e:
        print(f"✗ Compatibility test failed: {e}")
        return False


def test_alembic_environment():
    """Test Alembic migration environment."""
    print("\n" + "=" * 60)
    print("Testing Alembic Configuration")
    print("=" * 60)
    
    # Check if alembic.ini exists
    if os.path.exists('alembic.ini'):
        print("✓ alembic.ini found")
    else:
        print("✗ alembic.ini not found")
        return False
    
    # Check if alembic directory exists
    if os.path.exists('alembic'):
        print("✓ alembic directory found")
    else:
        print("✗ alembic directory not found")
        return False
    
    # Check key alembic files
    alembic_files = ['alembic/env.py', 'alembic/script.py.mako', 'alembic/README']
    for file in alembic_files:
        if os.path.exists(file):
            print(f"✓ {file} found")
        else:
            print(f"✗ {file} not found")
            return False
    
    # Check versions directory
    if os.path.exists('alembic/versions'):
        print("✓ alembic/versions directory found")
    else:
        print("✗ alembic/versions directory not found")
        return False
    
    print("\n  Note: Run 'alembic current' to verify Alembic can connect to database")
    
    return True


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "YunoBall Database Setup Test Suite" + " " * 14 + "║")
    print("║" + " " * 15 + "Day 1: SQLAlchemy + Alembic" + " " * 16 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("SQLAlchemy Imports", test_sqlalchemy_import),
        ("Database Connection", test_database_connection),
        ("Schema Access", test_schema_access),
        ("Psycopg2 Compatibility", test_psycopg2_compatibility),
        ("Alembic Environment", test_alembic_environment),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "-" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("-" * 60)
    
    if passed == total:
        print("\n✓ All tests passed! Day 1 setup is complete.")
        print("\nNext steps:")
        print("  1. Review the migration plan in cursor docs/PRODUCTION_READINESS_PLAN.md")
        print("  2. Start converting one model to SQLAlchemy (Day 2)")
        print("  3. Run: alembic revision --autogenerate -m 'Initial migration'")
        return 0
    else:
        print("\n✗ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

