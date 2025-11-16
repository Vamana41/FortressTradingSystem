#!/usr/bin/env python3
"""
Comprehensive test script for OpenAlgo API endpoints with proper request formats.
"""

import os
import sys
import requests
import json
from urllib.parse import urljoin

# Add the fortress directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fortress', 'src'))

from fortress.utils.api_key_manager import SecureAPIKeyManager

def get_api_key():
    """Get the API key from secure storage or environment."""
    api_key_manager = SecureAPIKeyManager()
    api_key = api_key_manager.get_api_key("openalgo")

    if not api_key:
        # Fallback to environment variable
        api_key = os.getenv("OPENALGO_API_KEY", "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0")

    return api_key

def test_ping_endpoint():
    """Test the ping endpoint with POST request."""
    base_url = "http://localhost:5000/api/v1"
    api_key = get_api_key()

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Ping endpoint requires POST with apikey in body
    data = {
        "apikey": api_key
    }

    try:
        response = requests.post(f"{base_url}/ping", headers=headers, json=data, timeout=10)

        print(f"🔍 Testing /ping endpoint:")
        print(f"  Method: POST")
        print(f"  Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                return True
            except:
                print(f"  ✅ Response: {response.text[:200]}")
                return True
        else:
            print(f"  ❌ Error: {response.text[:200]}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"  🚨 Connection error: {str(e)}")
        return False

def test_quotes_endpoint():
    """Test the quotes endpoint with POST request."""
    base_url = "http://localhost:5000/api/v1"
    api_key = get_api_key()

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Quotes endpoint requires POST with symbol and exchange
    data = {
        "apikey": api_key,
        "symbol": "NIFTY",
        "exchange": "NSE"
    }

    try:
        response = requests.post(f"{base_url}/quotes", headers=headers, json=data, timeout=10)

        print(f"\n🔍 Testing /quotes endpoint:")
        print(f"  Method: POST")
        print(f"  Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                return True
            except:
                print(f"  ✅ Response: {response.text[:200]}")
                return True
        else:
            print(f"  ❌ Error: {response.text[:200]}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"  🚨 Connection error: {str(e)}")
        return False

def test_funds_endpoint():
    """Test the funds endpoint."""
    base_url = "http://localhost:5000/api/v1"
    api_key = get_api_key()

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Funds endpoint might be GET or POST
    try:
        # Try GET first
        response = requests.get(f"{base_url}/funds", headers=headers, timeout=10)

        print(f"\n🔍 Testing /funds endpoint:")
        print(f"  Method: GET")
        print(f"  Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                return True
            except:
                print(f"  ✅ Response: {response.text[:200]}")
                return True
        else:
            # Try POST with apikey
            data = {"apikey": api_key}
            response = requests.post(f"{base_url}/funds", headers=headers, json=data, timeout=10)
            print(f"  Method: POST")
            print(f"  Status Code: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                    return True
                except:
                    print(f"  ✅ Response: {response.text[:200]}")
                    return True
            else:
                print(f"  ❌ Error: {response.text[:200]}")
                return False

    except requests.exceptions.RequestException as e:
        print(f"  🚨 Connection error: {str(e)}")
        return False

def test_positionbook_endpoint():
    """Test the positionbook endpoint."""
    base_url = "http://localhost:5000/api/v1"
    api_key = get_api_key()

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Positionbook endpoint might be GET or POST
    try:
        # Try GET first
        response = requests.get(f"{base_url}/positionbook", headers=headers, timeout=10)

        print(f"\n🔍 Testing /positionbook endpoint:")
        print(f"  Method: GET")
        print(f"  Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                return True
            except:
                print(f"  ✅ Response: {response.text[:200]}")
                return True
        else:
            # Try POST with apikey
            data = {"apikey": api_key}
            response = requests.post(f"{base_url}/positionbook", headers=headers, json=data, timeout=10)
            print(f"  Method: POST")
            print(f"  Status Code: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                    return True
                except:
                    print(f"  ✅ Response: {response.text[:200]}")
                    return True
            else:
                print(f"  ❌ Error: {response.text[:200]}")
                return False

    except requests.exceptions.RequestException as e:
        print(f"  🚨 Connection error: {str(e)}")
        return False

def test_symbol_endpoint():
    """Test the symbol endpoint."""
    base_url = "http://localhost:5000/api/v1"
    api_key = get_api_key()

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Symbol endpoint might be GET or POST
    try:
        # Try GET first
        response = requests.get(f"{base_url}/symbol", headers=headers, timeout=10)

        print(f"\n🔍 Testing /symbol endpoint:")
        print(f"  Method: GET")
        print(f"  Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                return True
            except:
                print(f"  ✅ Response: {response.text[:200]}")
                return True
        else:
            # Try POST with apikey and symbol
            data = {"apikey": api_key, "symbol": "NIFTY"}
            response = requests.post(f"{base_url}/symbol", headers=headers, json=data, timeout=10)
            print(f"  Method: POST")
            print(f"  Status Code: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                    return True
                except:
                    print(f"  ✅ Response: {response.text[:200]}")
                    return True
            else:
                print(f"  ❌ Error: {response.text[:200]}")
                return False

    except requests.exceptions.RequestException as e:
        print(f"  🚨 Connection error: {str(e)}")
        return False

def test_intervals_endpoint():
    """Test the intervals endpoint."""
    base_url = "http://localhost:5000/api/v1"
    api_key = get_api_key()

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Intervals endpoint might be GET or POST
    try:
        # Try GET first
        response = requests.get(f"{base_url}/intervals", headers=headers, timeout=10)

        print(f"\n🔍 Testing /intervals endpoint:")
        print(f"  Method: GET")
        print(f"  Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                result = response.json()
                print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                return True
            except:
                print(f"  ✅ Response: {response.text[:200]}")
                return True
        else:
            # Try POST with apikey
            data = {"apikey": api_key}
            response = requests.post(f"{base_url}/intervals", headers=headers, json=data, timeout=10)
            print(f"  Method: POST")
            print(f"  Status Code: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"  ✅ Response: {json.dumps(result, indent=2)}")
                    return True
                except:
                    print(f"  ✅ Response: {response.text[:200]}")
                    return True
            else:
                print(f"  ❌ Error: {response.text[:200]}")
                return False

    except requests.exceptions.RequestException as e:
        print(f"  🚨 Connection error: {str(e)}")
        return False

def main():
    """Main function."""
    print("🧪 Comprehensive OpenAlgo API Testing")
    print("=" * 60)

    api_key = get_api_key()
    print(f"Using API Key: {api_key[:10]}...")
    print()

    # Test all endpoints
    results = []

    results.append(("Ping", test_ping_endpoint()))
    results.append(("Quotes", test_quotes_endpoint()))
    results.append(("Funds", test_funds_endpoint()))
    results.append(("Positionbook", test_positionbook_endpoint()))
    results.append(("Symbol", test_symbol_endpoint()))
    results.append(("Intervals", test_intervals_endpoint()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")

    working = 0
    for endpoint, success in results:
        status = "✅ Working" if success else "❌ Failed"
        print(f"  {endpoint}: {status}")
        if success:
            working += 1

    print(f"\nWorking endpoints: {working}/{len(results)}")

    if working == len(results):
        print("🎉 All endpoints are working!")
    else:
        print("⚠️  Some endpoints need attention.")

if __name__ == "__main__":
    main()
