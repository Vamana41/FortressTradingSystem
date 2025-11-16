#!/usr/bin/env python3
"""
Validate OpenAlgo API key for the existing Reeshoo user.
"""

import sys
import os
import hashlib
import hmac

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

# Set the correct database URL
os.environ['DATABASE_URL'] = 'sqlite:///openalgo/db/openalgo.db'

from database.auth_db import db_session, ApiKeys
from argon2 import PasswordHasher

ph = PasswordHasher()

def validate_api_key(api_key):
    """Validate an API key against the database."""
    try:
        # Get the Reeshoo user's API key from database
        api_key_record = ApiKeys.query.filter_by(user_id='Reeshoo').first()

        if not api_key_record:
            print("❌ No API key found for user 'Reeshoo'")
            return False

        print(f"Found API key record for Reeshoo (created: {api_key_record.created_at})")

        # Verify the API key using Argon2
        try:
            ph.verify(api_key_record.api_key_hash, api_key)
            print("✅ API key validation successful!")
            return True
        except Exception as e:
            print(f"❌ API key validation failed: {e}")
            return False

    except Exception as e:
        print(f"❌ Error validating API key: {e}")
        return False

def get_reeshoo_api_key():
    """Get the current API key for Reeshoo user."""
    try:
        api_key_record = ApiKeys.query.filter_by(user_id='Reeshoo').first()

        if not api_key_record:
            print("❌ No API key found for user 'Reeshoo'")
            return None

        # The API key is stored encrypted, but we can see if it matches our expected key
        print(f"API key record found for Reeshoo")
        print(f"Created at: {api_key_record.created_at}")
        print(f"Hash: {api_key_record.api_key_hash[:50]}...")

        return api_key_record

    except Exception as e:
        print(f"❌ Error getting API key: {e}")
        return None

def main():
    """Main function."""
    print("Checking OpenAlgo API key for Reeshoo user...")

    # Get the current API key record
    api_key_record = get_reeshoo_api_key()

    if api_key_record:
        # Test with the API key from environment
        test_api_key = os.getenv("OPENALGO_API_KEY", "89cd257b0bee93f6798130ca99d487a7641a994b567c7646a96775d6c1d425f0")
        print(f"\nTesting with API key: {test_api_key[:10]}...")

        # Validate the API key
        is_valid = validate_api_key(test_api_key)

        if is_valid:
            print("\n✅ The API key is valid and ready to use!")
        else:
            print("\n❌ The API key is invalid. You may need to generate a new one from the OpenAlgo dashboard.")
            print("   Go to http://localhost:5000 and login as Reeshoo, then generate a new API key.")
    else:
        print("\n❌ No API key found for Reeshoo user. Please create one in the OpenAlgo dashboard.")

if __name__ == "__main__":
    main()
