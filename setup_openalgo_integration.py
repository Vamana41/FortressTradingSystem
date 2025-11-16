#!/usr/bin/env python3
"""
Complete OpenAlgo Integration Setup Script
This script will help set up the entire integration once you have your API key.
"""

import os
import sys
import requests
import json
from urllib.parse import urljoin

def update_fortress_env(api_key):
    """Update the Fortress .env file with the new API key."""

    env_file = ".env"

    if not os.path.exists(env_file):
        print(f"❌ .env file not found at {env_file}")
        return False

    try:
        # Read current .env file
        with open(env_file, 'r') as f:
            lines = f.readlines()

        # Update or add OPENALGO_API_KEY
        updated = False
        new_lines = []

        for line in lines:
            if line.startswith('OPENALGO_API_KEY='):
                new_lines.append(f'OPENALGO_API_KEY={api_key}\n')
                updated = True
            else:
                new_lines.append(line)

        # If not found, add it
        if not updated:
            new_lines.append(f'OPENALGO_API_KEY={api_key}\n')

        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(new_lines)

        print(f"✅ Updated {env_file} with new API key")
        return True

    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False

def test_api_key_integration(api_key):
    """Test the API key with all major endpoints."""

    print(f"\n🧪 Testing API Key Integration")
    print("-" * 40)

    base_url = "http://127.0.0.1:5000/api/v1"

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    # Test endpoints
    tests = [
        {
            "name": "Ping",
            "endpoint": "/ping",
            "method": "POST",
            "data": {"apikey": api_key}
        },
        {
            "name": "Quotes",
            "endpoint": "/quotes",
            "method": "POST",
            "data": {"apikey": api_key, "symbol": "NIFTY", "exchange": "NSE"}
        },
        {
            "name": "Funds",
            "endpoint": "/funds",
            "method": "POST",
            "data": {"apikey": api_key}
        },
        {
            "name": "Orderbook",
            "endpoint": "/orderbook",
            "method": "POST",
            "data": {"apikey": api_key}
        },
        {
            "name": "Tradebook",
            "endpoint": "/tradebook",
            "method": "POST",
            "data": {"apikey": api_key}
        }
    ]

    results = {}

    for test in tests:
        try:
            print(f"Testing {test['name']}...")

            if test["method"] == "POST":
                response = requests.post(
                    f"{base_url}{test['endpoint']}",
                    headers=headers,
                    json=test["data"],
                    timeout=10
                )
            else:
                response = requests.get(
                    f"{base_url}{test['endpoint']}",
                    headers=headers,
                    timeout=10
                )

            print(f"  Status: {response.status_code}")

            if response.status_code == 200:
                print(f"  ✅ Working")
                results[test["name"]] = True
            elif response.status_code == 403:
                print(f"  ❌ Authentication failed")
                results[test["name"]] = False
            else:
                print(f"  ⚠️  Status {response.status_code}: {response.text[:100]}")
                results[test["name"]] = False

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[test["name"]] = False

    return results

def create_integration_summary(api_key, test_results):
    """Create a summary of the integration."""

    summary_file = "openalgo_integration_summary.txt"

    with open(summary_file, "w") as f:
        f.write("OpenAlgo Integration Summary\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"API Key: {api_key[:10]}...\n\n")
        f.write("Test Results:\n")

        for test_name, result in test_results.items():
            status = "✅ Working" if result else "❌ Failed"
            f.write(f"  {test_name}: {status}\n")

        f.write("\nConfiguration:\n")
        f.write(f"  Base URL: http://127.0.0.1:5000/api/v1\n")
        f.write(f"  API Key Location: .env file\n")
        f.write(f"  Fortress Integration: Ready\n\n")

        f.write("Next Steps:\n")
        f.write("1. Test with real trading symbols\n")
        f.write("2. Configure AmiBroker integration\n")
        f.write("3. Test complete workflow\n")
        f.write("4. Monitor for any issues\n")

    print(f"\n📝 Created integration summary: {summary_file}")

def setup_fortress_integration(api_key):
    """Complete Fortress integration setup."""

    print("🚀 Setting up Fortress Integration")
    print("=" * 40)

    # 1. Update .env file
    if not update_fortress_env(api_key):
        return False

    # 2. Test API key integration
    test_results = test_api_key_integration(api_key)

    # 3. Create summary
    create_integration_summary(api_key, test_results)

    # 4. Summary
    print(f"\n📊 Integration Summary:")
    working_endpoints = sum(1 for result in test_results.values() if result)
    total_endpoints = len(test_results)

    print(f"Working endpoints: {working_endpoints}/{total_endpoints}")

    if working_endpoints == total_endpoints:
        print("🎉 All endpoints working! Integration complete.")
    else:
        print("⚠️  Some endpoints not working. Check configuration.")

    return working_endpoints == total_endpoints

def main():
    """Main function."""
    print("🔧 OpenAlgo Integration Setup")
    print("=" * 50)

    if len(sys.argv) != 2:
        print("Usage: python setup_openalgo_integration.py <API_KEY>")
        print("\nTo get your API key:")
        print("1. Go to http://127.0.0.1:5000")
        print("2. Create account and login")
        print("3. Configure broker credentials")
        print("4. Generate API key in dashboard")
        return

    api_key = sys.argv[1]

    print(f"Setting up integration with API key: {api_key[:10]}...")

    success = setup_fortress_integration(api_key)

    if success:
        print(f"\n✅ Integration setup complete!")
        print(f"Fortress is now ready to use with OpenAlgo.")
    else:
        print(f"\n❌ Integration setup failed.")
        print(f"Please check the summary file for details.")

if __name__ == "__main__":
    main()
