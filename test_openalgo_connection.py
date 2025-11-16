#!/usr/bin/env python3
"""
Test script to verify OpenAlgo API connection and authentication
"""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_openalgo_connection():
    """Test OpenAlgo API connection with the provided API key"""
    
    # Get configuration from environment
    base_url = os.getenv("OPENALGO_BASE_URL", "http://localhost:5000/api/v1")
    api_key = os.getenv("OPENALGO_API_KEY", "")
    
    if not api_key:
        print("❌ OPENALGO_API_KEY not found in environment")
        return False
    
    print(f"Testing OpenAlgo connection...")
    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:10]}...")
    
    # Test endpoints - OpenAlgo uses /api/v1/endpoint format
    endpoints_to_test = [
        "/api/v1/ping",  # Basic connectivity
        "/api/v1/funds",  # Account info (requires auth)
        "/api/v1/holdings"  # Holdings (requires auth)
    ]
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    results = {}
    
    for endpoint in endpoints_to_test:
        url = f"{base_url}{endpoint}"
        print(f"\nTesting {endpoint}...")
        
        try:
            if endpoint == "/api/v1/ping":
                # Ping requires POST with API key in body
                data = {"apikey": api_key}
                response = requests.post(url, json=data, timeout=10)
            else:
                # Other endpoints require auth header
                response = requests.get(url, headers=headers, timeout=10)
            
            results[endpoint] = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.text[:200] if len(response.text) > 200 else response.text
            }
            
            if response.status_code == 200:
                print(f"✅ {endpoint}: Success (200)")
            else:
                print(f"⚠️  {endpoint}: Status {response.status_code}")
                print(f"Response: {response.text[:100]}...")
                
        except requests.exceptions.RequestException as e:
            results[endpoint] = {
                "status_code": None,
                "success": False,
                "error": str(e)
            }
            print(f"❌ {endpoint}: Failed - {e}")
    
    # Summary
    print("\n" + "="*50)
    print("CONNECTION TEST SUMMARY")
    print("="*50)
    
    all_success = True
    for endpoint, result in results.items():
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"{endpoint}: {status}")
        if not result["success"]:
            all_success = False
    
    if all_success:
        print("\n🎉 All tests passed! OpenAlgo connection is working.")
    else:
        print("\n⚠️  Some tests failed. Check the configuration.")
    
    return all_success

if __name__ == "__main__":
    print("OpenAlgo Connection Test")
    print("=" * 30)
    success = test_openalgo_connection()
    
    if success:
        print("\n✅ You can now proceed with Fortress integration!")
    else:
        print("\n❌ Please check your OpenAlgo configuration and try again.")