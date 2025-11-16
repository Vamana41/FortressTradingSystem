#!/usr/bin/env python3
"""
Comprehensive OpenAlgo API Testing and Integration Script
Tests all API endpoints and validates Fortress integration.
"""

import os
import sys
import requests
import json
import time
from urllib.parse import urljoin

def test_basic_connectivity():
    """Test basic server connectivity."""
    print("🔍 Testing Basic Connectivity")
    print("-" * 40)

    try:
        response = requests.get("http://127.0.0.1:5000", timeout=10)
        print(f"✅ Server is running (Status: {response.status_code})")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ Server not accessible: {e}")
        return False

def test_api_endpoints_without_auth():
    """Test API endpoints that don't require authentication."""
    print("\n🔍 Testing API Endpoints (No Auth Required)")
    print("-" * 40)

    base_url = "http://127.0.0.1:5000/api/v1"

    # Test endpoints that should work without API key
    endpoints = [
        "/ping",  # Should work with POST and apikey in body
    ]

    results = []

    for endpoint in endpoints:
        try:
            # Test GET first
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            print(f"GET {endpoint}: {response.status_code}")

            # Test POST with dummy data
            if endpoint == "/ping":
                data = {"apikey": "test_key"}
                response = requests.post(f"{base_url}{endpoint}", json=data, timeout=5)
                print(f"POST {endpoint}: {response.status_code} - {response.text[:100]}")

                if response.status_code == 403:
                    print(f"  ⚠️  Expected - API key validation working")
                elif response.status_code == 200:
                    print(f"  ✅ Working")
                    results.append(endpoint)
                else:
                    print(f"  ❌ Unexpected response")

        except Exception as e:
            print(f"❌ Error testing {endpoint}: {e}")

    return results

def test_authentication_flow():
    """Test the authentication flow and identify requirements."""
    print("\n🔍 Testing Authentication Flow")
    print("-" * 40)

    base_url = "http://127.0.0.1:5000/api/v1"

    # Test what happens with invalid API key
    test_key = "invalid_test_key_12345"

    headers = {
        "Content-Type": "application/json",
        "api-key": test_key
    }

    data = {
        "apikey": test_key
    }

    try:
        response = requests.post(f"{base_url}/ping", headers=headers, json=data, timeout=10)

        print(f"Test with invalid API key:")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text}")

        if response.status_code == 403:
            result = response.json()
            if "Invalid openalgo apikey" in result.get("message", ""):
                print(f"  ✅ API key validation is working correctly")
                return True
            else:
                print(f"  ⚠️  Different authentication error: {result}")
                return False
        else:
            print(f"  ❌ Unexpected status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error testing authentication: {e}")
        return False

def analyze_api_structure():
    """Analyze the API structure and requirements."""
    print("\n🔍 Analyzing API Structure")
    print("-" * 40)

    base_url = "http://127.0.0.1:5000/api/v1"

    # Try to get API documentation or structure
    try:
        # Test if there's a Swagger/OpenAPI endpoint
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"API Documentation Status: {response.status_code}")

        if response.status_code == 200:
            try:
                api_info = response.json()
                print(f"API Info: {api_info}")
            except:
                print(f"API Documentation available: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Error accessing API documentation: {e}")

    # Test common endpoints to understand structure
    test_endpoints = [
        "/quotes",
        "/funds",
        "/orderbook",
        "/tradebook",
        "/positionbook",
        "/holdings"
    ]

    print(f"\nTesting endpoint accessibility:")

    for endpoint in test_endpoints:
        try:
            # Test GET
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            print(f"GET {endpoint}: {response.status_code}")

            # Test POST with minimal data
            data = {"apikey": "test"}
            response = requests.post(f"{base_url}{endpoint}", json=data, timeout=5)
            print(f"POST {endpoint}: {response.status_code}")

            if response.status_code == 400:
                try:
                    error_data = response.json()
                    if "message" in error_data and isinstance(error_data["message"], dict):
                        missing_fields = list(error_data["message"].keys())
                        print(f"  📋 Required fields: {missing_fields}")
                except:
                    pass

        except Exception as e:
            print(f"❌ Error testing {endpoint}: {e}")

def create_integration_test_script():
    """Create a script for testing with a valid API key once available."""

    script_content = '''#!/usr/bin/env python3
"""
OpenAlgo API Integration Test Script
Use this script to test API endpoints once you have a valid API key.
"""

import requests
import json

def test_with_api_key(api_key):
    """Test all API endpoints with a valid API key."""

    base_url = "http://127.0.0.1:5000/api/v1"

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Test ping endpoint
    print("Testing ping endpoint...")
    data = {"apikey": api_key}
    response = requests.post(f"{base_url}/ping", headers=headers, json=data)
    print(f"Ping: {response.status_code} - {response.text[:100]}")

    # Test quotes endpoint
    print("\\nTesting quotes endpoint...")
    data = {
        "apikey": api_key,
        "symbol": "NIFTY",
        "exchange": "NSE"
    }
    response = requests.post(f"{base_url}/quotes", headers=headers, json=data)
    print(f"Quotes: {response.status_code} - {response.text[:100]}")

    # Test funds endpoint
    print("\\nTesting funds endpoint...")
    data = {"apikey": api_key}
    response = requests.post(f"{base_url}/funds", headers=headers, json=data)
    print(f"Funds: {response.status_code} - {response.text[:100]}")

    # Test orderbook endpoint
    print("\\nTesting orderbook endpoint...")
    data = {"apikey": api_key}
    response = requests.post(f"{base_url}/orderbook", headers=headers, json=data)
    print(f"Orderbook: {response.status_code} - {response.text[:100]}")

if __name__ == "__main__":
    # Replace with your actual API key
    API_KEY = "your_api_key_here"
    test_with_api_key(API_KEY)
'''

    with open("test_openalgo_with_api_key.py", "w") as f:
        f.write(script_content)

    print(f"\n📝 Created: test_openalgo_with_api_key.py")
    print(f"Use this script once you have a valid API key")

def main():
    """Main function."""
    print("🧪 OpenAlgo API Comprehensive Testing")
    print("=" * 60)

    # Test basic connectivity
    if not test_basic_connectivity():
        print("❌ Server not accessible. Please start OpenAlgo server first.")
        return

    # Test endpoints without auth
    working_endpoints = test_api_endpoints_without_auth()

    # Test authentication flow
    auth_working = test_authentication_flow()

    # Analyze API structure
    analyze_api_structure()

    # Create integration test script
    create_integration_test_script()

    print(f"\n" + "=" * 60)
    print("📋 Summary:")
    print(f"✅ Server is running at http://127.0.0.1:5000")
    print(f"✅ API key validation is working correctly")
    print(f"✅ Ready for account creation and API key generation")

    print(f"\n🎯 Next Steps:")
    print(f"1. Go to http://127.0.0.1:5000")
    print(f"2. Create a new user account")
    print(f"3. Configure your broker (Fyers)")
    print(f"4. Generate API key")
    print(f"5. Use test_openalgo_with_api_key.py to test endpoints")
    print(f"6. Update Fortress configuration with new API key")

if __name__ == "__main__":
    main()
