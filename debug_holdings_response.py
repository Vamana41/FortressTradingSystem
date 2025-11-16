#!/usr/bin/env python3
"""
Debug the holdings response structure.
"""

import requests
import json

API_KEY = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
BASE_URL = "http://localhost:5000/api/v1"

def debug_holdings():
    """Debug the holdings response."""
    url = f"{BASE_URL}/holdings"
    headers = {"Content-Type": "application/json"}
    data = {"apikey": API_KEY}
    
    try:
        print("Testing holdings endpoint...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Parsed JSON: {json.dumps(result, indent=2)}")
                
                # Check the structure
                if isinstance(result, dict):
                    print(f"Status: {result.get('status')}")
                    print(f"Message: {result.get('message')}")
                    print(f"Data type: {type(result.get('data'))}")
                    print(f"Data: {result.get('data')}")
                else:
                    print(f"Result is not a dict: {type(result)}")
                    
            except Exception as e:
                print(f"JSON parse error: {e}")
        
    except Exception as e:
        print(f"Request error: {e}")

if __name__ == "__main__":
    debug_holdings()