"""Verify proxy configuration before running ingestion with --proxy flag.

This script checks:
1. Proxy credentials are configured
2. Proxy list is built correctly
3. Proxy configuration is accessible
4. Can make a test API call with proxy
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_proxy_configuration():
    """Check if proxy configuration is set up correctly."""
    print("="*70)
    print("Proxy Configuration Verification")
    print("="*70)
    
    # Import after setting environment
    from app.utils.config_utils import (
        SMARTPROXY_USERNAME,
        SMARTPROXY_PASSWORD,
        SMARTPROXY_HOST,
        SMARTPROXY_PORTS,
        PROXY_LIST,
        PROXY_ENABLED,
        FORCE_PROXY,
        FORCE_LOCAL
    )
    
    print("\n1. Checking Proxy Credentials...")
    print(f"   Username: {SMARTPROXY_USERNAME[:20]}..." if SMARTPROXY_USERNAME else "   [MISSING]")
    print(f"   Password: {'*' * len(SMARTPROXY_PASSWORD)} ({len(SMARTPROXY_PASSWORD)} chars)" if SMARTPROXY_PASSWORD else "   [MISSING]")
    print(f"   Host: {SMARTPROXY_HOST}")
    print(f"   Ports: {len(SMARTPROXY_PORTS)} ports configured")
    
    if not SMARTPROXY_USERNAME or not SMARTPROXY_PASSWORD:
        print("   [ERROR] Proxy credentials are missing!")
        return False
    
    print("   [OK] Proxy credentials configured")
    
    print("\n2. Checking Proxy List...")
    print(f"   Total proxies in list: {len(PROXY_LIST)}")
    if PROXY_LIST:
        # Show first proxy (masked for security)
        first_proxy = PROXY_LIST[0]
        if '@' in first_proxy:
            masked = first_proxy.split('@')[1]
            print(f"   First proxy: https://***:***@{masked}")
        else:
            print(f"   First proxy: {first_proxy[:50]}...")
        print("   [OK] Proxy list built successfully")
    else:
        print("   [ERROR] Proxy list is empty!")
        return False
    
    print("\n3. Checking Environment Variables...")
    force_proxy_env = os.getenv("FORCE_PROXY", "Not set")
    force_local_env = os.getenv("FORCE_LOCAL", "Not set")
    proxy_enabled_env = os.getenv("PROXY_ENABLED", "Not set")
    
    print(f"   FORCE_PROXY: {force_proxy_env}")
    print(f"   FORCE_LOCAL: {force_local_env}")
    print(f"   PROXY_ENABLED: {proxy_enabled_env}")
    
    print("\n4. Checking Proxy Status...")
    print(f"   PROXY_ENABLED (computed): {PROXY_ENABLED}")
    print(f"   FORCE_PROXY (computed): {FORCE_PROXY}")
    print(f"   FORCE_LOCAL (computed): {FORCE_LOCAL}")
    
    if FORCE_LOCAL:
        print("   [INFO] Local mode is forced - proxies will be disabled")
        print("   [WARNING] To use proxies, set FORCE_LOCAL=false or remove it")
    elif FORCE_PROXY or PROXY_ENABLED:
        print("   [OK] Proxy mode is enabled")
    else:
        print("   [INFO] Proxy mode is disabled (will use direct connection)")
        print("   [INFO] Use --proxy flag or set FORCE_PROXY=true to enable")
    
    return True

def test_proxy_connection():
    """Test if we can make an API call with proxy."""
    print("\n" + "="*70)
    print("Testing Proxy Connection")
    print("="*70)
    
    # Set FORCE_PROXY for this test
    os.environ["FORCE_PROXY"] = "true"
    os.environ["FORCE_LOCAL"] = "false"
    
    try:
        from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
        from nba_api.stats.endpoints import ScoreboardV2
        from datetime import datetime
        
        print("\n1. Getting API configuration...")
        api_config = get_api_config()
        
        if api_config['proxy']:
            # Mask proxy URL for security
            proxy_display = api_config['proxy'].split('@')[1] if '@' in api_config['proxy'] else api_config['proxy']
            print(f"   [OK] Proxy selected: {proxy_display}")
        else:
            print("   [WARNING] No proxy selected - will use direct connection")
            print("   [INFO] This might fail if running on AWS")
        
        print("\n2. Testing API call with proxy...")
        today = datetime.now().strftime("%Y-%m-%d")
        
        try:
            scoreboard = create_api_endpoint(ScoreboardV2, game_date=today)
            data = scoreboard.get_dict()
            
            print("   [SUCCESS] API call successful!")
            print(f"   Retrieved {len(data.get('resultSets', []))} result sets")
            
            # Check for games
            if 'resultSets' in data:
                game_header = next((rs for rs in data['resultSets'] if rs.get('name') == 'GameHeader'), None)
                if game_header and game_header.get('rowSet'):
                    print(f"   Found {len(game_header['rowSet'])} games for {today}")
                else:
                    print(f"   No games scheduled for {today} (this is normal)")
            
            return True
            
        except Exception as e:
            print(f"   [ERROR] API call failed: {e}")
            print("   [INFO] This could be due to:")
            print("     - Invalid proxy credentials")
            print("     - Proxy server issues")
            print("     - Network connectivity problems")
            print("     - NBA API rate limiting")
            return False
            
    except Exception as e:
        print(f"   [ERROR] Failed to test proxy: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_usage_instructions():
    """Show how to use proxies."""
    print("\n" + "="*70)
    print("Usage Instructions")
    print("="*70)
    print("\nTo run ingestion with proxies:")
    print("  python daily_ingest.py --proxy")
    print("\nTo run without proxies (direct connection):")
    print("  python daily_ingest.py --local")
    print("\nEnvironment Variables:")
    print("  FORCE_PROXY=true    - Force proxy usage")
    print("  FORCE_LOCAL=true    - Force direct connection")
    print("  PROXY_ENABLED=true  - Enable proxy mode")
    print("\nNote: The --proxy flag sets FORCE_PROXY=true automatically")

def main():
    """Run all verification checks."""
    print("\n")
    
    # Check configuration
    config_ok = check_proxy_configuration()
    
    if not config_ok:
        print("\n[ERROR] Proxy configuration is incomplete!")
        print("Please check app/utils/config_utils.py for proxy credentials.")
        return False
    
    # Test connection automatically (non-interactive)
    print("\n" + "="*70)
    print("Testing proxy connection...")
    test_ok = test_proxy_connection()
    
    if test_ok:
        print("\n[SUCCESS] Proxy setup is working correctly!")
        print("You can safely run: python daily_ingest.py --proxy")
    else:
        print("\n[WARNING] Proxy test failed. Check credentials and network.")
        print("You may still want to test with: python daily_ingest.py --proxy")
        print("Note: The test might fail if FORCE_LOCAL=true is set")
    
    show_usage_instructions()
    
    print("\n" + "="*70)
    print("Verification Complete")
    print("="*70)
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Interrupted] Verification cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

