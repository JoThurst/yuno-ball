"""Test NBA API connectivity with or without proxy.

Uses nba_api's documented interface:
  https://github.com/swar/nba_api

  endpoint(..., proxy='http://user:pass@host:port', headers=STATS_HEADERS, timeout=...)
"""

import sys
import os
import argparse
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def set_env_vars(force_proxy=False, force_local=False):
    """Set environment variables for proxy configuration"""
    if "FORCE_PROXY" in os.environ:
        del os.environ["FORCE_PROXY"]
    if "FORCE_LOCAL" in os.environ:
        del os.environ["FORCE_LOCAL"]

    if force_proxy:
        os.environ["FORCE_PROXY"] = "true"
        os.environ["FORCE_LOCAL"] = "false"
        print("[proxy] Forcing proxy usage for this test")

    if force_local:
        os.environ["FORCE_LOCAL"] = "true"
        os.environ["FORCE_PROXY"] = "false"
        print("[local] Forcing direct connection for this test")


parser = argparse.ArgumentParser(description="Test NBA API connection with or without proxy")
parser.add_argument("--proxy", action="store_true", help="Force using proxy")
parser.add_argument("--local", action="store_true", help="Force direct connection without proxy")
args = parser.parse_args()

if args.proxy and args.local:
    print("Error: Cannot specify both --proxy and --local")
    sys.exit(1)

set_env_vars(force_proxy=args.proxy, force_local=args.local)

from nba_api.stats.endpoints import ScoreboardV2, commonteamroster
from nba_api.stats.library.http import STATS_HEADERS
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint
from app.utils.config_utils import PROXY_LIST


def test_proxy_connection():
    today = datetime.now().strftime("%Y-%m-%d")
    api_config = get_api_config()

    print("\n=== API Configuration ===")
    print(f"FORCE_PROXY env var: {os.getenv('FORCE_PROXY', 'Not set')}")
    print(f"FORCE_LOCAL env var: {os.getenv('FORCE_LOCAL', 'Not set')}")
    if api_config["proxy"]:
        proxy_display = (
            api_config["proxy"].split("@")[1]
            if "@" in api_config["proxy"]
            else api_config["proxy"]
        )
        print(f"Using proxy: {proxy_display}")
    else:
        print("Using direct connection (no proxy)")
    print(f"Available proxies: {len(PROXY_LIST)}")
    print(f"Timeout: {api_config['timeout']} seconds")
    hdr_keys = sorted((api_config["headers"] or {}).keys())
    print(f"Header keys: {hdr_keys}")
    has_token = "x-nba-stats-token" in (api_config["headers"] or {})
    print(f"Has x-nba-stats-token: {has_token}")
    print("=========================\n")

    # Stick to one proxy for all tests (nba_api style)
    proxy = api_config["proxy"]
    headers = api_config["headers"] or STATS_HEADERS

    # 1) Scoreboard via helper (same path as ingest)
    print("=== Test: ScoreboardV2 via create_api_endpoint ===")
    try:
        scoreboard = create_api_endpoint(
            ScoreboardV2, game_date=today, proxy=proxy, headers=headers, timeout=60
        )
        data = scoreboard.get_dict()
        print(f"[OK] ScoreboardV2 — {len(data.get('resultSets', []))} result sets")
    except Exception as e:
        print(f"[FAIL] ScoreboardV2: {e}")

    # 2) Roster via helper (the failing ingest task)
    print("\n=== Test: CommonTeamRoster via create_api_endpoint ===")
    try:
        roster = create_api_endpoint(
            commonteamroster.CommonTeamRoster,
            team_id=1610612738,  # Celtics
            proxy=proxy,
            headers=headers,
            timeout=60,
        )
        nd = roster.get_normalized_dict()
        players = nd.get("CommonTeamRoster", [])
        print(f"[OK] CommonTeamRoster — {len(players)} players")
    except Exception as e:
        print(f"[FAIL] CommonTeamRoster: {e}")

    # 3) Raw nba_api call with library STATS_HEADERS (control)
    print("\n=== Test: raw nba_api CommonTeamRoster (library STATS_HEADERS) ===")
    try:
        roster = commonteamroster.CommonTeamRoster(
            team_id=1610612738,
            proxy=proxy,
            headers=STATS_HEADERS,
            timeout=60,
        )
        nd = roster.get_normalized_dict()
        print(f"[OK] raw nba_api — {len(nd.get('CommonTeamRoster', []))} players")
    except Exception as e:
        print(f"[FAIL] raw nba_api: {e}")

    print(
        "\nIf raw nba_api also fails, the issue is Decodo->stats.nba.com reachability, "
        "not our wrapper. Check Decodo plan/location (US residential) and username format."
    )


if __name__ == "__main__":
    test_proxy_connection()
