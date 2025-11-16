#!/usr/bin/env python3
"""
Debug the orderbook response from OpenAlgo
"""

import requests
import json

def debug_orderbook():
    """Debug the orderbook response"""
    
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
    base_url = "http://localhost:5000"
    
    print("🔍 Debugging Orderbook Response")
    print("=" * 40)
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/orderbook",
            json={"apikey": api_key},
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Type: {type(response.text)}")
        print(f"Response Length: {len(response.text)}")
        
        # Try to parse as JSON
        try:
            data = response.json()
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
            
            # Check the structure
            if "data" in data:
                print(f"Data type: {type(data['data'])}")
                if isinstance(data['data'], list):
                    print(f"Number of orders: {len(data['data'])}")
                    if data['data']:
                        print(f"First order structure: {data['data'][0]}")
                elif isinstance(data['data'], dict):
                    print(f"Data keys: {list(data['data'].keys())}")
                    if "orders" in data['data']:
                        print(f"Number of orders: {len(data['data']['orders'])}")
                        if data['data']['orders']:
                            print(f"First order structure: {data['data']['orders'][0]}")
            
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Raw response: {response.text[:500]}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    debug_orderbook()