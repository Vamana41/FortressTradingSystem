#!/usr/bin/env python3
"""
Manual OpenAlgo API Key Creation Script

This script manually creates an API key for the admin user in OpenAlgo.
"""

import sys
import os
from pathlib import Path
import secrets

# Add the openalgo directory to Python path
openalgo_path = Path(__file__).parent / "openalgo"
sys.path.insert(0, str(openalgo_path))

def create_api_key_manually():
    """Create API key manually using the database functions."""
    try:
        from database.auth_db import upsert_api_key, get_api_key_for_tradingview
        from database.user_db import find_user_by_username

        # Check if admin user exists
        admin_user = find_user_by_username()
        if not admin_user:
            print("Admin user not found!")
            return None

        print(f"Found admin user: {admin_user.username}")

        # Generate a new API key
        api_key = secrets.token_hex(32)
        print(f"Generated new API key: {api_key}")

        # Store the API key
        key_id = upsert_api_key(admin_user.username, api_key)

        if key_id:
            print(f"API key stored successfully with key_id: {key_id}")

            # Verify it was stored
            stored_key = get_api_key_for_tradingview(admin_user.username)
            if stored_key == api_key:
                print("✓ API key verified in database")
                return api_key
            else:
                print(f"✗ API key verification failed. Stored: {stored_key}, Expected: {api_key}")
                return None
        else:
            print("Failed to store API key")
            return None

    except Exception as e:
        print(f"Error creating API key: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_api_key(api_key):
    """Test the API key with a simple ping request."""
    try:
        import requests

        print(f"\nTesting API key: {api_key}")

        response = requests.post(
            "http://localhost:5000/api/v1/ping",
            json={"apikey": api_key}
        )

        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                print(f"✓ API key is valid! Server responded: {result.get('data', {})}")
                return True
            else:
                print(f"✗ API key test failed: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"✗ API key test failed with HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ Error testing API key: {e}")
        return False

def main():
    """Main function."""
    print("Manual OpenAlgo API Key Creation")
    print("=" * 40)

    # Create API key manually
    api_key = create_api_key_manually()

    if api_key:
        print(f"\nSuccessfully created API key: {api_key}")

        # Test the API key
        if test_api_key(api_key):
            print(f"\nPlease update your .env file with:")
            print(f"OPENALGO_API_KEY={api_key}")

            # Also update the secure API key manager
            sys.path.insert(0, str(Path(__file__).parent / "fortress" / "src"))
            from fortress.utils.api_key_manager import SecureAPIKeyManager

            manager = SecureAPIKeyManager()
            manager.store_api_key("openalgo", api_key)
            print(f"\nAPI key also stored securely in encrypted storage ✓")

            return True
        else:
            print("API key creation succeeded but validation failed")
            return False
    else:
        print("Failed to create API key")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
