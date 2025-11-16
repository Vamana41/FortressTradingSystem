#!/usr/bin/env python3
"""
Test OpenAlgo API with correct API key and endpoints.
"""

import requests
import json

# Use the correct API key from the database
API_KEY = "471c8eb891d229cc2816da27deabf6fd6cc019107dbf6fcd8c756d151c877371"
BASE_URL = "http://localhost:5000/api/v1"

def test_endpoint(method, endpoint, data=None):
    """Test a specific endpoint."""
    url = f"{BASE_URL}/{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    # Add API key to data
    if data is None:
        data = {}
    data["apikey"] = API_KEY
    
    try:
        print(f"Testing {method} {endpoint}")
        if method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == "GET":
            response = requests.get(url, headers=headers, params=data, timeout=10)
        
        print(f"  Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("status") == "success":
                    print(f"  ✅ Success: {result.get('message', 'OK')}")
                    if result.get("data"):
                        print(f"  Data preview: {str(result['data'])[:200]}...")
                else:
                    print(f"  ❌ API Error: {result.get('message', 'Unknown error')}")
            except Exception as e:
                print(f"  Response: {response.text[:100]}...")
        else:
            print(f"  Error: {response.text[:200]}...")
        
        return response.status_code == 200 and response.json().get("status") == "success"
        
    except Exception as e:
        print(f"  Exception: {e}")
        return False

def main():
    """Main function."""
    print("Testing OpenAlgo API with correct authentication...")
    print(f"API Key: {API_KEY[:10]}...")
    print()
    
    # Test basic endpoints
    success_count = 0
    total_tests = 0
    
    # Test ping
    total_tests += 1
    if test_endpoint("POST", "ping", {}):
        success_count += 1
    
    # Test funds
    total_tests += 1
    if test_endpoint("POST", "funds", {}):
        success_count += 1
    
    # Test orderbook
    total_tests += 1
    if test_endpoint("POST", "orderbook", {}):
        success_count += 1
    
    # Test positionbook
    total_tests += 1
    if test_endpoint("POST", "positionbook", {}):
        success_count += 1
    
    # Test holdings
    total_tests += 1
    if test_endpoint("POST", "holdings", {}):
        success_count += 1
    
    # Test quotes (with required fields)
    total_tests += 1
    if test_endpoint("POST", "quotes", {"symbol": "SBIN", "exchange": "NSE"}):
        success_count += 1
    
    # Test depth (with required fields)
    total_tests += 1
    if test_endpoint("POST", "depth", {"symbol": "SBIN", "exchange": "NSE"}):
        success_count += 1
    
    print(f"\nResults: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("✅ All OpenAlgo API endpoints are working correctly!")
    else:
        print("❌ Some endpoints failed. Check the logs above.")

if __name__ == "__main__":
    main()