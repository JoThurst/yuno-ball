import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables before importing app modules
def set_env_vars(force_proxy=False, force_local=False):
    if force_proxy:
        os.environ["FORCE_PROXY"] = "true"
        os.environ["FORCE_LOCAL"] = "false"
        print("🔄 Forcing proxy usage for this test")
    
    if force_local:
        os.environ["FORCE_LOCAL"] = "true"
        os.environ["FORCE_PROXY"] = "false"
        print("🔄 Forcing local (direct) connection for this test")

# Parse arguments first
parser = argparse.ArgumentParser(description='Test NBA API connection with or without proxy')
parser.add_argument('--proxy', action='store_true', help='Force using proxy even if disabled in config')
parser.add_argument('--local', action='store_true', help='Force direct connection without proxy')
args = parser.parse_args()

if args.proxy and args.local:
    print("Error: Cannot specify both --proxy and --local")
    sys.exit(1)

# Set environment variables before importing app modules
set_env_vars(force_proxy=args.proxy, force_local=args.local)

# Now import app modules after environment variables are set
from nba_api.stats.endpoints import ScoreboardV2
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
from app.utils.config_utils import logger, PROXY_ENABLED, PROXY_LIST

def test_proxy_connection():
    """
    Test NBA API connection with or without proxy
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Method 1: Using get_api_config
    api_config = get_api_config()
    
    # Print configuration
    print("\n=== API Configuration ===")
    print(f"Proxy enabled: {PROXY_ENABLED}")
    if PROXY_ENABLED and api_config['proxy']:
        # Only show host:port part of the proxy URL for security
        proxy_display = api_config['proxy'].split('@')[1] if '@' in api_config['proxy'] else api_config['proxy']
        print(f"Using proxy: {proxy_display}")
    else:
        print("Using direct connection (no proxy)")
    
    print(f"Available proxies: {len(PROXY_LIST)}")
    print(f"Timeout: {api_config['timeout']} seconds")
    print("=========================\n")
    
    # Test direct configuration
    print("\n=== Testing Direct Configuration ===")
    try:
        scoreboard = ScoreboardV2(
            game_date=today,
            proxy=api_config['proxy'],
            headers=api_config['headers'],
            timeout=api_config['timeout']
        )
        data = scoreboard.get_dict()
        print("✅ Connection successful using direct configuration")
        print(f"Retrieved {len(data.get('resultSets', []))} result sets")
        
        # Print some data to verify
        if 'resultSets' in data and len(data['resultSets']) > 0:
            game_header = next((rs for rs in data['resultSets'] if rs['name'] == 'GameHeader'), None)
            if game_header and 'rowSet' in game_header and len(game_header['rowSet']) > 0:
                print(f"Found {len(game_header['rowSet'])} games for {today}")
            else:
                print(f"No games found for {today}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    
    # Test helper function
    print("\n=== Testing Helper Function ===")
    try:
        scoreboard = create_api_endpoint(ScoreboardV2, game_date=today)
        data = scoreboard.get_dict()
        print("✅ Connection successful using helper function")
        print(f"Retrieved {len(data.get('resultSets', []))} result sets")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_proxy_connection() 