#!/usr/bin/env python3
"""
Script to remove conflicting fortress_system user and restore Reeshoo access.
"""

import os
import sys

# Add the openalgo directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'openalgo'))

from database.auth_db import ApiKeys, Auth, init_db as init_auth_db
from database.user_db import User, init_db as init_user_db
from utils.logging import get_logger

logger = get_logger(__name__)

def remove_fortress_system_user():
    """Remove the conflicting fortress_system user and related data."""

    print("🧹 Removing conflicting fortress_system user...")

    try:
        # Find fortress_system user
        fortress_user = User.query.filter_by(username='fortress_system').first()

        if fortress_user:
            print(f"Found fortress_system user: ID={fortress_user.id}")

            # Remove API keys for fortress_system
            fortress_api_keys = ApiKeys.query.filter_by(user_id='fortress_system').all()
            print(f"Found {len(fortress_api_keys)} API key(s) for fortress_system")

            for api_key in fortress_api_keys:
                print(f"Removing API key for {api_key.user_id}")
                # Delete from database
                from database.auth_db import db_session
                db_session.delete(api_key)

            # Remove auth tokens for fortress_system
            fortress_auth_tokens = Auth.query.filter_by(name='fortress_system').all()
            print(f"Found {len(fortress_auth_tokens)} auth token(s) for fortress_system")

            for auth_token in fortress_auth_tokens:
                print(f"Removing auth token for {auth_token.name}")
                db_session.delete(auth_token)

            # Remove the user
            print(f"Removing fortress_system user")
            db_session.delete(fortress_user)

            # Commit all changes
            db_session.commit()
            print("✅ Successfully removed fortress_system user and related data")

        else:
            print("ℹ️  fortress_system user not found - nothing to remove")

    except Exception as e:
        print(f"❌ Error removing fortress_system user: {e}")
        import traceback
        traceback.print_exc()

def check_reeshoo_user():
    """Check the Reeshoo user status."""

    print(f"\n🔍 Checking Reeshoo user status...")

    try:
        # Find Reeshoo user
        reeshoo_user = User.query.filter_by(username='Reeshoo').first()

        if reeshoo_user:
            print(f"✅ Found Reeshoo user: ID={reeshoo_user.id}, Email={reeshoo_user.email}")

            # Check API keys for Reeshoo
            reeshoo_api_keys = ApiKeys.query.filter_by(user_id='Reeshoo').all()
            print(f"Found {len(reeshoo_api_keys)} API key(s) for Reeshoo")

            for api_key in reeshoo_api_keys:
                print(f"  - Created: {api_key.created_at}")

            # Check auth tokens for Reeshoo
            reeshoo_auth_tokens = Auth.query.filter_by(name='Reeshoo').all()
            print(f"Found {len(reeshoo_auth_tokens)} auth token(s) for Reeshoo")

            for auth_token in reeshoo_auth_tokens:
                print(f"  - Broker: {auth_token.broker}, Revoked: {auth_token.is_revoked}")
                print(f"  - Has Auth Token: {'Yes' if auth_token.auth else 'No'}")
                print(f"  - Has Feed Token: {'Yes' if auth_token.feed_token else 'No'}")

            return True
        else:
            print("❌ Reeshoo user not found!")
            return False

    except Exception as e:
        print(f"❌ Error checking Reeshoo user: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_reeshoo_login():
    """Test if Reeshoo can log in."""

    print(f"\n🔑 Testing Reeshoo login capability...")

    try:
        # Find Reeshoo user
        reeshoo_user = User.query.filter_by(username='Reeshoo').first()

        if reeshoo_user:
            print(f"✅ Reeshoo user exists")

            # Check if auth tokens are valid
            valid_auth = Auth.query.filter_by(name='Reeshoo', is_revoked=False).first()

            if valid_auth and valid_auth.auth:
                print(f"✅ Reeshoo has valid auth token for broker: {valid_auth.broker}")
                print(f"✅ Reeshoo should be able to log in and use the API!")
                return True
            else:
                print(f"⚠️  Reeshoo has no valid auth tokens")
                print(f"This might explain login issues")
                return False
        else:
            print(f"❌ Reeshoo user not found")
            return False

    except Exception as e:
        print(f"❌ Error testing Reeshoo login: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function."""
    print("🛠️  OpenAlgo User Cleanup and Restoration")
    print("=" * 60)

    # Initialize databases
    init_auth_db()
    init_user_db()

    # Remove conflicting user
    remove_fortress_system_user()

    # Check Reeshoo user
    reeshoo_ok = check_reeshoo_user()

    # Test login capability
    login_ok = test_reeshoo_login()

    print(f"\n{'='*60}")
    print("📋 Summary:")

    if reeshoo_ok:
        print("✅ Reeshoo user is intact")
    else:
        print("❌ Reeshoo user has issues")

    if login_ok:
        print("✅ Reeshoo should be able to log in")
    else:
        print("⚠️  Reeshoo may have login issues")

    print(f"\n🎯 Next Steps:")
    print(f"1. Try logging in as Reeshoo at http://localhost:5000")
    print(f"2. If login fails, we may need to reset the Reeshoo password")
    print(f"3. Once logged in, generate a new API key for Reeshoo")
    print(f"4. Update the Fortress configuration with the new API key")

if __name__ == "__main__":
    main()
