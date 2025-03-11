#!/usr/bin/env python
"""
This script updates all remaining NBA API calls in the codebase to use the proxy configuration.
It searches for NBA API calls and provides instructions on how to update them.
"""

import os
import re
import sys
import glob
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    "teamgamelog",
    "playergamelogs",
    "leaguedashlineups"
]

# Directories to search
SEARCH_DIRS = [
    "app/utils/fetch",
    "app/utils/get",
    "app/routes",
    "app/services"
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
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            content = f.read()
                        except UnicodeDecodeError:
                            print(f"Error reading {file_path}, skipping...")
                            continue
                        
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

def update_ingest_scripts():
    """Print instructions for updating ingest scripts."""
    print("\n" + "=" * 80)
    print("INSTRUCTIONS FOR UPDATING INGEST SCRIPTS")
    print("=" * 80)
    print("\nTo enable proxy support in your ingest scripts, add these lines at the beginning:")
    print("\n```python")
    print("import sys")
    print("import os")
    print("")
    print("# Check for proxy configuration in command line arguments")
    print("if \"--proxy\" in sys.argv:")
    print("    os.environ[\"FORCE_PROXY\"] = \"true\"")
    print("    print(\"🔄 Forcing proxy usage for API calls\")")
    print("")
    print("if \"--local\" in sys.argv:")
    print("    os.environ[\"FORCE_LOCAL\"] = \"true\"")
    print("    print(\"🔄 Forcing local (direct) connection for API calls\")")
    print("```\n")
    print("Then you can run your scripts with proxy support:")
    print("python ingest_data.py --proxy  # Force proxy usage")
    print("python daily_ingest.py --local  # Force local connection")
    print("=" * 80)

if __name__ == "__main__":
    print_instructions()
    update_ingest_scripts()
    print("\nSearching for NBA API calls that need to be updated...\n")
    find_api_calls() 