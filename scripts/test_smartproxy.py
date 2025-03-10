#!/usr/bin/env python
import subprocess
import sys
import os
import random
import requests
from datetime import datetime

# SmartProxy configuration
SMARTPROXY_USERNAME = "user-sppc24ewsr-sessionduration-5"
SMARTPROXY_PASSWORD = "jnD6WnupJ4Zv21i_ai"
SMARTPROXY_HOST = "gate.smartproxy.com"
SMARTPROXY_PORTS = [f"1000{i}" for i in range(1, 11)]  # 10001 through 10010

def test_with_requests():
    """Test NBA API connection using requests with SmartProxy"""
    today = datetime.now().strftime("%m/%d/%Y")
    
    # Select a random port
    port = random.choice(SMARTPROXY_PORTS)
    proxy_url = f"https://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@{SMARTPROXY_HOST}:{port}"
    
    # Build the request
    url = f"https://stats.nba.com/stats/scoreboardV2?GameDate={today}&LeagueID=00&DayOffset=0"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.nba.com/',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    proxies = {
        'http': proxy_url,
        'https': proxy_url
    }
    
    print(f"Testing NBA API connection using requests with SmartProxy on port {port}")
    print(f"Date: {today}")
    print(f"URL: {url}")
    print(f"Proxy: {proxy_url.split('@')[1]}")  # Only show host:port for security
    
    try:
        # Make the request
        response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
        
        # Check if the request was successful
        if response.status_code == 200:
            print("\n✅ Connection successful!")
            print(f"Status code: {response.status_code}")
            
            # Check if the response contains expected data
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
            else:
                print("❌ Response does not contain expected data")
                
            # Print a small sample of the response
            print("\nResponse sample (first 300 characters):")
            print(str(response.text)[:300] + "...")
        else:
            print("\n❌ Connection failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
    
    except Exception as e:
        print(f"\n❌ Error making request: {e}")

if __name__ == "__main__":
    test_with_requests() 