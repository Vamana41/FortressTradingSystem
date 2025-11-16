#!/usr/bin/env python3
"""
Script to get OpenAlgo API key from web interface and test integration.
This script will:
1. Check if OpenAlgo server is running
2. Guide user to get API key from web interface
3. Test the API key with OpenAlgo endpoints
4. Store the API key securely for Fortress to use
"""

import requests
import json
import sys
import os
from urllib.parse import urljoin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fortress', 'src'))
from fortress.utils.api_key_manager import SecureAPIKeyManager

def check_server_status():
    """Check if OpenAlgo server is running"""
    try:
        response = requests.get('http://localhost:5000/', timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def test_api_key(api_key):
    """Test the API key with OpenAlgo ping endpoint"""
    url = 'http://localhost:5000/api/v1/ping/'
    headers = {'Content-Type': 'application/json'}
    data = {'apikey': api_key}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        return response.status_code, response.json()
    except requests.exceptions.RequestException as e:
        return None, {'error': str(e)}

def main():
    print("OpenAlgo API Key Integration Tool")
    print("=" * 50)

    # Check if OpenAlgo server is running
    print("Checking if OpenAlgo server is running...")
    if not check_server_status():
        print("❌ OpenAlgo server is not running on localhost:5000")
        print("Please start the OpenAlgo server first by running: python openalgo/app.py")
        return 1

    print("✅ OpenAlgo server is running")

    # Get API key from user
    print("\nTo get your OpenAlgo API key:")
    print("1. Open your browser and go to: http://localhost:5000")
    print("2. Log in with your OpenAlgo credentials")
    print("3. Navigate to the API Key section in the dashboard")
    print("4. Copy your API key")
    print("5. Paste it here:")

    api_key = input("\nEnter your OpenAlgo API key: ").strip()

    if not api_key:
        print("❌ No API key provided")
        return 1

    # Test the API key
    print("\nTesting API key...")
    status_code, response = test_api_key(api_key)

    if status_code == 200:
        print("✅ API key is valid!")
        print(f"Response: {response}")

        # Store the API key securely
        print("\nStoring API key securely...")
        try:
            api_key_manager = SecureAPIKeyManager()
            api_key_manager.store_api_key("openalgo", api_key)
            print("✅ API key stored securely for Fortress Trading System")

            # Test other API endpoints
            print("\nTesting other OpenAlgo API endpoints...")

            # Test funds endpoint
            funds_url = 'http://localhost:5000/api/v1/funds/'
            funds_response = requests.post(funds_url, headers={'Content-Type': 'application/json'}, json={'apikey': api_key})
            print(f"Funds endpoint: {'✅' if funds_response.status_code == 200 else '❌'} {funds_response.status_code}")

            # Test orderbook endpoint
            orderbook_url = 'http://localhost:5000/api/v1/orderbook/'
            orderbook_response = requests.post(orderbook_url, headers={'Content-Type': 'application/json'}, json={'apikey': api_key})
            print(f"Orderbook endpoint: {'✅' if orderbook_response.status_code == 200 else '❌'} {orderbook_response.status_code}")

            # Test positionbook endpoint
            positionbook_url = 'http://localhost:5000/api/v1/positionbook/'
            positionbook_response = requests.post(positionbook_url, headers={'Content-Type': 'application/json'}, json={'apikey': api_key})
            print(f"Positionbook endpoint: {'✅' if positionbook_response.status_code == 200 else '❌'} {positionbook_response.status_code}")

            print("\n🎉 OpenAlgo integration setup complete!")
            print("Your Fortress Trading System can now use the OpenAlgo API key.")

        except Exception as e:
            print(f"❌ Error storing API key: {e}")
            return 1

    else:
        print(f"❌ API key test failed")
        print(f"Status Code: {status_code}")
        print(f"Response: {response}")

        if response.get('status') == 'error' and 'Invalid openalgo apikey' in response.get('message', ''):
            print("\nThe API key appears to be invalid. Please:")
            print("1. Double-check that you copied the correct API key from the dashboard")
            print("2. Make sure you're logged into OpenAlgo with the correct user account")
            print("3. Try regenerating the API key if necessary")

        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
