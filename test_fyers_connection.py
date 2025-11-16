#!/usr/bin/env python3
"""
Test Fyers Connection in OpenAlgo

This script tests the Fyers broker connection to identify the Status 500 error.
"""

import sys
import os
from pathlib import Path

# Add the openalgo directory to Python path
openalgo_path = Path(__file__).parent / "openalgo"
sys.path.insert(0, str(openalgo_path))

def test_fyers_connection():
    """Test Fyers broker connection."""
    try:
        from database.user_db import find_user_by_username
        from database.auth_db import get_auth_token_broker
        from broker.fyers.api.auth_api import authenticate_fyers
        from utils.logging import get_logger

        logger = get_logger(__name__)

        # Get admin user
        admin_user = find_user_by_username()
        if not admin_user:
            print("Admin user not found!")
            return

        print(f"Testing Fyers connection for user: {admin_user.username}")

        # Get auth token and broker
        auth_token, broker = get_auth_token_broker("420ff93cf719bdcd81f5f33db189f9e9b08fa25e76c03fcfcd89762c0868efbd")

        if not auth_token:
            print("❌ No auth token found for API key")
            return

        print(f"✓ Found auth token for broker: {broker}")
        print(f"Auth token: {auth_token[:50]}...")

        # Test Fyers authentication
        print("\nTesting Fyers authentication...")

        try:
            # Try to authenticate with Fyers
            fyers_client = authenticate_fyers(auth_token)

            if fyers_client:
                print("✓ Fyers authentication successful!")

                # Test getting profile
                print("\nTesting Fyers profile...")
                profile = fyers_client.get_profile()

                if profile.get('s') == 'ok':
                    print("✓ Fyers profile retrieved successfully!")
                    print(f"User: {profile.get('data', {}).get('name', 'Unknown')}")
                else:
                    print(f"❌ Fyers profile failed: {profile.get('message', 'Unknown error')}")

                # Test getting funds
                print("\nTesting Fyers funds...")
                funds = fyers_client.funds()

                if funds.get('s') == 'ok':
                    print("✓ Fyers funds retrieved successfully!")
                    fund_data = funds.get('data', {})
                    if fund_data:
                        print(f"Available balance: {fund_data.get('fund_limit', [{}])[0].get('equityAmount', 'N/A')}")
                else:
                    print(f"❌ Fyers funds failed: {funds.get('message', 'Unknown error')}")

            else:
                print("❌ Fyers authentication failed - no client returned")

        except Exception as e:
            print(f"❌ Fyers authentication error: {e}")
            logger.error(f"Fyers authentication error: {e}", exc_info=True)

    except Exception as e:
        print(f"Error testing Fyers connection: {e}")
        import traceback
        traceback.print_exc()

def test_api_endpoints():
    """Test various API endpoints to identify which ones are working."""
    import requests

    api_key = "420ff93cf719bdcd81f5f33db189f9e9b08fa25e76c03fcfcd89762c0868efbd"

    endpoints = [
        ("ping", "POST", {}),
        ("funds", "POST", {}),
        ("orderbook", "POST", {}),
        ("positions", "POST", {}),
        ("holdings", "POST", {}),
    ]

    print("\n" + "="*50)
    print("Testing OpenAlgo API Endpoints")
    print("="*50)

    for endpoint, method, data in endpoints:
        print(f"\nTesting {endpoint}...")

        # Add API key to data
        test_data = {**data, "apikey": api_key}

        try:
            if method == "POST":
                response = requests.post(
                    f"http://localhost:5000/api/v1/{endpoint}",
                    json=test_data
                )
            else:
                response = requests.get(
                    f"http://localhost:5000/api/v1/{endpoint}",
                    params=test_data
                )

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    print(f"✓ Success: {endpoint}")
                    if 'data' in result:
                        data_len = len(str(result['data']))
                        print(f"  Data size: {data_len} characters")
                else:
                    print(f"❌ API Error: {result.get('message', 'Unknown error')}")
            else:
                print(f"❌ HTTP Error: {response.text[:200]}")

        except Exception as e:
            print(f"❌ Request Error: {e}")

def main():
    """Main function."""
    print("OpenAlgo Fyers Connection Test")
    print("=" * 40)

    test_fyers_connection()
    test_api_endpoints()

if __name__ == "__main__":
    main()
