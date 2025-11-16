#!/usr/bin/env python3
"""
Extract the actual API key for Reeshoo user from OpenAlgo database.
"""

import sys
import os

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

# Set the correct database URL
os.environ['DATABASE_URL'] = 'sqlite:///openalgo/db/openalgo.db'

from database.auth_db import db_session, ApiKeys, fernet

def extract_api_key():
    """Extract the API key for Reeshoo user."""
    try:
        # Get the Reeshoo user's API key from database
        api_key_record = ApiKeys.query.filter_by(user_id='Reeshoo').first()

        if not api_key_record:
            print("❌ No API key found for user 'Reeshoo'")
            return None

        print(f"Found API key record for Reeshoo (created: {api_key_record.created_at})")

        # Decrypt the API key
        try:
            decrypted_key = fernet.decrypt(api_key_record.api_key_encrypted.encode()).decode()
            print(f"✅ Decrypted API key: {decrypted_key}")
            return decrypted_key
        except Exception as e:
            print(f"❌ Error decrypting API key: {e}")
            return None

    except Exception as e:
        print(f"❌ Error extracting API key: {e}")
        return None

def main():
    """Main function."""
    print("Extracting OpenAlgo API key for Reeshoo user...")

    api_key = extract_api_key()

    if api_key:
        print(f"\n✅ Successfully extracted API key: {api_key}")
        print(f"\nTo use this API key in Fortress, update your .env file with:")
        print(f"OPENALGO_API_KEY={api_key}")
    else:
        print("\n❌ Could not extract API key. Please generate a new one in the OpenAlgo dashboard.")

if __name__ == "__main__":
    main()
