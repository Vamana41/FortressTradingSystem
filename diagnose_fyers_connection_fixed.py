#!/usr/bin/env python3
"""
Diagnose Fyers connection issues in OpenAlgo with proper API key
"""

import requests
import json
import sys

def diagnose_fyers_connection():
    """Diagnose Fyers connection issues with proper API key"""
    
    base_url = "http://localhost:5000"
    api_key = "703177ad6119e28828504d17d87197cb276dc557c68f7c7c53ac5c88e8d3fb6b"
    
    print("🔍 Diagnosing Fyers Connection Issues with API Key")
    print("=" * 60)
    
    # Test basic server connectivity
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"✅ Server Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Server Error: {e}")
        return
    
    # Test broker status endpoint
    try:
        response = requests.post(
            f"{base_url}/api/v1/broker_status",
            json={"apikey": api_key},
            timeout=10
        )
        print(f"📊 Broker Status Response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"📈 Broker Status: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Broker Status Error: {response.text}")
    except Exception as e:
        print(f"❌ Broker Status Error: {e}")
    
    # Test Fyers-specific endpoints
    endpoints = [
        "/api/v1/funds",
        "/api/v1/positionbook", 
        "/api/v1/orderbook",
        "/api/v1/holdings"
    ]
    
    print(f"\n🔍 Testing Fyers-specific Endpoints with API Key:")
    for endpoint in endpoints:
        try:
            response = requests.post(
                f"{base_url}{endpoint}",
                json={"apikey": api_key},
                timeout=10
            )
            print(f"  {endpoint}: {response.status_code}")
            if response.status_code != 200:
                print(f"    Error: {response.text[:200]}")
            else:
                try:
                    data = response.json()
                    print(f"    Success: {json.dumps(data, indent=2)[:150]}...")
                except:
                    print(f"    Success: {response.text[:100]}...")
        except Exception as e:
            print(f"  {endpoint}: Error - {e}")
    
    # Check if we can get more detailed error info
    print(f"\n🔍 Checking for Detailed Error Messages:")
    try:
        # Try to get logs or error details
        response = requests.post(
            f"{base_url}/api/v1/funds",
            json={"apikey": api_key},
            timeout=10
        )
        if response.status_code == 500:
            print(f"💥 Status 500 Details: {response.text}")
            try:
                error_data = response.json()
                if 'message' in error_data:
                    print(f"📝 Error Message: {error_data['message']}")
                if 'error' in error_data:
                    print(f"🔧 Technical Error: {error_data['error']}")
            except:
                pass
        elif response.status_code == 200:
            print(f"✅ Fyers connection is working!")
            data = response.json()
            print(f"💰 Funds Data: {json.dumps(data, indent=2)}")
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Could not get detailed error: {e}")

if __name__ == "__main__":
    diagnose_fyers_connection()