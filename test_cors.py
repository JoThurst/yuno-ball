import requests
import json

def test_cors():
    base_url = 'http://localhost:8000'
    endpoints = ['/api/team-stats']
    origins = [
        'http://localhost:3000',
        'https://yunoball.xyz',
        'https://invalid-origin.com'
    ]
    
    for endpoint in endpoints:
        print(f"\nTesting endpoint: {endpoint}")
        
        for origin in origins:
            print(f"\nTesting with Origin: {origin}")
            
            # Test OPTIONS preflight request
            options_headers = {
                'Origin': origin,
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'X-API-Key'
            }
            
            try:
                options_response = requests.options(
                    f'{base_url}{endpoint}',
                    headers=options_headers
                )
                print("\nOPTIONS Response Headers:")
                for key, value in options_response.headers.items():
                    if key.lower().startswith('access-control'):
                        print(f"{key}: {value}")
            except requests.exceptions.RequestException as e:
                print(f"OPTIONS request failed: {str(e)}")
            
            # Test actual GET request
            headers = {
                'Origin': origin,
                'X-API-Key': 'test-key'
            }
            
            try:
                response = requests.get(
                    f'{base_url}{endpoint}',
                    headers=headers,
                    params={'team_id': 1}
                )
                print("\nGET Response Headers:")
                for key, value in response.headers.items():
                    if key.lower().startswith('access-control'):
                        print(f"{key}: {value}")
                
                if response.ok:
                    print("\nResponse Status:", response.status_code)
                else:
                    print("\nRequest failed with status:", response.status_code)
                    print("Response:", response.text)
            except requests.exceptions.RequestException as e:
                print(f"GET request failed: {str(e)}")

if __name__ == '__main__':
    test_cors() 