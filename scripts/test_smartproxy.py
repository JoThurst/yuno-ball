#!/usr/bin/env python
import subprocess
import sys
import os
import random
import requests
from datetime import datetime
import time

# SmartProxy configuration
SMARTPROXY_USERNAME = "user-sppc24ewsr-sessionduration-5"
SMARTPROXY_PASSWORD = "jnD6WnupJ4Zv21i_ai"
SMARTPROXY_HOST = "gate.smartproxy.com"
SMARTPROXY_PORTS = ["10001", "10002", "10003", "10004", "10005", "10006", "10007", "10008", "10009", "10010"]  # Fixed port list

# Different user agents to try
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

def test_with_requests():
    """Test NBA API connection using requests with SmartProxy"""
    today = datetime.now().strftime("%m/%d/%Y")
    
    # Try each port with different headers
    for port in SMARTPROXY_PORTS:
        proxy_url = f"https://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@{SMARTPROXY_HOST}:{port}"
        
        # Build the request
        url = f"https://stats.nba.com/stats/scoreboardV2?GameDate={today}&LeagueID=00&DayOffset=0"
        
        # Try different user agents
        for user_agent in USER_AGENTS:
            headers = {
                'User-Agent': user_agent,
                'Referer': 'https://www.nba.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Origin': 'https://www.nba.com',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
                'DNT': '1'
            }
            
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            print(f"\nTesting NBA API connection using requests with SmartProxy on port {port}")
            print(f"Date: {today}")
            print(f"URL: {url}")
            print(f"Proxy: {proxy_url.split('@')[1]}")  # Only show host:port for security
            print(f"User-Agent: {user_agent[:30]}...")
            
            try:
                # Make the request
                response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
                
                # Check if the request was successful
                if response.status_code == 200:
                    print("\n✅ Connection successful!")
                    print(f"Status code: {response.status_code}")
                    
                    # Check if the response contains expected data
                    try:
                        data = response.json()
                        if "resultSets" in data:
                            print("✅ Response contains expected data")
                            print(f"Retrieved {len(data.get('resultSets', []))} result sets")
                            
                            # Print game information if available
                            game_header = next((rs for rs in data['resultSets'] if rs['name'] == 'GameHeader'), None)
                            if game_header and 'rowSet' in game_header and len(game_header['rowSet']) > 0:
                                print(f"Found {len(game_header['rowSet'])} games for {today}")
                            else:
                                print(f"No games found for {today}")
                                
                            # Success! No need to try other combinations
                            return True
                        else:
                            print("❌ Response does not contain expected data")
                    except ValueError:
                        print("❌ Response is not valid JSON")
                        print("\nResponse sample (first 300 characters):")
                        print(str(response.text)[:300] + "...")
                else:
                    print("\n❌ Connection failed!")
                    print(f"Status code: {response.status_code}")
                    print(f"Response: {response.text[:300]}...")
            
            except Exception as e:
                print(f"\n❌ Error making request: {e}")
            
            # Wait a bit before trying the next combination
            time.sleep(2)
    
    return False

if __name__ == "__main__":
    if not test_with_requests():
        print("\n❌ All proxy combinations failed. The NBA API may be blocking proxy requests.")
        print("Try using a different proxy service or running without a proxy.")
        sys.exit(1)
    else:
        print("\n✅ Found a working proxy configuration!")
        sys.exit(0) 