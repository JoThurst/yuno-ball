import os
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
This script helps identify NBA API calls in the codebase that need to be updated
to use the new proxy configuration. It doesn't modify files automatically but
provides guidance on what changes to make.
"""

# NBA API endpoint classes to look for
NBA_API_CLASSES = [
    "playercareerstats",
    "LeagueGameFinder",
    "PlayerGameLogs",
    "commonplayerinfo",
    "commonteamroster",
    "leaguedashplayerstats",
    "leaguedashteamstats",
    "ScoreboardV2",
    "cumestatsteam",
    "teamgamelog"
]

# Directories to search
SEARCH_DIRS = [
    "app/utils/fetch",
    "app/utils/get",
    "app/routes"
]

def find_api_calls():
    """Find NBA API calls in the codebase that need to be updated."""
    pattern = r'(\w+)\s*=\s*(' + '|'.join(NBA_API_CLASSES) + r')\s*\('
    
    for search_dir in SEARCH_DIRS:
        if not os.path.exists(search_dir):
            print(f"Directory {search_dir} does not exist, skipping...")
            continue
            
        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_no = content[:match.start()].count('\n') + 1
                        print(f"Found API call in {file_path}:{line_no}")
                        print(f"  {match.group(0)}")
                        print("  Suggested update:")
                        print(f"  {match.group(1)} = create_api_endpoint({match.group(2)}, ...)")
                        print()

def print_instructions():
    """Print instructions for updating API calls."""
    print("=" * 80)
    print("INSTRUCTIONS FOR UPDATING NBA API CALLS")
    print("=" * 80)
    print("\n1. Import the api_utils module in each file:")
    print("   from app.utils.fetch.api_utils import get_api_config, create_api_endpoint\n")
    print("2. Replace direct API calls with create_api_endpoint:")
    print("   BEFORE: scoreboard = ScoreboardV2(game_date=today)")
    print("   AFTER:  scoreboard = create_api_endpoint(ScoreboardV2, game_date=today)\n")
    print("3. Or add proxy configuration to existing calls:")
    print("   BEFORE: scoreboard = ScoreboardV2(game_date=today)")
    print("   AFTER:  api_config = get_api_config()")
    print("           scoreboard = ScoreboardV2(")
    print("               game_date=today,")
    print("               proxy=api_config['proxy'],")
    print("               headers=api_config['headers'],")
    print("               timeout=api_config['timeout']")
    print("           )\n")
    print("=" * 80)

if __name__ == "__main__":
    print_instructions()
    print("\nSearching for NBA API calls that need to be updated...\n")
    find_api_calls() 