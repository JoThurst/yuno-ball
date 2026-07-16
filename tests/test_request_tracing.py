"""Test script for request tracing and error handling.

Run this while your Flask app is running on http://127.0.0.1:8000
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_request_tracing():
    """Test that request IDs are returned in headers."""
    print("=" * 60)
    print("Testing Request Tracing")
    print("=" * 60)
    
    # Test 1: Normal request
    print("\n1. Testing normal request (GET /api/players)...")
    response = requests.get(f"{BASE_URL}/api/players")
    request_id = response.headers.get('X-Request-ID')
    
    if request_id:
        print(f"   ✅ Request ID found: {request_id}")
        print(f"   Status Code: {response.status_code}")
    else:
        print("   ❌ Request ID NOT found in headers")
        print(f"   Available headers: {list(response.headers.keys())}")
    
    # Test 2: 404 error
    print("\n2. Testing 404 error (GET /api/nonexistent)...")
    response = requests.get(f"{BASE_URL}/api/nonexistent")
    request_id = response.headers.get('X-Request-ID')
    
    if request_id:
        print(f"   ✅ Request ID found: {request_id}")
        print(f"   Status Code: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   Error Response: {json.dumps(error_data, indent=2)}")
        except:
            print(f"   Response: {response.text}")
    else:
        print("   ❌ Request ID NOT found")
    
    # Test 3: DataNotFoundError (if endpoint exists)
    print("\n3. Testing DataNotFoundError (GET /api/players/99999)...")
    response = requests.get(f"{BASE_URL}/api/players/99999")
    request_id = response.headers.get('X-Request-ID')
    
    if request_id:
        print(f"   ✅ Request ID found: {request_id}")
        print(f"   Status Code: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   Error Response: {json.dumps(error_data, indent=2)}")
            if 'error' in error_data and 'request_id' in error_data:
                print("   ✅ Error response includes structured error and request_id")
        except:
            print(f"   Response: {response.text}")
    else:
        print("   ❌ Request ID NOT found")
    
    print("\n" + "=" * 60)
    print("Request Tracing Test Complete")
    print("=" * 60)
    print("\nCheck your Flask app logs for:")
    print("  - 'request_start' logs with method, path, request_id")
    print("  - 'request_end' logs with status_code, duration_ms")
    print("  - All logs should include request_id in context")

if __name__ == "__main__":
    try:
        test_request_tracing()
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to Flask app")
        print("   Make sure your app is running on http://127.0.0.1:8000")
        print("   Run: python run.py")
    except Exception as e:
        print(f"❌ ERROR: {e}")

