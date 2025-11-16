#!/usr/bin/env python3
"""
Script to extract the Reeshoo user's API key for Fortress integration.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import ApiKeys, decrypt_token
from utils.logging import get_logger

logger = get_logger(__name__)

def get_reeshoo_api_key():
    """Get the API key for Reeshoo user."""

    print("🔑 Extracting Reeshoo API Key")
    print("=" * 40)

    try:
        # Find API key for Reeshoo user
        api_key_obj = ApiKeys.query.filter_by(user_id='Reeshoo').first()

        if api_key_obj:
            print(f"✅ Found API key for Reeshoo")
            print(f"  Created: {api_key_obj.created_at}")
            print(f"  Has Hash: {'Yes' if api_key_obj.api_key_hash else 'No'}")
            print(f"  Has Encrypted: {'Yes' if api_key_obj.api_key_encrypted else 'No'}")

            if api_key_obj.api_key_encrypted:
                # Decrypt the API key
                decrypted_key = decrypt_token(api_key_obj.api_key_encrypted)
                print(f"  Decrypted API Key: {decrypted_key}")
                return decrypted_key
            else:
                print("❌ No encrypted API key found")
                return None
        else:
            print("❌ No API key found for Reeshoo user")
            return None

    except Exception as e:
        print(f"❌ Error extracting API key: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_api_key(api_key):
    """Test if the API key works with OpenAlgo API."""

    import requests

    print(f"\n🧪 Testing API Key with OpenAlgo API")
    print("=" * 40)

    if not api_key:
        print("❌ No API key to test")
        return False

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    data = {
        "apikey": api_key
    }

    try:
        # Test ping endpoint
        response = requests.post(
            "http://localhost:5000/api/v1/ping",
            headers=headers,
            json=data,
            timeout=10
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"✅ API Key is working!")
            print(f"Response: {result}")
            return True
        else:
            print(f"❌ API Key test failed")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def main():
    """Main function."""
    # Initialize database
    from database.auth_db import init_db
    init_db()

    # Get Reeshoo's API key
    api_key = get_reeshoo_api_key()

    if api_key:
        # Test the API key
        is_working = test_api_key(api_key)

        if is_working:
            print(f"\n🎯 SUCCESS! Use this API key in your Fortress configuration:")
            print(f"API Key: {api_key}")
            print(f"\nUpdate your .env file with:")
            print(f"OPENALGO_API_KEY={api_key}")
        else:
            print(f"\n⚠️  The extracted API key is not working with the API")
            print(f"You may need to generate a new API key through the OpenAlgo web interface")
    else:
        print(f"\n❌ Could not extract API key for Reeshoo")
        print(f"The Reeshoo user may need to generate a new API key through the web interface")

if __name__ == "__main__":
    main()
