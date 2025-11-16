#!/usr/bin/env python3
"""
OpenAlgo API Key Helper
This script helps you get the fresh API key from OpenAlgo dashboard
"""

import requests
import json
import time
import os
from pathlib import Path

def get_api_key_guide():
    """Guide user to get API key from OpenAlgo dashboard"""

    print("=" * 80)
    print("OPENALGO API KEY HELPER")
    print("=" * 80)
    print()
    print("OpenAlgo is now running on http://127.0.0.1:5000")
    print()
    print("STEPS TO GET YOUR FRESH API KEY:")
    print("1. Open your web browser")
    print("2. Go to: http://127.0.0.1:5000")
    print("3. Click 'Login' button")
    print("4. Enter your OpenAlgo credentials")
    print("5. After successful login, you should see the dashboard")
    print("6. Look for 'API Key' section in the dashboard")
    print("7. Copy the API key (it changes daily after restart)")
    print()
    print("ALTERNATIVE METHOD:")
    print("If you can't find the API key in dashboard, try:")
    print("http://127.0.0.1:5000/apikey")
    print()

    api_key = input("Enter your fresh API key: ").strip()

    if not api_key:
        print("❌ No API key provided!")
        return None

    # Test the API key
    print(f"\nTesting API key: {api_key[:10]}...")

    try:
        # Test with ping endpoint using correct API v1 path
        response = requests.post(
            "http://127.0.0.1:5000/api/v1/ping",
            json={'apikey': api_key},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("✅ API key is VALID!")

                # Save to configuration file
                config_path = Path("openalgo_symbol_injector.env")

                # Read current config
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        lines = f.readlines()
                else:
                    lines = []

                # Update API key line
                api_key_found = False
                new_lines = []
                for line in lines:
                    if line.startswith('OPENALGO_API_KEY='):
                        new_lines.append(f'OPENALGO_API_KEY={api_key}\n')
                        api_key_found = True
                    else:
                        new_lines.append(line)

                # If API key line not found, add it
                if not api_key_found:
                    new_lines.append(f'OPENALGO_API_KEY={api_key}\n')

                # Write updated config
                with open(config_path, 'w') as f:
                    f.writelines(new_lines)

                print(f"✅ API key saved to {config_path}")
                print("✅ You can now run the automatic symbol injector!")

                return api_key
            else:
                print(f"❌ API key test failed: {data.get('message', 'Unknown error')}")
                return None
        else:
            print(f"❌ API key test failed: HTTP {response.status_code}")
            return None

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to OpenAlgo. Make sure it's running on http://127.0.0.1:5000")
        return None
    except Exception as e:
        print(f"❌ Error testing API key: {e}")
        return None

def main():
    """Main function"""
    print("OpenAlgo API Key Helper")
    print("This will help you get and validate your fresh API key")
    print()

    # Check if OpenAlgo is running
    try:
        response = requests.get("http://127.0.0.1:5000", timeout=5)
        if response.status_code == 200:
            print("✅ OpenAlgo is running on http://127.0.0.1:5000")
        else:
            print("❌ OpenAlgo is not responding properly")
            return
    except:
        print("❌ Cannot connect to OpenAlgo. Make sure it's running first.")
        print("Run: cd openalgo && python app.py")
        return

    api_key = get_api_key_guide()

    if api_key:
        print("\n" + "=" * 80)
        print("SUCCESS! You can now run the automatic symbol injector:")
        print("python openalgo_automatic_symbols_injector.py")
        print("=" * 80)
    else:
        print("\n❌ Failed to get valid API key. Please try again.")

if __name__ == "__main__":
    main()
