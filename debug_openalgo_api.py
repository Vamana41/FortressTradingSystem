#!/usr/bin/env python3
"""
Debug script to test OpenAlgo API connection
"""

import requests
import json
import os

def test_connection():
    """Test OpenAlgo API connection"""
    
    # Load API key from environment file
    api_key = os.getenv('OPENALGO_API_KEY', '703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b')
    base_url = "http://127.0.0.1:5000/api/v1"
    
    print("Testing OpenAlgo API connection...")
    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:10]}...")
    print()
    
    # Test 1: Ping endpoint
    print("1. Testing ping endpoint...")
    try:
        response = requests.post(
            f"{base_url}/ping",
            json={'apikey': api_key},
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("   ✅ Ping successful!")
            else:
                print(f"   ❌ Ping failed: {data}")
        else:
            print(f"   ❌ Ping failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Ping error: {e}")
    
    print()
    
    # Test 2: Quotes endpoint
    print("2. Testing quotes endpoint...")
    try:
        response = requests.post(
            f"{base_url}/quotes",
            json={
                'apikey': api_key,
                'exchange': 'NSE',
                'symbol': 'SBIN'
            },
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("   ✅ Quotes successful!")
                print(f"   LTP: {data['data']['ltp']}")
            else:
                print(f"   ❌ Quotes failed: {data}")
        else:
            print(f"   ❌ Quotes failed: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Quotes error: {e}")
    
    print()
    
    # Test 3: Check if we're getting HTML instead of JSON
    print("3. Checking response headers...")
    try:
        response = requests.post(
            f"{base_url}/ping",
            json={'apikey': api_key},
            timeout=10
        )
        print(f"   Content-Type: {response.headers.get('content-type', 'Not found')}")
        print(f"   Response starts with: {response.text[:100]}")
        
        if 'text/html' in response.headers.get('content-type', ''):
            print("   ⚠️  Getting HTML response - this might be a login page!")
        elif 'application/json' in response.headers.get('content-type', ''):
            print("   ✅ Getting JSON response - API is working!")
            
    except Exception as e:
        print(f"   ❌ Header check error: {e}")

if __name__ == "__main__":
    test_connection()