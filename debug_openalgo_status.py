#!/usr/bin/env python3
"""
Debug OpenAlgo User and API Key Status

This script checks the current user and API key status in OpenAlgo.
"""

import sys
import os
from pathlib import Path

# Add the openalgo directory to Python path
openalgo_path = Path(__file__).parent / "openalgo"
sys.path.insert(0, str(openalgo_path))

def debug_user_status():
    """Debug user and API key status."""
    try:
        from database.user_db import find_user_by_username
        from database.auth_db import get_api_key_for_tradingview, verify_api_key
        from database.auth_db import ApiKeys
        from database import auth_db

        # Check admin user
        admin_user = find_user_by_username()
        if admin_user:
            print(f"Found admin user:")
            print(f"  Username: {admin_user.username}")
            print(f"  Email: {admin_user.email}")
            print(f"  User ID: {admin_user.id}")
            print(f"  Is Admin: {admin_user.is_admin}")
        else:
            print("No admin user found!")
            return

        # Check API keys
        print(f"\nChecking API keys for user ID: {admin_user.id}")

        # Query all API keys
        all_keys = ApiKeys.query.all()
        print(f"Total API keys in database: {len(all_keys)}")

        for key in all_keys:
            print(f"\nAPI Key {key.id}:")
            print(f"  User ID: {key.user_id}")
            print(f"  Created: {key.created_at}")

            # Try to get the decrypted key
            try:
                decrypted_key = get_api_key_for_tradingview(key.user_id)
                if decrypted_key:
                    print(f"  Decrypted Key: {decrypted_key}")

                    # Test verification
                    is_valid = verify_api_key(decrypted_key)
                    print(f"  Verification: {'✓ Valid' if is_valid else '✗ Invalid'}")
                else:
                    print(f"  Could not decrypt key")
            except Exception as e:
                print(f"  Error decrypting: {e}")

    except Exception as e:
        print(f"Error debugging user status: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function."""
    print("OpenAlgo User and API Key Debug")
    print("=" * 40)

    debug_user_status()

if __name__ == "__main__":
    main()
